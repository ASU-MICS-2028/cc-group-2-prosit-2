"""GHS dashboard and DHIMS2 export: totals only, never names."""
import json
import runpy

import pytest


@pytest.fixture
def demo_data(client):
    runpy.run_path("seed_demo_data.py")  # ~800 fake visits, cholera spike in Tamale


def test_only_ghs_can_see_dashboard(client, login):
    for user in ["chv1", "nurse1", "doctor1", "admin1"]:
        assert client.get("/surveillance/summary", headers=login(user)).status_code == 403
    assert client.get("/surveillance/summary", headers=login("ghs1")).status_code == 200


def test_no_names_and_small_counts_hidden(client, login, make_patient, demo_data):
    chv = login("chv1")
    patient = make_patient(chv, full_name="Test Secret Name", phone="0240000000")
    client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"temperature": 39, "symptoms": ["fever", "rash"]})

    summary = client.get("/surveillance/summary", headers=login("ghs1")).json()
    text = json.dumps(summary)
    for private in ["Test Secret Name", "Demo Patient", "HC-", "0240000000", "full_name", "patient_id"]:
        assert private not in text
    # The single measles case in Bolgatanga is shown as "<5", never as 1
    bolga = next(d for d in summary["districts"] if d["district"] == "Bolgatanga Municipal")
    assert bolga["conditions"]["measles"][0] == "<5"


def test_outbreak_alert(client, login, demo_data):
    alerts = client.get("/surveillance/summary", headers=login("ghs1")).json()["alerts"]
    assert any(a["district"] == "Tamale Metropolitan" and a["condition"] == "cholera" for a in alerts)


def test_dhims2_export_shape(client, login, demo_data):
    assert client.get("/surveillance/dhims2-export", headers=login("nurse1")).status_code == 403
    export = client.get("/surveillance/dhims2-export", headers=login("ghs1")).json()
    assert export["period"][4] == "W"  # DHIS2 ISO week, e.g. 2026W43
    assert export["dataValues"]
    value = export["dataValues"][0]
    assert set(value) == {"dataElement", "orgUnit", "value"} and isinstance(value["value"], str)
    assert "Demo Patient" not in json.dumps(export)
