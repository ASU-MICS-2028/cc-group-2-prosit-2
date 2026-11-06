"""Behaviour the AWS deployment depends on: health check, no caching, and SMS reminders
that are sent once even when two runs overlap (Lambda delivers events at least once)."""
from datetime import datetime, timedelta, timezone

import pytest

import database
import lambda_handler
import reminders


def query(sql, params=()):
    conn = database.get_db()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


@pytest.fixture
def appointment(client, login, make_patient):
    """A booked appointment 20 hours from now for a patient with a phone: due for a reminder."""
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv, phone="0240000000")
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv,
                      json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    referral_id = client.get("/referrals", headers=nurse).json()[0]["id"]
    when = (datetime.now(timezone.utc) + timedelta(hours=20)).replace(tzinfo=None).isoformat(timespec="minutes")
    res = client.post(f"/referrals/{referral_id}/appointments", headers=nurse, json={"scheduled_at": when})
    assert res.status_code == 200, res.text
    assert res.json()["sms_sent"] is False  # no SMS key in tests, so the reminder is still due
    return res.json()["id"]


def reminder_row(appointment_id):
    return query("SELECT reminder_status, reminder_attempts FROM appointments WHERE id = ?", (appointment_id,))[0]


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200 and res.json() == {"status": "ok"}


def test_api_answers_are_never_cached(client, login):
    assert client.get("/health").headers["cache-control"] == "no-store"
    assert client.get("/patients", headers=login("chv1")).headers["cache-control"] == "no-store"


def test_reminder_is_sent_once(appointment, monkeypatch):
    sent = []
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: sent.append(message) or True)
    assert reminders.send_due_reminders()["sent"] == 1
    assert reminders.send_due_reminders()["due"] == 0  # second run: nothing left to do
    assert len(sent) == 1
    assert reminder_row(appointment)["reminder_status"] == "sent"


def test_overlapping_runs_send_one_sms(appointment, monkeypatch):
    # While the first run is sending, a second run starts (two servers, or Lambda
    # delivering the same event twice). The appointment is already claimed, so it skips it.
    sent, second_run = [], {}

    def slow_sms(phone, message):
        second_run.update(reminders.send_due_reminders())
        sent.append(message)
        return True

    monkeypatch.setattr(reminders, "send_sms", slow_sms)
    first_run = reminders.send_due_reminders()
    assert len(sent) == 1
    assert first_run["sent"] == 1
    assert second_run["sent"] == 0 and second_run["due"] == 0


def test_failed_sms_is_retried_then_given_up(appointment, monkeypatch):
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: False)
    assert reminders.send_due_reminders()["retry"] == 1
    assert reminder_row(appointment) == {"reminder_status": None, "reminder_attempts": 1}  # tried again next run
    assert reminders.send_due_reminders()["retry"] == 1
    assert reminders.send_due_reminders()["failed"] == 1
    assert reminder_row(appointment) == {"reminder_status": "failed", "reminder_attempts": 3}
    assert reminders.send_due_reminders()["due"] == 0  # no more attempts after 3


def test_crashed_run_releases_its_claim(appointment, monkeypatch):
    # A run claimed the appointment and then died before sending
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn = database.get_db()
    conn.execute("UPDATE appointments SET reminder_status = 'sending', reminder_claimed_at = ? WHERE id = ?",
                 (long_ago, appointment))
    conn.commit()
    conn.close()
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: True)
    assert reminders.send_due_reminders()["sent"] == 1


def test_lambda_handler(appointment, monkeypatch):
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: False)
    with pytest.raises(RuntimeError):  # a failed SMS makes Lambda retry, then use the dead-letter queue
        lambda_handler.handler({}, None)
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: True)
    assert lambda_handler.handler({}, None)["sent"] == 1
