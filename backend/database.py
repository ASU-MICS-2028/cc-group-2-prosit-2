import sqlite3

DB_PATH = "healthconnect.db"


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
        facility_phone TEXT
    );

    -- FHIR Patient. Registered by a CHV, only after consent (Act 843)
    CREATE TABLE IF NOT EXISTS patients (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ref        TEXT UNIQUE NOT NULL,
        chv_id     INTEGER NOT NULL REFERENCES users(id),
        full_name  TEXT NOT NULL,
        age        INTEGER NOT NULL,
        community  TEXT,
        consent    INTEGER NOT NULL CHECK (consent = 1),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- FHIR Observation. One row per vitals check + its risk result
    CREATE TABLE IF NOT EXISTS observations (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id             INTEGER NOT NULL REFERENCES patients(id),
        recorded_by            INTEGER NOT NULL REFERENCES users(id),
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

    -- FHIR ServiceRequest. A CHV asks a facility to receive a HIGH-risk patient
    CREATE TABLE IF NOT EXISTS referrals (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        observation_id INTEGER UNIQUE NOT NULL REFERENCES observations(id),
        patient_id     INTEGER NOT NULL REFERENCES patients(id),
        chv_id         INTEGER NOT NULL REFERENCES users(id),
        facility       TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','arrived','completed')),
        outcome        TEXT,
        updated_by     INTEGER REFERENCES users(id),
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT
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
    conn.commit()
    conn.close()


def log_access(conn, user_id, action, resource=None):
    conn.execute(
        "INSERT INTO access_log (user_id, action, resource) VALUES (?, ?, ?)",
        (user_id, action, resource),
    )
