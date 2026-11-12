import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

# Load settings (.env locally, AWS Secrets Manager in the cloud) BEFORE importing auth,
# so JWT_SECRET is available
import config  # noqa: F401

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from admin import router as admin_router
from pharmacy import router as pharmacy_router
from monitoring import router as monitoring_router
from calls import router as calls_router
from surveillance import router as surveillance_router
from impact import router as impact_router
from insurance import router as insurance_router
from healers import router as healers_router
from immunisation import router as immunisation_router
from survey import router as survey_router
from community_alerts import router as community_alerts_router
from passkeys import router as passkeys_router
from photos import router as photos_router
from scans import router as scans_router
from eprescription import router as eprescription_router
from e2e import router as e2e_router
from tts import router as tts_router
from equipment import router as equipment_router
from education import router as education_router
from training import router as training_router
from fees import router as fees_router
from facility import router as facility_router
from auth import (verify_password, hash_password, create_token, login_response, get_user_allow_temp_password, require_role,
                  offline_key_for)
from database import get_db, init_db, log_access, new_patient_ref, now_text
from general_model import assess_general, advice_for
from model import predict_risk
from escalation import escalate_overdue, run_auto_escalation
from priority import priority
from reminders import REMIND_HOURS_BEFORE, appointment_message, send_due_reminders
from schemas import (LoginRequest, PasswordChange, PatientCreate, PatientData, VitalsIn, ReferralUpdate, VisitIn,
                     PregnancyUpdate, ReferralCreate, EscalateIn, AppointmentCreate, AppointmentStatus,
                     ReminderPreference)
from seed_demo_data import keep_demo_data_current
from sms import send_sms

# Only report whether the key exists; never print the secret itself
if not os.getenv("ARKESEL_API_KEY"):
    print("WARNING: ARKESEL_API_KEY is not set; referral and reminder SMS will fail")

init_db()

# In the cloud an AWS Lambda function sends reminders (lambda_handler.py), so the
# servers set REMINDERS_IN_PROCESS=off. On a laptop the API sends them itself.
REMINDERS_IN_PROCESS = os.getenv("REMINDERS_IN_PROCESS", "on").lower() != "off"
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() == "on"


async def background_loop():
    # At start-up, then every 10 minutes
    while True:
        try:
            if REMINDERS_IN_PROCESS:
                # Send reminders for appointments in the next 24 hours
                await asyncio.to_thread(send_due_reminders)
            # Urgent referrals nobody has seen in 30 minutes go to a hospital
            await asyncio.to_thread(run_auto_escalation)
            # Demo only (DEMO_MODE=on): keep the fake surveillance data dated "now"
            await asyncio.to_thread(keep_demo_data_current)
        except Exception as err:  # keep the loop alive whatever happens
            print("BACKGROUND JOB ERROR:", type(err).__name__)
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(background_loop())  # auto-escalation always runs
    yield
    if task:
        task.cancel()  # stops with the server


app = FastAPI(title="HealthConnect Ghana API", lifespan=lifespan)
app.include_router(calls_router)  # video consult signalling (calls.py)
app.include_router(surveillance_router)  # GHS dashboard (surveillance.py)
app.include_router(impact_router)  # GHS: SDG 3 progress (impact.py)
app.include_router(insurance_router)  # community insurance, simulated mobile money (insurance.py)
app.include_router(healers_router)  # traditional healers working with CHVs (healers.py)
app.include_router(immunisation_router)  # child immunisation tracking (immunisation.py)
app.include_router(survey_router)  # household health surveys (survey.py)
app.include_router(community_alerts_router)  # GHS health alert SMS to a district
app.include_router(passkeys_router)  # fingerprint / face / PIN sign-in (passkeys.py)
app.include_router(photos_router)  # clinical photos and image sharing (photos.py)
app.include_router(scans_router)  # DICOM medical scans: X-ray, CT, ultrasound (scans.py)
app.include_router(eprescription_router)  # prescriptions any pharmacy can check and dispense once
app.include_router(e2e_router)  # end-to-end encryption keys for notes and photos (e2e.py)
app.include_router(tts_router)  # spoken lessons in Twi, Ewe, English (tts.py, Abena AI)
app.include_router(equipment_router)  # medical equipment at each facility (equipment.py)
app.include_router(education_router)  # health education lessons (education.py)
app.include_router(training_router)  # health worker training and certificates (training.py)
app.include_router(fees_router)  # consultation and training fees (fees.py)
app.include_router(facility_router)  # health centre self-management (facility.py)
app.include_router(admin_router)  # account management (admin.py)
app.include_router(pharmacy_router)  # drug stock and e-prescriptions (pharmacy.py)
app.include_router(monitoring_router)  # admin: CloudWatch alarm states (monitoring.py)

# Only our own frontend may call this API from a browser
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # PUT: save my encryption key; DELETE: remove a photo, vaccine record or fingerprint
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def no_store(request: Request, call_next):
    # Patient data must never be kept by CloudFront, a proxy or the browser's HTTP cache
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/")
def root():
    return {"message": "HealthConnect Ghana API is running"}


@app.get("/health")
def health():
    # The load balancer calls this every 15 s. Healthy = the API can reach its database.
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as err:
        print("HEALTH CHECK FAILED:", type(err).__name__)
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ok"}


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

    if not user["active"]:
        log_access(conn, user["id"], "login_disabled")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=403, detail="This account is disabled. Contact your system admin.")

    log_access(conn, user["id"], "login")
    conn.commit()
    conn.close()
    return login_response(user)


@app.get("/auth/me")
def me(user=Depends(get_user_allow_temp_password)):
    return user


@app.post("/auth/change-password")
def change_password(body: PasswordChange, user=Depends(get_user_allow_temp_password)):
    new = body.new_password
    if not (any(c.isalpha() for c in new) and any(c.isdigit() for c in new)):
        raise HTTPException(status_code=422, detail="Use at least one letter and one number")
    if user["username"].lower() in new.lower():
        raise HTTPException(status_code=422, detail="The password must not contain your username")

    conn = get_db()
    current_hash = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()["password_hash"]
    if not verify_password(body.current_password, current_hash):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password is wrong")
    if verify_password(new, current_hash):
        conn.close()
        raise HTTPException(status_code=422, detail="Choose a password different from the current one")

    conn.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                 (hash_password(new), user["id"]))
    log_access(conn, user["id"], "change_password")
    conn.commit()
    conn.close()
    return {"success": True}


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
    ref = new_patient_ref(conn)
    patient = conn.execute(
        "INSERT INTO patients (ref, chv_id, full_name, age, sex, pregnant, phone, community, district, consent, "
        "reminder_method, language, health_alerts, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?) RETURNING *",
        (ref, user["id"], body.full_name.strip(), body.age, body.sex, int(body.pregnant),
         body.phone.strip() or None, body.community.strip(), user["district"], body.reminder_method,
         body.language, int(body.health_alerts), now_text()),
    ).fetchone()
    log_access(conn, user["id"], "create_patient", ref)
    conn.commit()
    conn.close()
    return dict(patient)


@app.post("/patients/{patient_id}/reminder-preference")
def set_reminder_preference(patient_id: int, body: ReminderPreference, user=Depends(require_role("chv"))):
    # How this patient wants to be reminded: SMS, or the CHV in person (for patients who cannot read)
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)
    conn.execute("UPDATE patients SET reminder_method = ?, language = ?, health_alerts = ? WHERE id = ?",
                 (body.reminder_method, body.language, int(body.health_alerts), patient_id))
    log_access(conn, user["id"], "set_reminder_preference", f"{patient['ref']} {body.reminder_method}")
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/chv/reminders")
def chv_reminders(user=Depends(require_role("chv"))):
    """The CHV's own patients with an appointment in the next 7 days whom an SMS will not reach:
    they chose a CHV visit, have no phone, or their SMS failed."""
    now = datetime.now(timezone.utc)
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id, a.facility, a.scheduled_at, a.reason, a.reminder_status,
               p.id AS patient_id, p.ref, p.full_name, p.community, p.reminder_method, p.language
        FROM appointments a JOIN patients p ON p.id = a.patient_id
        WHERE p.chv_id = ? AND a.status = 'booked' AND a.scheduled_at > ? AND a.scheduled_at <= ?
          AND (p.reminder_method != 'sms' OR p.phone IS NULL OR a.reminder_status IN ('failed', 'no_phone', 'chv'))
        ORDER BY a.scheduled_at
    """, (user["id"], now.strftime("%Y-%m-%d %H:%M"), (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"))).fetchall()
    log_access(conn, user["id"], "list_chv_reminders")
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/patients/{patient_id}")
def get_patient(patient_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)
    # Each check comes with its referral chain: health centre (r), then hospital if escalated (e)
    observations = conn.execute("""
        SELECT o.*,
               r.id AS referral_id, r.status AS referral_status, r.outcome AS referral_outcome,
               r.reason AS referral_reason,
               e.facility AS escalated_to, e.status AS escalated_status, e.outcome AS escalated_outcome
        FROM observations o
        LEFT JOIN referrals r ON r.observation_id = o.id AND r.parent_id IS NULL
        LEFT JOIN referrals e ON e.parent_id = r.id
        WHERE o.patient_id = ?
        ORDER BY o.id DESC
    """, (patient_id,)).fetchall()
    # Upcoming appointments, so the CHV can remind patients who have no phone
    appointments = conn.execute(
        "SELECT id, facility, scheduled_at, reason, status, reminder_status FROM appointments "
        "WHERE patient_id = ? AND status = 'booked' ORDER BY scheduled_at",
        (patient_id,),
    ).fetchall()
    log_access(conn, user["id"], "view_patient", patient["ref"])
    conn.commit()
    conn.close()
    return {"patient": dict(patient), "observations": [dict(o) for o in observations],
            "appointments": [dict(a) for a in appointments]}


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
    return recorded_at.strftime("%Y-%m-%d %H:%M:%S") if recorded_at else now_text()


@app.post("/patients/{patient_id}/visit")
def general_visit(patient_id: int, visit: VisitIn, user=Depends(require_role("chv"))):
    vitals = [visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate, visit.weight, visit.height]
    if not visit.symptoms and all(v is None for v in vitals):
        raise HTTPException(status_code=400, detail="Enter at least one symptom or vital sign")
    conn = get_db()
    patient = get_own_patient(conn, patient_id, user)

    risk_level, conditions = assess_general(
        visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate, visit.symptoms
    )
    observation = conn.execute("""
        INSERT INTO observations (patient_id, recorded_by, visit_type, body_temp, systolic_bp, diastolic_bp,
            heart_rate, weight, height, symptoms, possible_conditions, notes, risk_level, created_at)
        VALUES (?, ?, 'general', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING *
    """, (patient_id, user["id"], visit.temperature, visit.systolic_bp, visit.diastolic_bp, visit.heart_rate,
          visit.weight, visit.height,
          ",".join(visit.symptoms), ",".join(conditions), visit.notes.strip(), risk_level,
          to_db_time(visit.recorded_at))).fetchone()
    log_access(conn, user["id"], "sync_offline_visit" if visit.recorded_at else "general_visit", patient["ref"])
    conn.commit()
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
    risk_score, risk_level = predict_risk(PatientData(age=patient["age"], **vitals.model_dump(exclude={"height", "recorded_at"})))

    observation = conn.execute("""
        INSERT INTO observations (patient_id, recorded_by, gestational_age, systolic_bp, diastolic_bp,
            weight, height, hemoglobin, body_temp, heart_rate, previous_complications, risk_score, risk_level,
            created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING *
    """, (patient_id, user["id"], vitals.gestational_age, vitals.systolic_bp, vitals.diastolic_bp,
          vitals.weight, vitals.height, vitals.hemoglobin, vitals.body_temp, vitals.heart_rate,
          int(vitals.previous_complications), risk_score, risk_level,
          to_db_time(vitals.recorded_at))).fetchone()
    log_access(conn, user["id"], "sync_offline_check" if vitals.recorded_at else "assess_patient", patient["ref"])
    conn.commit()
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
        "INSERT INTO referrals (observation_id, patient_id, chv_id, referred_by, facility, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (observation_id, patient["id"], user["id"], user["id"], user["facility"], reason or None, now_text()),
    )
    conn.execute("UPDATE observations SET referral_sent = 1 WHERE id = ?", (observation_id,))

    # 2. The SMS: only a heads-up. If it fails, the referral still exists.
    sms_sent = send_referral_sms(user, patient, obs)
    log_access(conn, user["id"], "create_referral", f"{patient['ref']} sms={'ok' if sms_sent else 'failed'}")
    conn.commit()
    conn.close()
    return {"success": True, "sms_sent": sms_sent}


def send_referral_sms(user, patient, obs):
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
    return send_sms(user["facility_phone"], message)


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
    escalate_overdue(conn)  # opening any inbox also checks for urgent cases nobody has seen
    rows = conn.execute("""
        SELECT r.id, r.patient_id, r.status, r.outcome, r.reason, r.parent_id, r.created_at, r.updated_at,
               r.auto_escalated_at, (r.parent_id IS NOT NULL AND r.referred_by IS NULL) AS auto_escalated,
               p.ref, p.full_name, p.age, p.community,
               (SELECT im.paid_until FROM insurance_members im WHERE im.patient_id = r.patient_id) AS insured_until,
               (SELECT h.full_name FROM healer_referrals hr JOIN healers h ON h.id = hr.healer_id
                WHERE hr.patient_id = r.patient_id ORDER BY hr.id DESC LIMIT 1) AS healer_name,
               (SELECT hr.remedy_given FROM healer_referrals hr
                WHERE hr.patient_id = r.patient_id ORDER BY hr.id DESC LIMIT 1) AS healer_remedy,
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


@app.get("/referrals/{referral_id}/history")
def referral_history(referral_id: int, user=Depends(require_role("nurse", "doctor"))):
    # Need-to-know: staff can only open the history of a patient referred to THEIR facility.
    # The referral is the "permission slip"; there is no way to browse other patients.
    conn = get_db()
    referral = get_facility_referral(conn, referral_id, user)
    patient = conn.execute(
        "SELECT ref, full_name, age, sex, pregnant, community, created_at FROM patients WHERE id = ?",
        (referral["patient_id"],),
    ).fetchone()
    observations = conn.execute("""
        SELECT o.*,
               r.facility AS referral_facility, r.status AS referral_status, r.outcome AS referral_outcome,
               e.facility AS escalated_to, e.status AS escalated_status, e.outcome AS escalated_outcome
        FROM observations o
        LEFT JOIN referrals r ON r.observation_id = o.id AND r.parent_id IS NULL
        LEFT JOIN referrals e ON e.parent_id = r.id
        WHERE o.patient_id = ?
        ORDER BY o.id DESC
    """, (referral["patient_id"],)).fetchall()
    log_access(conn, user["id"], "view_history_via_referral", referral["ref"])
    conn.commit()
    conn.close()
    return {"patient": dict(patient), "observations": [dict(o) for o in observations]}


# ---------- Appointments (nurse/doctor, only for patients referred to their facility) ----------

@app.post("/referrals/{referral_id}/appointments")
def book_appointment(referral_id: int, body: AppointmentCreate, user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    referral = get_facility_referral(conn, referral_id, user)  # need-to-know check
    when = body.scheduled_at.strftime("%Y-%m-%d %H:%M")
    if when <= datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"):
        conn.close()
        raise HTTPException(status_code=400, detail="Choose a time in the future")

    appointment_id = conn.execute(
        "INSERT INTO appointments (patient_id, referral_id, booked_by, facility, scheduled_at, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (referral["patient_id"], referral_id, user["id"], user["facility"], when, body.reason.strip() or None,
         now_text()),
    ).fetchone()["id"]
    patient = conn.execute("SELECT ref, phone, reminder_method FROM patients WHERE id = ?",
                           (referral["patient_id"],)).fetchone()
    by_sms = patient["reminder_method"] == "sms"
    if not by_sms:
        # CHV visit: the CHV reminds the patient in person
        conn.execute("UPDATE appointments SET reminder_status = 'chv' WHERE id = ?", (appointment_id,))
    # Confirmation SMS straight away (the 24-hour reminder comes later from the reminder job)
    confirmed = by_sms and bool(patient["phone"]) and send_sms(
        patient["phone"], appointment_message("confirm", user["facility"], when, patient["ref"])
    )
    # Appointment less than a day away? The confirmation already serves as the reminder,
    # so mark it done and the patient doesn't get two SMS minutes apart.
    soon = (body.scheduled_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() < REMIND_HOURS_BEFORE * 3600
    if confirmed and soon:
        conn.execute("UPDATE appointments SET reminder_status = 'sent' WHERE id = ?", (appointment_id,))
    log_access(conn, user["id"], "book_appointment", f"{patient['ref']} {when}")
    conn.commit()
    conn.close()
    return {"id": appointment_id, "scheduled_at": when, "has_phone": bool(patient["phone"]), "sms_sent": confirmed,
            "reminder_method": patient["reminder_method"]}


@app.get("/appointments")
def list_appointments(user=Depends(require_role("nurse", "doctor"))):
    # Booked appointments at this facility, soonest first
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id, a.scheduled_at, a.reason, a.status, a.reminder_status,
               p.ref, p.full_name, p.age, p.sex, (p.phone IS NOT NULL) AS has_phone,
               u.full_name AS booked_by_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        JOIN users u ON u.id = a.booked_by
        WHERE a.facility = ? AND a.status = 'booked'
        ORDER BY a.scheduled_at
    """, (user["facility"],)).fetchall()
    log_access(conn, user["id"], "list_appointments", user["facility"])
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/appointments/{appointment_id}/status")
def update_appointment(appointment_id: int, body: AppointmentStatus, user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    appt = conn.execute(
        "SELECT a.id, p.ref FROM appointments a JOIN patients p ON p.id = a.patient_id "
        "WHERE a.id = ? AND a.facility = ?",
        (appointment_id, user["facility"]),
    ).fetchone()
    if not appt:
        log_access(conn, user["id"], "access_denied", f"appointment:{appointment_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Appointment not found")
    conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (body.status, appointment_id))
    log_access(conn, user["id"], f"appointment_{body.status}", appt["ref"])
    conn.commit()
    conn.close()
    return {"success": True}


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
        "UPDATE referrals SET status = ?, outcome = ?, updated_by = ?, updated_at = ? WHERE id = ?",
        (body.status, (body.outcome or "").strip() or referral["outcome"], user["id"], now_text(), referral_id),
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
        "SELECT DISTINCT facility FROM users WHERE role = 'doctor' AND active = 1 AND facility IS NOT NULL ORDER BY facility"
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
    now = now_text()
    auto = conn.execute(
        "SELECT id FROM referrals WHERE parent_id = ? AND referred_by IS NULL AND status <> 'completed'", (referral_id,)
    ).fetchone()
    if auto:
        # The system already sent this urgent case on: add the nurse's treatment to that referral
        conn.execute("UPDATE referrals SET referred_by = ?, facility = ?, reason = ? WHERE id = ?",
                     (user["id"], body.facility, f"{reason} (after auto-escalation)", auto["id"]))
    else:
        # New referral to the hospital, linked to this one...
        conn.execute(
            "INSERT INTO referrals (observation_id, patient_id, chv_id, referred_by, parent_id, facility, reason, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (referral["observation_id"], referral["patient_id"], referral["chv_id"], user["id"],
             referral_id, body.facility, reason, now),
        )
    # ...and this one is closed, recording the nurse's treatment and where the patient went
    conn.execute(
        "UPDATE referrals SET status = 'completed', outcome = ?, updated_by = ?, updated_at = ? WHERE id = ?",
        (f"Referred on to {body.facility}: {reason}", user["id"], now, referral_id),
    )
    log_access(conn, user["id"], "escalate_referral", f"{referral['ref']} -> {body.facility}")
    conn.commit()
    conn.close()
    return {"success": True}
