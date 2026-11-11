"""E-prescriptions that any pharmacy can check, even one that does not use HealthConnect.

The doctor gives the patient a slip with a code and a QR code (e.g. 7KQ4-M9TX). At any
pharmacy, the pharmacist scans the QR code or types the code on the HealthConnect website
(no account needed) and sees:
  - whether it is genuine, still valid, or already dispensed / cancelled / expired
  - the drugs, quantities and instructions, the doctor and facility
  - the patient's initials, age and sex only (Act 843: enough to check the right person)
After handing over the drugs, the pharmacist records their pharmacy and its Pharmacy Council
licence number. The prescription is then used up: a second pharmacy is refused.
(FHIR: MedicationRequest.identifier = the code; MedicationDispense.performer = the pharmacy.)

Honest limits: we cannot check the licence number against the Pharmacy Council register
(no access); the outside pharmacy's own stock is not tracked.
"""
import os
import threading
from io import BytesIO
import time
from datetime import datetime, timedelta, timezone

import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import rx_rules
from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()
wrong_codes = {}  # internet address -> times of wrong codes in the last hour
lock = threading.Lock()


def client_ip(request: Request):
    """The pharmacy's internet address. On AWS, CloudFront and the load balancer each add one
    address to X-Forwarded-For, so the real one is second from the end (a faked value sits before it)."""
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if len(forwarded) >= 2:
        return forwarded[-2]
    return forwarded[0] if forwarded else request.client.host


def masked(ip):
    """41.66.12.34 -> 41.66.x.x: enough to spot a pattern, not to identify a person."""
    parts = ip.split(".")
    return ".".join(parts[:2] + ["x", "x"]) if len(parts) == 4 else ip.split(":")[0] + ":…"


def recent_wrong(ip):
    hour_ago = time.time() - 3600
    with lock:
        wrong_codes[ip] = [t for t in wrong_codes.get(ip, []) if t > hour_ago]
        return len(wrong_codes[ip])


def find(conn, code_text, request):
    """The prescription for a code, or 404. Too many wrong codes from one address: 429."""
    ip = client_ip(request)
    if recent_wrong(ip) >= rx_rules.WRONG_CODES_PER_HOUR:
        conn.close()
        raise HTTPException(status_code=429, detail="Too many wrong codes. Try again in an hour.")
    code = rx_rules.clean_code(code_text)
    rx = code and conn.execute("SELECT * FROM prescriptions WHERE code = ?", (code,)).fetchone()
    if not rx:
        with lock:
            wrong_codes.setdefault(ip, []).append(time.time())
            count = len(wrong_codes[ip])
        log_access(conn, None, "rx_wrong_code", masked(ip))
        if count == rx_rules.WRONG_CODES_PER_HOUR:  # flag once, when the limit is reached
            conn.execute("INSERT INTO prescription_flags (kind, detail, created_at) VALUES (?, ?, ?)",
                         ("code_guessing", f"{count} wrong prescription codes in an hour from {masked(ip)}", now_text()))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="No prescription has this code. Check it and try again.")
    return rx


def status_of(rx):
    if rx["status"] == "pending" and rx["valid_until"] and rx["valid_until"] < now_text():
        return "expired"
    return {"pending": "valid"}.get(rx["status"], rx["status"])


@router.get("/rx/{code}")
def check(code: str, request: Request):
    """Public: what an outside pharmacy sees after scanning the QR code."""
    conn = get_db()
    rx = find(conn, code, request)
    patient = conn.execute("SELECT ref, full_name, age, sex FROM patients WHERE id = ?", (rx["patient_id"],)).fetchone()
    doctor = conn.execute("SELECT full_name FROM users WHERE id = ?", (rx["prescribed_by"],)).fetchone()
    items = conn.execute(
        "SELECT d.name, d.unit, i.quantity, i.instructions FROM prescription_items i JOIN drugs d ON d.id = i.drug_id "
        "WHERE i.prescription_id = ? ORDER BY i.id", (rx["id"],)).fetchall()
    where = rx["outside_pharmacy"] or (rx["facility"] + " pharmacy" if rx["status"] == "dispensed" else None)
    log_access(conn, None, "rx_checked", f"rx:{rx['id']} {masked(client_ip(request))}")
    conn.commit()
    conn.close()
    return {
        "code": rx_rules.show_code(rx["code"]),
        "status": status_of(rx),
        "created_at": rx["created_at"],
        "valid_until": rx["valid_until"],
        "facility": rx["facility"],
        "prescribed_by": doctor["full_name"],
        "patient": {"ref": patient["ref"], "initials": rx_rules.initials(patient["full_name"]),
                    "age": patient["age"], "sex": patient["sex"]},
        "items": [{**dict(i), "controlled": i["name"] in rx_rules.CONTROLLED} for i in items],
        "notes": rx["notes"],
        "dispensed_at": rx["dispensed_at"],
        "dispensed_where": where,
    }


class OutsideDispense(BaseModel):
    pharmacy: str = Field(min_length=3, max_length=100)
    licence: str = Field(min_length=3, max_length=30)  # Pharmacy Council licence number
    pharmacist: str = Field(min_length=3, max_length=100)
    checked_patient: bool  # "I checked this is the right patient"


@router.post("/rx/{code}/dispense")
def dispense_outside(code: str, body: OutsideDispense, request: Request):
    """Public: an outside pharmacy records that it handed over the drugs. Works once."""
    if not body.checked_patient:
        raise HTTPException(status_code=400, detail="Check the patient's initials, age and sex first")
    conn = get_db()
    rx = find(conn, code, request)
    now = now_text()
    # One UPDATE does the check and the change together, so two pharmacies cannot both succeed
    claimed = conn.execute(
        "UPDATE prescriptions SET status = 'dispensed', dispensed_at = ?, outside_pharmacy = ?, outside_licence = ?, "
        "outside_pharmacist = ? WHERE id = ? AND status = 'pending' AND valid_until >= ?",
        (now, body.pharmacy.strip(), body.licence.strip().upper(), body.pharmacist.strip(), rx["id"], now)).rowcount
    if claimed != 1:  # already dispensed, cancelled or expired: say which
        state = status_of(conn.execute("SELECT * FROM prescriptions WHERE id = ?", (rx["id"],)).fetchone())
        conn.close()
        raise HTTPException(status_code=409, detail=f"Not dispensed: this prescription is {state}")
    log_access(conn, None, "rx_dispensed_outside",
               f"rx:{rx['id']} {body.pharmacy.strip()} licence {body.licence.strip().upper()} {masked(client_ip(request))}")
    conn.commit()
    conn.close()
    return {"success": True}


def site_address():
    """The website address the QR code opens (the first allowed origin: CloudFront on AWS)."""
    return os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")[0].strip()


@router.get("/prescriptions/{prescription_id}/qr.svg")
def qr_code(prescription_id: int, user=Depends(require_role("doctor", "pharmacist"))):
    """QR code for the printed slip. It holds only the link with the code: no names, no drugs."""
    conn = get_db()
    rx = conn.execute("SELECT code FROM prescriptions WHERE id = ? AND facility = ?",
                      (prescription_id, user["facility"])).fetchone()
    conn.close()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    link = f"{site_address()}/?rx={rx_rules.show_code(rx['code'])}"
    out = BytesIO()
    segno.make(link, error="m").save(out, kind="svg", scale=6, border=2)  # a full SVG file (with xmlns)
    return Response(content=out.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@router.get("/surveillance/prescription-flags")
def prescription_flags(user=Depends(require_role("ghs"))):
    """GHS: fraud and safety warnings from the last 30 days. Doctors and facilities, never patients."""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    rows = conn.execute(
        "SELECT f.id, f.kind, f.detail, f.created_at, rx.facility, u.full_name AS doctor "
        "FROM prescription_flags f LEFT JOIN prescriptions rx ON rx.id = f.prescription_id "
        "LEFT JOIN users u ON u.id = rx.prescribed_by WHERE f.created_at >= ? ORDER BY f.id DESC LIMIT 200",
        (since,)).fetchall()
    log_access(conn, user["id"], "view_prescription_flags")
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]
