"""Community ownership: a health centre's own manager runs its local part of the system.

The manager is a nurse or doctor named by the system admin. They manage their own centre's
staff, set its consultation fee and see its figures. Totals only, never patient records.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text
from fees import consultation_fee

router = APIRouter()

MANAGED_ROLES = ("chv", "nurse", "doctor", "pharmacist")


class FacilityFee(BaseModel):
    consultation_fee_ghs: int = Field(ge=0, le=100)


class StaffActive(BaseModel):
    active: bool


def require_manager(user=Depends(require_role("nurse", "doctor"))):
    if not user["facility_manager"]:
        raise HTTPException(status_code=403, detail="Only this centre's manager can do this")
    return user


def count(conn, sql, *params):
    return conn.execute(sql, params).fetchone()["n"] or 0


@router.get("/facility/overview")
def overview(user=Depends(require_manager)):
    facility = user["facility"]
    month = now_text()[:7] + "-01"
    conn = get_db()
    placeholders = ", ".join("?" for _ in MANAGED_ROLES)
    staff = conn.execute(
        f"SELECT id, full_name, role, active FROM users WHERE facility = ? AND role IN ({placeholders}) ORDER BY full_name",
        (facility, *MANAGED_ROLES)).fetchall()
    result = {
        "facility": facility,
        "consultation_fee_ghs": consultation_fee(conn, facility),
        "staff": [{**dict(s), "is_you": s["id"] == user["id"]} for s in staff],
        "this_month": {
            "visits": count(conn, "SELECT COUNT(*) AS n FROM observations o JOIN users u ON u.id = o.recorded_by "
                                  "WHERE u.facility = ? AND o.created_at >= ?", facility, month),
            "referrals": count(conn, "SELECT COUNT(*) AS n FROM referrals WHERE facility = ? AND created_at >= ?", facility, month),
            "appointments": count(conn, "SELECT COUNT(*) AS n FROM appointments WHERE facility = ? AND scheduled_at >= ?", facility, month),
            "consultation_fees_ghs": count(conn, "SELECT SUM(amount_ghs) AS n FROM fee_payments WHERE facility = ? AND kind = 'consultation' "
                                                 "AND completed_at >= ?", facility, month),
            "premiums_ghs": count(conn, "SELECT SUM(p.amount_ghs) AS n FROM premium_payments p JOIN users u ON u.id = p.recorded_by "
                                        "WHERE u.facility = ? AND p.created_at >= ?", facility, month),
        },
    }
    log_access(conn, user["id"], "view_facility_overview", facility)
    conn.commit()
    conn.close()
    return result


@router.post("/facility/fee")
def set_fee(body: FacilityFee, user=Depends(require_manager)):
    conn = get_db()
    conn.execute(
        "INSERT INTO facility_settings (facility, consultation_fee_ghs, updated_by, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (facility) DO UPDATE SET consultation_fee_ghs = excluded.consultation_fee_ghs, "
        "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
        (user["facility"], body.consultation_fee_ghs, user["id"], now_text()),
    )
    log_access(conn, user["id"], "set_consultation_fee", f"{user['facility']} GHS {body.consultation_fee_ghs}")
    conn.commit()
    conn.close()
    return {"consultation_fee_ghs": body.consultation_fee_ghs}


@router.post("/facility/staff/{staff_id}/active")
def set_staff_active(staff_id: int, body: StaffActive, user=Depends(require_manager)):
    if staff_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    conn = get_db()
    target = conn.execute("SELECT username, role FROM users WHERE id = ? AND facility = ?", (staff_id, user["facility"])).fetchone()
    if not target or target["role"] not in MANAGED_ROLES:
        conn.close()
        raise HTTPException(status_code=404, detail="Staff member not found at this centre")
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(body.active), staff_id))
    log_access(conn, user["id"], "facility_enable_user" if body.active else "facility_disable_user", target["username"])
    conn.commit()
    conn.close()
    return {"success": True}
