"""Referral priority: who should the nurse or doctor see first?

score = risk points + danger-sign points + waiting points
  HIGH = 50, MEDIUM = 20
  any danger sign = +30
  waiting (not completed yet) = +1 per 10 minutes, capped at +30
Urgent >= 80, High >= 50, otherwise Routine.
"""
from datetime import datetime, timezone

from general_model import DANGER_SIGNS

MAX_WAITING_POINTS = 30  # so waiting alone can never beat a HIGH case with danger signs


def waiting_minutes(created_at, now=None):
    # created_at is stored by SQLite as UTC text: "YYYY-MM-DD HH:MM:SS"
    start = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - start).total_seconds() // 60))


def danger_signs(row):
    found = []
    # General visit: danger-sign symptoms ticked by the CHV
    for symptom in (row["symptoms"] or "").split(","):
        if symptom in DANGER_SIGNS:
            found.append(symptom)
    # Any visit: dangerously high BP; antenatal: severe anaemia
    if (row["systolic_bp"] or 0) >= 160 or (row["diastolic_bp"] or 0) >= 110:
        found.append("severe_hypertension")
    if row["hemoglobin"] is not None and row["hemoglobin"] < 7:
        found.append("severe_anaemia")
    return found


def priority(row, now=None):
    score = {"HIGH": 50, "MEDIUM": 20}.get(row["risk_level"], 0)

    signs = danger_signs(row)
    if signs:
        score += 30

    waited = 0
    if row["status"] != "completed":
        waited = waiting_minutes(row["created_at"], now)
        score += min(waited // 10, MAX_WAITING_POINTS)

    label = "urgent" if score >= 80 else "high" if score >= 50 else "routine"
    return {"priority_score": score, "priority_label": label, "danger_signs": signs, "waiting_minutes": waited}
