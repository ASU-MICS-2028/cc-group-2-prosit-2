"""TURN relay credentials: short-lived, made from TURN_SECRET, checkable the way coturn checks them."""
import base64
import hashlib
import hmac
import time


def test_stun_only_when_no_relay(client, login, monkeypatch):
    monkeypatch.delenv("TURN_HOST", raising=False)
    data = client.get("/calls/ice-servers", headers=login("chv1")).json()
    assert data == {"ice_servers": [{"urls": "stun:stun.l.google.com:19302"}], "relay": False}


def test_relay_credentials(client, login, monkeypatch):
    monkeypatch.setenv("TURN_HOST", "203.0.113.10")
    monkeypatch.setenv("TURN_SECRET", "test-turn-secret")
    data = client.get("/calls/ice-servers", headers=login("nurse1")).json()
    assert data["relay"] is True
    turn = data["ice_servers"][1]
    assert turn["urls"] == ["turn:203.0.113.10:3478?transport=udp", "turn:203.0.113.10:3478?transport=tcp"]

    # What coturn does: recompute the HMAC from the shared secret and check the expiry
    expiry, _user_id = turn["username"].split(":")
    expected = base64.b64encode(hmac.new(b"test-turn-secret", turn["username"].encode(), hashlib.sha1).digest()).decode()
    assert turn["credential"] == expected
    assert time.time() < int(expiry) <= time.time() + 4 * 3600 + 5
    assert "test-turn-secret" not in str(data)  # the secret itself never leaves the server


def test_only_call_roles(client, login):
    assert client.get("/calls/ice-servers", headers=login("ghs1")).status_code == 403
    assert client.get("/calls/ice-servers").status_code == 401
