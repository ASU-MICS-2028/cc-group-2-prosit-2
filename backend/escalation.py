"""Emergency auto-escalation: an urgent case must never sit unseen.

Rule: a referral that is URGENT (HIGH risk + a danger sign) and still 'pending' at the
health centre after AUTO_ESCALATE_MINUTES is sent automatically to a hospital with a
doctor in the same district. The hospital gets an SMS and the case appears in the doctor's
inbox marked "Auto-escalated". The health centre keeps its referral, because the patient
may still arrive there.

Runs whenever a nurse or doctor opens the inbox, and in the background loop. Safe to run
twice at once: each referral is first CLAIMED with an UPDATE that only one run can win.
"""
from datetime import datetime, timedelta, timezone

from database import get_db, log_access, now_text
from priority import danger_signs
from sms import send_sms

AUTO_ESCALATE_MINUTES = 30


def hospital_for(conn, health_centre):
    """A facility with an active doctor, in the health centre's district if possible."""
    rows = conn.execute(
        "SELECT DISTINCT d.facility, (d.district = (SELECT district FROM users WHERE facility = ? "
        "AND district IS NOT NULL LIMIT 1)) AS same_district "
        "FROM users d WHERE d.role = 'doctor' AND d.active = 1 AND d.facility IS NOT NULL AND d.facility <> ?",
        (health_centre, health_centre),
    ).fetchall()
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: (not r["same_district"], r["facility"]))
    return rows[0]["facility"]


def escalate_overdue(conn, now=None):
    """Escalate every overdue urgent referral once. Returns how many were escalated."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=AUTO_ESCALATE_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    # Waiting at a health centre (no parent = first referral from a CHV), never escalated
    waiting = conn.execute(
        "SELECT r.*, p.ref, p.age, p.sex, o.risk_level, o.symptoms, o.systolic_bp, o.diastolic_bp, "
        "o.hemoglobin, o.possible_conditions "
        "FROM referrals r JOIN patients p ON p.id = r.patient_id JOIN observations o ON o.id = r.observation_id "
        "WHERE r.status = 'pending' AND r.parent_id IS NULL AND r.auto_escalated_at IS NULL AND r.created_at <= ?",
        (cutoff,),
    ).fetchall()
    done = 0
    for r in waiting:
        signs = danger_signs(r)
        if r["risk_level"] != "HIGH" or not signs:
            continue  # only urgent cases
        hospital = hospital_for(conn, r["facility"])
        if not hospital:
            continue
        # Claim it: only one run can change NULL to a time
        claimed = conn.execute(
            "UPDATE referrals SET auto_escalated_at = ? WHERE id = ? AND auto_escalated_at IS NULL",
            (now_text(), r["id"]),
        ).rowcount
        if not claimed:
            continue
        reason = (f"AUTO-ESCALATED: urgent case ({', '.join(signs).replace('_', ' ')}) not marked arrived at "
                  f"{r['facility']} within {AUTO_ESCALATE_MINUTES} minutes")
        # referred_by stays empty: the system made this referral, not a person
        conn.execute(
            "INSERT INTO referrals (observation_id, patient_id, chv_id, parent_id, facility, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["observation_id"], r["patient_id"], r["chv_id"], r["id"], hospital, reason, now_text()),
        )
        phone = conn.execute(
            "SELECT facility_phone FROM users WHERE facility = ? AND facility_phone IS NOT NULL LIMIT 1", (hospital,)
        ).fetchone()
        # Ref only, no name (data minimisation), like every HealthConnect SMS
        sent = send_sms(phone["facility_phone"] if phone else None,
                        f"HealthConnect EMERGENCY\nRef: {r['ref']}\nAge: {r['age']} ({r['sex'] or '-'})\n"
                        f"Urgent case not yet seen at {r['facility']}.\nOpen your HealthConnect inbox now.")
        log_access(conn, None, "auto_escalate_referral", f"{r['ref']} -> {hospital} sms={'ok' if sent else 'failed'}")
        done += 1
    conn.commit()
    return done


def run_auto_escalation():
    """Background loop entry point (its own connection)."""
    conn = get_db()
    try:
        return escalate_overdue(conn)
    finally:
        conn.close()
