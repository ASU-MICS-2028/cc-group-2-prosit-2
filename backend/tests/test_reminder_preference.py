"""How to remind a patient: SMS, or the CHV in person (for patients who cannot read)."""
from datetime import datetime, timedelta, timezone

import database
import reminders


def booked(client, login, make_patient, hours_ahead=48, **patient):
    """Register a patient with chv1, refer them, and have nurse1 book an appointment."""
    chv, nurse = login("chv1"), login("nurse1")
    p = make_patient(chv, **patient)
    obs = client.post(f"/patients/{p['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    rid = client.get("/referrals", headers=nurse).json()[0]["id"]
    when = (datetime.now(timezone.utc) + timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M")
    res = client.post(f"/referrals/{rid}/appointments", headers=nurse, json={"scheduled_at": when})
    assert res.status_code == 200, res.text
    return p, res.json()


def test_choice_saved_and_validated(client, login, make_patient):
    p = make_patient(login("chv1"), reminder_method="chv", language="dag")
    assert (p["reminder_method"], p["language"]) == ("chv", "dag")
    assert make_patient(login("chv1"))["reminder_method"] == "sms"  # default, as before
    bad = client.post("/patients", headers=login("chv1"),
                      json={"full_name": "X", "age": 30, "sex": "male", "consent": True, "reminder_method": "voice"})
    assert bad.status_code == 422  # voice calls were dropped


def test_chv_visit_patient_gets_no_sms_and_is_on_the_chv_list(client, login, make_patient):
    p, appt = booked(client, login, make_patient, reminder_method="chv", language="tw", phone="0240000000")
    assert appt["sms_sent"] is False and appt["reminder_method"] == "chv"
    to_remind = client.get("/chv/reminders", headers=login("chv1")).json()
    assert [(r["ref"], r["language"], r["reminder_status"]) for r in to_remind] == [(p["ref"], "tw", "chv")]
    assert client.get("/chv/reminders", headers=login("chv2")).json() == []  # another CHV sees nothing


def test_sms_patient_with_phone_is_not_on_the_list(client, login, make_patient):
    booked(client, login, make_patient, phone="0240000000")
    assert client.get("/chv/reminders", headers=login("chv1")).json() == []


def test_reminder_job_never_texts_a_chv_visit_patient(client, login, make_patient, monkeypatch):
    texts = []
    monkeypatch.setattr(reminders, "send_sms", lambda phone, message: texts.append(phone) or True)
    p, appt = booked(client, login, make_patient, hours_ahead=12, phone="0240000000")
    # After the booking the CHV learns the patient cannot read; the appointment is not reminded yet
    conn = database.get_db()
    conn.execute("UPDATE appointments SET reminder_status = NULL WHERE id = ?", (appt["id"],))
    conn.commit()
    conn.close()
    client.post(f"/patients/{p['id']}/reminder-preference", headers=login("chv1"),
                json={"reminder_method": "chv", "language": "ee"})

    counts = reminders.send_due_reminders()
    assert counts["chv"] == 1 and counts["sent"] == 0 and texts == []
    assert client.get("/chv/reminders", headers=login("chv1")).json()[0]["reminder_status"] == "chv"


def test_only_own_patient_can_be_changed(client, login, make_patient):
    p = make_patient(login("chv1"))
    res = client.post(f"/patients/{p['id']}/reminder-preference", headers=login("chv2"), json={"reminder_method": "chv"})
    assert res.status_code == 404
