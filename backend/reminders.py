"""Appointment SMS: confirmation when booked, reminder about 24 hours before.

The reminder job runs every 10 minutes inside the API (see main.py).
In the cloud this would be an EventBridge Scheduler rule calling a Lambda function.
"""
from datetime import datetime, timedelta, timezone

from database import get_db, log_access
from sms import send_sms

REMIND_HOURS_BEFORE = 24


def appointment_message(kind, facility, scheduled_at, ref):
    # No name, no diagnosis: the phone may be shared (data minimisation)
    when = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M").strftime("%a %d %b, %H:%M")
    first = "Your appointment is booked" if kind == "confirm" else "Reminder: you have an appointment"
    return f"HealthConnect: {first} at {facility} on {when}. Ref {ref}. Please come on time."


def send_due_reminders(now=None):
    """Remind every booked appointment starting within the next 24 hours, once."""
    now = now or datetime.now(timezone.utc)
    window_end = (now + timedelta(hours=REMIND_HOURS_BEFORE)).strftime("%Y-%m-%d %H:%M")
    now_text = now.strftime("%Y-%m-%d %H:%M")

    conn = get_db()
    due = conn.execute("""
        SELECT a.id, a.facility, a.scheduled_at, p.ref, p.phone
        FROM appointments a JOIN patients p ON p.id = a.patient_id
        WHERE a.status = 'booked' AND a.reminder_status IS NULL
          AND a.scheduled_at > ? AND a.scheduled_at <= ?
    """, (now_text, window_end)).fetchall()

    for a in due:
        if not a["phone"]:
            result = "no_phone"  # the CHV sees it in the app and reminds in person
        elif send_sms(a["phone"], appointment_message("remind", a["facility"], a["scheduled_at"], a["ref"])):
            result = "sent"
        else:
            result = "failed"
        # Tried once, whatever happened, so we never spam the patient
        conn.execute("UPDATE appointments SET reminder_status = ? WHERE id = ?", (result, a["id"]))
        log_access(conn, None, f"appointment_reminder_{result}", a["ref"])
    conn.commit()
    conn.close()
    return len(due)
