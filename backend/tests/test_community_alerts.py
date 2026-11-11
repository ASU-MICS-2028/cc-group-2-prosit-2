"""Community health alert SMS: GHS only, facilities + residents who agreed, no numbers shown."""
import json



def test_alert_reaches_facilities_and_consenting_residents(client, login, make_patient, monkeypatch, audit):
    sent = []
    monkeypatch.setattr("community_alerts.send_sms", lambda phone, text: sent.append((phone, text)) or True)
    chv, ghs = login("chv1"), login("ghs1")
    make_patient(chv, phone="0241111111", health_alerts=True)
    make_patient(chv, phone="0242222222")  # did not agree: never texted
    assert client.get("/alerts/community/preview?district=Bolgatanga%20Municipal", headers=chv).status_code == 403
    preview = client.get("/alerts/community/preview?district=Bolgatanga%20Municipal", headers=ghs).json()
    assert preview == {"district": "Bolgatanga Municipal", "facilities": 1, "residents": 1}

    body = {"district": "Bolgatanga Municipal", "message": "Cholera cases rising. Drink safe water and wash hands."}
    res = client.post("/alerts/community", headers=ghs, json=body).json()
    assert res == {"recipients": 2, "delivered": 2}
    phones = {p for p, _ in sent}
    assert phones == {"0240000000", "0241111111"} and "0242222222" not in phones
    assert sent[0][1].startswith("HealthConnect GHS alert (Bolgatanga Municipal): Cholera")
    history = client.get("/alerts/community", headers=ghs).json()
    assert history[0]["recipients"] == 2 and "024" not in json.dumps(history)  # no numbers for GHS
    assert "send_community_alert" in audit()


def test_empty_district_refused(client, login):
    ghs = login("ghs1")
    res = client.post("/alerts/community", headers=ghs, json={"district": "Nowhere", "message": "Test message here"})
    assert res.status_code == 400
