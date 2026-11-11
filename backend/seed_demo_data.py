"""FAKE surveillance demo data: 8 weeks of general visits across 5 districts,
with a simulated cholera spike in Tamale this week. Run once: python seed_demo_data.py

The dates count back from "now". So that the dashboard looks the same on any day
(spike always "this week"), the backend re-creates these records at start-up and
every 10 minutes (keep_demo_data_current), but ONLY when DEMO_MODE=on in .env.
The fixed random seed makes every re-creation identical. Off by default, so a
cloud/real deployment never touches this unless someone deliberately turns it on.

Districts and communities are real places; every person and every health record is invented.
Names are typical of each region (Dagbani names in Tamale, Fante names in Cape Coast...) so the
demo looks realistic; any match with a real person is coincidence. Demo patients are recognised
by their demo CHV (usernames demo_chv_...), so never register real patients under those accounts.
"""
import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from database import get_db, init_db, new_patient_ref, now_text
from general_model import assess_general
from training_list import TRAINING_MODULES

DISTRICTS = {
    # district: (demo CHV username, demo CHV name, typical visits per week)
    "Bolgatanga Municipal": ("demo_chv_bolga", "Patience Akolgo", 18),
    "Tamale Metropolitan": ("demo_chv_tamale", "Salamatu Iddrisu", 22),
    "Wa Municipal": ("demo_chv_wa", "Bernice Dery", 14),
    "Kumasi Metropolitan": ("demo_chv_kumasi", "Akosua Owusu", 25),
    "Cape Coast Metropolitan": ("demo_chv_capecoast", "Efua Quansah", 16),
}

# Invented names typical of each region: (female first names, male first names, surnames), communities
NAMES = {
    "Bolgatanga Municipal": (
        ["Grace", "Agnes", "Asibi", "Awinpoka", "Felicia", "Joyce", "Ayinbisa", "Lydia", "Atampoka", "Mary"],
        ["Atinga", "Joseph", "Francis", "Akolbire", "Awuni", "Daniel", "Anaba", "Moses", "Peter", "Ayine"],
        ["Atanga", "Ayamga", "Akolgo", "Abugri", "Azure", "Anaba", "Atia", "Awuni", "Asaah", "Ayine"]),
    "Tamale Metropolitan": (
        ["Amina", "Salamatu", "Fati", "Mariama", "Zenabu", "Rahinatu", "Ayishetu", "Hawa", "Memunatu", "Sana"],
        ["Abdulai", "Fuseini", "Iddrisu", "Alhassan", "Mohammed", "Yakubu", "Issah", "Abukari", "Sulemana", "Mustapha"],
        ["Alhassan", "Iddrisu", "Abdulai", "Yakubu", "Fuseini", "Mohammed", "Issah", "Abukari", "Sulemana", "Salifu"]),
    "Wa Municipal": (
        ["Bernice", "Sakina", "Ayisha", "Faustina", "Magdalene", "Hawawu", "Gifty", "Asana", "Mwinbong", "Rita"],
        ["Mwinkaara", "Francis", "Sumaila", "Yahaya", "Bernard", "Saaka", "Anthony", "Issahaku", "Lambert", "Dominic"],
        ["Dery", "Bayor", "Kuuire", "Issahaku", "Bakuri", "Sumaila", "Saaka", "Yahaya", "Dabuo", "Bakor"]),
    "Kumasi Metropolitan": (
        ["Akosua", "Ama", "Abena", "Adwoa", "Afua", "Yaa", "Akua", "Comfort", "Gifty", "Esther"],
        ["Kwame", "Kofi", "Kwaku", "Yaw", "Kwabena", "Kwasi", "Kwadwo", "Samuel", "Isaac", "Michael"],
        ["Asante", "Boateng", "Owusu", "Osei", "Mensah", "Agyeman", "Frimpong", "Appiah", "Ofori", "Opoku"]),
    "Cape Coast Metropolitan": (
        ["Esi", "Efua", "Araba", "Ekua", "Aba", "Adwoa", "Ama", "Abena", "Mercy", "Elizabeth"],
        ["Kweku", "Ekow", "Kobina", "Kwesi", "Kojo", "Fiifi", "Kwamena", "Ebo", "Joseph", "Paul"],
        ["Quansah", "Arhin", "Essel", "Eshun", "Amissah", "Ansah", "Baidoo", "Turkson", "Ackah", "Hagan"]),
}
COMMUNITIES = {
    "Bolgatanga Municipal": ["Zuarungu", "Sumbrungu", "Yikene", "Sherigu", "Gambibgo", "Zaare"],
    "Tamale Metropolitan": ["Lamashegu", "Kalpohin", "Vittin", "Choggu", "Sagnarigu", "Gumani"],
    "Wa Municipal": ["Kpongu", "Busa", "Charia", "Dobile", "Kperisi", "Danko"],
    "Kumasi Metropolitan": ["Asawase", "Aboabo", "Suame", "Bantama", "Kwadaso", "Asokwa"],
    "Cape Coast Metropolitan": ["Kakumdo", "Abura", "Ola", "Pedu", "Amamoma", "Ekon"],
}


def demo_person(names, district, sex):
    """An invented name and a real community from the district. A separate random generator,
    so adding names never changes the visits themselves (the cholera spike stays the same)."""
    female, male, surnames = NAMES[district]
    first = names.choice(female if sex == "female" else male)
    return f"{first} {names.choice(surnames)}", names.choice(COMMUNITIES[district])

# Everyday visits: (symptoms, temperature) picked at random
COMMON = [
    (["fever"], 38.4), (["fever", "severe_headache"], 38.9), (["cough"], 37.0),
    (["cough", "fever"], 38.2), (["diarrhoea"], 37.2), ([], 37.0), (["rash"], 36.9),
]
CHOLERA_LIKE = (["diarrhoea", "vomiting"], 37.6)
# A few serious visits (danger signs) so the HIGH-risk numbers are realistic
SERIOUS = [(["cough", "fever", "difficulty_breathing"], 39.0), (["fever", "convulsions"], 39.8), (["fever"], 39.7)]

DEMO_CHVS = ", ".join(f"'{username}'" for username, _, _ in DISTRICTS.values())
# Demo patients belong to a demo CHV. "Demo Patient NNNN" catches data made by older versions.
DEMO_PATIENTS = (f"SELECT id FROM patients WHERE chv_id IN (SELECT id FROM users WHERE username IN ({DEMO_CHVS})) "
                 "OR full_name LIKE 'Demo Patient%'")


def demo_data_exists(conn):
    return conn.execute(DEMO_PATIENTS).fetchone() is not None


def remove_demo_data(conn):
    # Children first. Real test patients are never touched.
    demo_rx = f"SELECT id FROM prescriptions WHERE patient_id IN ({DEMO_PATIENTS})"
    # Stock history stays (the stock really moved); it just no longer points at the prescription
    conn.execute(f"UPDATE stock_movements SET prescription_id = NULL WHERE prescription_id IN ({demo_rx})")
    conn.execute(f"DELETE FROM prescription_items WHERE prescription_id IN ({demo_rx})")
    for table in ["healer_referrals", "premium_checkouts", "premium_payments", "insurance_members", "prescriptions", "appointments", "referrals", "observations"]:
        conn.execute(f"DELETE FROM {table} WHERE patient_id IN ({DEMO_PATIENTS})")
    conn.execute(f"DELETE FROM patients WHERE id IN ({DEMO_PATIENTS})")


def create_demo_data(conn):
    random.seed(42)  # same "random" data every time
    names = random.Random(7)  # names and communities, separate so the visits never change
    now = datetime.now(timezone.utc)
    count = 0
    for district, (username, chv_name, per_week) in DISTRICTS.items():
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, facility, district) "
                "VALUES (?, ?, 'chv', ?, ?, ?)",
                (username, hash_password("Demo@1234"), chv_name, f"Demo Clinic {district.split()[0]}", district),
            )
        # Accounts made by older versions were called "Demo CHV ..."
        conn.execute("UPDATE users SET full_name = ? WHERE username = ? AND full_name LIKE 'Demo CHV%'",
                     (chv_name, username))
        chv_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]

        for week in range(8):
            visits = [random.choice(SERIOUS) if random.random() < 0.06 else random.choice(COMMON)
                      for _ in range(per_week + random.randint(-3, 3))]
            if district == "Tamale Metropolitan":
                # 1-3 cholera-like cases most weeks, then a spike of 14 this week
                visits += [CHOLERA_LIKE] * (14 if week == 0 else random.randint(1, 3))
            for symptoms, temp in visits:
                count += 1
                age, sex = random.randint(1, 80), random.choice(["female", "male"])
                full_name, community = demo_person(names, district, sex)
                patient_id = conn.execute(
                    "INSERT INTO patients (ref, chv_id, full_name, age, sex, community, district, consent) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1) RETURNING id",
                    (new_patient_ref(conn), chv_id, full_name, age, sex, community, district),
                ).fetchone()["id"]
                level, conditions = assess_general(temp, None, None, None, symptoms)
                when = now - timedelta(days=week * 7 + random.randint(0, 6), hours=random.randint(0, 23))
                conn.execute(
                    "INSERT INTO observations (patient_id, recorded_by, visit_type, body_temp, symptoms, "
                    "possible_conditions, risk_level, created_at) VALUES (?, ?, 'general', ?, ?, ?, ?, ?)",
                    (patient_id, chv_id, temp, ",".join(symptoms), ",".join(conditions), level,
                     when.strftime("%Y-%m-%d %H:%M:%S")),
                )
        count = create_demo_care(conn, district, chv_id, now, count, names)
    return count


# How often a pregnant demo patient gets an antenatal check. Invented, so the SDG 3 panel has
# something to show: some districts do better, and every district improves a little each week.
ANTENATAL_RATE = {"Bolgatanga Municipal": 0.5, "Tamale Metropolitan": 0.6, "Wa Municipal": 0.45,
                  "Kumasi Metropolitan": 0.75, "Cape Coast Metropolitan": 0.7}


def create_demo_care(conn, district, chv_id, now, count, names):
    """Fake pregnancies, antenatal checks, referrals and appointments for the SDG 3 panel."""
    facility = f"Demo Clinic {district.split()[0]}"
    stamp = lambda moment: moment.strftime("%Y-%m-%d %H:%M:%S")
    for week in range(8):
        chance = ANTENATAL_RATE[district] + 0.02 * (7 - week)
        for _ in range(5):
            count += 1
            when = now - timedelta(days=week * 7 + random.randint(0, 6), hours=random.randint(1, 23))
            full_name, community = demo_person(names, district, "female")
            patient_id = conn.execute(
                "INSERT INTO patients (ref, chv_id, full_name, age, sex, pregnant, community, district, consent, created_at) "
                "VALUES (?, ?, ?, ?, 'female', 1, ?, ?, 1, ?) RETURNING id",
                (new_patient_ref(conn), chv_id, full_name, random.randint(16, 42), community, district, stamp(when)),
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


# Demo equipment: facility name start -> {item: (working, broken)}. Other devices get (2, 0).
DEMO_EQUIPMENT = {"Demo Clinic Tamale": {"thermometer": (1, 3)}, "Demo Clinic Wa": {"bp_monitor": (0, 2)},
                  "Demo Clinic Bolgatanga": {"weighing_scale": (1, 1)}, "Demo Clinic Kumasi": {}, "Demo Clinic Cape": {}}


def create_demo_equipment(conn):
    """Only once per facility, so a nurse's own counts are never overwritten."""
    created = 0
    for facility_start, amounts in DEMO_EQUIPMENT.items():
        row = conn.execute("SELECT DISTINCT facility FROM users WHERE facility LIKE ?", (facility_start + "%",)).fetchone()
        if not row or conn.execute("SELECT 1 FROM equipment WHERE facility = ?", (row["facility"],)).fetchone():
            continue
        for item in ["bp_monitor", "thermometer", "weighing_scale"]:
            working, broken = amounts.get(item, (2, 0))
            conn.execute("INSERT INTO equipment (facility, item, working, broken, updated_at) VALUES (?, ?, ?, ?, ?)",
                         (row["facility"], item, working, broken, now_text()))
        created += 1
    return created


def create_demo_training(conn):
    """Fake certificates so the GHS list shows each status. Only once. The approvals are demo approvals."""
    if conn.execute("SELECT 1 FROM certificates WHERE code LIKE 'DEMO-%'").fetchone():
        return
    doctor = conn.execute("SELECT id FROM users WHERE username = 'doctor1'").fetchone()
    if not doctor:
        return
    for module in TRAINING_MODULES:
        conn.execute("INSERT INTO training_reviews (module, reviewed_by, reviewed_at) VALUES (?, ?, ?) "
                     "ON CONFLICT (module) DO NOTHING", (module, doctor["id"], now_text()))
    # username, module, days until expiry, revoke reason
    examples = [("chv2", "danger_signs", 300, None), ("chv2", "malaria_testing", 12, None),
                ("nurse2", "privacy_consent", -20, None), ("pharm1", "danger_signs", 200, "Demo: issued in error")]
    now = datetime.now(timezone.utc)
    for number, (username, module, days, reason) in enumerate(examples):
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            continue
        expires = now + timedelta(days=days)
        issued = expires - timedelta(days=365)
        conn.execute(
            "INSERT INTO certificates (code, user_id, module, source, issued_at, expires_at, revoked_at, revoke_reason) "
            "VALUES (?, ?, ?, 'quiz', ?, ?, ?, ?)",
            (f"DEMO-{number}", user["id"], module, issued.strftime("%Y-%m-%d %H:%M:%S"), expires.strftime("%Y-%m-%d %H:%M:%S"),
             now_text() if reason else None, reason),
        )


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
    create_demo_equipment(conn)
    create_demo_training(conn)
    conn.commit()
    print(f"Demo stock created for {pharmacies} pharmacies." if pharmacies else "Demo stock already exists. Nothing to do.")
    conn.close()
