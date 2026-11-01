"""System admin: create and disable staff accounts. No patient data here.

The admin never chooses passwords: the server makes a random temporary one,
shows it once, and stores only its bcrypt hash.
Accounts are disabled, never deleted: their patients, referrals and audit log
entries still point to them.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException

from auth import hash_password, require_role
from database import get_db, log_access
from schemas import AccountActive, AccountCreate
from surveillance import DISTRICT_CENTRES

router = APIRouter()

NEEDS_FACILITY = ("chv", "nurse", "doctor")  # referrals are routed by facility


@router.get("/admin/users")
def list_users(user=Depends(require_role("admin"))):
    conn = get_db()
    # Account details only. No password hashes, no patients.
    rows = conn.execute(
        "SELECT id, username, role, full_name, facility, facility_phone, district, active "
        "FROM users ORDER BY role, username"
    ).fetchall()
    log_access(conn, user["id"], "list_users")
    conn.commit()
    conn.close()
    return {"users": [dict(r) for r in rows], "districts": list(DISTRICT_CENTRES)}


@router.post("/admin/users")
def create_user(body: AccountCreate, user=Depends(require_role("admin"))):
    if body.role in NEEDS_FACILITY and not body.facility:
        raise HTTPException(status_code=422, detail="CHVs, nurses and doctors need a facility")
    if body.district and body.district not in DISTRICT_CENTRES:
        raise HTTPException(status_code=422, detail="Unknown district")

    conn = get_db()
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (body.username,)).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="That username is already taken")

    temporary_password = secrets.token_urlsafe(9)  # 12 random characters
    conn.execute(
        """INSERT INTO users (username, password_hash, role, full_name, facility, facility_phone, district)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (body.username, hash_password(temporary_password), body.role, body.full_name,
         body.facility or None, body.facility_phone or None, body.district or None),
    )
    log_access(conn, user["id"], "create_user", f"{body.username} ({body.role})")
    conn.commit()
    conn.close()
    # Shown to the admin once, to hand over in person. Never stored in plain text.
    return {"username": body.username, "temporary_password": temporary_password}


@router.post("/admin/users/{user_id}/active")
def set_active(user_id: int, body: AccountActive, user=Depends(require_role("admin"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")

    conn = get_db()
    target = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(body.active), user_id))
    log_access(conn, user["id"], "enable_user" if body.active else "disable_user", target["username"])
    conn.commit()
    conn.close()
    return {"success": True}
