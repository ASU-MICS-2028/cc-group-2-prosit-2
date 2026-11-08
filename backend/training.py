"""Health worker training: read a module, pass a quiz, earn a certificate that expires.

Certificates are HealthConnect training records, simulated: there is no real link to GHS.
Workers see only their own. The GHS officer sees every worker's so it can issue and revoke;
this is staff data only, and patient data stays anonymous for GHS.
"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text
from fees import training_fee_due
from training_list import TRAINING_MODULES

router = APIRouter()

WORKERS = ("chv", "nurse", "doctor", "pharmacist")
PASS_PERCENT = 80
VALID_DAYS = 365
EXPIRING_DAYS = 30  # shown as "expiring soon", and renewal opens
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

CERT_COLUMNS = """c.id, c.user_id, c.code, c.module, c.source, c.note, c.issued_at, c.expires_at, c.revoked_at,
                  c.revoke_reason, issuer.full_name AS issued_by_name"""
CERT_JOIN = "FROM certificates c LEFT JOIN users issuer ON issuer.id = c.issued_by"


class QuizAnswers(BaseModel):
    answers: list[int]


class IssueCertificate(BaseModel):
    module: str
    note: str = Field(min_length=3, max_length=200)  # why, e.g. "completed in-person training"


class RevokeCertificate(BaseModel):
    reason: str = Field(min_length=5, max_length=200)


def get_module(code):
    if code not in TRAINING_MODULES:
        raise HTTPException(status_code=404, detail="Training module not found")
    return TRAINING_MODULES[code]


def describe(row):
    """A certificate row plus its status today. Status is worked out, so it can never be out of date."""
    cert = dict(row)
    cert["title"] = TRAINING_MODULES.get(cert["module"], {}).get("title", cert["module"])
    days_left = (datetime.strptime(cert["expires_at"], TIME_FORMAT) - datetime.strptime(now_text(), TIME_FORMAT)).days
    cert["days_left"] = days_left
    if cert["revoked_at"]:
        cert["status"] = "revoked"
    elif days_left < 0:
        cert["status"] = "expired"
    elif days_left <= EXPIRING_DAYS:
        cert["status"] = "expiring"
    else:
        cert["status"] = "valid"
    return cert


def latest_certificate(conn, user_id, module):
    row = conn.execute(f"SELECT {CERT_COLUMNS} {CERT_JOIN} WHERE c.user_id = ? AND c.module = ? ORDER BY c.id DESC LIMIT 1",
                       (user_id, module)).fetchone()
    return describe(row) if row else None


def create_certificate(conn, user_id, module, source, issued_by=None, note=None):
    issued = datetime.strptime(now_text(), TIME_FORMAT)
    code = "HC-" + secrets.token_hex(4).upper()
    conn.execute(
        "INSERT INTO certificates (code, user_id, module, source, issued_by, note, issued_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (code, user_id, module, source, issued_by, note, issued.strftime(TIME_FORMAT),
         (issued + timedelta(days=VALID_DAYS)).strftime(TIME_FORMAT)),
    )
    return code


@router.get("/training/modules")
def my_training(user=Depends(require_role(*WORKERS))):
    conn = get_db()
    reviews = {r["module"]: r for r in conn.execute(
        "SELECT r.module, r.reviewed_at, u.full_name AS reviewer_name "
        "FROM training_reviews r JOIN users u ON u.id = r.reviewed_by").fetchall()}
    best = {r["module"]: r for r in conn.execute(
        "SELECT module, MAX(score) AS best_score, COUNT(*) AS tries FROM training_attempts WHERE user_id = ? GROUP BY module",
        (user["id"],)).fetchall()}
    certificates = [describe(r) for r in conn.execute(
        f"SELECT {CERT_COLUMNS} {CERT_JOIN} WHERE c.user_id = ? ORDER BY c.id DESC", (user["id"],)).fetchall()]
    fee_due = {code: training_fee_due(conn, user, code) for code in TRAINING_MODULES}
    conn.close()

    modules = []
    for code, module in TRAINING_MODULES.items():
        modules.append({
            "code": code,
            "title": module["title"],
            "body": module["body"],
            # The answers are left out on purpose: anything sent to the phone can be read
            "questions": [{"text": q["text"], "options": q["options"]} for q in module["questions"]],
            "reviewed_at": reviews[code]["reviewed_at"] if code in reviews else None,
            "reviewer_name": reviews[code]["reviewer_name"] if code in reviews else None,
            "best_score": best[code]["best_score"] if code in best else None,
            "tries": best[code]["tries"] if code in best else 0,
            "fee_due": fee_due[code],
            "certificate": next((c for c in certificates if c["module"] == code), None),
        })
    return {"modules": modules, "certificates": certificates, "pass_percent": PASS_PERCENT, "expiring_days": EXPIRING_DAYS}


@router.post("/training/modules/{code}/attempt")
def take_quiz(code: str, body: QuizAnswers, user=Depends(require_role(*WORKERS))):
    module = get_module(code)
    questions = module["questions"]
    if len(body.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Please answer every question")
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM training_reviews WHERE module = ?", (code,)).fetchone():
            raise HTTPException(status_code=400, detail="A nurse or doctor must approve this module first")
        latest = latest_certificate(conn, user["id"], code)
        if latest and latest["status"] == "revoked":
            # Otherwise a retake would quietly undo the officer's decision
            raise HTTPException(status_code=403, detail="This certificate was revoked. Please contact your GHS officer")
        if latest and latest["status"] == "valid":
            raise HTTPException(status_code=400, detail="Your certificate is still valid. You can renew it close to its expiry date")

        if training_fee_due(conn, user, code):
            raise HTTPException(status_code=402, detail="Please pay the training fee first")

        score = sum(given == q["answer"] for given, q in zip(body.answers, questions))
        passed = score * 100 >= PASS_PERCENT * len(questions)
        conn.execute("INSERT INTO training_attempts (user_id, module, score, total, passed, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (user["id"], code, score, len(questions), int(passed), now_text()))
        certificate = create_certificate(conn, user["id"], code, "quiz") if passed else None
        log_access(conn, user["id"], "pass_training" if passed else "fail_training", code)
        conn.commit()
    finally:
        conn.close()
    # Only the score comes back, so the right answers stay private
    return {"score": score, "total": len(questions), "passed": passed, "certificate_code": certificate}


@router.post("/training/modules/{code}/review")
def approve_module(code: str, user=Depends(require_role("nurse", "doctor"))):
    get_module(code)
    conn = get_db()
    if conn.execute("SELECT 1 FROM training_reviews WHERE module = ?", (code,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="This module has already been approved")
    conn.execute("INSERT INTO training_reviews (module, reviewed_by, reviewed_at) VALUES (?, ?, ?)", (code, user["id"], now_text()))
    log_access(conn, user["id"], "approve_training_module", code)
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/training/workers")
def all_workers(user=Depends(require_role("ghs"))):
    conn = get_db()
    placeholders = ", ".join("?" for _ in WORKERS)
    people = conn.execute(
        f"SELECT id, full_name, role, facility, district FROM users WHERE active = 1 AND role IN ({placeholders}) ORDER BY full_name",
        WORKERS).fetchall()
    rows = conn.execute(f"SELECT {CERT_COLUMNS} {CERT_JOIN} ORDER BY c.id").fetchall()
    log_access(conn, user["id"], "view_worker_certificates")
    conn.commit()
    conn.close()

    # Oldest first, so a renewal replaces the older certificate for that module
    latest = {}
    for row in rows:
        latest.setdefault(row["user_id"], {})[row["module"]] = describe(row)

    workers = [{**dict(p), "certificates": list(latest.get(p["id"], {}).values())} for p in people]
    summary = {"valid": 0, "expiring": 0, "expired": 0, "revoked": 0}
    for worker in workers:
        for cert in worker["certificates"]:
            summary[cert["status"]] += 1
    summary["no_certificate"] = sum(not w["certificates"] for w in workers)
    modules = [{"code": code, "title": m["title"]} for code, m in TRAINING_MODULES.items()]
    return {"workers": workers, "summary": summary, "modules": modules}


@router.post("/training/workers/{worker_id}/certificates")
def issue_certificate(worker_id: int, body: IssueCertificate, user=Depends(require_role("ghs"))):
    get_module(body.module)
    conn = get_db()
    try:
        worker = conn.execute("SELECT role, active FROM users WHERE id = ?", (worker_id,)).fetchone()
        if not worker or worker["role"] not in WORKERS or not worker["active"]:
            raise HTTPException(status_code=404, detail="Health worker not found")
        latest = latest_certificate(conn, worker_id, body.module)
        if latest and latest["status"] == "valid":
            raise HTTPException(status_code=400, detail="This worker already holds a valid certificate for this module")
        code = create_certificate(conn, worker_id, body.module, "ghs", user["id"], body.note.strip())
        log_access(conn, user["id"], "issue_certificate", code)
        conn.commit()
    finally:
        conn.close()
    return {"code": code}


@router.post("/training/certificates/{certificate_id}/revoke")
def revoke_certificate(certificate_id: int, body: RevokeCertificate, user=Depends(require_role("ghs"))):
    conn = get_db()
    try:
        cert = conn.execute("SELECT code, revoked_at FROM certificates WHERE id = ?", (certificate_id,)).fetchone()
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        if cert["revoked_at"]:
            raise HTTPException(status_code=400, detail="This certificate is already revoked")
        conn.execute("UPDATE certificates SET revoked_at = ?, revoked_by = ?, revoke_reason = ? WHERE id = ?",
                     (now_text(), user["id"], body.reason.strip(), certificate_id))
        log_access(conn, user["id"], "revoke_certificate", cert["code"])
        conn.commit()
    finally:
        conn.close()
    return {"success": True}
