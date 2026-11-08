"""Consultation and training fees, and health centre self-management. Paystack is off, so payments simulate."""
import database
import paystack
from training_list import TRAINING_MODULES

CODE = "danger_signs"
RIGHT = [q["answer"] for q in TRAINING_MODULES[CODE]["questions"]]


def appointment(client, login, make_patient):
    """A real appointment at Test Health Centre, made the way staff make one."""
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv)
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    referral = client.get("/referrals", headers=nurse).json()[0]["id"]
    res = client.post(f"/referrals/{referral}/appointments", headers=nurse, json={"scheduled_at": "2030-01-01T09:00", "reason": "Follow-up"})
    assert res.status_code == 200, res.text
    return client.get("/appointments", headers=nurse).json()[0]["id"]


def test_consultation_fee_simulated_once_and_facility_only(client, login, make_patient):
    nurse = login("nurse1")
    url = f"/fees/consultation/{appointment(client, login, make_patient)}"
    assert client.get(url, headers=login("nurse2")).status_code == 404  # another centre
    assert client.get(url, headers=login("chv1")).status_code == 403
    before = client.get(url, headers=nurse).json()
    assert before["due"] is True and before["amount_ghs"] == 1 and before["simulated"] is True
    assert client.post(url, headers=nurse).json()["due"] is False
    assert client.post(url, headers=nurse).status_code == 400  # not twice


def test_centre_sets_its_own_fee(client, login, make_patient):
    nurse = login("nurse1")
    assert client.post("/facility/fee", headers=nurse, json={"consultation_fee_ghs": 0}).status_code == 200
    url = f"/fees/consultation/{appointment(client, login, make_patient)}"
    assert client.get(url, headers=nurse).json()["due"] is False  # free here
    assert client.post(url, headers=nurse).status_code == 400
    assert client.post("/facility/fee", headers=nurse, json={"consultation_fee_ghs": 500}).status_code == 422


def test_paystack_fee_needs_confirmation_by_the_payer(client, login, make_patient, monkeypatch):
    paid = {"value": False}
    monkeypatch.setattr(paystack, "secret_key", lambda: "sk_test_fake")
    monkeypatch.setattr(paystack, "start_payment", lambda reference, amount: "https://checkout.example/x")
    monkeypatch.setattr(paystack, "is_paid", lambda reference, amount: paid["value"])
    nurse = login("nurse1")
    url = f"/fees/consultation/{appointment(client, login, make_patient)}"
    reference = client.post(url, headers=nurse).json()["pending"]["reference"]
    confirm = f"/fees/confirm/{reference}"
    assert client.post(confirm, headers=nurse).status_code == 400
    assert client.get(url, headers=nurse).json()["due"] is True
    paid["value"] = True
    assert client.post(confirm, headers=login("doctor1")).status_code == 404  # not the payer
    assert client.post(confirm, headers=nurse).status_code == 200
    assert client.post(confirm, headers=nurse).status_code == 200  # safe to press twice
    assert client.get(url, headers=nurse).json()["due"] is False


def test_training_fee_for_staff_but_chvs_are_free(client, login):
    doctor, nurse, chv = login("doctor1"), login("nurse1"), login("chv1")
    client.post(f"/training/modules/{CODE}/review", headers=nurse)
    attempt = f"/training/modules/{CODE}/attempt"
    assert client.post(attempt, headers=chv, json={"answers": RIGHT}).status_code == 200
    assert client.get(f"/fees/training/{CODE}", headers=chv).status_code == 403
    assert client.post(attempt, headers=doctor, json={"answers": RIGHT}).status_code == 402
    assert client.post(f"/fees/training/{CODE}", headers=doctor).json()["due"] is False
    assert client.post(attempt, headers=doctor, json={"answers": RIGHT}).json()["passed"] is True


def test_manager_only_and_totals_only(client, login):
    assert client.get("/facility/overview", headers=login("doctor1")).status_code == 403  # not a manager
    assert client.get("/facility/overview", headers=login("chv1")).status_code == 403
    data = client.get("/facility/overview", headers=login("nurse1")).json()
    assert data["facility"] == "Test Health Centre" and {"Test CHV One", "Test Nurse"} <= {s["full_name"] for s in data["staff"]}
    assert "Patient" not in str(data)


def test_manager_can_only_manage_own_centre(client, login):
    manager = login("nurse1")
    staff = client.get("/facility/overview", headers=manager).json()["staff"]
    chv2 = next(s for s in staff if s["full_name"] == "Test CHV Two")
    me = next(s for s in staff if s["is_you"])
    assert client.post(f"/facility/staff/{me['id']}/active", headers=manager, json={"active": False}).status_code == 400
    assert client.post(f"/facility/staff/{chv2['id']}/active", headers=manager, json={"active": False}).status_code == 200
    conn = database.get_db()
    other = conn.execute("SELECT id FROM users WHERE username = 'nurse2'").fetchone()["id"]
    conn.close()
    assert client.post(f"/facility/staff/{other}/active", headers=manager, json={"active": False}).status_code == 404


def test_admin_names_a_manager(client, login, audit):
    admin = login("admin1")
    users = client.get("/admin/users", headers=admin).json()["users"]
    doctor = next(u for u in users if u["username"] == "doctor1")
    chv = next(u for u in users if u["username"] == "chv1")
    assert client.post(f"/admin/users/{chv['id']}/facility-manager", headers=admin, json={"manager": True}).status_code == 400
    assert client.post(f"/admin/users/{doctor['id']}/facility-manager", headers=login("nurse1"), json={"manager": True}).status_code == 403
    assert client.post(f"/admin/users/{doctor['id']}/facility-manager", headers=admin, json={"manager": True}).status_code == 200
    assert client.get("/facility/overview", headers=login("doctor1")).status_code == 200
    assert "set_facility_manager" in audit()
