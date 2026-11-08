"""Patients (consent, need-to-know) and the referral chain CHV -> nurse -> doctor."""


def test_consent_required(client, login):
    body = {"full_name": "Test Patient B", "age": 30, "sex": "female", "consent": False}
    assert client.post("/patients", headers=login("chv1"), json=body).status_code == 400


def test_chv_sees_only_own_patients(client, login, make_patient, audit):
    chv1, chv2 = login("chv1"), login("chv2")
    patient = make_patient(chv1)
    assert client.get(f"/patients/{patient['id']}", headers=chv1).status_code == 200
    # 404, not 403: chv2 is not even told the patient exists
    assert client.get(f"/patients/{patient['id']}", headers=chv2).status_code == 404
    assert client.get("/patients", headers=chv2).json() == []
    assert "access_denied" in audit()


def test_general_visit_scored_on_server(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv, sex="male")
    res = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"temperature": 38.5, "symptoms": ["fever"]})
    assert res.status_code == 200
    assert res.json()["observation"]["risk_level"] == "MEDIUM"


def test_offline_check_synced_later(client, login, make_patient, audit):
    # A check done offline arrives later with recorded_at. The server re-scores it
    # (it never trusts the phone's result) and keeps the time it really happened.
    chv = login("chv1")
    patient = make_patient(chv)
    body = {"temperature": 39, "symptoms": ["stiff_neck"], "recorded_at": "2026-10-30T09:15:00Z"}
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv, json=body).json()["observation"]
    assert obs["risk_level"] == "HIGH"
    assert obs["created_at"] == "2026-10-30 09:15:00"
    assert "sync_offline_visit" in audit()


def visit(client, chv, patient, **body):
    res = client.post(f"/patients/{patient['id']}/visit", headers=chv, json=body)
    return res.json()["observation"]


def test_referral_rules(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv)
    low = visit(client, chv, patient, temperature=37, symptoms=["cough"])
    medium = visit(client, chv, patient, temperature=38.5, symptoms=["fever"])
    high = visit(client, chv, patient, symptoms=["convulsions"])
    refer = lambda obs, body=None: client.post(f"/observations/{obs['id']}/referral", headers=chv, json=body)
    assert refer(low).status_code == 400  # LOW cannot be referred
    assert refer(medium).status_code == 400  # MEDIUM needs a reason
    assert refer(medium, {"reason": "Fever not improving after 2 days"}).status_code == 200
    assert refer(high).status_code == 200  # SMS fails in tests (no key), the referral is still saved


def test_every_case_reaches_a_doctor(client, login, make_patient):
    chv, nurse1, nurse2, doctor = login("chv1"), login("nurse1"), login("nurse2"), login("doctor1")
    patient = make_patient(chv)
    obs = visit(client, chv, patient, temperature=40, symptoms=["bleeding", "convulsions"])
    client.post(f"/observations/{obs['id']}/referral", headers=chv)

    assert client.get("/referrals", headers=nurse2).json() == []  # other facility sees nothing
    ref = client.get("/referrals", headers=nurse1).json()[0]
    assert ref["priority_label"] == "urgent"
    rid = ref["id"]
    assert client.post(f"/referrals/{rid}/status", headers=nurse1, json={"status": "arrived"}).status_code == 200
    # The nurse cannot close the case: it must go to a doctor
    closed = client.post(f"/referrals/{rid}/status", headers=nurse1, json={"status": "completed", "outcome": "Treated"})
    assert closed.status_code == 403
    escalate = {"facility": "Test District Hospital", "reason": "IV fluids given; needs doctor review"}
    assert client.post(f"/referrals/{rid}/escalate", headers=nurse1, json=escalate).status_code == 200

    dref = client.get("/referrals", headers=doctor).json()[0]
    done = {"status": "completed", "outcome": "Stabilised, admitted"}
    assert client.post(f"/referrals/{dref['id']}/status", headers=doctor, json=done).status_code == 200
    history = client.get(f"/patients/{patient['id']}", headers=chv).json()["observations"][0]
    assert history["escalated_status"] == "completed"


def test_patient_ref_never_repeats(client, login, make_patient, monkeypatch):
    # Force the random generator to repeat itself: the second patient must still get a new reference
    import secrets
    values = iter(["AAAAAA", "AAAAAA", "BBBBBB"])
    monkeypatch.setattr(secrets, "token_hex", lambda n: next(values))
    chv = login("chv1")
    assert make_patient(chv)["ref"] == "HC-AAAAAA"
    assert make_patient(chv)["ref"] == "HC-BBBBBB"


def test_other_kinds_of_case(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv)
    assert visit(client, chv, patient, symptoms=["snake_bite"])["risk_level"] == "HIGH"
    assert visit(client, chv, patient, symptoms=["other"], notes="Swollen painful knee")["risk_level"] == "MEDIUM"
    assert visit(client, chv, patient, symptoms=["abdominal_pain"])["risk_level"] == "LOW"
