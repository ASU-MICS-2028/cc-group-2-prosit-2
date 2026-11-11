"""Emergency auto-escalation: urgent cases nobody has seen in 30 minutes go to a hospital."""
import database
from escalation import escalate_overdue


def refer(client, chv, patient, **visit):
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv, json=visit).json()["observation"]
    assert client.post(f"/observations/{obs['id']}/referral", headers=chv, json={"reason": "test"}).status_code == 200
    return obs


def age_referrals(minutes):
    """Pretend every referral was made `minutes` ago."""
    conn = database.get_db()
    for r in conn.execute("SELECT id, created_at FROM referrals").fetchall():
        conn.execute("UPDATE referrals SET created_at = ? WHERE id = ?", (shift(minutes), r["id"]))
    conn.commit()
    conn.close()


def shift(minutes):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def test_urgent_case_unseen_for_30_minutes_goes_to_hospital(client, login, make_patient, audit):
    chv, nurse, doctor = login("chv1"), login("nurse1"), login("doctor1")
    urgent = make_patient(chv)
    refer(client, chv, urgent, temperature=39, symptoms=["convulsions"])          # HIGH + danger sign
    medium = make_patient(chv, full_name="Test Patient Medium")
    refer(client, chv, medium, temperature=38.5, symptoms=["fever"])             # not urgent

    age_referrals(10)
    assert client.get("/referrals", headers=doctor).json() == []  # too early

    age_referrals(31)
    inbox = client.get("/referrals", headers=doctor).json()       # opening the inbox runs the check
    assert len(inbox) == 1 and inbox[0]["auto_escalated"] and inbox[0]["full_name"] == "Test Patient A"
    assert "AUTO-ESCALATED" in inbox[0]["reason"]
    assert "auto_escalate_referral" in audit()

    # The health centre keeps its copy, marked as sent on
    centre = {r["full_name"]: r for r in client.get("/referrals", headers=nurse).json()}
    assert centre["Test Patient A"]["auto_escalated_at"] and centre["Test Patient A"]["escalated_to"] == "Test District Hospital"
    assert not centre["Test Patient Medium"]["auto_escalated_at"]

    # Only once, however often it runs
    conn = database.get_db()
    assert escalate_overdue(conn) == 0
    conn.close()
    assert len(client.get("/referrals", headers=doctor).json()) == 1


def test_arrived_case_is_not_escalated(client, login, make_patient):
    chv, nurse, doctor = login("chv1"), login("nurse1"), login("doctor1")
    refer(client, chv, make_patient(chv), symptoms=["unconscious"])
    rid = client.get("/referrals", headers=nurse).json()[0]["id"]
    client.post(f"/referrals/{rid}/status", headers=nurse, json={"status": "arrived"})
    age_referrals(60)
    assert client.get("/referrals", headers=doctor).json() == []


def test_nurse_refers_on_after_auto_escalation_without_duplicate(client, login, make_patient):
    chv, nurse, doctor = login("chv1"), login("nurse1"), login("doctor1")
    refer(client, chv, make_patient(chv), symptoms=["convulsions"])
    age_referrals(45)
    assert len(client.get("/referrals", headers=doctor).json()) == 1
    rid = next(r["id"] for r in client.get("/referrals", headers=nurse).json())
    client.post(f"/referrals/{rid}/status", headers=nurse, json={"status": "arrived"})
    body = {"facility": "Test District Hospital", "reason": "Diazepam given"}
    assert client.post(f"/referrals/{rid}/escalate", headers=nurse, json=body).status_code == 200
    inbox = client.get("/referrals", headers=doctor).json()
    assert len(inbox) == 1 and inbox[0]["reason"].startswith("Diazepam given")
    assert inbox[0]["referred_by_name"] == "Mercy Akolgo" and not inbox[0]["auto_escalated"]
