import sqlite3

DB_PATH = "healthconnect.db"

# FHIR ServiceRequest. CHV -> health centre, or nurse -> hospital (parent_id links the chain)
REFERRALS_TABLE = """
CREATE TABLE IF NOT EXISTS referrals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    patient_id     INTEGER NOT NULL REFERENCES patients(id),
    chv_id         INTEGER NOT NULL REFERENCES users(id),   -- CHV who owns the patient
    referred_by    INTEGER REFERENCES users(id),            -- who made this referral (CHV or nurse)
    parent_id      INTEGER REFERENCES referrals(id),        -- set when a nurse escalates
    facility       TEXT NOT NULL,                           -- where the patient is sent
    reason         TEXT,
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','arrived','completed')),
    outcome        TEXT,
    updated_by     INTEGER REFERENCES users(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT
)
"""


def get_db():
    # One connection per request; rows behave like dicts (row["name"])
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    -- App accounts. Roles: chv, nurse, doctor, ghs, admin (RBAC)
    CREATE TABLE IF NOT EXISTS users (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        username       TEXT UNIQUE NOT NULL,
        password_hash  TEXT NOT NULL,
        role           TEXT NOT NULL CHECK (role IN ('chv','nurse','doctor','ghs','admin')),
        full_name      TEXT NOT NULL,
        facility       TEXT,
        facility_phone TEXT,
        district       TEXT   -- for surveillance totals (GHS sees districts, never names)
    );

    -- FHIR Patient. Registered by a CHV, only after consent (Act 843)
    CREATE TABLE IF NOT EXISTS patients (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ref        TEXT UNIQUE NOT NULL,
        chv_id     INTEGER NOT NULL REFERENCES users(id),
        full_name  TEXT NOT NULL,
        age        INTEGER NOT NULL,
        sex        TEXT CHECK (sex IN ('female','male')),
        pregnant   INTEGER NOT NULL DEFAULT 0,
        phone      TEXT,      -- optional; used ONLY for appointment reminders
        community  TEXT,
        district   TEXT,      -- copied from the registering CHV
        consent    INTEGER NOT NULL CHECK (consent = 1),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- FHIR Observation. One row per check: 'antenatal' or 'general' visit
    CREATE TABLE IF NOT EXISTS observations (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id             INTEGER NOT NULL REFERENCES patients(id),
        recorded_by            INTEGER NOT NULL REFERENCES users(id),
        visit_type             TEXT NOT NULL DEFAULT 'antenatal' CHECK (visit_type IN ('antenatal','general')),
        symptoms               TEXT,      -- general visit: comma-separated symptom codes
        possible_conditions    TEXT,      -- general visit: e.g. 'malaria,meningitis' (not a diagnosis)
        notes                  TEXT,
        gestational_age        INTEGER,
        systolic_bp            INTEGER,
        diastolic_bp           INTEGER,
        weight                 REAL,
        hemoglobin             REAL,
        body_temp              REAL,
        heart_rate             INTEGER,
        previous_complications INTEGER,
        risk_score             REAL,
        risk_level             TEXT,
        referral_sent          INTEGER NOT NULL DEFAULT 0,
        created_at             TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- FHIR Appointment. Follow-up booked by a nurse/doctor; SMS reminder ~24h before
    CREATE TABLE IF NOT EXISTS appointments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id      INTEGER NOT NULL REFERENCES patients(id),
        referral_id     INTEGER NOT NULL REFERENCES referrals(id),
        booked_by       INTEGER NOT NULL REFERENCES users(id),
        facility        TEXT NOT NULL,
        scheduled_at    TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM' (Ghana time = UTC)
        reason          TEXT,
        status          TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked','attended','missed','cancelled')),
        reminder_status TEXT,            -- NULL = not tried yet, then 'sent' / 'failed' / 'no_phone'
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- FHIR AuditEvent. Who did what to which record, and when
    CREATE TABLE IF NOT EXISTS access_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER REFERENCES users(id),
        action    TEXT NOT NULL,
        resource  TEXT,
        timestamp TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)
    conn.execute(REFERRALS_TABLE)
    migrate(conn)
    conn.commit()
    conn.close()


def add_column_if_missing(conn, table, column, definition):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column in columns:
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    return True


def migrate(conn):
    # Databases created before general visits existed get the new columns.
    # Their patients were all antenatal, so they are marked female + pregnant.
    if add_column_if_missing(conn, "patients", "sex", "TEXT CHECK (sex IN ('female','male'))"):
        add_column_if_missing(conn, "patients", "pregnant", "INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE patients SET sex = 'female', pregnant = 1")
    add_column_if_missing(conn, "patients", "phone", "TEXT")
    add_column_if_missing(conn, "users", "district", "TEXT")
    if add_column_if_missing(conn, "patients", "district", "TEXT"):
        # Existing patients take their CHV's district
        conn.execute("UPDATE patients SET district = (SELECT district FROM users WHERE users.id = patients.chv_id)")
    add_column_if_missing(conn, "observations", "visit_type", "TEXT NOT NULL DEFAULT 'antenatal'")
    add_column_if_missing(conn, "observations", "symptoms", "TEXT")
    add_column_if_missing(conn, "observations", "possible_conditions", "TEXT")
    add_column_if_missing(conn, "observations", "notes", "TEXT")

    # Old referrals table allowed only one referral per check (UNIQUE observation_id).
    # Escalation needs two, so rebuild the table and copy the rows across.
    old_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'referrals'").fetchone()["sql"]
    if "observation_id INTEGER UNIQUE" in old_sql:
        conn.execute("ALTER TABLE referrals RENAME TO referrals_old")
        conn.execute(REFERRALS_TABLE)
        conn.execute("""
            INSERT INTO referrals (id, observation_id, patient_id, chv_id, referred_by, facility,
                                   status, outcome, updated_by, created_at, updated_at)
            SELECT id, observation_id, patient_id, chv_id, chv_id, facility,
                   status, outcome, updated_by, created_at, updated_at
            FROM referrals_old
        """)
        conn.execute("DROP TABLE referrals_old")


def log_access(conn, user_id, action, resource=None):
    conn.execute(
        "INSERT INTO access_log (user_id, action, resource) VALUES (?, ?, ?)",
        (user_id, action, resource),
    )
