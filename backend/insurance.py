"""Community health insurance with mobile money premiums, through Paystack.

Members pay a small monthly premium into a shared pot (risk pooling). Each payment extends
the date they are covered until. With a live key REAL money moves, for small demo payments only:
running a real scheme needs a licence we do not hold; see the report. With no key it is simulated.

No phone or mobile money number is stored: the payer types it on Paystack's page (Act 843).
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import paystack
from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()

MONTHLY_PREMIUM_GHS = 1  # an example amount for the prototype, not an actuarial figure
DAYS_PER_MONTH = 30


class JoinScheme(BaseModel):
    consent: bool


class PremiumPayment(BaseModel):
    months: int = Field(ge=1, le=12)
    network: Literal["mtn", "telecel", "at"]


def today():
    return datetime.now(timezone.utc).date()


def own_patient(conn, patient_id, user):
    # Need-to-know: a CHV only reaches their own patients. Others get 404, so existence is not revealed.
    patient = conn.execute("SELECT id, ref FROM patients WHERE id = ? AND chv_id = ?", (patient_id, user["id"])).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def get_member(conn, patient_id):
    return conn.execute("SELECT paid_until FROM insurance_members WHERE patient_id = ?", (patient_id,)).fetchone()


def status(conn, patient_id):
    member = get_member(conn, patient_id)
    paid_until = member["paid_until"] if member else None
    payments = conn.execute(
        "SELECT months, amount_ghs, network, reference, created_at FROM premium_payments "
        "WHERE patient_id = ? ORDER BY id DESC", (patient_id,)).fetchall()
    pending = conn.execute(
        "SELECT reference, checkout_url, amount_ghs FROM premium_checkouts "
        "WHERE patient_id = ? AND completed_at IS NULL ORDER BY id DESC LIMIT 1", (patient_id,)).fetchone()
    return {
        "simulated": not paystack.is_configured(),
        "live": paystack.is_live(),
        "monthly_premium_ghs": MONTHLY_PREMIUM_GHS,
        "member": member is not None,
        "paid_until": paid_until,
        "covered": bool(paid_until) and paid_until >= today().isoformat(),
        "payments": [dict(p) for p in payments],
        "pending": dict(pending) if pending else None,
    }


@router.get("/patients/{patient_id}/insurance")
def get_insurance(patient_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    result = status(conn, patient_id)
    log_access(conn, user["id"], "view_insurance", patient["ref"])
    conn.commit()
    conn.close()
    return result


@router.post("/patients/{patient_id}/insurance/join")
def join_scheme(patient_id: int, body: JoinScheme, user=Depends(require_role("chv"))):
    # Joining is a separate purpose from care, so it needs its own consent (Act 843)
    if not body.consent:
        raise HTTPException(status_code=400, detail="The patient must agree to join the scheme")
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    if get_member(conn, patient_id):
        conn.close()
        raise HTTPException(status_code=400, detail="This patient has already joined")
    conn.execute("INSERT INTO insurance_members (patient_id, enrolled_by, created_at) VALUES (?, ?, ?)",
                 (patient_id, user["id"], now_text()))
    log_access(conn, user["id"], "join_insurance", patient["ref"])
    conn.commit()
    result = status(conn, patient_id)
    conn.close()
    return result


def add_cover(conn, patient_id, months, amount_ghs, network, reference, user_id):
    # Paying early adds to the time left; paying after a gap starts from today
    member = get_member(conn, patient_id)
    start = today()
    if member["paid_until"]:
        start = max(start, datetime.strptime(member["paid_until"], "%Y-%m-%d").date())
    paid_until = (start + timedelta(days=months * DAYS_PER_MONTH)).isoformat()
    conn.execute(
        "INSERT INTO premium_payments (patient_id, months, amount_ghs, network, reference, recorded_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (patient_id, months, amount_ghs, network, reference, user_id, now_text()),
    )
    conn.execute("UPDATE insurance_members SET paid_until = ? WHERE patient_id = ?", (paid_until, patient_id))


@router.post("/patients/{patient_id}/insurance/pay")
def pay_premium(patient_id: int, body: PremiumPayment, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    if not get_member(conn, patient_id):
        conn.close()
        raise HTTPException(status_code=400, detail="Join the scheme before paying")
    amount = body.months * MONTHLY_PREMIUM_GHS  # worked out here, never taken from the phone

    if paystack.is_configured():
        conn.close()  # do not hold the database open while waiting on the internet
        reference = "HC-" + secrets.token_hex(8).upper()
        url = paystack.start_payment(reference, amount)
        conn = get_db()
        conn.execute(
            "INSERT INTO premium_checkouts (reference, patient_id, months, amount_ghs, network, checkout_url, started_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (reference, patient_id, body.months, amount, body.network, url, user["id"], now_text()),
        )
        log_access(conn, user["id"], "start_premium_payment", f"{patient['ref']} {reference}")
    else:
        reference = "SIM-" + secrets.token_hex(4).upper()  # clearly not a real transaction id
        add_cover(conn, patient_id, body.months, amount, body.network, reference, user["id"])
        log_access(conn, user["id"], "pay_premium_simulated", f"{patient['ref']} {reference}")
    conn.commit()
    result = status(conn, patient_id)
    conn.close()
    return result


@router.post("/patients/{patient_id}/insurance/confirm/{reference}")
def confirm_payment(patient_id: int, reference: str, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    checkout = conn.execute("SELECT * FROM premium_checkouts WHERE reference = ? AND patient_id = ?",
                            (reference, patient_id)).fetchone()
    conn.close()
    if not checkout:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not checkout["completed_at"] and not paystack.is_paid(reference, checkout["amount_ghs"]):
        raise HTTPException(status_code=400, detail="Paystack has not received this payment yet")

    conn = get_db()
    # Marking it complete only succeeds once, so pressing twice can never add cover twice
    if conn.execute("UPDATE premium_checkouts SET completed_at = ? WHERE reference = ? AND completed_at IS NULL RETURNING reference",
                    (now_text(), reference)).fetchone():
        add_cover(conn, patient_id, checkout["months"], checkout["amount_ghs"], checkout["network"], reference, user["id"])
        log_access(conn, user["id"], "confirm_premium_payment", f"{patient['ref']} {reference}")
    conn.commit()
    result = status(conn, patient_id)
    conn.close()
    return result
