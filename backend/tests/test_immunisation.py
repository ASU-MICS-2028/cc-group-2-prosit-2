"""Child immunisation tracking: due dates from the Ghana EPI schedule, CHV-only, GHS sees totals."""
import json
from datetime import date, timedelta

from immunisation import card


def test_card_statuses():
    born = date(2026, 1, 1)
    doses = {d["code"]: d for d in card(born.isoformat(), {"bcg": "2026-01-02"}, on=date(2026, 3, 20))}
    assert doses["bcg"]["status"] == "given"
    assert doses["opv0"]["status"] == "overdue"       # due at birth, more than 4 weeks late
    assert doses["penta1"]["due_on"] == "2026-02-12"  # 6 weeks
    assert doses["penta1"]["status"] == "overdue"     # 36 days late
    assert doses["penta2"]["status"] == "due"         # 12 March: due, not yet 4 weeks late
    assert doses["penta3"]["status"] == "upcoming"    # 9 April: 20 days away, more than 2 weeks
    assert doses["mr1"]["status"] == "upcoming"


def test_chv_records_doses(client, login, make_patient, audit):
    chv, other = login("chv1"), login("chv2")
    child = make_patient(chv, full_name="Test Child", age=0, sex="male")
    url = f"/patients/{child['id']}/immunisations"
    assert client.get(url, headers=chv).json() == {"birth_date": None, "schedule": []}
    assert client.post(url, headers=chv, json={"vaccine": "bcg", "given_on": date.today().isoformat()}).status_code == 400

    born = date.today() - timedelta(days=70)
    assert client.post(f"/patients/{child['id']}/birth-date", headers=chv, json={"birth_date": born.isoformat()}).status_code == 200
    assert client.post(f"/patients/{child['id']}/birth-date", headers=chv,
                       json={"birth_date": (date.today() - timedelta(days=6 * 365)).isoformat()}).status_code == 400

    ok = client.post(url, headers=chv, json={"vaccine": "bcg", "given_on": born.isoformat()})
    assert ok.status_code == 200
    assert client.post(url, headers=chv, json={"vaccine": "bcg", "given_on": born.isoformat()}).status_code == 400  # twice
    assert client.post(url, headers=chv, json={"vaccine": "nonsense", "given_on": born.isoformat()}).status_code == 400
    assert client.post(url, headers=chv, json={"vaccine": "opv0", "given_on": (born - timedelta(days=1)).isoformat()}).status_code == 400
    statuses = {d["code"]: d["status"] for d in client.get(url, headers=chv).json()["schedule"]}
    assert statuses["bcg"] == "given" and statuses["opv0"] == "overdue" and statuses["penta2"] == "due"
    assert "record_immunisation" in audit()

    due = client.get("/chv/immunisations-due", headers=chv).json()
    assert due[0]["full_name"] == "Test Child" and "OPV 0 (polio drops)" in due[0]["doses"]
    assert client.get(url, headers=other).status_code == 404  # need-to-know
    assert client.get("/chv/immunisations-due", headers=other).json() == []

    assert client.delete(f"{url}/bcg", headers=chv).status_code == 200
    assert {d["code"]: d["status"] for d in client.get(url, headers=chv).json()["schedule"]}["bcg"] == "overdue"


def test_ghs_sees_district_coverage_only(client, login, make_patient):
    chv, ghs = login("chv1"), login("ghs1")
    for i in range(6):
        child = make_patient(chv, full_name=f"Test Secret Name {i}", age=1, sex="female")
        born = (date.today() - timedelta(days=400)).isoformat()
        client.post(f"/patients/{child['id']}/birth-date", headers=chv, json={"birth_date": born})
        if i < 3:  # half the children had the measles dose
            client.post(f"/patients/{child['id']}/immunisations", headers=chv, json={"vaccine": "mr1", "given_on": born})
    assert client.get("/surveillance/immunisation", headers=chv).status_code == 403
    data = client.get("/surveillance/immunisation", headers=ghs).json()
    assert data == [{"district": "Bolgatanga Municipal", "tracked": 6, "up_to_date_pct": 0, "measles_pct": 50}]
    assert "Secret" not in json.dumps(data)
