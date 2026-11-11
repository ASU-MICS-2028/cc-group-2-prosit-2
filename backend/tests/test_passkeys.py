"""Fingerprint sign-in (WebAuthn passkeys), tested with a software 'phone' that really signs."""
import hashlib
import json
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url

ORIGIN = "http://localhost:5173"
RP_ID = "localhost"


class SoftPhone:
    """Plays the phone's part: keeps a private key, signs challenges (fingerprint 'always OK')."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = b"test-credential-" + bytes(8)
        self.count = 0

    def client_data(self, kind, challenge):
        return json.dumps({"type": kind, "challenge": challenge, "origin": ORIGIN, "crossOrigin": False}).encode()

    def register(self, options):
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        auth_data = (hashlib.sha256(RP_ID.encode()).digest() + bytes([0x45]) + struct.pack(">I", 0)
                     + bytes(16) + struct.pack(">H", len(self.cred_id)) + self.cred_id + cose)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = bytes_to_base64url(self.cred_id)
        return {"id": cid, "rawId": cid, "type": "public-key", "response": {
            "clientDataJSON": bytes_to_base64url(self.client_data("webauthn.create", options["challenge"])),
            "attestationObject": bytes_to_base64url(attestation)}}

    def sign_in(self, options, user_id):
        self.count += 1
        client_data = self.client_data("webauthn.get", options["challenge"])
        auth_data = hashlib.sha256(RP_ID.encode()).digest() + bytes([0x05]) + struct.pack(">I", self.count)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.cred_id)
        return {"id": cid, "rawId": cid, "type": "public-key", "response": {
            "clientDataJSON": bytes_to_base64url(client_data), "authenticatorData": bytes_to_base64url(auth_data),
            "signature": bytes_to_base64url(signature), "userHandle": bytes_to_base64url(str(user_id).encode())}}


def test_turn_on_then_sign_in_with_fingerprint(client, login, audit):
    chv = login("chv1")
    phone = SoftPhone()
    assert client.post("/auth/passkey/register/options", json={"origin": ORIGIN}).status_code in (401, 403)  # must be signed in
    options = client.post("/auth/passkey/register/options", headers=chv, json={"origin": ORIGIN}).json()
    assert options["rp"]["id"] == RP_ID and options["authenticatorSelection"]["userVerification"] == "required"
    res = client.post("/auth/passkey/register/verify", headers=chv,
                      json={"origin": ORIGIN, "credential": phone.register(options), "label": "Test phone"})
    assert res.status_code == 200, res.text
    assert client.get("/auth/passkeys", headers=chv).json()[0]["label"] == "Test phone"

    # Sign in: no username, no password
    options = client.post("/auth/passkey/login/options", json={"origin": ORIGIN}).json()
    signed = phone.sign_in(options, 1)
    res = client.post("/auth/passkey/login/verify", json={"origin": ORIGIN, "credential": signed})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["user"]["username"] == "chv1" and data["token"] and data["offline_key"]
    assert client.get("/patients", headers={"Authorization": f"Bearer {data['token']}"}).status_code == 200
    assert "login_passkey" in audit()

    # The same signed answer cannot be used twice (the challenge is gone)
    assert client.post("/auth/passkey/login/verify", json={"origin": ORIGIN, "credential": signed}).status_code == 400


def test_wrong_key_and_unknown_site_refused(client, login):
    chv = login("chv1")
    phone = SoftPhone()
    options = client.post("/auth/passkey/register/options", headers=chv, json={"origin": ORIGIN}).json()
    client.post("/auth/passkey/register/verify", headers=chv, json={"origin": ORIGIN, "credential": phone.register(options)})
    thief = SoftPhone()  # same credential id, different private key
    options = client.post("/auth/passkey/login/options", json={"origin": ORIGIN}).json()
    res = client.post("/auth/passkey/login/verify", json={"origin": ORIGIN, "credential": thief.sign_in(options, 1)})
    assert res.status_code == 401
    assert client.post("/auth/passkey/login/options", json={"origin": "https://evil.example"}).status_code == 400


def test_disabled_account_cannot_use_fingerprint(client, login):
    chv, admin = login("chv1"), login("admin1")
    phone = SoftPhone()
    options = client.post("/auth/passkey/register/options", headers=chv, json={"origin": ORIGIN}).json()
    client.post("/auth/passkey/register/verify", headers=chv, json={"origin": ORIGIN, "credential": phone.register(options)})
    users = client.get("/admin/users", headers=admin).json()["users"]
    chv_id = next(u["id"] for u in users if u["username"] == "chv1")
    assert client.post(f"/admin/users/{chv_id}/active", headers=admin, json={"active": False}).status_code == 200
    options = client.post("/auth/passkey/login/options", json={"origin": ORIGIN}).json()
    res = client.post("/auth/passkey/login/verify", json={"origin": ORIGIN, "credential": phone.sign_in(options, chv_id)})
    assert res.status_code == 403
