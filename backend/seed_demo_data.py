"""FAKE surveillance demo data: 8 weeks of general visits across 5 districts,
with a simulated cholera spike in Tamale this week. Run once: python seed_demo_data.py

The dates count back from "now". So that the dashboard looks the same on any day
(spike always "this week"), the backend re-creates these records at start-up and
every 10 minutes (keep_demo_data_current), but ONLY when DEMO_MODE=on in .env.
The fixed random seed makes every re-creation identical. Off by default, so a
cloud/real deployment never touches this unless someone deliberately turns it on.

Every patient is "Demo Patient NNNN". District names are real; all data is invented.
"""
import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from database import get_db, init_db, new_patient_ref
from general_model import assess_general

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

DEMO_PATIENTS = "SELECT id FROM patients WHERE full_name LIKE 'Demo Patient%'"


def demo_data_exists(conn):
    return conn.execute(DEMO_PATIENTS).fetchone() is not None


def remove_demo_data(conn):
    # Children first. Real test patients are never touched.
    for table in ["appointments", "referrals", "observations"]:
        conn.execute(f"DELETE FROM {table} WHERE patient_id IN ({DEMO_PATIENTS})")
    conn.execute("DELETE FROM patients WHERE full_name LIKE 'Demo Patient%'")


def create_demo_data(conn):
    random.seed(42)  # same "random" data every time
    now = datetime.now(timezone.utc)
    count = 0
    for district, (username, per_week) in DISTRICTS.items():
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, facility, district) "
                "VALUES (?, ?, 'chv', ?, ?, ?)",
                (username, hash_password("Demo@1234"), f"Demo CHV {district.split()[0]}",
                 f"Demo Clinic {district.split()[0]}", district),
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
    return count


def keep_demo_data_current():
    # Re-date the demo visits to "now" (remove + re-create in one transaction,
    # so the dashboard never sees half the data).
    # Two locks: DEMO_MODE must be switched on, AND demo records must exist.
    if os.getenv("DEMO_MODE", "").lower() != "on":
        return
    conn = get_db()
    if demo_data_exists(conn):
        remove_demo_data(conn)
        create_demo_data(conn)
        conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    conn = get_db()
    if demo_data_exists(conn):
        print("Demo data already exists. Nothing to do.")
    else:
        count = create_demo_data(conn)
        conn.commit()
        print(f"Created {count} fake demo visits across {len(DISTRICTS)} districts (cholera spike in Tamale this week).")
    conn.close()
