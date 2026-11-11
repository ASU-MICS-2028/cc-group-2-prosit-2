"""Create one FAKE test account per role. Run once: python seed.py

The people are invented (names typical of each region); any match with a real person is coincidence.
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
    ("chv1",    "chv",       "Grace Atanga",       "Test Health Centre",     "0240000000", "Bolgatanga Municipal"),
    ("chv2",    "chv",       "Joseph Ayamga",      "Test Health Centre",     "0240000000", "Bolgatanga Municipal"),
    ("nurse1",  "nurse",     "Mercy Akolgo",       "Test Health Centre",     None,         "Bolgatanga Municipal"),
    ("nurse2",  "nurse",     "Ramatu Alhassan",    "Other Test Clinic",      None,         "Tamale Metropolitan"),
    ("doctor1", "doctor",    "Dr Emmanuel Abugri", "Test District Hospital", None,         "Bolgatanga Municipal"),
    ("pharm1",  "pharmacist", "Comfort Azure",      "Test District Hospital", None,         "Bolgatanga Municipal"),
    ("ghs1",    "ghs",       "Selorm Dzokoto",     "GHS District Office",    None,         None),  # national view
    ("admin1",  "admin",     "Kojo Ofori",         None,                     None,         None),
]

init_db()
conn = get_db()
for username, role, full_name, facility, phone, district in USERS:
    conn.execute(
        """INSERT INTO users (username, password_hash, role, full_name, facility, facility_phone, district)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (username) DO NOTHING""",
        (username, hash_password(DEMO_PASSWORD), role, full_name, facility, phone, district),
    )
    # Accounts made by older versions were called "Test ..."; give them their name now
    conn.execute("UPDATE users SET full_name = ? WHERE username = ? AND full_name LIKE 'Test %'", (full_name, username))
    # Accounts created before districts existed get theirs now
    conn.execute("UPDATE users SET district = ? WHERE username = ? AND district IS NULL", (district, username))
conn.execute("UPDATE users SET facility_manager = 1 WHERE username = 'nurse1'")  # demo manager of Test Health Centre
conn.execute("UPDATE patients SET district = (SELECT district FROM users WHERE users.id = patients.chv_id) "
             "WHERE district IS NULL")
conn.commit()
conn.close()
print(f"Seeded {len(USERS)} demo users. Password: {DEMO_PASSWORD}")
