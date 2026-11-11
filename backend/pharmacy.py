"""Pharmacy: drug stock and e-prescriptions.

Doctor:      writes a prescription on a referral at their facility; it goes to that facility's pharmacy.
Pharmacist:  sees and changes their own facility's stock, and dispenses its prescriptions.
GHS officer: sees which districts are low on or out of drugs (counts of facilities, no patients).

Every stock change is written to stock_movements (who, when, why), so the quantity can
always be explained. Dispensing is all-or-nothing: every drug on the prescription is
taken from stock together, or nothing changes.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

import rx_rules
from auth import require_role
from database import get_db, log_access, now_text
from schemas import PrescriptionCreate, ReorderLevel, StockAdjust, StockReceive
from surveillance import DISTRICT_CENTRES

router = APIRouter()


def stock_status(quantity, reorder_level):
    if quantity == 0:
        return "out"
    return "low" if quantity <= reorder_level else "ok"


def get_stock_row(conn, facility, drug_id):
    """This facility's stock row for a drug, created at 0 the first time it is needed."""
    conn.execute(
        "INSERT INTO stock (facility, drug_id, quantity, reorder_level) "
        "SELECT ?, id, 0, default_reorder_level FROM drugs WHERE id = ? "
        "ON CONFLICT (facility, drug_id) DO NOTHING",
        (facility, drug_id),
    )
    return conn.execute(
        "SELECT s.quantity, s.reorder_level, d.name, d.unit FROM stock s JOIN drugs d ON d.id = s.drug_id "
        "WHERE s.facility = ? AND s.drug_id = ?",
        (facility, drug_id),
    ).fetchone()


def record_movement(conn, user, drug_id, change, quantity_after, reason, prescription_id=None, note=None):
    conn.execute(
        "INSERT INTO stock_movements (facility, drug_id, change, quantity_after, reason, prescription_id, note, "
        "user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user["facility"], drug_id, change, quantity_after, reason, prescription_id, note, user["id"], now_text()),
    )


def fail(conn, status_code, detail):
    # Undo everything this request changed, then tell the user why
    conn.rollback()
    conn.close()
    raise HTTPException(status_code=status_code, detail=detail)


# ---------- Drug list (doctor chooses from it; shows what this facility has) ----------

@router.get("/drugs")
def list_drugs(user=Depends(require_role("doctor", "pharmacist"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT d.id, d.name, d.unit, d.condition, COALESCE(s.quantity, 0) AS in_stock
        FROM drugs d LEFT JOIN stock s ON s.drug_id = d.id AND s.facility = ?
        ORDER BY d.name
    """, (user["facility"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Prescriptions: written by the doctor ----------

def get_doctor_referral(conn, referral_id, user):
    # Need-to-know: only a referral to the doctor's own facility (same rule as the inbox)
    referral = conn.execute(
        "SELECT r.id, r.patient_id, p.ref FROM referrals r JOIN patients p ON p.id = r.patient_id "
        "WHERE r.id = ? AND r.facility = ?",
        (referral_id, user["facility"]),
    ).fetchone()
    if not referral:
        log_access(conn, user["id"], "access_denied", f"referral:{referral_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


def load_prescriptions(conn, where, params, facility):
    """Prescriptions with their drugs, and how much of each this facility has now."""
    rows = conn.execute(f"""
        SELECT rx.id, rx.status, rx.notes, rx.created_at, rx.dispensed_at, rx.referral_id,
               rx.code, rx.valid_until, rx.outside_pharmacy, rx.outside_licence, rx.facility,
               p.ref, p.full_name, p.age, p.sex,
               doc.full_name AS prescribed_by_name, ph.full_name AS dispensed_by_name
        FROM prescriptions rx
        JOIN patients p ON p.id = rx.patient_id
        JOIN users doc ON doc.id = rx.prescribed_by
        LEFT JOIN users ph ON ph.id = rx.dispensed_by
        WHERE {where}
        ORDER BY CASE rx.status WHEN 'pending' THEN 0 ELSE 1 END, rx.id DESC
        LIMIT 100
    """, params).fetchall()
    prescriptions = []
    for rx in rows:
        items = conn.execute("""
            SELECT i.drug_id, i.quantity, i.instructions, d.name, d.unit, COALESCE(s.quantity, 0) AS in_stock
            FROM prescription_items i
            JOIN drugs d ON d.id = i.drug_id
            LEFT JOIN stock s ON s.drug_id = i.drug_id AND s.facility = ?
            WHERE i.prescription_id = ? ORDER BY i.id
        """, (facility, rx["id"])).fetchall()
        expired = rx["status"] == "pending" and bool(rx["valid_until"]) and rx["valid_until"] < now_text()
        prescriptions.append({**dict(rx), "code": rx_rules.show_code(rx["code"]), "expired": expired,
                              "items": [{**dict(i), "controlled": i["name"] in rx_rules.CONTROLLED} for i in items]})
    return prescriptions


def days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def add_flag(conn, prescription_id, kind, detail):
    conn.execute("INSERT INTO prescription_flags (prescription_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
                 (prescription_id, kind, detail, now_text()))


@router.post("/referrals/{referral_id}/prescriptions")
def create_prescription(referral_id: int, body: PrescriptionCreate, user=Depends(require_role("doctor"))):
    """Write a prescription, after the fraud and safety checks in rx_rules.py."""
    conn = get_db()
    referral = get_doctor_referral(conn, referral_id, user)
    drug_ids = [item.drug_id for item in body.items]
    if len(set(drug_ids)) != len(drug_ids):
        fail(conn, 422, "Each drug can appear only once in a prescription")
    names = {}
    for drug_id in drug_ids:
        drug = conn.execute("SELECT name FROM drugs WHERE id = ?", (drug_id,)).fetchone()
        if not drug:
            fail(conn, 422, "Unknown drug")
        names[drug_id] = drug["name"]

    # Check 1: quantity limit per drug (stops typos and "extra" quantities)
    for item in body.items:
        limit = rx_rules.max_quantity(names[item.drug_id])
        if item.quantity > limit:
            fail(conn, 422, f"{names[item.drug_id]}: at most {limit} on one prescription")

    # Check 2: controlled drugs need a written reason
    controlled = [names[d] for d in drug_ids if names[d] in rx_rules.CONTROLLED]
    if controlled and len(body.notes.strip()) < 10:
        fail(conn, 422, f"{', '.join(controlled)}: controlled drug. Write the reason in the notes.")

    # Check 3: same drug for the same patient in the last 14 days (not cancelled) needs a reason
    marks = ", ".join("?" for _ in drug_ids)
    earlier = conn.execute(
        f"SELECT d.name, rx.created_at, u.full_name FROM prescriptions rx "
        f"JOIN prescription_items i ON i.prescription_id = rx.id JOIN drugs d ON d.id = i.drug_id "
        f"JOIN users u ON u.id = rx.prescribed_by "
        f"WHERE rx.patient_id = ? AND rx.status != 'cancelled' AND rx.created_at >= ? AND i.drug_id IN ({marks})",
        (referral["patient_id"], days_ago(rx_rules.DUPLICATE_DAYS), *drug_ids)).fetchall()
    duplicate_reason = body.duplicate_reason.strip()
    if earlier and len(duplicate_reason) < 5:
        found = "; ".join(f"{r['name']} ({str(r['created_at'])[:10]}, {r['full_name']})" for r in earlier)
        fail(conn, 409, f"Already prescribed in the last {rx_rules.DUPLICATE_DAYS} days: {found}. "
                        "To prescribe it again, give a reason.")

    days = rx_rules.CONTROLLED_VALID_DAYS if controlled else rx_rules.VALID_DAYS
    valid_until = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    code = rx_rules.new_code()
    prescription_id = conn.execute(
        "INSERT INTO prescriptions (patient_id, referral_id, prescribed_by, facility, notes, code, valid_until, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (referral["patient_id"], referral_id, user["id"], user["facility"], body.notes.strip() or None, code,
         valid_until, now_text()),
    ).fetchone()["id"]
    for item in body.items:
        conn.execute(
            "INSERT INTO prescription_items (prescription_id, drug_id, quantity, instructions) VALUES (?, ?, ?, ?)",
            (prescription_id, item.drug_id, item.quantity, item.instructions.strip()),
        )

    # Warnings for GHS (prescription allowed, but someone should be able to look)
    if controlled:
        add_flag(conn, prescription_id, "controlled", f"{', '.join(controlled)}. Reason: {body.notes.strip()}")
        count = conn.execute(
            f"SELECT COUNT(DISTINCT rx.id) AS n FROM prescriptions rx JOIN prescription_items i ON i.prescription_id = rx.id "
            f"JOIN drugs d ON d.id = i.drug_id WHERE rx.prescribed_by = ? AND rx.created_at >= ? "
            f"AND d.name IN ({', '.join('?' for _ in rx_rules.CONTROLLED)})",
            (user["id"], days_ago(7), *sorted(rx_rules.CONTROLLED))).fetchone()["n"]
        if count >= rx_rules.HIGH_VOLUME_CONTROLLED:
            add_flag(conn, prescription_id, "high_volume", f"{count} controlled-drug prescriptions in 7 days by this doctor")
    if earlier:
        add_flag(conn, prescription_id, "duplicate",
                 f"{', '.join(sorted({r['name'] for r in earlier}))} again within {rx_rules.DUPLICATE_DAYS} days. "
                 f"Reason: {duplicate_reason}")
    log_access(conn, user["id"], "create_prescription", f"{referral['ref']} rx:{prescription_id}")
    conn.commit()
    conn.close()
    return {"id": prescription_id, "code": rx_rules.show_code(code), "valid_until": valid_until}


@router.get("/referrals/{referral_id}/prescriptions")
def referral_prescriptions(referral_id: int, user=Depends(require_role("doctor"))):
    conn = get_db()
    get_doctor_referral(conn, referral_id, user)
    result = load_prescriptions(conn, "rx.referral_id = ? AND rx.facility = ?", (referral_id, user["facility"]),
                                user["facility"])
    conn.close()
    return result


@router.post("/prescriptions/{prescription_id}/cancel")
def cancel_prescription(prescription_id: int, user=Depends(require_role("doctor"))):
    # Only before it is dispensed; drugs already handed over cannot be "cancelled"
    conn = get_db()
    changed = conn.execute(
        "UPDATE prescriptions SET status = 'cancelled' WHERE id = ? AND facility = ? AND status = 'pending'",
        (prescription_id, user["facility"]),
    ).rowcount
    if changed != 1:
        fail(conn, 409, "Only a waiting prescription at your facility can be cancelled")
    log_access(conn, user["id"], "cancel_prescription", f"rx:{prescription_id}")
    conn.commit()
    conn.close()
    return {"success": True}


# ---------- Pharmacist: stock ----------

@router.get("/pharmacy/stock")
def list_stock(user=Depends(require_role("pharmacist"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT d.id AS drug_id, d.name, d.unit, d.condition,
               COALESCE(s.quantity, 0) AS quantity,
               COALESCE(s.reorder_level, d.default_reorder_level) AS reorder_level,
               s.updated_at
        FROM drugs d LEFT JOIN stock s ON s.drug_id = d.id AND s.facility = ?
        ORDER BY d.name
    """, (user["facility"],)).fetchall()
    conn.close()
    stock = [{**dict(r), "status": stock_status(r["quantity"], r["reorder_level"])} for r in rows]
    # Out of stock first, then low, then the rest
    stock.sort(key=lambda s: ({"out": 0, "low": 1, "ok": 2}[s["status"]], s["name"]))
    return stock


@router.post("/pharmacy/stock/{drug_id}/receive")
def receive_stock(drug_id: int, body: StockReceive, user=Depends(require_role("pharmacist"))):
    conn = get_db()
    if not get_stock_row(conn, user["facility"], drug_id):
        fail(conn, 404, "Unknown drug")
    new_quantity = conn.execute(
        "UPDATE stock SET quantity = quantity + ?, updated_at = ? WHERE facility = ? AND drug_id = ? RETURNING quantity",
        (body.quantity, now_text(), user["facility"], drug_id),
    ).fetchone()["quantity"]
    record_movement(conn, user, drug_id, body.quantity, new_quantity, "received", note=body.note.strip() or None)
    log_access(conn, user["id"], "stock_received", f"drug:{drug_id} +{body.quantity}")
    conn.commit()
    conn.close()
    return {"quantity": new_quantity}


@router.post("/pharmacy/stock/{drug_id}/adjust")
def adjust_stock(drug_id: int, body: StockAdjust, user=Depends(require_role("pharmacist"))):
    # Set the count to what is really on the shelf (expired, damaged, counting error)
    conn = get_db()
    row = get_stock_row(conn, user["facility"], drug_id)
    if not row:
        fail(conn, 404, "Unknown drug")
    change = body.new_quantity - row["quantity"]
    conn.execute("UPDATE stock SET quantity = ?, updated_at = ? WHERE facility = ? AND drug_id = ?",
                 (body.new_quantity, now_text(), user["facility"], drug_id))
    record_movement(conn, user, drug_id, change, body.new_quantity, "adjusted", note=body.note.strip())
    log_access(conn, user["id"], "stock_adjusted", f"drug:{drug_id} {change:+d}")
    conn.commit()
    conn.close()
    return {"quantity": body.new_quantity}


@router.post("/pharmacy/stock/{drug_id}/reorder-level")
def set_reorder_level(drug_id: int, body: ReorderLevel, user=Depends(require_role("pharmacist"))):
    conn = get_db()
    if not get_stock_row(conn, user["facility"], drug_id):
        fail(conn, 404, "Unknown drug")
    conn.execute("UPDATE stock SET reorder_level = ? WHERE facility = ? AND drug_id = ?",
                 (body.reorder_level, user["facility"], drug_id))
    log_access(conn, user["id"], "reorder_level_set", f"drug:{drug_id} {body.reorder_level}")
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/pharmacy/history")
def stock_history(user=Depends(require_role("pharmacist"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT m.id, m.change, m.quantity_after, m.reason, m.note, m.created_at, m.prescription_id,
               d.name, d.unit, u.full_name AS by_name
        FROM stock_movements m JOIN drugs d ON d.id = m.drug_id JOIN users u ON u.id = m.user_id
        WHERE m.facility = ? ORDER BY m.id DESC LIMIT 100
    """, (user["facility"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Pharmacist: prescriptions ----------

@router.get("/pharmacy/prescriptions")
def pharmacy_prescriptions(user=Depends(require_role("pharmacist"))):
    # Name, ref, age and sex to hand the drugs to the right person. No visit history or notes
    # from the referral: the pharmacist does not need them (Act 843, data minimisation).
    conn = get_db()
    result = load_prescriptions(conn, "rx.facility = ?", (user["facility"],), user["facility"])
    log_access(conn, user["id"], "list_prescriptions", user["facility"])
    conn.commit()
    conn.close()
    return result


@router.post("/pharmacy/prescriptions/{prescription_id}/dispense")
def dispense(prescription_id: int, user=Depends(require_role("pharmacist"))):
    conn = get_db()
    rx = conn.execute("SELECT id, status, valid_until FROM prescriptions WHERE id = ? AND facility = ?",
                      (prescription_id, user["facility"])).fetchone()
    if not rx:
        log_access(conn, user["id"], "access_denied", f"prescription:{prescription_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Prescription not found")
    if rx["status"] != "pending":
        fail(conn, 409, f"This prescription is already {rx['status']}")
    if rx["valid_until"] and rx["valid_until"] < now_text():
        fail(conn, 409, "This prescription has expired. The patient needs a new one from the doctor.")

    items = conn.execute("SELECT drug_id, quantity FROM prescription_items WHERE prescription_id = ?",
                         (prescription_id,)).fetchall()
    # 1. Check everything first, so the pharmacist sees every shortage at once
    short = []
    for item in items:
        row = get_stock_row(conn, user["facility"], item["drug_id"])
        if row["quantity"] < item["quantity"]:
            short.append(f"{row['name']} (need {item['quantity']}, have {row['quantity']})")
    if short:
        fail(conn, 409, "Not enough stock: " + "; ".join(short))

    # 2. Claim the prescription. "AND status = 'pending'" stops two pharmacists dispensing it twice.
    now = now_text()
    claimed = conn.execute(
        "UPDATE prescriptions SET status = 'dispensed', dispensed_by = ?, dispensed_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (user["id"], now, prescription_id),
    ).rowcount
    if claimed != 1:
        fail(conn, 409, "This prescription was just dispensed by someone else")

    # 3. Take each drug from stock. "AND quantity >= ?" refuses if stock ran out meanwhile;
    #    then everything above is undone (rollback), so no prescription is half-dispensed.
    for item in items:
        row = conn.execute(
            "UPDATE stock SET quantity = quantity - ?, updated_at = ? "
            "WHERE facility = ? AND drug_id = ? AND quantity >= ? RETURNING quantity",
            (item["quantity"], now, user["facility"], item["drug_id"], item["quantity"]),
        ).fetchone()
        if not row:
            fail(conn, 409, "Stock changed while dispensing. Please try again.")
        record_movement(conn, user, item["drug_id"], -item["quantity"], row["quantity"], "dispensed",
                        prescription_id=prescription_id)
    log_access(conn, user["id"], "dispense_prescription", f"rx:{prescription_id}")
    conn.commit()
    conn.close()
    return {"success": True}


# ---------- GHS: stock-outs by district (facility counts only, no patient data) ----------

@router.get("/surveillance/stock")
def stock_by_district(user=Depends(require_role("ghs"))):
    conn = get_db()
    # A facility's district comes from its staff accounts
    facility_district = {}
    for r in conn.execute("SELECT DISTINCT facility, district FROM users "
                          "WHERE facility IS NOT NULL AND district IS NOT NULL ORDER BY facility"):
        facility_district.setdefault(r["facility"], r["district"])
    rows = conn.execute("""
        SELECT s.facility, s.quantity, s.reorder_level, d.name, d.unit, d.condition
        FROM stock s JOIN drugs d ON d.id = s.drug_id
    """).fetchall()
    log_access(conn, user["id"], "view_stock_by_district")
    conn.commit()
    conn.close()

    districts = {}
    for r in rows:
        district = facility_district.get(r["facility"])
        if district not in DISTRICT_CENTRES:
            continue
        d = districts.setdefault(district, {"district": district, "facilities": set(), "drugs": {}})
        d["facilities"].add(r["facility"])
        status = stock_status(r["quantity"], r["reorder_level"])
        if status != "ok":
            drug = d["drugs"].setdefault(r["name"], {"name": r["name"], "condition": r["condition"], "out": 0, "low": 0})
            drug[status] += 1

    result = []
    for d in sorted(districts.values(), key=lambda d: d["district"]):
        drugs = sorted(d["drugs"].values(), key=lambda x: (-x["out"], -x["low"], x["name"]))
        result.append({"district": d["district"], "facilities": len(d["facilities"]), "drugs": drugs})
    return {"districts": result, "generated_at": now_text()}
