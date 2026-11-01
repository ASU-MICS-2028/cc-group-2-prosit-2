"""GHS dashboard and DHIMS2 export: totals only, never names."""
import json

import pytest

import database
from seed_demo_data import create_demo_data, keep_demo_data_current


@pytest.fixture
def demo_data(client):
    conn = database.get_db()
    create_demo_data(conn)  # ~800 fake visits, cholera spike in Tamale
    conn.commit()
    conn.close()


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


# ---------- 2-week outbreak forecast (forecast.py: statistics, not ML) ----------

def test_poisson_chance():
    from forecast import chance_at_least
    assert chance_at_least(5, 0) == 0
    assert chance_at_least(0, 3) == pytest.approx(1)  # "0 or more" is certain
    assert chance_at_least(1, 2) == pytest.approx(1 - 2.718281828 ** -2)  # 1 - chance of zero
    assert chance_at_least(20, 10) < 0.01 < chance_at_least(10, 10) < chance_at_least(5, 10)


def test_forecast_follows_the_trend():
    from forecast import forecast
    rising = forecast([12, 6, 3, 3, 2, 2, 2, 2], outbreak_level=5)
    assert rising["direction"] == "rising" and rising["chance"] > 0.9
    falling = forecast([1, 3, 5, 7, 7, 7, 7, 7], outbreak_level=10)
    assert falling["direction"] == "falling" and falling["chance"] < 0.01
    assert falling["expected_next_2_weeks"] == 0  # never below zero
    steady = forecast([10, 10, 10, 10, 10, 10, 10, 10], outbreak_level=20)
    assert steady["direction"] == "steady" and steady["expected_next_2_weeks"] == 20


def test_dashboard_forecast(client, login, demo_data):
    forecasts = client.get("/surveillance/summary", headers=login("ghs1")).json()["forecasts"]
    top = forecasts[0]
    assert (top["district"], top["condition"]) == ("Tamale Metropolitan", "cholera")
    assert top["chance"] > 0.9 and top["direction"] == "rising"
    assert all(f["condition"] != "hypertension" for f in forecasts)  # not infectious: no outbreak forecast
    assert all(f["expected_next_2_weeks"] == "<5" or f["expected_next_2_weeks"] >= 5 for f in forecasts)


def test_demo_data_stays_current(client, login, make_patient, demo_data):
    chv = login("chv1")
    make_patient(chv, full_name="Test Patient Real")
    ghs = login("ghs1")
    before = client.get("/surveillance/summary", headers=ghs).json()
    keep_demo_data_current()  # what the backend does every 10 minutes
    after = client.get("/surveillance/summary", headers=ghs).json()
    assert before["districts"] == after["districts"] and before["forecasts"] == after["forecasts"]  # same picture
    names = [r["full_name"] for r in database.get_db().execute("SELECT full_name FROM patients")]
    assert "Test Patient Real" in names  # real patients untouched


def test_no_demo_data_is_created_on_a_real_database(client):
    keep_demo_data_current()
    assert database.get_db().execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0
