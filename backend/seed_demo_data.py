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
from database import get_db, init_db, new_patient_ref, now_text
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
    demo_rx = f"SELECT id FROM prescriptions WHERE patient_id IN ({DEMO_PATIENTS})"
    # Stock history stays (the stock really moved); it just no longer points at the prescription
    conn.execute(f"UPDATE stock_movements SET prescription_id = NULL WHERE prescription_id IN ({demo_rx})")
    conn.execute(f"DELETE FROM prescription_items WHERE prescription_id IN ({demo_rx})")
    for table in ["prescriptions", "appointments", "referrals", "observations"]:
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
                patient_id = conn.execute(
                    "INSERT INTO patients (ref, chv_id, full_name, age, sex, community, district, consent) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1) RETURNING id",
                    (new_patient_ref(conn), chv_id, f"Demo Patient {count:04d}",
                     random.randint(1, 80), random.choice(["female", "male"]), "Demo community", district),
                ).fetchone()["id"]
                level, conditions = assess_general(temp, None, None, None, symptoms)
                when = now - timedelta(days=week * 7 + random.randint(0, 6), hours=random.randint(0, 23))
                conn.execute(
                    "INSERT INTO observations (patient_id, recorded_by, visit_type, body_temp, symptoms, "
                    "possible_conditions, risk_level, created_at) VALUES (?, ?, 'general', ?, ?, ?, ?, ?)",
                    (patient_id, chv_id, temp, ",".join(symptoms), ",".join(conditions), level,
                     when.strftime("%Y-%m-%d %H:%M:%S")),
                )
        count = create_demo_care(conn, district, chv_id, now, count)
    return count


# How often a pregnant demo patient gets an antenatal check. Invented, so the SDG 3 panel has
# something to show: some districts do better, and every district improves a little each week.
ANTENATAL_RATE = {"Bolgatanga Municipal": 0.5, "Tamale Metropolitan": 0.6, "Wa Municipal": 0.45,
                  "Kumasi Metropolitan": 0.75, "Cape Coast Metropolitan": 0.7}


def create_demo_care(conn, district, chv_id, now, count):
    """Fake pregnancies, antenatal checks, referrals and appointments for the SDG 3 panel."""
    facility = f"Demo Clinic {district.split()[0]}"
    stamp = lambda moment: moment.strftime("%Y-%m-%d %H:%M:%S")
    for week in range(8):
        chance = ANTENATAL_RATE[district] + 0.02 * (7 - week)
        for _ in range(5):
            count += 1
            when = now - timedelta(days=week * 7 + random.randint(0, 6), hours=random.randint(1, 23))
            patient_id = conn.execute(
                "INSERT INTO patients (ref, chv_id, full_name, age, sex, pregnant, community, district, consent, created_at) "
                "VALUES (?, ?, ?, ?, 'female', 1, ?, ?, 1, ?) RETURNING id",
                (new_patient_ref(conn), chv_id, f"Demo Patient {count:04d}", random.randint(16, 42),
                 "Demo community", district, stamp(when)),
            ).fetchone()["id"]
            if random.random() >= chance:
                continue
            level = random.choice(["LOW", "MEDIUM", "HIGH"])
            observation_id = conn.execute(
                "INSERT INTO observations (patient_id, recorded_by, visit_type, risk_level, created_at) "
                "VALUES (?, ?, 'antenatal', ?, ?) RETURNING id",
                (patient_id, chv_id, level, stamp(when)),
            ).fetchone()["id"]
            if level == "LOW":
                continue
            done = random.random() < 0.8
            finished = when + timedelta(hours=random.randint(4, 72))
            referral_id = conn.execute(
                "INSERT INTO referrals (observation_id, patient_id, chv_id, referred_by, facility, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (observation_id, patient_id, chv_id, chv_id, facility, "completed" if done else "pending",
                 stamp(when), stamp(finished) if done else None),
            ).fetchone()["id"]
            # Only an appointment already in the past can have been attended or missed
            if done and finished + timedelta(days=2) < now:
                conn.execute(
                    "INSERT INTO appointments (patient_id, referral_id, booked_by, facility, scheduled_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (patient_id, referral_id, chv_id, facility, (finished + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                     "attended" if random.random() < 0.75 else "missed"),
                )
    return count


# Demo pharmacy stock: (facility, {drug name start: quantity}). Drugs not listed get a healthy amount.
# Tamale's clinic is out of ORS and low on zinc, to match its cholera spike.
DEMO_STOCK = [
    ("Test District Hospital", {"Amoxicillin": 150, "Artemether": 12, "Oral rehydration": 400, "Paracetamol": 2000}),
    ("Demo Clinic Tamale", {"Oral rehydration": 0, "Zinc": 40, "Cholera rapid": 3}),
    ("Demo Clinic Bolgatanga", {"Artemether": 15}),
    ("Demo Clinic Wa", {"Amoxicillin": 0}),
    ("Demo Clinic Kumasi", {}),
    ("Demo Clinic Cape", {}),
]


def create_demo_stock(conn):
    """Opening stock for the demo pharmacies. Only once: a facility that already has stock
    is left alone, so a pharmacist's own changes are never overwritten."""
    drugs = conn.execute("SELECT id, name, default_reorder_level FROM drugs").fetchall()
    pharmacist = conn.execute("SELECT id FROM users WHERE username = 'pharm1'").fetchone()
    created = 0
    for facility_start, amounts in DEMO_STOCK:
        row = conn.execute("SELECT DISTINCT facility FROM users WHERE facility LIKE ?", (facility_start + "%",)).fetchone()
        if not row or conn.execute("SELECT 1 FROM stock WHERE facility = ?", (row["facility"],)).fetchone():
            continue
        for drug in drugs:
            quantity = next((q for start, q in amounts.items() if drug["name"].startswith(start)),
                            drug["default_reorder_level"] * 3)
            conn.execute("INSERT INTO stock (facility, drug_id, quantity, reorder_level, updated_at) VALUES (?, ?, ?, ?, ?)",
                         (row["facility"], drug["id"], quantity, drug["default_reorder_level"], now_text()))
            if pharmacist and row["facility"] == "Test District Hospital" and quantity:
                conn.execute(
                    "INSERT INTO stock_movements (facility, drug_id, change, quantity_after, reason, note, user_id, created_at) "
                    "VALUES (?, ?, ?, ?, 'received', 'Opening stock (demo data)', ?, ?)",
                    (row["facility"], drug["id"], quantity, quantity, pharmacist["id"], now_text()))
        created += 1
    return created


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
    pharmacies = create_demo_stock(conn)
    conn.commit()
    print(f"Demo stock created for {pharmacies} pharmacies." if pharmacies else "Demo stock already exists. Nothing to do.")
    conn.close()
