"""FAKE surveillance demo data: 8 weeks of general visits across 5 districts,
with a simulated cholera spike in Tamale this week. Run once: python seed_demo_data.py

Dates count back from today, so the spike slowly becomes "last week". Before a demo:
    python seed_demo_data.py --refresh     (replaces ONLY the "Demo Patient" records)

Every patient is "Demo Patient NNNN". District names are real; all data is invented.
"""
import random
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from database import get_db, init_db, new_patient_ref
from general_model import assess_general

random.seed(42)  # same "random" data every time

DISTRICTS = {
    # district: (demo CHV username, typical visits per week)
    "Bolgatanga Municipal": ("demo_chv_bolga", 18),
    "Tamale Metropolitan": ("demo_chv_tamale", 22),
    "Wa Municipal": ("demo_chv_wa", 14),
    "Kumasi Metropolitan": ("demo_chv_kumasi", 25),
    "Cape Coast Metropolitan": ("demo_chv_capecoast", 16),
}

# Everyday visits: (symptoms, temperature) picked at random
COMMON = [
    (["fever"], 38.4), (["fever", "severe_headache"], 38.9), (["cough"], 37.0),
    (["cough", "fever"], 38.2), (["diarrhoea"], 37.2), ([], 37.0), (["rash"], 36.9),
]
CHOLERA_LIKE = (["diarrhoea", "vomiting"], 37.6)
# A few serious visits (danger signs) so the HIGH-risk numbers are realistic
SERIOUS = [(["cough", "fever", "difficulty_breathing"], 39.0), (["fever", "convulsions"], 39.8), (["fever"], 39.7)]

init_db()
conn = get_db()
if "--refresh" in sys.argv:
    # Remove the old demo records (children first). Real test patients are never touched.
    demo = "SELECT id FROM patients WHERE full_name LIKE 'Demo Patient%'"
    for table in ["appointments", "referrals", "observations"]:
        conn.execute(f"DELETE FROM {table} WHERE patient_id IN ({demo})")
    removed = conn.execute("DELETE FROM patients WHERE full_name LIKE 'Demo Patient%'").rowcount
    print(f"Removed {removed} old demo patients.")
if conn.execute("SELECT 1 FROM patients WHERE full_name LIKE 'Demo Patient%'").fetchone():
    print("Demo data already exists. Nothing to do.")
    raise SystemExit

now = datetime.now(timezone.utc)
count = 0
for district, (username, per_week) in DISTRICTS.items():
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role, full_name, facility, district) "
        "VALUES (?, ?, 'chv', ?, ?, ?)",
        (username, hash_password("Demo@1234"), f"Demo CHV {district.split()[0]}", f"Demo Clinic {district.split()[0]}", district),
    )
    chv_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]

    for week in range(8):
        visits = [random.choice(SERIOUS) if random.random() < 0.06 else random.choice(COMMON)
                  for _ in range(per_week + random.randint(-3, 3))]
        if district == "Tamale Metropolitan":
            # 1-3 cholera-like cases most weeks, then a spike of 14 this week
            visits += [CHOLERA_LIKE] * (14 if week == 0 else random.randint(1, 3))
        for symptoms, temp in visits:
            count += 1
            cur = conn.execute(
                "INSERT INTO patients (ref, chv_id, full_name, age, sex, community, district, consent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (new_patient_ref(conn), chv_id, f"Demo Patient {count:04d}",
                 random.randint(1, 80), random.choice(["female", "male"]), "Demo community", district),
            )
            level, conditions = assess_general(temp, None, None, None, symptoms)
            when = now - timedelta(days=week * 7 + random.randint(0, 6), hours=random.randint(0, 23))
            conn.execute(
                "INSERT INTO observations (patient_id, recorded_by, visit_type, body_temp, symptoms, "
                "possible_conditions, risk_level, created_at) VALUES (?, ?, 'general', ?, ?, ?, ?, ?)",
                (cur.lastrowid, chv_id, temp, ",".join(symptoms), ",".join(conditions), level,
                 when.strftime("%Y-%m-%d %H:%M:%S")),
            )
conn.commit()
conn.close()
print(f"Created {count} fake demo visits across {len(DISTRICTS)} districts (cholera spike in Tamale this week).")
