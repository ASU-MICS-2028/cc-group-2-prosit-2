"""Household surveys: CHV submits without names, GHS sees district percentages only."""
import json

ALL_YES = {c: True for c in ["bed_nets", "safe_water", "latrine", "long_cough", "child_no_net", "diarrhoea"]}


def test_chv_submits_and_ghs_sees_percentages(client, login):
    chv, ghs = login("chv1"), login("ghs1")
    assert client.post("/surveys", headers=chv, json={"people": 4, "answers": {"bed_nets": True}}).status_code == 400
    for i in range(5):
        answers = {**ALL_YES, "latrine": i < 2}  # 2 of 5 households have a latrine
        assert client.post("/surveys", headers=chv, json={"community": "Zuarungu", "people": 5, "answers": answers}).status_code == 200
    assert client.get("/chv/surveys", headers=chv).json() == {"last_30_days": 5}
    assert client.get("/surveillance/surveys", headers=chv).status_code == 403
    data = client.get("/surveillance/surveys", headers=ghs).json()
    row = data["districts"][0]
    assert row["district"] == "Bolgatanga Municipal" and row["households"] == 5
    assert row["yes_pct"]["latrine"] == 40 and row["yes_pct"]["bed_nets"] == 100
    assert "Zuarungu" not in json.dumps(data)  # community is not shown to GHS


def test_small_numbers_hidden(client, login):
    chv, ghs = login("chv1"), login("ghs1")
    client.post("/surveys", headers=chv, json={"people": 3, "answers": ALL_YES})
    row = client.get("/surveillance/surveys", headers=ghs).json()["districts"][0]
    assert row["households"] == "<5" and row["yes_pct"]["latrine"] is None
