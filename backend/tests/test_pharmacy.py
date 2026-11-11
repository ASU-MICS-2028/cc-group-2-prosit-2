"""Pharmacist role, drug stock and e-prescriptions."""
import database
from auth import hash_password
from seed_demo_data import create_demo_data, create_demo_stock


def drug_id(client, headers, name_start):
    return next(d["id"] for d in client.get("/drugs", headers=headers).json() if d["name"].startswith(name_start))


def stock_of(client, pharm, name_start):
    return next(s for s in client.get("/pharmacy/stock", headers=pharm).json() if s["name"].startswith(name_start))


def doctor_referral(client, login, make_patient):
    """CHV -> nurse -> doctor at Test District Hospital (the pharmacy of pharm1). Returns the doctor's referral id."""
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv, full_name="Test Patient Rx")
    obs = client.post(f"/patients/{patient['id']}/visit", headers=chv, json={"symptoms": ["convulsions"]}).json()["observation"]
    client.post(f"/observations/{obs['id']}/referral", headers=chv)
    rid = client.get("/referrals", headers=nurse).json()[0]["id"]
    client.post(f"/referrals/{rid}/status", headers=nurse, json={"status": "arrived"})
    client.post(f"/referrals/{rid}/escalate", headers=nurse,
                json={"facility": "Test District Hospital", "reason": "Needs doctor review"})
    return client.get("/referrals", headers=login("doctor1")).json()[0]["id"]


def test_admin_can_create_pharmacist_with_facility(client, login):
    admin = login("admin1")
    body = {"username": "pharm9", "full_name": "Pharmacist Nine", "role": "pharmacist"}
    assert client.post("/admin/users", headers=admin, json=body).status_code == 422  # no facility
    body["facility"] = "Test District Hospital"
    assert client.post("/admin/users", headers=admin, json=body).status_code == 200


def test_only_the_right_roles(client, login):
    chv, doctor, pharm, ghs = login("chv1"), login("doctor1"), login("pharm1"), login("ghs1")
    assert client.get("/pharmacy/stock", headers=chv).status_code == 403
    assert client.get("/pharmacy/stock", headers=doctor).status_code == 403
    assert client.post("/pharmacy/stock/1/receive", headers=doctor, json={"quantity": 5}).status_code == 403
    assert client.post("/referrals/1/prescriptions", headers=pharm,
                       json={"items": [{"drug_id": 1, "quantity": 1, "instructions": "once"}]}).status_code == 403
    assert client.get("/surveillance/stock", headers=pharm).status_code == 403
    assert client.get("/surveillance/stock", headers=ghs).status_code == 200


def test_receive_adjust_and_history(client, login, audit):
    pharm = login("pharm1")
    stock = client.get("/pharmacy/stock", headers=pharm).json()
    assert len(stock) == 17 and all(s["status"] == "out" for s in stock)  # starter list, nothing on the shelf yet

    amox = drug_id(client, pharm, "Amoxicillin")
    assert client.post(f"/pharmacy/stock/{amox}/receive", headers=pharm, json={"quantity": 500, "note": "Delivery"}).json() == {"quantity": 500}
    assert stock_of(client, pharm, "Amoxicillin")["status"] == "ok"
    # An adjustment needs a reason
    assert client.post(f"/pharmacy/stock/{amox}/adjust", headers=pharm, json={"new_quantity": 480}).status_code == 422
    client.post(f"/pharmacy/stock/{amox}/adjust", headers=pharm, json={"new_quantity": 150, "note": "20 expired, recount"})
    assert stock_of(client, pharm, "Amoxicillin")["status"] == "low"  # 150 <= reorder level 200

    history = client.get("/pharmacy/history", headers=pharm).json()
    assert [(h["reason"], h["change"], h["quantity_after"]) for h in history] == [("adjusted", -350, 150), ("received", 500, 500)]
    assert "stock_received" in audit() and "stock_adjusted" in audit()


def test_prescribe_and_dispense_all_or_nothing(client, login, make_patient, audit):
    doctor, pharm = login("doctor1"), login("pharm1")
    rid = doctor_referral(client, login, make_patient)
    amox, para = drug_id(client, doctor, "Amoxicillin"), drug_id(client, doctor, "Paracetamol")
    items = [{"drug_id": amox, "quantity": 15, "instructions": "1 tablet 3 times a day for 5 days"},
             {"drug_id": para, "quantity": 10, "instructions": "1 tablet when needed for fever"}]
    rx_id = client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={"items": items}).json()["id"]

    waiting = client.get("/pharmacy/prescriptions", headers=pharm).json()[0]
    assert waiting["status"] == "pending" and waiting["full_name"] == "Test Patient Rx"
    assert "possible_conditions" not in waiting and "notes" not in waiting["items"][0]  # no clinical history

    # Only paracetamol in stock: refused, and NOTHING changes (no half-dispensed prescription)
    client.post(f"/pharmacy/stock/{para}/receive", headers=pharm, json={"quantity": 100})
    res = client.post(f"/pharmacy/prescriptions/{rx_id}/dispense", headers=pharm)
    assert res.status_code == 409 and "Amoxicillin" in res.json()["detail"]
    assert stock_of(client, pharm, "Paracetamol")["quantity"] == 100

    client.post(f"/pharmacy/stock/{amox}/receive", headers=pharm, json={"quantity": 20})
    assert client.post(f"/pharmacy/prescriptions/{rx_id}/dispense", headers=pharm).status_code == 200
    assert stock_of(client, pharm, "Amoxicillin")["quantity"] == 5
    assert stock_of(client, pharm, "Paracetamol")["quantity"] == 90
    assert client.post(f"/pharmacy/prescriptions/{rx_id}/dispense", headers=pharm).status_code == 409  # not twice
    dispensed = [h for h in client.get("/pharmacy/history", headers=pharm).json() if h["reason"] == "dispensed"]
    assert sorted(h["change"] for h in dispensed) == [-15, -10] and all(h["prescription_id"] == rx_id for h in dispensed)
    assert client.get(f"/referrals/{rid}/prescriptions", headers=doctor).json()[0]["status"] == "dispensed"
    assert "dispense_prescription" in audit()


def test_bad_prescriptions_and_cancel(client, login, make_patient):
    doctor = login("doctor1")
    rid = doctor_referral(client, login, make_patient)
    amox = drug_id(client, doctor, "Amoxicillin")
    item = {"drug_id": amox, "quantity": 5, "instructions": "twice a day"}
    assert client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={"items": [item, item]}).status_code == 422
    assert client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={"items": []}).status_code == 422
    assert client.post(f"/referrals/{rid}/prescriptions", headers=doctor,
                       json={"items": [{**item, "drug_id": 99999}]}).status_code == 422
    rx_id = client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={"items": [item]}).json()["id"]
    assert client.post(f"/prescriptions/{rx_id}/cancel", headers=doctor).status_code == 200
    assert client.post(f"/prescriptions/{rx_id}/cancel", headers=doctor).status_code == 409
    assert client.post(f"/pharmacy/prescriptions/{rx_id}/dispense", headers=login("pharm1")).status_code == 409


def test_other_facility_sees_nothing(client, login, make_patient, audit):
    conn = database.get_db()
    conn.execute("INSERT INTO users (username, password_hash, role, full_name, facility) VALUES (?, ?, 'pharmacist', ?, ?)",
                 ("pharm_other", hash_password("Demo@1234"), "Other Pharmacist", "Other Test Clinic"))
    conn.commit()
    conn.close()
    doctor, other = login("doctor1"), login("pharm_other")
    rid = doctor_referral(client, login, make_patient)
    item = {"drug_id": drug_id(client, doctor, "Paracetamol"), "quantity": 5, "instructions": "when needed"}
    rx_id = client.post(f"/referrals/{rid}/prescriptions", headers=doctor, json={"items": [item]}).json()["id"]

    assert client.get("/pharmacy/prescriptions", headers=other).json() == []
    assert client.post(f"/pharmacy/prescriptions/{rx_id}/dispense", headers=other).status_code == 404
    assert "access_denied" in audit()
    # A doctor cannot prescribe on another facility's referral either
    assert client.post("/referrals/99999/prescriptions", headers=doctor, json={"items": [item]}).status_code == 404


def test_ghs_sees_stock_outs_by_district_only(client, login):
    conn = database.get_db()
    create_demo_data(conn)
    assert create_demo_stock(conn) == 6
    assert create_demo_stock(conn) == 0  # only once: never overwrites real changes
    conn.commit()
    conn.close()

    data = client.get("/surveillance/stock", headers=login("ghs1")).json()
    tamale = next(d for d in data["districts"] if d["district"] == "Tamale Metropolitan")
    ors = next(x for x in tamale["drugs"] if x["name"].startswith("Oral rehydration"))
    assert ors["out"] == 1 and ors["condition"] == "cholera"
    text = str(data)
    assert "Demo Patient" not in text and "Comfort Azure" not in text  # facilities counted, nobody named
