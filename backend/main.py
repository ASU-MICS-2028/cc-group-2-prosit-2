import os
import secrets

import requests
from dotenv import load_dotenv

# Load .env BEFORE importing auth, so JWT_SECRET is available
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_password, create_token, get_current_user, require_role
from database import get_db, init_db, log_access
from model import predict_risk
from schemas import LoginRequest, PatientCreate, PatientData, VitalsIn

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


@app.get("/patients")
def list_patients(user=Depends(require_role("chv"))):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.ref, p.full_name, p.age, p.community, p.created_at,
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

    conn = get_db()
    ref = "HC-" + secrets.token_hex(3).upper()  # random, not derived from the name
    cur = conn.execute(
        "INSERT INTO patients (ref, chv_id, full_name, age, community, consent) VALUES (?, ?, ?, ?, ?, 1)",
        (ref, user["id"], body.full_name.strip(), body.age, body.community.strip()),
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
    observations = conn.execute(
        "SELECT * FROM observations WHERE patient_id = ? ORDER BY id DESC", (patient_id,)
    ).fetchall()
    log_access(conn, user["id"], "view_patient", patient["ref"])
    conn.commit()
    conn.close()
    return {"patient": dict(patient), "observations": [dict(o) for o in observations]}


@app.post("/patients/{patient_id}/assess")
def assess(patient_id: int, vitals: VitalsIn, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)

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
          vitals.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if vitals.recorded_at else None))
    log_access(conn, user["id"], "sync_offline_check" if vitals.recorded_at else "assess_patient", patient["ref"])
    conn.commit()
    observation = conn.execute("SELECT * FROM observations WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    advice = ("Refer immediately to the nearest health facility." if risk_level == "HIGH"
              else "Monitor closely and schedule a follow-up visit." if risk_level == "MEDIUM"
              else "Continue routine antenatal care.")
    return {"observation": dict(observation), "advice": advice}


@app.post("/observations/{observation_id}/referral")
def send_referral(observation_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    obs = conn.execute("SELECT * FROM observations WHERE id = ?", (observation_id,)).fetchone()
    if not obs:
        conn.close()
        raise HTTPException(status_code=404, detail="Observation not found")
    patient = get_own_patient(conn, obs["patient_id"], user)
    if obs["risk_level"] != "HIGH":
        conn.close()
        raise HTTPException(status_code=400, detail="Referral SMS is only for HIGH risk")

    phone = (user["facility_phone"] or "").strip()
    if phone.startswith("0"):
        phone = "233" + phone[1:]

    # No patient name in the SMS: reference only (data minimisation)
    message = f"""HealthConnect Referral
Ref: {patient['ref']}
Age: {patient['age']}
Risk: {obs['risk_level']}
CHV: {user['full_name']}
Please prepare to receive this patient."""

    try:
        response = requests.get(
            "https://sms.arkesel.com/sms/api",
            params={
                "action": "send-sms",
                "api_key": os.getenv("ARKESEL_API_KEY"),
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
    success = code == "ok"
    if success:
        conn.execute("UPDATE observations SET referral_sent = 1 WHERE id = ?", (observation_id,))
    log_access(conn, user["id"], "send_referral" if success else "send_referral_failed", patient["ref"])
    conn.commit()
    conn.close()
    return {"success": success}
