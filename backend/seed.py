"""Create one FAKE test account per role. Run once: python seed.py

These accounts are for local testing only. Change or delete them before any real deployment.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from database import get_db, init_db

# Password for all demo accounts; override with DEMO_PASSWORD in .env
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@1234")

USERS = [
    # username,  role,     full name,          facility,                 facility phone (fake), district (real name, fake data)
    ("chv1",    "chv",    "Test CHV One",     "Test Health Centre",     "0240000000", "Bolgatanga Municipal"),
    ("chv2",    "chv",    "Test CHV Two",     "Test Health Centre",     "0240000000", "Bolgatanga Municipal"),
    ("nurse1",  "nurse",  "Test Nurse",       "Test Health Centre",     None,         "Bolgatanga Municipal"),
    ("nurse2",  "nurse",  "Test Nurse Two",   "Other Test Clinic",      None,         "Tamale Metropolitan"),
    ("doctor1", "doctor", "Test Doctor",      "Test District Hospital", None,         "Bolgatanga Municipal"),
    ("ghs1",    "ghs",    "Test GHS Officer", "GHS District Office",    None,         None),  # national view
    ("admin1",  "admin",  "Test Admin",       None,                     None,         None),
]

init_db()
conn = get_db()
for username, role, full_name, facility, phone, district in USERS:
    conn.execute(
        """INSERT OR IGNORE INTO users (username, password_hash, role, full_name, facility, facility_phone, district)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (username, hash_password(DEMO_PASSWORD), role, full_name, facility, phone, district),
    )
    # Accounts created before districts existed get theirs now
    conn.execute("UPDATE users SET district = ? WHERE username = ? AND district IS NULL", (district, username))
conn.execute("UPDATE patients SET district = (SELECT district FROM users WHERE users.id = patients.chv_id) "
             "WHERE district IS NULL")
conn.commit()
conn.close()
print(f"Seeded {len(USERS)} demo users. Password: {DEMO_PASSWORD}")
