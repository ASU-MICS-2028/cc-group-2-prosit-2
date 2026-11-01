"""Run ONCE before HealthConnect is used with real patients.

1. Creates the first real admin (random temporary password, must be changed at first login).
2. Disables every account still using the demo password. That password is written in the
   README of a PUBLIC repo, so anyone could log in with it.

Usage:  python prepare_real_use.py <admin_username> "<Admin full name>"
"""
import os
import re
import secrets
import sys

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password, verify_password
from database import get_db, init_db, log_access

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@1234")

if len(sys.argv) != 3 or not re.fullmatch(r"[a-z0-9_]{3,30}", sys.argv[1]):
    print(__doc__)
    raise SystemExit(1)
username, full_name = sys.argv[1], sys.argv[2]

init_db()
conn = get_db()
if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
    print(f"'{username}' already exists. Choose another username.")
    raise SystemExit(1)

# Disable demo accounts first, so the new admin (random password) is never caught by the check
disabled = []
for user in conn.execute("SELECT id, username, password_hash FROM users WHERE active = 1").fetchall():
    if verify_password(DEMO_PASSWORD, user["password_hash"]):
        conn.execute("UPDATE users SET active = 0 WHERE id = ?", (user["id"],))
        disabled.append(user["username"])

temporary_password = secrets.token_urlsafe(9)
conn.execute(
    "INSERT INTO users (username, password_hash, role, full_name, must_change_password) VALUES (?, ?, 'admin', ?, 1)",
    (username, hash_password(temporary_password), full_name),
)
log_access(conn, None, "prepare_real_use", f"admin={username} disabled={len(disabled)}")
conn.commit()
conn.close()

print(f"Disabled {len(disabled)} demo account(s): {', '.join(disabled) or 'none'}")
print(f"Created admin '{username}'. Temporary password (shown once): {temporary_password}")
print("Log in, set a new password, then create the real staff accounts from the admin screen.")
