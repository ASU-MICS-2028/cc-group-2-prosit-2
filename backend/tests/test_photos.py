"""Clinical photos: consent, real image bytes only, need-to-know sharing along the referral chain."""
import base64

JPEG = b"\xff\xd8\xff\xe0" + b"fake jpeg body" * 10
URL = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()


def refer(client, chv, patient):
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)


def test_photo_shared_along_referral_chain_only(client, login, make_patient, audit):
    chv, chv2, nurse, nurse2, pharm, ghs = (login(u) for u in ["chv1", "chv2", "nurse1", "nurse2", "pharm1", "ghs1"])
    patient = make_patient(chv)
    url = f"/patients/{patient['id']}/photos"
    body = {"kind": "wound", "caption": "Leg wound, day 1", "consent": True, "image": URL}
    assert client.post(url, headers=chv, json={**body, "consent": False}).status_code == 400  # no consent, no photo
    assert client.post(url, headers=chv, json=body).status_code == 200
    photos = client.get(url, headers=chv).json()
    assert photos[0]["caption"] == "Leg wound, day 1" and "data" not in photos[0]
    img = client.get(f"/photos/{photos[0]['id']}", headers=chv)
    assert img.status_code == 200 and img.content == JPEG and img.headers["cache-control"] == "no-store"

    # Before a referral the nurse cannot see it; after, the nurse at that facility can (and can add an X-ray)
    assert client.get(url, headers=nurse).status_code == 404
    refer(client, chv, patient)
    assert len(client.get(url, headers=nurse).json()) == 1
    assert client.post(url, headers=nurse, json={**body, "kind": "xray", "caption": "Chest X-ray"}).status_code == 200
    assert {p["kind"] for p in client.get(url, headers=chv).json()} == {"wound", "xray"}  # shared back to the CHV

    for outsider in [chv2, nurse2]:
        assert client.get(url, headers=outsider).status_code == 404
        assert client.get(f"/photos/{photos[0]['id']}", headers=outsider).status_code == 404
    for no_role in [pharm, ghs]:
        assert client.get(url, headers=no_role).status_code == 403
    assert {"upload_photo", "view_photo", "access_denied"} <= set(audit())

    # Only the uploader can delete
    assert client.delete(f"/photos/{photos[0]['id']}", headers=nurse).status_code == 404
    assert client.delete(f"/photos/{photos[0]['id']}", headers=chv).status_code == 200


def test_only_real_images_accepted(client, login, make_patient):
    chv = login("chv1")
    patient = make_patient(chv)
    url = f"/patients/{patient['id']}/photos"
    fake = "data:image/jpeg;base64," + base64.b64encode(b"<script>alert(1)</script>").decode()
    assert client.post(url, headers=chv, json={"kind": "skin", "consent": True, "image": fake}).status_code == 400
    big = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + bytes(500_000)).decode()
    assert client.post(url, headers=chv, json={"kind": "skin", "consent": True, "image": big}).status_code == 400
    assert client.post(url, headers=chv, json={"kind": "selfie", "consent": True, "image": URL}).status_code == 422
