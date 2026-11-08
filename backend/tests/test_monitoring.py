"""Admin system health: CloudWatch alarm states (faked here, since tests have no AWS)."""
from datetime import datetime, timezone

import monitoring


def fake_alarm(name, state):
    return {"AlarmName": name, "AlarmDescription": f"About {name}", "StateValue": state,
            "StateReason": "Threshold crossed" if state == "ALARM" else "",
            "StateUpdatedTimestamp": datetime(2026, 11, 8, 14, 5, tzinfo=timezone.utc)}


def test_only_admin(client, login):
    for user in ["chv1", "nurse1", "doctor1", "pharm1", "ghs1"]:
        assert client.get("/admin/system-health", headers=login(user)).status_code == 403


def test_laptop_has_no_cloud_monitoring(client, login, audit):
    data = client.get("/admin/system-health", headers=login("admin1")).json()
    assert data == {"available": False, "alarms": []}
    assert "view_system_health" in audit()


def test_cloud_alarms_firing_first(client, login, monkeypatch):
    monkeypatch.setenv("APP_SECRET_ID", "healthconnect/app")
    monkeypatch.setattr(monitoring, "read_alarms", lambda: [fake_alarm("hc-api-5xx", "OK"), fake_alarm("hc-db-storage", "ALARM")])
    data = client.get("/admin/system-health", headers=login("admin1")).json()
    assert data["available"] is True
    assert [(a["name"], a["state"]) for a in data["alarms"]] == [("hc-db-storage", "ALARM"), ("hc-api-5xx", "OK")]
    assert data["alarms"][0]["since"] == "2026-11-08 14:05"


def test_monitoring_unreachable_does_not_break_screen(client, login, monkeypatch):
    def broken():
        raise RuntimeError("no route to CloudWatch")
    monkeypatch.setenv("APP_SECRET_ID", "healthconnect/app")
    monkeypatch.setattr(monitoring, "read_alarms", broken)
    res = client.get("/admin/system-health", headers=login("admin1"))
    assert res.status_code == 200 and res.json()["error"] is True
