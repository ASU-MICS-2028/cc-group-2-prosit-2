"""End-to-end encryption (E2E) for visit notes and clinical photos.

"End to end" means the text and photos are locked on the phone of the person who writes them
and unlocked only on the phones of the patient's care team. The server (and anyone who
breaks into it, or into the database or its backups) only ever holds scrambled data.

The locks (all done in the browser with the Web Crypto API, see frontend/src/e2eCrypto.js):
- Every CHV, nurse and doctor has a key pair (RSA-OAEP 2048). The PUBLIC key is like an open
  padlock: anyone can use it to lock something for that person. The PRIVATE key opens it and
  never leaves the phone readable.
- Every patient has one random data key (AES-GCM 256). Notes and photos are locked with it.
- The patient's data key is locked separately for each member of the care team with THEIR
  public key, and those locked copies are stored here (patient_keys).
- A backup of each person's private key is stored here too, locked with a key made from their
  password (PBKDF2, 600,000 rounds), so they can sign in on a new phone.

Who is on the care team (same rule as photos): the patient's CHV, and nurses and doctors at
any facility the patient was referred to. Never GHS, pharmacists or admins.
When a new person joins the team (e.g. the patient is referred to a hospital), the server
cannot give them the key: it does not have it. The next team member who opens the patient
locks a copy for them (GET .../e2e-missing, then POST .../e2e-keys).

What E2E does NOT protect (honest): vital signs, symptoms and risk levels stay readable by the
server, because risk checks, inbox priority, escalation and the GHS dashboard need them (they
are still encrypted at rest and in transit). The server picks who is on the care team and gives
out their public keys, so a server changed by an attacker could add a fake member; and the
website code itself comes from the server. Admin password resets make a person's old copies
unreadable until a team member shares the key again.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()
CARE_ROLES = ("chv", "nurse", "doctor")


class MyKey(BaseModel):
    public_key: str = Field(min_length=50, max_length=2000)       # JWK text
    wrapped_private: str = Field(min_length=50, max_length=5000)  # base64, locked with the password key
    salt: str = Field(min_length=16, max_length=100)
    iv: str = Field(min_length=12, max_length=100)
    replace: bool = False  # true only when the old backup cannot be opened (e.g. after a password reset)


class Rewrap(BaseModel):
    """Password changed: same key pair, backup locked with the new password."""
    wrapped_private: str = Field(min_length=50, max_length=5000)
    salt: str = Field(min_length=16, max_length=100)
    iv: str = Field(min_length=12, max_length=100)


class Grant(BaseModel):
    user_id: int
    wrapped_key: str = Field(min_length=50, max_length=2000)  # the patient key, locked for that person


class Grants(BaseModel):
    grants: list[Grant] = Field(min_length=1, max_length=100)


def care_team(conn, patient_id):
    """User ids who may read this patient's notes and photos (active accounts only)."""
    rows = conn.execute(
        "SELECT u.id FROM users u JOIN patients p ON p.chv_id = u.id WHERE p.id = ? AND u.active = 1 "
        "UNION SELECT u.id FROM users u JOIN referrals r ON r.facility = u.facility "
        "WHERE r.patient_id = ? AND u.role IN ('nurse', 'doctor') AND u.active = 1",
        (patient_id, patient_id)).fetchall()
    return {r["id"] for r in rows}


def require_team(conn, patient_id, user):
    if user["id"] not in care_team(conn, patient_id):
        log_access(conn, user["id"], "access_denied", f"e2e:patient:{patient_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")


@router.get("/e2e/my-key")
def get_my_key(user=Depends(require_role(*CARE_ROLES))):
    conn = get_db()
    row = conn.execute("SELECT public_key, wrapped_private, salt, iv FROM user_keys WHERE user_id = ?",
                       (user["id"],)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No key yet")
    return dict(row)


@router.put("/e2e/my-key")
def set_my_key(body: MyKey, user=Depends(require_role(*CARE_ROLES))):
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM user_keys WHERE user_id = ?", (user["id"],)).fetchone()
    if exists and not body.replace:
        conn.close()
        raise HTTPException(status_code=409, detail="You already have a key")
    if exists:
        # A new key pair: copies locked for the old one can never be opened again
        conn.execute("DELETE FROM patient_keys WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM user_keys WHERE user_id = ?", (user["id"],))
    conn.execute("INSERT INTO user_keys (user_id, public_key, wrapped_private, salt, iv, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (user["id"], body.public_key, body.wrapped_private, body.salt, body.iv, now_text()))
    log_access(conn, user["id"], "e2e_key_replaced" if exists else "e2e_key_created")
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/e2e/my-key/rewrap")
def rewrap_my_key(body: Rewrap, user=Depends(require_role(*CARE_ROLES))):
    conn = get_db()
    changed = conn.execute("UPDATE user_keys SET wrapped_private = ?, salt = ?, iv = ? WHERE user_id = ?",
                           (body.wrapped_private, body.salt, body.iv, user["id"])).rowcount
    log_access(conn, user["id"], "e2e_key_rewrapped")
    conn.commit()
    conn.close()
    if not changed:
        raise HTTPException(status_code=404, detail="No key yet")
    return {"success": True}


@router.get("/patients/{patient_id}/e2e-key")
def my_copy_of_patient_key(patient_id: int, user=Depends(require_role(*CARE_ROLES))):
    """My locked copy of this patient's key. 404 'no key' = nobody has made one yet."""
    conn = get_db()
    require_team(conn, patient_id, user)
    mine = conn.execute("SELECT wrapped_key FROM patient_keys WHERE patient_id = ? AND user_id = ?",
                        (patient_id, user["id"])).fetchone()
    anyone = conn.execute("SELECT 1 FROM patient_keys WHERE patient_id = ? LIMIT 1", (patient_id,)).fetchone()
    conn.close()
    if mine:
        return {"wrapped_key": mine["wrapped_key"]}
    if anyone:
        raise HTTPException(status_code=404, detail="Waiting for the care team to share this patient's key with you")
    raise HTTPException(status_code=404, detail="No key yet")


@router.get("/patients/{patient_id}/e2e-missing")
def team_members_without_key(patient_id: int, user=Depends(require_role(*CARE_ROLES))):
    """Care team members who have a key pair but no copy of this patient's key yet, with their public keys."""
    conn = get_db()
    require_team(conn, patient_id, user)
    team = care_team(conn, patient_id)
    have = {r["user_id"] for r in conn.execute("SELECT user_id FROM patient_keys WHERE patient_id = ?", (patient_id,))}
    rows = conn.execute("SELECT k.user_id, k.public_key, u.full_name FROM user_keys k JOIN users u ON u.id = k.user_id")
    missing = [dict(r) for r in rows if r["user_id"] in team and r["user_id"] not in have]
    conn.close()
    return missing


@router.post("/patients/{patient_id}/e2e-keys")
def share_patient_key(patient_id: int, body: Grants, user=Depends(require_role(*CARE_ROLES))):
    """Store copies of the patient key, each locked for one team member.
    Allowed for someone who already has a copy, or for the first person (making the key)."""
    conn = get_db()
    require_team(conn, patient_id, user)
    holders = {r["user_id"] for r in conn.execute("SELECT user_id FROM patient_keys WHERE patient_id = ?", (patient_id,))}
    first = not holders
    if not first and user["id"] not in holders:
        conn.close()
        raise HTTPException(status_code=403, detail="Only someone who has this patient's key can share it")
    if first and user["id"] not in {g.user_id for g in body.grants}:
        conn.close()
        raise HTTPException(status_code=400, detail="Keep a copy for yourself when making a patient key")
    team = care_team(conn, patient_id)
    for grant in body.grants:
        if grant.user_id not in team:
            conn.close()
            raise HTTPException(status_code=400, detail="That person is not on this patient's care team")
    added = 0
    for grant in body.grants:
        added += conn.execute(
            "INSERT INTO patient_keys (patient_id, user_id, wrapped_key, granted_by, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (patient_id, user_id) DO NOTHING",
            (patient_id, grant.user_id, grant.wrapped_key, user["id"], now_text())).rowcount
    ref = conn.execute("SELECT ref FROM patients WHERE id = ?", (patient_id,)).fetchone()["ref"]
    log_access(conn, user["id"], "e2e_key_made" if first else "e2e_key_shared", f"{ref} to {added}")
    conn.commit()
    conn.close()
    return {"added": added}
