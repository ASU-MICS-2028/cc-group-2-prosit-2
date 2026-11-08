"""Consultation and training fees, paid through Paystack (see paystack.py). Simulated if no key is set.

CHVs are volunteers, so they never pay training fees. Each health centre sets its own
consultation fee (facility.py). The amount is always worked out here, never taken from the phone.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException

import paystack
from auth import require_role
from database import get_db, log_access, now_text
from training_list import TRAINING_MODULES

router = APIRouter()

DEFAULT_CONSULTATION_FEE_GHS = 1
TRAINING_FEE_GHS = 1
PAYING_TRAINEES = ("nurse", "doctor", "pharmacist")


def consultation_fee(conn, facility):
    row = conn.execute("SELECT consultation_fee_ghs FROM facility_settings WHERE facility = ?", (facility,)).fetchone()
    return row["consultation_fee_ghs"] if row else DEFAULT_CONSULTATION_FEE_GHS


def completed_count(conn, kind, item):
    return conn.execute("SELECT COUNT(*) AS n FROM fee_payments WHERE kind = ? AND item = ? AND completed_at IS NOT NULL",
                        (kind, item)).fetchone()["n"]


def training_fee_due(conn, user, module):
    """One fee covers one certificate, so a renewal is paid for again. CHVs are free."""
    if user["role"] not in PAYING_TRAINEES:
        return False
    earned = conn.execute("SELECT COUNT(*) AS n FROM certificates WHERE user_id = ? AND module = ? AND source = 'quiz'",
                          (user["id"], module)).fetchone()["n"]
    return completed_count(conn, "training", f"{module}:{user['id']}") <= earned


def summary(conn, kind, item, amount, due):
    pending = conn.execute(
        "SELECT reference, checkout_url FROM fee_payments WHERE kind = ? AND item = ? AND completed_at IS NULL ORDER BY id DESC LIMIT 1",
        (kind, item)).fetchone()
    return {"amount_ghs": amount, "due": due, "pending": dict(pending) if pending and due else None,
            "simulated": not paystack.is_configured(), "live": paystack.is_live()}


def charge(conn, kind, item, amount, user, facility):
    """Start a payment. conn is closed while waiting on the internet; returns a fresh one."""
    if paystack.is_configured():
        conn.close()
        reference = "HC-" + secrets.token_hex(8).upper()
        url = paystack.start_payment(reference, amount)
        conn = get_db()
        completed = None
    else:
        reference, url, completed = "SIM-" + secrets.token_hex(4).upper(), "", now_text()
    conn.execute(
        "INSERT INTO fee_payments (reference, kind, item, facility, amount_ghs, payer_id, checkout_url, completed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (reference, kind, item, facility, amount, user["id"], url, completed, now_text()),
    )
    log_access(conn, user["id"], f"start_{kind}_fee", reference)
    return conn


def facility_appointment(conn, appointment_id, user):
    row = conn.execute("SELECT facility FROM appointments WHERE id = ? AND facility = ?", (appointment_id, user["facility"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")


def consultation_summary(conn, appointment_id, user):
    amount = consultation_fee(conn, user["facility"])
    return summary(conn, "consultation", str(appointment_id), amount, amount > 0 and completed_count(conn, "consultation", str(appointment_id)) == 0)


@router.get("/fees/consultation/{appointment_id}")
def consultation_status(appointment_id: int, user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    facility_appointment(conn, appointment_id, user)
    result = consultation_summary(conn, appointment_id, user)
    conn.close()
    return result


@router.post("/fees/consultation/{appointment_id}")
def pay_consultation(appointment_id: int, user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    facility_appointment(conn, appointment_id, user)
    current = consultation_summary(conn, appointment_id, user)
    if not current["due"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No fee is due for this consultation")
    conn = charge(conn, "consultation", str(appointment_id), current["amount_ghs"], user, user["facility"])
    conn.commit()
    result = consultation_summary(conn, appointment_id, user)
    conn.close()
    return result


def training_summary(conn, module, user):
    return summary(conn, "training", f"{module}:{user['id']}", TRAINING_FEE_GHS, training_fee_due(conn, user, module))


@router.get("/fees/training/{module}")
def training_status(module: str, user=Depends(require_role(*PAYING_TRAINEES))):
    if module not in TRAINING_MODULES:
        raise HTTPException(status_code=404, detail="Training module not found")
    conn = get_db()
    result = training_summary(conn, module, user)
    conn.close()
    return result


@router.post("/fees/training/{module}")
def pay_training(module: str, user=Depends(require_role(*PAYING_TRAINEES))):
    if module not in TRAINING_MODULES:
        raise HTTPException(status_code=404, detail="Training module not found")
    conn = get_db()
    if not training_fee_due(conn, user, module):
        conn.close()
        raise HTTPException(status_code=400, detail="No fee is due for this module")
    conn = charge(conn, "training", f"{module}:{user['id']}", TRAINING_FEE_GHS, user, user["facility"])
    conn.commit()
    result = training_summary(conn, module, user)
    conn.close()
    return result


@router.post("/fees/confirm/{reference}")
def confirm_fee(reference: str, user=Depends(require_role("nurse", "doctor", "pharmacist"))):
    conn = get_db()
    payment = conn.execute("SELECT amount_ghs, completed_at FROM fee_payments WHERE reference = ? AND payer_id = ?",
                           (reference, user["id"])).fetchone()
    conn.close()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not payment["completed_at"] and not paystack.is_paid(reference, payment["amount_ghs"]):
        raise HTTPException(status_code=400, detail="Paystack has not received this payment yet")
    conn = get_db()
    if conn.execute("UPDATE fee_payments SET completed_at = ? WHERE reference = ? AND completed_at IS NULL RETURNING reference",
                    (now_text(), reference)).fetchone():
        log_access(conn, user["id"], "confirm_fee", reference)
    conn.commit()
    conn.close()
    return {"success": True}
