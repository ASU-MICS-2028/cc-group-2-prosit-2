"""End-to-end encryption: the server only stores locked keys, and only for the patient's care team.

The real locking happens in the browser (frontend/src/e2eCrypto.js, tested with Vitest).
Here the keys are stand-in strings: the server never opens them, it only decides who gets which copy.
"""
import base64
import os

from tests.test_photos import refer

KEY = {"public_key": "{\"kty\":\"RSA\",\"n\":\"" + "A" * 60 + "\"}", "wrapped_private": "W" * 80,
       "salt": "S" * 24, "iv": "I" * 16}


def locked(name):
    return "locked-for-" + name + "-" + "x" * 50


def test_my_key_backup(client, login):
    chv, ghs = login("chv1"), login("ghs1")
    assert client.get("/e2e/my-key", headers=chv).status_code == 404
    assert client.put("/e2e/my-key", headers=chv, json=KEY).status_code == 200
    assert client.get("/e2e/my-key", headers=chv).json()["wrapped_private"] == "W" * 80
    assert client.put("/e2e/my-key", headers=chv, json=KEY).status_code == 409  # never overwritten by accident
    assert client.post("/e2e/my-key/rewrap", headers=chv, json={**{k: KEY[k] for k in ["salt", "iv"]}, "wrapped_private": "N" * 80}).status_code == 200
    assert client.get("/e2e/my-key", headers=chv).json()["wrapped_private"] == "N" * 80
    assert client.put("/e2e/my-key", headers=ghs, json=KEY).status_code == 403  # GHS is never on a care team


def test_patient_key_shared_with_care_team_only(client, login, make_patient, audit):
    chv, nurse, nurse2, doctor = login("chv1"), login("nurse1"), login("nurse2"), login("doctor1")
    patient = make_patient(chv)
    pid = patient["id"]
    for who in [chv, nurse, nurse2]:
        client.put("/e2e/my-key", headers=who, json=KEY)
    assert client.get(f"/patients/{pid}/e2e-key", headers=chv).json()["detail"] == "No key yet"

    # The CHV makes the patient key and must keep a copy
    me = client.get("/auth/me", headers=chv).json()["id"]
    nurse_id = client.get("/auth/me", headers=nurse).json()["id"]
    nurse2_id = client.get("/auth/me", headers=nurse2).json()["id"]
    assert client.post(f"/patients/{pid}/e2e-keys", headers=chv, json={"grants": [{"user_id": nurse_id, "wrapped_key": locked("n")}]}).status_code == 400
    assert client.post(f"/patients/{pid}/e2e-keys", headers=chv, json={"grants": [{"user_id": me, "wrapped_key": locked("chv")}]}).status_code == 200
    assert client.get(f"/patients/{pid}/e2e-key", headers=chv).json() == {"wrapped_key": locked("chv")}

    # Before a referral the nurse is not on the team: cannot get a copy, and the CHV cannot give one
    assert client.get(f"/patients/{pid}/e2e-key", headers=nurse).status_code == 404
    assert client.post(f"/patients/{pid}/e2e-keys", headers=chv, json={"grants": [{"user_id": nurse_id, "wrapped_key": locked("n")}]}).status_code == 400
    refer(client, chv, patient)

    # After the referral the nurse is on the team, and the CHV's phone sees she needs a copy
    missing = client.get(f"/patients/{pid}/e2e-missing", headers=chv).json()
    assert [m["user_id"] for m in missing] == [nurse_id] and missing[0]["public_key"] == KEY["public_key"]
    waiting = client.get(f"/patients/{pid}/e2e-key", headers=nurse)
    assert waiting.status_code == 404 and "Waiting for the care team" in waiting.json()["detail"]
    assert client.post(f"/patients/{pid}/e2e-keys", headers=nurse, json={"grants": [{"user_id": nurse_id, "wrapped_key": locked("n")}]}).status_code == 403  # cannot give herself one
    assert client.post(f"/patients/{pid}/e2e-keys", headers=chv, json={"grants": [{"user_id": nurse_id, "wrapped_key": locked("n")}]}).json() == {"added": 1}
    assert client.get(f"/patients/{pid}/e2e-key", headers=nurse).json() == {"wrapped_key": locked("n")}
    assert client.get(f"/patients/{pid}/e2e-missing", headers=chv).json() == []

    # Outsiders: another facility's nurse, a doctor not yet involved, GHS
    assert client.get(f"/patients/{pid}/e2e-key", headers=nurse2).status_code == 404
    assert client.post(f"/patients/{pid}/e2e-keys", headers=chv, json={"grants": [{"user_id": nurse2_id, "wrapped_key": locked("n2")}]}).status_code == 400
    assert client.get(f"/patients/{pid}/e2e-key", headers=doctor).status_code == 404
    assert client.get(f"/patients/{pid}/e2e-key", headers=login("ghs1")).status_code == 403
    assert {"e2e_key_made", "e2e_key_shared", "access_denied"} <= set(audit())

    # A new key pair (e.g. after a password reset) makes the nurse's old copy useless, so it is removed
    assert client.put("/e2e/my-key", headers=nurse, json={**KEY, "replace": True}).status_code == 200
    assert client.get(f"/patients/{pid}/e2e-key", headers=nurse).status_code == 404
    assert [m["user_id"] for m in client.get(f"/patients/{pid}/e2e-missing", headers=chv).json()] == [nurse_id]


def test_encrypted_notes_and_photos_stored_as_given(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv)
    note = "e2e:v1:" + base64.b64encode(os.urandom(1500)).decode()  # a long locked note
    res = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"symptoms": ["fever"], "notes": note})
    assert res.status_code == 200 and res.json()["observation"]["notes"] == note
    plain_too_long = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"symptoms": ["fever"], "notes": "a" * 600})
    assert plain_too_long.status_code == 422

    blob = os.urandom(5000)  # what a locked photo looks like to the server: random bytes
    body = {"kind": "wound", "caption": "e2e:v1:" + "c" * 300, "consent": True,
            "image": base64.b64encode(blob).decode(), "encrypted": True}
    url = f"/patients/{patient['id']}/photos"
    assert client.post(url, headers=chv, json=body).status_code == 200
    assert client.post(url, headers=chv, json={**body, "encrypted": False, "caption": "Leg"}).status_code == 400  # not a JPEG
    assert client.post(url, headers=chv, json={**body, "encrypted": False}).status_code == 422  # typed captions: 200 at most
    photo = client.get(url, headers=chv).json()[0]
    assert photo["encrypted"] == 1
    got = client.get(f"/photos/{photo['id']}", headers=chv)
    assert got.content == blob and got.headers["content-type"] == "application/octet-stream"
