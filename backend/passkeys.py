"""Sign in with the phone's own lock: fingerprint, face or PIN (WebAuthn "passkeys").

Why: many CHVs find typing a password on a small screen hard. After one normal sign-in,
they turn on fingerprint sign-in once; after that they just touch the sensor.

How it works (public-key cryptography, nothing secret is sent):
1. Turn on: the phone makes a key pair. The PRIVATE key stays locked inside the phone and
   is only used after the fingerprint/face/PIN check. The server stores the PUBLIC key.
2. Sign in: the server sends a random one-time challenge; the phone signs it with the
   private key; the server checks the signature with the public key. A copied signature is
   useless because every challenge is different and used once.
The server never sees the fingerprint: it stays on the phone (that is how WebAuthn works).
"""
import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorAttachment, AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from auth import get_current_user, login_response
from database import get_db, log_access, now_text

router = APIRouter()
CHALLENGE_MINUTES = 5
DB_TIME = "%Y-%m-%d %H:%M:%S"


def allowed_origins():
    # The website addresses allowed to use passkeys: the same list CORS uses
    return [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


def rp_id_for(origin):
    """The 'relying party' id is the website's host name, e.g. d2o8wlf1glknxm.cloudfront.net."""
    if origin not in allowed_origins():
        raise HTTPException(status_code=400, detail="This website address cannot use fingerprint sign-in")
    return origin.split("://", 1)[1].split(":")[0].split("/")[0]


def save_challenge(conn, challenge, purpose, user_id=None):
    expires = (datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_MINUTES)).strftime(DB_TIME)
    conn.execute("DELETE FROM passkey_challenges WHERE expires_at < ?", (now_text(),))  # tidy old ones
    conn.execute("INSERT INTO passkey_challenges (challenge, user_id, purpose, expires_at) VALUES (?, ?, ?, ?)",
                 (bytes_to_base64url(challenge), user_id, purpose, expires))


def use_challenge(conn, credential, purpose):
    """Read the challenge the phone signed, check we issued it, and delete it (one use only)."""
    try:
        client_data = json.loads(base64url_to_bytes(credential["response"]["clientDataJSON"]))
        challenge = client_data["challenge"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Fingerprint sign-in failed. Please try again.")
    row = conn.execute("SELECT * FROM passkey_challenges WHERE challenge = ? AND purpose = ? AND expires_at >= ?",
                       (challenge, purpose, now_text())).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Fingerprint sign-in expired. Please try again.")
    conn.execute("DELETE FROM passkey_challenges WHERE id = ?", (row["id"],))
    return row, base64url_to_bytes(challenge)


class OriginIn(BaseModel):
    origin: str  # window.location.origin; the phone also signs it, so it cannot be faked


class CredentialIn(OriginIn):
    credential: dict
    label: str = ""


# ---------- Turn on (signed in with a password first) ----------

@router.post("/auth/passkey/register/options")
def register_options(body: OriginIn, user=Depends(get_current_user)):
    conn = get_db()
    existing = conn.execute("SELECT credential_id FROM passkeys WHERE user_id = ?", (user["id"],)).fetchall()
    options = generate_registration_options(
        rp_id=rp_id_for(body.origin), rp_name="HealthConnect Ghana",
        user_id=str(user["id"]).encode(), user_name=user["username"], user_display_name=user["full_name"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,  # the phone's own sensor
            resident_key=ResidentKeyRequirement.REQUIRED,               # sign in without typing a username
            user_verification=UserVerificationRequirement.REQUIRED,     # fingerprint, face or PIN every time
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"])) for r in existing],
    )
    save_challenge(conn, options.challenge, "register", user["id"])
    conn.commit()
    conn.close()
    return json.loads(options_to_json(options))


@router.post("/auth/passkey/register/verify")
def register_verify(body: CredentialIn, user=Depends(get_current_user)):
    conn = get_db()
    try:
        row, challenge = use_challenge(conn, body.credential, "register")
        if row["user_id"] != user["id"]:
            raise HTTPException(status_code=400, detail="Fingerprint sign-in failed. Please try again.")
        try:
            verified = verify_registration_response(credential=body.credential, expected_challenge=challenge,
                                                    expected_rp_id=rp_id_for(body.origin), expected_origin=allowed_origins(),
                                                    require_user_verification=True)
        except Exception:
            raise HTTPException(status_code=400, detail="This phone could not be set up. Please try again.")
        conn.execute("INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, label, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (user["id"], bytes_to_base64url(verified.credential_id), bytes_to_base64url(verified.credential_public_key),
                      verified.sign_count, body.label.strip()[:60] or None, now_text()))
        log_access(conn, user["id"], "passkey_added")
        conn.commit()
    finally:
        conn.close()
    return {"success": True}


@router.get("/auth/passkeys")
def my_passkeys(user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("SELECT id, label, created_at, last_used_at FROM passkeys WHERE user_id = ? ORDER BY id",
                        (user["id"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/auth/passkeys/{passkey_id}")
def remove_passkey(passkey_id: int, user=Depends(get_current_user)):
    conn = get_db()
    conn.execute("DELETE FROM passkeys WHERE id = ? AND user_id = ?", (passkey_id, user["id"]))
    log_access(conn, user["id"], "passkey_removed")
    conn.commit()
    conn.close()
    return {"success": True}


# ---------- Sign in with the fingerprint ----------

@router.post("/auth/passkey/login/options")
def login_options(body: OriginIn):
    options = generate_authentication_options(rp_id=rp_id_for(body.origin),
                                              user_verification=UserVerificationRequirement.REQUIRED)
    conn = get_db()
    save_challenge(conn, options.challenge, "login")
    conn.commit()
    conn.close()
    return json.loads(options_to_json(options))


@router.post("/auth/passkey/login/verify")
def login_verify(body: CredentialIn):
    conn = get_db()
    try:
        _, challenge = use_challenge(conn, body.credential, "login")
        conn.commit()  # the challenge is used up even if the rest fails
        key = conn.execute("SELECT * FROM passkeys WHERE credential_id = ?", (str(body.credential.get("id")),)).fetchone()
        user = key and conn.execute("SELECT * FROM users WHERE id = ?", (key["user_id"],)).fetchone()
        if not user:
            log_access(conn, None, "passkey_login_failed")
            conn.commit()
            raise HTTPException(status_code=401, detail="This fingerprint is not set up for HealthConnect. Sign in with your password.")
        try:
            verified = verify_authentication_response(
                credential=body.credential, expected_challenge=challenge, expected_rp_id=rp_id_for(body.origin),
                expected_origin=allowed_origins(), credential_public_key=base64url_to_bytes(key["public_key"]),
                credential_current_sign_count=key["sign_count"], require_user_verification=True)
        except Exception:
            log_access(conn, user["id"], "passkey_login_failed")
            conn.commit()
            raise HTTPException(status_code=401, detail="Fingerprint sign-in failed. Please try again.")
        if not user["active"]:
            raise HTTPException(status_code=403, detail="This account is disabled. Contact your system admin.")
        conn.execute("UPDATE passkeys SET sign_count = ?, last_used_at = ? WHERE id = ?",
                     (verified.new_sign_count, now_text(), key["id"]))
        log_access(conn, user["id"], "login_passkey")
        conn.commit()
        return login_response(user)
    finally:
        conn.close()
