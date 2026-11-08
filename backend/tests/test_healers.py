"""Traditional healers: registered by a CHV, referrals reach the clinic inbox."""


def add_healer(client, headers, name="Test Healer"):
    res = client.post("/healers", headers=headers, json={"full_name": name, "community": "Test", "registration_no": "TEST-1"})
    assert res.status_code == 200, res.text
    return res.json()


def test_chv_registers_healers_and_sees_only_their_own(client, login):
    add_healer(client, login("chv1"))
    assert [h["full_name"] for h in client.get("/healers", headers=login("chv1")).json()] == ["Test Healer"]
    assert client.get("/healers", headers=login("chv2")).json() == []
    for other in ["nurse1", "doctor1", "ghs1", "admin1"]:
        assert client.get("/healers", headers=login(other)).status_code == 403
    assert client.get("/healers").status_code == 401


def test_referral_is_recorded_and_validated(client, login, make_patient):
    chv = login("chv1")
    p, healer = make_patient(chv), add_healer(client, chv)
    url = f"/patients/{p['id']}/healer-referrals"
    assert client.post(url, headers=chv, json={"healer_id": healer["id"], "signs": "x"}).status_code == 422
    assert client.post(url, headers=chv, json={"healer_id": healer["id"], "signs": "Convulsions", "remedy_given": "Herbal drink"}).status_code == 200
    rows = client.get(url, headers=chv).json()
    assert (rows[0]["healer_name"], rows[0]["signs"], rows[0]["remedy_given"]) == ("Test Healer", "Convulsions", "Herbal drink")


def test_cannot_use_another_chvs_patient_or_healer(client, login, make_patient):
    chv1, chv2 = login("chv1"), login("chv2")
    p1, p2 = make_patient(chv1), make_patient(chv2)
    healer1, healer2 = add_healer(client, chv1), add_healer(client, chv2, "Other Healer")
    body = {"healer_id": healer1["id"], "signs": "Heavy bleeding"}
    assert client.post(f"/patients/{p2['id']}/healer-referrals", headers=chv1, json=body).status_code == 404
    assert client.get(f"/patients/{p1['id']}/healer-referrals", headers=chv2).status_code == 404
    body["healer_id"] = healer2["id"]
    assert client.post(f"/patients/{p1['id']}/healer-referrals", headers=chv1, json=body).status_code == 404


def test_clinic_sees_the_healer_and_the_remedy(client, login, make_patient):
    chv, nurse = login("chv1"), login("nurse1")
    p, healer = make_patient(chv), add_healer(client, chv)
    client.post(f"/patients/{p['id']}/healer-referrals", headers=chv,
                json={"healer_id": healer["id"], "signs": "Convulsions", "remedy_given": "Herbal drink"})
    obs = client.post(f"/patients/{p['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    card = client.get("/referrals", headers=nurse).json()[0]
    assert (card["healer_name"], card["healer_remedy"]) == ("Test Healer", "Herbal drink")
