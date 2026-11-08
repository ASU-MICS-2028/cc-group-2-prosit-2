"""Community insurance with simulated mobile money: rules, cover dates and access."""
from datetime import datetime, timedelta, timezone

import database
import paystack


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
    assert second["payments"][0]["amount_ghs"] == 2 and second["payments"][0]["reference"].startswith("SIM-")


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


def paystack_on(monkeypatch, paid):
    """Pretend Paystack is set up; paid["value"] is what it reports."""
    monkeypatch.setattr(paystack, "secret_key", lambda: "sk_test_fake")
    monkeypatch.setattr(paystack, "start_payment", lambda reference, amount: f"https://checkout.example/{reference}")
    monkeypatch.setattr(paystack, "is_paid", lambda reference, amount: paid["value"])


def test_paystack_gives_cover_only_after_it_confirms_and_only_once(client, login, make_patient, monkeypatch):
    paid = {"value": False}
    paystack_on(monkeypatch, paid)
    chv = login("chv1")
    p = joined(client, chv, make_patient)
    started = client.post(f"/patients/{p['id']}/insurance/pay", headers=chv, json={"months": 2, "network": "mtn"}).json()
    assert started["simulated"] is False and started["covered"] is False and started["payments"] == []
    assert started["pending"]["amount_ghs"] == 2
    confirm = f"/patients/{p['id']}/insurance/confirm/{started['pending']['reference']}"

    assert client.post(confirm, headers=chv).status_code == 400  # not paid yet: no cover
    paid["value"] = True
    done = client.post(confirm, headers=chv).json()
    assert done["covered"] is True and done["paid_until"] == in_days(60) and done["pending"] is None
    again = client.post(confirm, headers=chv).json()  # pressing twice must not add cover twice
    assert again["paid_until"] == in_days(60) and len(again["payments"]) == 1


def test_paystack_reference_must_belong_to_this_patient(client, login, make_patient, monkeypatch):
    paystack_on(monkeypatch, {"value": True})
    chv = login("chv1")
    first, second = joined(client, chv, make_patient), make_patient(chv, full_name="Test Patient B")
    reference = client.post(f"/patients/{first['id']}/insurance/pay", headers=chv, json={"months": 1, "network": "mtn"}).json()["pending"]["reference"]
    assert client.post(f"/patients/{second['id']}/insurance/confirm/{reference}", headers=chv).status_code == 404
    assert client.post(f"/patients/{first['id']}/insurance/confirm/{reference}", headers=login("chv2")).status_code == 404


def test_is_paid_needs_success_and_the_full_amount(monkeypatch):
    def answer(status, amount, currency="GHS"):
        monkeypatch.setattr(paystack, "call", lambda *a, **k: {"data": {"status": status, "amount": amount, "currency": currency}})
    answer("success", 500)
    assert paystack.is_paid("X", 5) is True
    answer("abandoned", 500)
    assert paystack.is_paid("X", 5) is False
    answer("success", 100)  # paid less than was due
    assert paystack.is_paid("X", 5) is False
    answer("success", 500, "NGN")
    assert paystack.is_paid("X", 5) is False


def test_a_live_key_needs_the_on_switch(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_live_x")
    monkeypatch.delenv("PAYSTACK_ALLOW_LIVE", raising=False)
    assert paystack.is_configured() is False
    monkeypatch.setenv("PAYSTACK_ALLOW_LIVE", "on")
    assert paystack.is_configured() is True and paystack.is_live() is True
