"""Community insurance with simulated mobile money: rules, cover dates and access."""
from datetime import datetime, timedelta, timezone

import database


def in_days(days):
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def joined(client, chv, make_patient):
    p = make_patient(chv)
    res = client.post(f"/patients/{p['id']}/insurance/join", headers=chv, json={"consent": True})
    assert res.status_code == 200, res.text
    return p


def test_join_needs_consent_and_happens_once(client, login, make_patient):
    chv = login("chv1")
    p = make_patient(chv)
    url = f"/patients/{p['id']}/insurance/join"
    assert client.post(url, headers=chv, json={"consent": False}).status_code == 400
    body = client.post(url, headers=chv, json={"consent": True}).json()
    assert body["member"] is True and body["covered"] is False  # not covered until a premium is paid
    assert client.post(url, headers=chv, json={"consent": True}).status_code == 400


def test_payment_needs_membership_and_valid_input(client, login, make_patient):
    chv = login("chv1")
    p = make_patient(chv)
    url = f"/patients/{p['id']}/insurance/pay"
    assert client.post(url, headers=chv, json={"months": 1, "network": "mtn"}).status_code == 400
    joined_patient = joined(client, chv, make_patient)
    url = f"/patients/{joined_patient['id']}/insurance/pay"
    assert client.post(url, headers=chv, json={"months": 0, "network": "mtn"}).status_code == 422
    assert client.post(url, headers=chv, json={"months": 1, "network": "bank"}).status_code == 422


def test_paying_gives_cover_and_early_payment_adds_time(client, login, make_patient):
    chv = login("chv1")
    p = joined(client, chv, make_patient)
    url = f"/patients/{p['id']}/insurance/pay"
    first = client.post(url, headers=chv, json={"months": 1, "network": "mtn"}).json()
    assert first["covered"] is True and first["paid_until"] == in_days(30)
    second = client.post(url, headers=chv, json={"months": 2, "network": "telecel"}).json()
    assert second["paid_until"] == in_days(90)
    assert second["payments"][0]["amount_ghs"] == 10 and second["payments"][0]["reference"].startswith("SIM-")


def test_lapsed_cover_is_not_covered_and_restarts_from_today(client, login, make_patient):
    chv = login("chv1")
    p = joined(client, chv, make_patient)
    conn = database.get_db()
    conn.execute("UPDATE insurance_members SET paid_until = ? WHERE patient_id = ?", (in_days(-10), p["id"]))
    conn.commit()
    conn.close()
    assert client.get(f"/patients/{p['id']}/insurance", headers=chv).json()["covered"] is False
    after = client.post(f"/patients/{p['id']}/insurance/pay", headers=chv, json={"months": 1, "network": "at"}).json()
    assert after["paid_until"] == in_days(30)


def test_only_the_patients_own_chv_can_reach_it(client, login, make_patient):
    p = make_patient(login("chv1"))
    url = f"/patients/{p['id']}/insurance"
    assert client.get(url, headers=login("chv2")).status_code == 404
    assert client.post(url + "/join", headers=login("chv2"), json={"consent": True}).status_code == 404
    for other in ["nurse1", "doctor1", "pharm1", "ghs1", "admin1"]:
        assert client.get(url, headers=login(other)).status_code == 403
    assert client.get(url).status_code == 401


def test_inbox_shows_the_cover_date_only(client, login, make_patient):
    chv, nurse = login("chv1"), login("nurse1")
    p = joined(client, chv, make_patient)
    client.post(f"/patients/{p['id']}/insurance/pay", headers=chv, json={"months": 1, "network": "mtn"})
    obs = client.post(f"/patients/{p['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    card = client.get("/referrals", headers=nurse).json()[0]
    assert card["insured_until"] == in_days(30)
    assert "SIM-" not in str(card) and "premium" not in str(card)
