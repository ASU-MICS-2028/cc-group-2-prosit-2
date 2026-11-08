"""Appointment SMS: confirmation when booked, reminder about 24 hours before.

Who runs the reminder job:
- on a laptop: the API itself, every 10 minutes (main.py);
- in the cloud: an AWS Lambda function started every 10 minutes by EventBridge Scheduler
  (lambda_handler.py), so it runs once however many API servers there are.

Safe to run twice at the same time (Week 7: idempotency). Event delivery is "at least
once", so Lambda may run twice for one event. Each appointment is first CLAIMED with an
UPDATE that only one run can win; only the winner sends the SMS. A patient never gets the
same reminder twice because two runs overlapped.

A failed SMS is retried on the next runs, up to MAX_ATTEMPTS, then marked 'failed'
(the CHV still sees it in the app and can remind the patient in person).
"""
from datetime import datetime, timedelta, timezone

from database import get_db, log_access
from sms import send_sms

REMIND_HOURS_BEFORE = 24
MAX_ATTEMPTS = 3
STALE_CLAIM_MINUTES = 15  # a run that crashed mid-send releases its claim after this long

DB_TIME = "%Y-%m-%d %H:%M:%S"


def appointment_message(kind, facility, scheduled_at, ref):
    # No name, no diagnosis: the phone may be shared (data minimisation)
    when = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M").strftime("%a %d %b, %H:%M")
    first = "Your appointment is booked" if kind == "confirm" else "Reminder: you have an appointment"
    return f"HealthConnect: {first} at {facility} on {when}. Ref {ref}. Please come on time."


# Not reminded yet, or claimed by a run that never finished
CLAIMABLE = "(reminder_status IS NULL OR (reminder_status = 'sending' AND reminder_claimed_at < ?))"


def send_due_reminders(now=None):
    """Remind every booked appointment starting within the next 24 hours, once.
    Returns counts, e.g. {"due": 3, "sent": 2, "no_phone": 1, "retry": 0, "failed": 0, "skipped": 0}."""
    now = now or datetime.now(timezone.utc)
    window_start = now.strftime("%Y-%m-%d %H:%M")
    window_end = (now + timedelta(hours=REMIND_HOURS_BEFORE)).strftime("%Y-%m-%d %H:%M")
    stale_before = (now - timedelta(minutes=STALE_CLAIM_MINUTES)).strftime(DB_TIME)

    conn = get_db()
    due = conn.execute(f"""
        SELECT a.id, a.facility, a.scheduled_at, a.reminder_attempts, p.ref, p.phone, p.reminder_method
        FROM appointments a JOIN patients p ON p.id = a.patient_id
        WHERE a.status = 'booked' AND {CLAIMABLE.replace('reminder_', 'a.reminder_')}
          AND a.scheduled_at > ? AND a.scheduled_at <= ?
    """, (stale_before, window_start, window_end)).fetchall()
    conn.commit()

    counts = {"due": len(due), "sent": 0, "no_phone": 0, "chv": 0, "retry": 0, "failed": 0, "skipped": 0}
    for a in due:
        # 1. Claim it. If another run got there first, no row comes back and we move on.
        claimed = conn.execute(
            f"UPDATE appointments SET reminder_status = 'sending', reminder_claimed_at = ? "
            f"WHERE id = ? AND {CLAIMABLE} RETURNING id",
            (now.strftime(DB_TIME), a["id"], stale_before),
        ).fetchone()
        conn.commit()
        if not claimed:
            counts["skipped"] += 1
            continue

        # 2. Send, and record the result
        attempts = a["reminder_attempts"]
        if a["reminder_method"] != "sms":
            result = "chv"  # the patient chose a CHV visit: the CHV reminds in person
        elif not a["phone"]:
            result = "no_phone"  # the CHV sees it in the app and reminds in person
        elif send_sms(a["phone"], appointment_message("remind", a["facility"], a["scheduled_at"], a["ref"])):
            result = "sent"
        else:
            attempts += 1
            result = "failed" if attempts >= MAX_ATTEMPTS else "retry"

        # 'retry' puts the status back to NULL so a later run tries again
        conn.execute(
            "UPDATE appointments SET reminder_status = ?, reminder_attempts = ?, reminder_claimed_at = NULL "
            "WHERE id = ?",
            (None if result == "retry" else result, attempts, a["id"]),
        )
        log_access(conn, None, f"appointment_reminder_{result}", a["ref"])
        conn.commit()
        counts[result] += 1

    conn.close()
    return counts
