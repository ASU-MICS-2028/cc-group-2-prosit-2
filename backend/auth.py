import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database import get_db

# Secret used to sign tokens. Must come from .env in real use.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Fallback for local dev only: random each start, so old tokens stop working
    JWT_SECRET = secrets.token_hex(32)
    print("WARNING: JWT_SECRET not set; using a temporary one (logins reset on restart)")

TOKEN_HOURS = 8  # roughly one CHV working day

bearer = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def offline_key_for(user_id: int) -> str:
    # Same user always gets the same key, so their queued checks can be read
    # after they log in again. Derived from the server secret; never stored.
    digest = hmac.new(JWT_SECRET.encode(), f"offline-key:{user_id}".encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()  # 32 bytes = AES-256 key


def create_token(user) -> str:
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    # Reject missing, tampered or expired tokens
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db()
    user = conn.execute(
        "SELECT id, username, role, full_name, facility, facility_phone, district FROM users WHERE id = ?",
        (int(payload["sub"]),),
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return dict(user)


def require_role(*roles):
    # Usage: user = Depends(require_role("chv"))
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot do this")
        return user
    return checker
