"""E-prescriptions for outside pharmacies, and the fraud/safety checks (rx_rules.py)."""
import json

import pytest

import database
import eprescription
import rx_rules
from tests.test_pharmacy import doctor_referral, drug_id, stock_of


@pytest.fixture(autouse=True)
def forget_wrong_codes():
    """The wrong-code counter lives in memory: start every test with a clean one."""
    eprescription.wrong_codes.clear()


def prescribe(client, doctor, rid, drug, quantity, notes="", duplicate_reason=""):
    return client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={
        "items": [{"drug_id": drug, "quantity": quantity, "instructions": "As directed"}],
        "notes": notes, "duplicate_reason": duplicate_reason})


def flags(client, login):
    return client.get("/surveillance/prescription-flags", headers=login("ghs1")).json()


def test_outside_pharmacy_checks_and_dispenses_once(client, login, make_patient, audit):
    doctor, pharm = login("doctor1"), login("pharm1")
    rid = doctor_referral(client, login, make_patient)
    amox = drug_id(client, doctor, "Amoxicillin")
    res = prescribe(client, doctor, rid, amox, 15)
    assert res.status_code == 200
    code = res.json()["code"]
    assert len(code) == 9 and code[4] == "-"

    # Anyone with the code (no account) sees it; typed in lower case without the dash works too
    seen = client.get(f"/rx/{code.replace('-', '').lower()}")
    assert seen.status_code == 200
    data = seen.json()
    assert data["status"] == "valid" and data["items"][0]["quantity"] == 15
    assert data["patient"]["initials"] == "T. P. R." and data["facility"] == "Test District Hospital"
    assert "Test Patient Rx" not in json.dumps(data)  # initials, age and sex only

    body = {"pharmacy": "Sunrise Community Pharmacy", "licence": "pc/12345", "pharmacist": "Ama Mensah", "checked_patient": True}
    assert client.post(f"/rx/{code}/dispense", json={**body, "checked_patient": False}).status_code == 400
    assert client.post(f"/rx/{code}/dispense", json=body).status_code == 200
    again = client.post(f"/rx/{code}/dispense", json={**body, "pharmacy": "Another Pharmacy"})
    assert again.status_code == 409 and "dispensed" in again.json()["detail"]  # a second pharmacy is refused
    assert client.get(f"/rx/{code}").json()["dispensed_where"] == "Sunrise Community Pharmacy"

    # Our own pharmacy sees it was dispensed elsewhere, cannot dispense it, and its stock is unchanged
    rx = client.get("/pharmacy/prescriptions", headers=pharm).json()[0]
    assert rx["status"] == "dispensed" and rx["outside_pharmacy"] == "Sunrise Community Pharmacy" and rx["outside_licence"] == "PC/12345"
    assert client.post(f"/pharmacy/prescriptions/{rx['id']}/dispense", headers=pharm).status_code == 409
    assert stock_of(client, pharm, "Amoxicillin")["quantity"] == 0
    assert {"rx_checked", "rx_dispensed_outside"} <= set(audit())


def test_quantity_limit_and_controlled_drugs(client, login, make_patient):
    doctor = login("doctor1")
    rid = doctor_referral(client, login, make_patient)
    para, tramadol = drug_id(client, doctor, "Paracetamol"), drug_id(client, doctor, "Tramadol")
    too_many = prescribe(client, doctor, rid, para, 600)  # a typo for 60
    assert too_many.status_code == 422 and "at most 60" in too_many.json()["detail"]

    no_reason = prescribe(client, doctor, rid, tramadol, 10)
    assert no_reason.status_code == 422 and "controlled" in no_reason.json()["detail"]
    ok = prescribe(client, doctor, rid, tramadol, 10, notes="Severe pain after fracture, 5 days")
    assert ok.status_code == 200
    assert ok.json()["valid_until"][:10] == client.get(f"/rx/{ok.json()['code']}").json()["valid_until"][:10]
    rx = client.get(f"/referrals/{rid}/prescriptions", headers=doctor).json()[0]
    assert rx["items"][0]["controlled"] is True
    assert [f["kind"] for f in flags(client, login)] == ["controlled"]


def test_duplicate_needs_a_reason(client, login, make_patient):
    doctor = login("doctor1")
    rid = doctor_referral(client, login, make_patient)
    amox = drug_id(client, doctor, "Amoxicillin")
    assert prescribe(client, doctor, rid, amox, 15).status_code == 200
    dup = prescribe(client, doctor, rid, amox, 15)
    assert dup.status_code == 409 and "Already prescribed" in dup.json()["detail"] and "give a reason" in dup.json()["detail"]
    assert prescribe(client, doctor, rid, amox, 15, duplicate_reason="First pack lost in flood").status_code == 200
    flag = flags(client, login)[0]
    assert flag["kind"] == "duplicate" and "flood" in flag["detail"] and flag["doctor"] == "Dr Emmanuel Abugri"

    # A cancelled prescription does not count as a duplicate
    rid_rx = client.get(f"/referrals/{rid}/prescriptions", headers=doctor).json()
    for rx in rid_rx:
        client.post(f"/prescriptions/{rx['id']}/cancel", headers=doctor)
    assert prescribe(client, doctor, rid, amox, 15).status_code == 200


def test_expired_prescription_refused_everywhere(client, login, make_patient):
    doctor, pharm = login("doctor1"), login("pharm1")
    rid = doctor_referral(client, login, make_patient)
    res = prescribe(client, doctor, rid, drug_id(client, doctor, "Paracetamol"), 20)
    conn = database.get_db()
    conn.execute("UPDATE prescriptions SET valid_until = '2020-01-01 00:00:00' WHERE id = ?", (res.json()["id"],))
    conn.commit()
    conn.close()
    code = res.json()["code"]
    assert client.get(f"/rx/{code}").json()["status"] == "expired"
    body = {"pharmacy": "Sunrise Pharmacy", "licence": "PC/1", "pharmacist": "Ama Mensah", "checked_patient": True}
    late = client.post(f"/rx/{code}/dispense", json=body)
    assert late.status_code == 409 and "expired" in late.json()["detail"]
    assert client.get("/pharmacy/prescriptions", headers=pharm).json()[0]["expired"] is True
    assert "expired" in client.post(f"/pharmacy/prescriptions/{res.json()['id']}/dispense", headers=pharm).json()["detail"]


def test_code_guessing_is_blocked_and_flagged(client, login):
    for _ in range(rx_rules.WRONG_CODES_PER_HOUR):
        assert client.get("/rx/2222-2222").status_code == 404
    assert client.get("/rx/3333-3333").status_code == 429  # blocked for an hour
    flag = flags(client, login)[0]
    assert flag["kind"] == "code_guessing" and ("x.x" in flag["detail"] or "…" in flag["detail"])
    assert client.get("/surveillance/prescription-flags", headers=login("doctor1")).status_code == 403


def test_high_volume_of_controlled_drugs_flagged(client, login, make_patient):
    doctor = login("doctor1")
    rid = doctor_referral(client, login, make_patient)
    diazepam = drug_id(client, doctor, "Diazepam")
    for i in range(rx_rules.HIGH_VOLUME_CONTROLLED):
        res = prescribe(client, doctor, rid, diazepam, 5, notes="Anxiety, short course only",
                        duplicate_reason="" if i == 0 else f"Repeat number {i}")
        assert res.status_code == 200
    assert "high_volume" in [f["kind"] for f in flags(client, login)]


def test_qr_code_for_the_slip(client, login, make_patient):
    doctor = login("doctor1")
    rid = doctor_referral(client, login, make_patient)
    res = prescribe(client, doctor, rid, drug_id(client, doctor, "Paracetamol"), 20)
    qr = client.get(f"/prescriptions/{res.json()['id']}/qr.svg", headers=doctor)
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml") and b'xmlns="http://www.w3.org/2000/svg"' in qr.content
    assert client.get(f"/prescriptions/{res.json()['id']}/qr.svg", headers=login("nurse2")).status_code == 403
    assert rx_rules.clean_code("0OIL-1234") is None  # letters we never use are refused straight away
