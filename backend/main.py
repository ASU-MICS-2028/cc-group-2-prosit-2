import os
import secrets

import requests
from dotenv import load_dotenv

# Load .env BEFORE importing auth, so JWT_SECRET is available
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_password, create_token, get_current_user, require_role, offline_key_for
from database import get_db, init_db, log_access
from general_model import assess_general, advice_for
from model import predict_risk
from priority import priority
from schemas import (LoginRequest, PatientCreate, PatientData, VitalsIn, ReferralUpdate, VisitIn,
                     PregnancyUpdate, ReferralCreate, EscalateIn)

# Only report whether the key exists; never print the secret itself
if not os.getenv("ARKESEL_API_KEY"):
    print("WARNING: ARKESEL_API_KEY is not set; referral SMS will fail")

init_db()

app = FastAPI(title="HealthConnect Ghana API")

# Only our own frontend may call this API from a browser
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def root():
    return {"message": "HealthConnect Ghana API is running"}


# ---------- Login ----------

@app.post("/auth/login")
def login(body: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()

    # Same error for wrong username or wrong password: don't reveal which
    if not user or not verify_password(body.password, user["password_hash"]):
        log_access(conn, None, "login_failed", body.username)
        conn.commit()
        conn.close()
        raise HTTPException(status_code=401, detail="Wrong username or password")

    log_access(conn, user["id"], "login")
    conn.commit()
    conn.close()
    return {
        "token": create_token(user),
        "offline_key": offline_key_for(user["id"]),  # encrypts checks queued on the phone
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
            "facility": user["facility"],
        },
    }


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


# ---------- Patients (CHV only, own patients only) ----------

def get_own_patient(conn, patient_id, user):
    patient = conn.execute(
        "SELECT * FROM patients WHERE id = ? AND chv_id = ?", (patient_id, user["id"])
    ).fetchone()
    if not patient:
        # Record the blocked attempt, then answer 404 (not 403) so a CHV
        # can't even learn that another CHV's patient exists
        log_access(conn, user["id"], "access_denied", f"patient:{patient_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def can_be_pregnant(sex, age):
    return sex == "female" and age >= 10


@app.get("/patients")
def list_patients(user=Depends(require_role("chv"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.ref, p.full_name, p.age, p.sex, p.pregnant, p.community, p.created_at,
               (SELECT risk_level FROM observations o
                 WHERE o.patient_id = p.id ORDER BY o.id DESC LIMIT 1) AS latest_risk
        FROM patients p
        WHERE p.chv_id = ?
        ORDER BY p.id DESC
    """, (user["id"],)).fetchall()
    log_access(conn, user["id"], "list_patients")
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/patients")
def create_patient(body: PatientCreate, user=Depends(require_role("chv"))):
    # Act 843: no consent, no record
    if not body.consent:
        raise HTTPException(status_code=400, detail="Patient consent is required")
    if body.pregnant and not can_be_pregnant(body.sex, body.age):
        raise HTTPException(status_code=400, detail="Only female patients aged 10 or over can be marked pregnant")

    conn = get_db()
    ref = "HC-" + secrets.token_hex(3).upper()  # random, not derived from the name
    cur = conn.execute(
        "INSERT INTO patients (ref, chv_id, full_name, age, sex, pregnant, community, consent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (ref, user["id"], body.full_name.strip(), body.age, body.sex, int(body.pregnant), body.community.strip()),
    )
    log_access(conn, user["id"], "create_patient", ref)
    conn.commit()
    patient = conn.execute("SELECT * FROM patients WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(patient)


@app.get("/patients/{patient_id}")
def get_patient(patient_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)
    # Each check comes with its referral chain: health centre (r), then hospital if escalated (e)
    observations = conn.execute("""
        SELECT o.*,
               r.status AS referral_status, r.outcome AS referral_outcome, r.reason AS referral_reason,
               e.facility AS escalated_to, e.status AS escalated_status, e.outcome AS escalated_outcome
        FROM observations o
        LEFT JOIN referrals r ON r.observation_id = o.id AND r.parent_id IS NULL
        LEFT JOIN referrals e ON e.parent_id = r.id
        WHERE o.patient_id = ?
        ORDER BY o.id DESC
    """, (patient_id,)).fetchall()
    log_access(conn, user["id"], "view_patient", patient["ref"])
    conn.commit()
    conn.close()
    return {"patient": dict(patient), "observations": [dict(o) for o in observations]}


@app.post("/patients/{patient_id}/pregnancy")
def set_pregnancy(patient_id: int, body: PregnancyUpdate, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)
    if body.pregnant and not can_be_pregnant(patient["sex"], patient["age"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Only female patients aged 10 or over can be marked pregnant")
    conn.execute("UPDATE patients SET pregnant = ? WHERE id = ?", (int(body.pregnant), patient_id))
    log_access(conn, user["id"], "set_pregnancy", patient["ref"])
    conn.commit()
    conn.close()
    return {"success": True}


def to_db_time(recorded_at):
    # Offline checks carry the time they were really done; online ones use "now"
    return recorded_at.strftime("%Y-%m-%d %H:%M:%S") if recorded_at else None


@app.post("/patients/{patient_id}/visit")
def general_visit(patient_id: int, visit: VisitIn, user=Depends(require_role("chv"))):
    vitals = [visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate]
    if not visit.symptoms and all(v is None for v in vitals):
        raise HTTPException(status_code=400, detail="Enter at least one symptom or vital sign")
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)

    risk_level, conditions = assess_general(
        visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate, visit.symptoms
    )
    cur = conn.execute("""
        INSERT INTO observations (patient_id, recorded_by, visit_type, body_temp, systolic_bp, diastolic_bp,
            heart_rate, symptoms, possible_conditions, notes, risk_level, created_at)
        VALUES (?, ?, 'general', ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))
    """, (patient_id, user["id"], visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate,
          ",".join(visit.symptoms), ",".join(conditions), visit.notes.strip(), risk_level,
          to_db_time(visit.recorded_at)))
    log_access(conn, user["id"], "sync_offline_visit" if visit.recorded_at else "general_visit", patient["ref"])
    conn.commit()
    observation = conn.execute("SELECT * FROM observations WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return {"observation": dict(observation), "advice": advice_for(risk_level)}


@app.post("/patients/{patient_id}/assess")
def assess(patient_id: int, vitals: VitalsIn, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)
    if not (patient["sex"] == "female" and patient["pregnant"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Antenatal checks are only for pregnant patients")

    # The server always re-scores, even for offline checks: its result is the official one
    risk_score, risk_level = predict_risk(PatientData(age=patient["age"], **vitals.model_dump()))

    cur = conn.execute("""
        INSERT INTO observations (patient_id, recorded_by, gestational_age, systolic_bp, diastolic_bp,
            weight, hemoglobin, body_temp, heart_rate, previous_complications, risk_score, risk_level,
            created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))
    """, (patient_id, user["id"], vitals.gestational_age, vitals.systolic_bp, vitals.diastolic_bp,
          vitals.weight, vitals.hemoglobin, vitals.body_temp, vitals.heart_rate,
          int(vitals.previous_complications), risk_score, risk_level,
          to_db_time(vitals.recorded_at)))
    log_access(conn, user["id"], "sync_offline_check" if vitals.recorded_at else "assess_patient", patient["ref"])
    conn.commit()
    observation = conn.execute("SELECT * FROM observations WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    advice = ("Refer immediately to the nearest health facility." if risk_level == "HIGH"
              else "Monitor closely and schedule a follow-up visit." if risk_level == "MEDIUM"
              else "Continue routine antenatal care.")
    return {"observation": dict(observation), "advice": advice}


@app.post("/observations/{observation_id}/referral")
def send_referral(observation_id: int, body: ReferralCreate | None = None, user=Depends(require_role("chv"))):
    conn = get_db()
    obs = conn.execute("SELECT * FROM observations WHERE id = ?", (observation_id,)).fetchone()
    if not obs:
        conn.close()
        raise HTTPException(status_code=404, detail="Observation not found")
    patient = get_own_patient(conn, obs["patient_id"], user)
    reason = body.reason.strip() if body else ""  # body is optional: HIGH needs no reason

    # HIGH: always allowed. MEDIUM: allowed if the CHV explains why. LOW: no.
    if obs["risk_level"] == "LOW":
        conn.close()
        raise HTTPException(status_code=400, detail="LOW risk checks cannot be referred")
    if obs["risk_level"] == "MEDIUM" and not reason:
        conn.close()
        raise HTTPException(status_code=400, detail="Please give a reason for referring a MEDIUM risk patient")
    if obs["referral_sent"]:
        conn.close()
        raise HTTPException(status_code=400, detail="This check was already referred")

    # 1. The referral record: this is what the facility's inbox reads
    conn.execute(
        "INSERT INTO referrals (observation_id, patient_id, chv_id, referred_by, facility, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (observation_id, patient["id"], user["id"], user["id"], user["facility"], reason or None),
    )
    conn.execute("UPDATE observations SET referral_sent = 1 WHERE id = ?", (observation_id,))

    # 2. The SMS: only a heads-up. If it fails, the referral still exists.
    sms_sent = send_referral_sms(user, patient, obs)
    log_access(conn, user["id"], "create_referral", f"{patient['ref']} sms={'ok' if sms_sent else 'failed'}")
    conn.commit()
    conn.close()
    return {"success": True, "sms_sent": sms_sent}


def send_referral_sms(user, patient, obs):
    api_key = os.getenv("ARKESEL_API_KEY")
    if not api_key:
        return False

    phone = (user["facility_phone"] or "").strip()
    if phone.startswith("0"):
        phone = "233" + phone[1:]

    # No patient name in the SMS: reference only (data minimisation)
    visit = "Antenatal" if obs["visit_type"] == "antenatal" else "General"
    watch = f"\nCheck for: {obs['possible_conditions'].replace(',', ', ')}" if obs["possible_conditions"] else ""
    message = f"""HealthConnect Referral
Ref: {patient['ref']}
Age: {patient['age']} ({patient['sex'] or '-'})
Visit: {visit}
Risk: {obs['risk_level']}{watch}
CHV: {user['full_name']}
Please prepare to receive this patient."""

    try:
        response = requests.get(
            "https://sms.arkesel.com/sms/api",
            params={
                "action": "send-sms",
                "api_key": api_key,
                "to": phone,
                # Sender IDs must be registered with Arkesel before they work
                "from": os.getenv("ARKESEL_SENDER", "SafeArriv"),
                "sms": message,
            },
            timeout=15,
        )
        code = response.json().get("code")
    except (requests.RequestException, ValueError):
        code = "network_error"

    # Log only the status code; the full reply has account details we don't need
    print("ARKESEL STATUS:", code)
    return code == "ok"


# ---------- Referral inbox (nurse = health centre, doctor = hospital; own facility only) ----------

def get_facility_referral(conn, referral_id, user):
    referral = conn.execute(
        "SELECT r.*, p.ref FROM referrals r JOIN patients p ON p.id = r.patient_id "
        "WHERE r.id = ? AND r.facility = ?",
        (referral_id, user["facility"]),
    ).fetchone()
    if not referral:
        # Another facility's referral: record the attempt, reveal nothing
        log_access(conn, user["id"], "access_denied", f"referral:{referral_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


@app.get("/referrals")
def list_referrals(user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT r.id, r.status, r.outcome, r.reason, r.parent_id, r.created_at, r.updated_at,
               p.ref, p.full_name, p.age, p.community,
               p.sex, o.visit_type, o.symptoms, o.possible_conditions, o.body_temp, o.heart_rate,
               o.risk_level, o.systolic_bp, o.diastolic_bp, o.hemoglobin, o.gestational_age,
               o.previous_complications, o.notes,
               u.full_name AS chv_name,
               rb.full_name AS referred_by_name, rb.role AS referred_by_role,
               parent.facility AS from_facility,
               esc.facility AS escalated_to
        FROM referrals r
        JOIN patients p ON p.id = r.patient_id
        JOIN observations o ON o.id = r.observation_id
        JOIN users u ON u.id = r.chv_id
        LEFT JOIN users rb ON rb.id = COALESCE(r.referred_by, r.chv_id)
        LEFT JOIN referrals parent ON parent.id = r.parent_id
        LEFT JOIN referrals esc ON esc.parent_id = r.id
        WHERE r.facility = ?
    """, (user["facility"],)).fetchall()
    log_access(conn, user["id"], "list_referrals", user["facility"])
    conn.commit()
    conn.close()

    # Add each referral's priority (risk + danger signs + waiting time), then sort:
    # open cases first, highest score first, and on a tie whoever has waited longest
    referrals = [{**dict(r), **priority(r)} for r in rows]
    status_order = {"pending": 0, "arrived": 1, "completed": 2}
    referrals.sort(key=lambda r: (status_order[r["status"]], -r["priority_score"], r["created_at"]))
    return referrals


@app.post("/referrals/{referral_id}/status")
def update_referral(referral_id: int, body: ReferralUpdate, user=Depends(require_role("nurse", "doctor"))):
    # Team decision: every patient must be seen by a doctor, so only doctors close a case.
    # A nurse finishes her part by referring the patient on (see escalate_referral).
    if body.status == "completed" and user["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Only a doctor can close a case. Refer the patient to a doctor.")
    conn = get_db()
    referral = get_facility_referral(conn, referral_id, user)
    if body.status == "completed" and not (body.outcome or "").strip():
        conn.close()
        raise HTTPException(status_code=400, detail="Please record the outcome")

    conn.execute(
        "UPDATE referrals SET status = ?, outcome = ?, updated_by = ?, updated_at = datetime('now') WHERE id = ?",
        (body.status, (body.outcome or "").strip() or referral["outcome"], user["id"], referral_id),
    )
    log_access(conn, user["id"], f"referral_{body.status}", referral["ref"])
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/facilities/hospitals")
def list_hospitals(user=Depends(require_role("nurse"))):
    # Facilities that have at least one doctor = places a nurse can escalate to
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT facility FROM users WHERE role = 'doctor' AND facility IS NOT NULL ORDER BY facility"
    ).fetchall()
    conn.close()
    return [r["facility"] for r in rows]


@app.post("/referrals/{referral_id}/escalate")
def escalate_referral(referral_id: int, body: EscalateIn, user=Depends(require_role("nurse"))):
    conn = get_db()
    referral = get_facility_referral(conn, referral_id, user)
    if referral["status"] != "arrived":
        conn.close()
        raise HTTPException(status_code=400, detail="Mark the patient as arrived before referring onward")
    doctor_here = conn.execute(
        "SELECT 1 FROM users WHERE role = 'doctor' AND facility = ?", (body.facility,)
    ).fetchone()
    if not doctor_here:
        conn.close()
        raise HTTPException(status_code=400, detail="Choose a hospital from the list")

    reason = body.reason.strip()
    # New referral to the hospital, linked to this one...
    conn.execute(
        "INSERT INTO referrals (observation_id, patient_id, chv_id, referred_by, parent_id, facility, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (referral["observation_id"], referral["patient_id"], referral["chv_id"], user["id"],
         referral_id, body.facility, reason),
    )
    # ...and this one is closed, recording the nurse's treatment and where the patient went
    conn.execute(
        "UPDATE referrals SET status = 'completed', outcome = ?, updated_by = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (f"Referred on to {body.facility}: {reason}", user["id"], referral_id),
    )
    log_access(conn, user["id"], "escalate_referral", f"{referral['ref']} -> {body.facility}")
    conn.commit()
    conn.close()
    return {"success": True}
