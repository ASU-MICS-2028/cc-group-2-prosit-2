"""SDG 3 impact dashboard: district totals only, no percentages from tiny numbers."""
import json

import pytest

import database
from seed_demo_data import create_demo_data


@pytest.fixture
def demo_data(client):
    conn = database.get_db()
    create_demo_data(conn)
    conn.commit()
    conn.close()


def test_only_ghs_can_see_impact(client, login):
    for user in ["chv1", "nurse1", "doctor1", "pharm1", "admin1"]:
        assert client.get("/surveillance/impact", headers=login(user)).status_code == 403
    assert client.get("/surveillance/impact", headers=login("ghs1")).status_code == 200
    assert client.get("/surveillance/impact").status_code == 401


def test_no_names_or_references(client, login, make_patient, demo_data):
    make_patient(login("chv1"), full_name="Test Secret Name", phone="0240000000")
    text = json.dumps(client.get("/surveillance/impact", headers=login("ghs1")).json())
    for private in ["Test Secret Name", "Demo Patient", "HC-", "0240000000", "full_name", "patient_id"]:
        assert private not in text


def test_demo_data_fills_every_measure(client, login, demo_data):
    data = client.get("/surveillance/impact", headers=login("ghs1")).json()
    now = data["current"]
    assert now["antenatal"]["percent"] is not None
    assert now["referrals"]["percent"] is not None
    assert now["avg_hours_to_complete"] is not None
    assert now["appointments"]["percent"] is not None
    assert len(data["districts"]) == 5
    assert data["gap"]["highest"]["visits"] >= data["gap"]["lowest"]["visits"]


def test_tiny_numbers_are_hidden_and_give_no_percentage(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv)
    conn = database.get_db()
    conn.execute("UPDATE patients SET pregnant = 1 WHERE id = ?", (patient["id"],))
    conn.commit()
    conn.close()

    data = client.get("/surveillance/impact", headers=login("ghs1")).json()
    assert data["current"]["antenatal"] == {"count": 0, "total": "<5", "percent": None}
    assert data["gap"] is None  # fewer than two districts have enough visits to compare
