"""Equipment tracking: each facility updates its own counts; GHS sees district totals."""
import json


def test_nurse_updates_only_their_own_facility(client, login):
    nurse1, nurse2 = login("nurse1"), login("nurse2")
    rows = client.post("/equipment/bp_monitor", headers=nurse1, json={"working": 2, "broken": 1}).json()
    assert next(r for r in rows if r["item"] == "bp_monitor")["working"] == 2
    other = client.get("/equipment", headers=nurse2).json()
    assert next(r for r in other if r["item"] == "bp_monitor")["working"] == 0


def test_saving_again_replaces_the_count(client, login):
    nurse = login("nurse1")
    client.post("/equipment/thermometer", headers=nurse, json={"working": 2, "broken": 0})
    rows = client.post("/equipment/thermometer", headers=nurse, json={"working": 1, "broken": 1}).json()
    item = next(r for r in rows if r["item"] == "thermometer")
    assert (item["working"], item["broken"]) == (1, 1)


def test_bad_input_and_wrong_roles_are_refused(client, login):
    nurse = login("nurse1")
    assert client.post("/equipment/spaceship", headers=nurse, json={"working": 1, "broken": 0}).status_code == 404
    assert client.post("/equipment/bp_monitor", headers=nurse, json={"working": -1, "broken": 0}).status_code == 422
    for other in ["chv1", "pharm1", "ghs1", "admin1"]:
        assert client.get("/equipment", headers=login(other)).status_code == 403
    assert client.get("/equipment").status_code == 401


def test_ghs_sees_district_totals_only(client, login):
    client.post("/equipment/bp_monitor", headers=login("nurse1"), json={"working": 0, "broken": 2})
    assert client.get("/surveillance/equipment", headers=login("nurse1")).status_code == 403
    data = client.get("/surveillance/equipment", headers=login("ghs1")).json()
    bolga = next(d for d in data["districts"] if d["district"] == "Bolgatanga Municipal")
    item = next(i for i in bolga["items"] if i["item"] == "bp_monitor")
    assert (item["working"], item["broken"], item["facilities_without"]) == (0, 2, 1)
    assert "Mercy Akolgo" not in json.dumps(data) and "Test Health Centre" not in json.dumps(data)
