"""Traditional healers working with CHVs: a healer who sees danger signs sends the patient on.

Many patients see a healer first. The CHV registers the healers in their community and records
a referral for them, because a healer may not read or have a smartphone. Nothing replaces the
healer: the aim is that serious cases reach a clinic early, and the clinic knows what was given.

The registration number is what the healer states; it is NOT checked against the real register
of Ghana's Traditional Medicine Practice Council (no such link exists in this prototype).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()


class HealerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    community: str = Field(default="", max_length=100)
    registration_no: str = Field(default="", max_length=50)


class HealerReferralCreate(BaseModel):
    healer_id: int
    signs: str = Field(min_length=3, max_length=300)  # the danger signs the healer saw
    remedy_given: str = Field(default="", max_length=300)  # so the clinic knows what the patient has taken


def own_patient(conn, patient_id, user):
    # Need-to-know: a CHV only reaches their own patients. Others get 404, so existence is not revealed.
    patient = conn.execute("SELECT id, ref FROM patients WHERE id = ? AND chv_id = ?", (patient_id, user["id"])).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/healers")
def list_healers(user=Depends(require_role("chv"))):
    conn = get_db()
    rows = conn.execute("SELECT id, full_name, community, registration_no FROM healers WHERE chv_id = ? ORDER BY full_name",
                        (user["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/healers")
def add_healer(body: HealerCreate, user=Depends(require_role("chv"))):
    conn = get_db()
    healer = conn.execute(
        "INSERT INTO healers (chv_id, full_name, community, registration_no, created_at) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id, full_name, community, registration_no",
        (user["id"], body.full_name.strip(), body.community.strip() or None, body.registration_no.strip() or None, now_text()),
    ).fetchone()
    log_access(conn, user["id"], "add_healer", str(healer["id"]))
    conn.commit()
    conn.close()
    return dict(healer)


@router.get("/patients/{patient_id}/healer-referrals")
def list_healer_referrals(patient_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    own_patient(conn, patient_id, user)
    rows = conn.execute("""
        SELECT hr.id, hr.signs, hr.remedy_given, hr.created_at, h.full_name AS healer_name
        FROM healer_referrals hr JOIN healers h ON h.id = hr.healer_id
        WHERE hr.patient_id = ? ORDER BY hr.id DESC
    """, (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/patients/{patient_id}/healer-referrals")
def add_healer_referral(patient_id: int, body: HealerReferralCreate, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    # Only a healer this CHV registered: 404 rather than revealing another CHV's healers
    if not conn.execute("SELECT 1 FROM healers WHERE id = ? AND chv_id = ?", (body.healer_id, user["id"])).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Healer not found")
    conn.execute(
        "INSERT INTO healer_referrals (patient_id, healer_id, signs, remedy_given, recorded_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, body.healer_id, body.signs.strip(), body.remedy_given.strip() or None, user["id"], now_text()),
    )
    log_access(conn, user["id"], "add_healer_referral", patient["ref"])
    conn.commit()
    conn.close()
    return {"success": True}
