"""Training certificates: quiz, expiry, approval, GHS issue and revoke, and who can see what."""
import database
from training_list import TRAINING_MODULES

CODE = "danger_signs"
RIGHT = [q["answer"] for q in TRAINING_MODULES[CODE]["questions"]]


def approve(client, login):
    assert client.post(f"/training/modules/{CODE}/review", headers=login("nurse1")).status_code == 200


def module(client, headers):
    return next(m for m in client.get("/training/modules", headers=headers).json()["modules"] if m["code"] == CODE)


def set_expiry(days_from_now):
    conn = database.get_db()
    from datetime import datetime, timedelta, timezone
    when = (datetime.now(timezone.utc) + timedelta(days=days_from_now)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE certificates SET expires_at = ?", (when,))
    conn.commit()
    conn.close()


def test_access(client, login):
    for user in ["ghs1", "admin1"]:
        assert client.get("/training/modules", headers=login(user)).status_code == 403
    for user in ["chv1", "nurse1", "doctor1", "pharm1"]:
        assert client.get("/training/modules", headers=login(user)).status_code == 200
    for user in ["chv1", "nurse1", "admin1"]:
        assert client.get("/training/workers", headers=login(user)).status_code == 403
    assert client.post(f"/training/modules/{CODE}/review", headers=login("chv1")).status_code == 403


def test_answers_never_reach_the_phone(client, login):
    assert all("answer" not in q for q in module(client, login("chv1"))["questions"])


def test_quiz_needs_approval_then_pass_gives_certificate(client, login):
    chv = login("chv1")
    url = f"/training/modules/{CODE}/attempt"
    assert client.post(url, headers=chv, json={"answers": RIGHT}).status_code == 400  # not approved
    approve(client, login)
    assert client.post(url, headers=chv, json={"answers": RIGHT[:2]}).status_code == 400  # incomplete

    wrong = [(a + 1) % 3 for a in RIGHT]
    failed = client.post(url, headers=chv, json={"answers": wrong}).json()
    assert failed["passed"] is False and failed["certificate_code"] is None and failed["score"] == 0

    four_right = [(RIGHT[0] + 1) % 3] + RIGHT[1:]
    passed = client.post(url, headers=chv, json={"answers": four_right}).json()  # exactly 80%
    assert passed["passed"] is True and passed["certificate_code"].startswith("HC-")
    saved = module(client, chv)
    assert saved["certificate"]["status"] == "valid" and saved["best_score"] == 4 and saved["tries"] == 2
    assert client.post(url, headers=chv, json={"answers": RIGHT}).status_code == 400  # valid: no retake yet


def test_expiry_and_renewal(client, login):
    chv = login("chv1")
    url = f"/training/modules/{CODE}/attempt"
    approve(client, login)
    client.post(url, headers=chv, json={"answers": RIGHT})
    set_expiry(10)
    assert module(client, chv)["certificate"]["status"] == "expiring"
    assert client.post(url, headers=chv, json={"answers": RIGHT}).json()["passed"] is True  # renewal
    set_expiry(-2)
    assert module(client, chv)["certificate"]["status"] == "expired"
    assert len(client.get("/training/modules", headers=chv).json()["certificates"]) == 2  # history kept


def test_ghs_issue_and_revoke(client, login, audit):
    ghs, chv = login("ghs1"), login("chv1")
    data = client.get("/training/workers", headers=ghs).json()
    names = [w["full_name"] for w in data["workers"]]
    assert "Test CHV One" in names and "Test Admin" not in names and "Test GHS Officer" not in names
    worker = next(w for w in data["workers"] if w["full_name"] == "Test CHV One")
    issue = f"/training/workers/{worker['id']}/certificates"

    body = {"module": CODE, "note": "Completed in-person training"}
    assert client.post(issue, headers=ghs, json=body).status_code == 200
    assert client.post(issue, headers=ghs, json=body).status_code == 400  # already valid
    cert = module(client, chv)["certificate"]
    assert cert["source"] == "ghs" and cert["issued_by_name"] == "Test GHS Officer"

    revoke = f"/training/certificates/{cert['id']}/revoke"
    assert client.post(revoke, headers=ghs, json={"reason": "no"}).status_code == 422  # a reason is required
    assert client.post(revoke, headers=chv, json={"reason": "Trying my luck"}).status_code == 403
    assert client.post(revoke, headers=ghs, json={"reason": "Issued in error"}).status_code == 200
    assert client.post(revoke, headers=ghs, json={"reason": "Issued in error"}).status_code == 400
    revoked = module(client, chv)["certificate"]
    assert revoked["status"] == "revoked" and revoked["revoke_reason"] == "Issued in error"

    # A retake must not undo the officer's decision; only GHS can issue again
    approve(client, login)
    assert client.post(f"/training/modules/{CODE}/attempt", headers=chv, json={"answers": RIGHT}).status_code == 403
    assert client.post(issue, headers=ghs, json=body).status_code == 200
    assert client.get("/training/workers", headers=ghs).json()["summary"]["valid"] == 1
    assert {"issue_certificate", "revoke_certificate"} <= set(audit())


def test_issue_rejects_non_workers_and_unknown(client, login):
    ghs = login("ghs1")
    assert client.post("/training/workers/99999/certificates", headers=ghs, json={"module": CODE, "note": "Test"}).status_code == 404
    assert client.post("/training/workers/1/certificates", headers=ghs, json={"module": "nope", "note": "Test"}).status_code == 404
    assert client.post("/training/certificates/99999/revoke", headers=ghs, json={"reason": "Not real"}).status_code == 404


def test_worker_sees_only_their_own(client, login):
    chv1, chv2 = login("chv1"), login("chv2")
    approve(client, login)
    client.post(f"/training/modules/{CODE}/attempt", headers=chv1, json={"answers": RIGHT})
    assert client.get("/training/modules", headers=chv2).json()["certificates"] == []
