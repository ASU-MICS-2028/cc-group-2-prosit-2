"""Child immunisation tracking (FHIR Immunization).

The CHV enters a child's date of birth, then records each dose from the child's health
record book. The app works out every due date from Ghana's EPI schedule and shows which
doses are given, due, overdue or still to come. GHS sees only district totals.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from database import get_db, log_access, now_text
from immunisation_list import CODES, DUE_SOON_DAYS, GRACE_DAYS, MAX_AGE_YEARS, SCHEDULE
from surveillance import SMALL_COUNT, hide_small

router = APIRouter()


class BirthDate(BaseModel):
    birth_date: date


class DoseGiven(BaseModel):
    vaccine: str
    given_on: date


def today():
    return datetime.now(timezone.utc).date()


def card(birth_date, given, on=None):
    """The child's vaccination card: every dose with its due date and status."""
    on = on or today()
    born = date.fromisoformat(birth_date)
    rows = []
    for code, name, age_days, protects in SCHEDULE:
        due = born + timedelta(days=age_days)
        if code in given:
            status = "given"
        elif on > due + timedelta(days=GRACE_DAYS):
            status = "overdue"
        elif on >= due - timedelta(days=DUE_SOON_DAYS):
            status = "due"
        else:
            status = "upcoming"
        rows.append({"code": code, "name": name, "protects": protects, "due_on": due.isoformat(),
                     "status": status, "given_on": given.get(code)})
    return rows


def is_child(birth_date, on=None):
    """Under 5 (365.25 days a year, so 29 February needs no special case)."""
    return bool(birth_date) and ((on or today()) - date.fromisoformat(birth_date)).days < MAX_AGE_YEARS * 365.25


def own_patient(conn, patient_id, user):
    patient = conn.execute("SELECT * FROM patients WHERE id = ? AND chv_id = ?", (patient_id, user["id"])).fetchone()
    if not patient:
        log_access(conn, user["id"], "access_denied", f"patient:{patient_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def doses_given(conn, patient_id):
    return {r["vaccine"]: r["given_on"] for r in
            conn.execute("SELECT vaccine, given_on FROM immunisations WHERE patient_id = ?", (patient_id,))}


@router.get("/patients/{patient_id}/immunisations")
def get_card(patient_id: int, user=Depends(require_role("chv"))):
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    given = doses_given(conn, patient_id)
    log_access(conn, user["id"], "view_immunisations", patient["ref"])
    conn.commit()
    conn.close()
    if not patient["birth_date"]:
        return {"birth_date": None, "schedule": []}
    return {"birth_date": patient["birth_date"], "schedule": card(patient["birth_date"], given)}


@router.post("/patients/{patient_id}/birth-date")
def set_birth_date(patient_id: int, body: BirthDate, user=Depends(require_role("chv"))):
    if body.birth_date > today():
        raise HTTPException(status_code=400, detail="Date of birth cannot be in the future")
    if not is_child(body.birth_date.isoformat()):
        raise HTTPException(status_code=400, detail="Immunisations are tracked for children under 5")
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    years = (today() - body.birth_date).days // 365
    conn.execute("UPDATE patients SET birth_date = ?, age = ? WHERE id = ?", (body.birth_date.isoformat(), years, patient_id))
    log_access(conn, user["id"], "set_birth_date", patient["ref"])
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/patients/{patient_id}/immunisations")
def record_dose(patient_id: int, body: DoseGiven, user=Depends(require_role("chv"))):
    if body.vaccine not in CODES:
        raise HTTPException(status_code=400, detail="Unknown vaccine")
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    if not patient["birth_date"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Enter the child's date of birth first")
    if not (date.fromisoformat(patient["birth_date"]) <= body.given_on <= today()):
        conn.close()
        raise HTTPException(status_code=400, detail="The date given must be between birth and today")
    if conn.execute("SELECT 1 FROM immunisations WHERE patient_id = ? AND vaccine = ?", (patient_id, body.vaccine)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="This dose is already recorded")
    conn.execute("INSERT INTO immunisations (patient_id, vaccine, given_on, recorded_by, created_at) VALUES (?, ?, ?, ?, ?)",
                 (patient_id, body.vaccine, body.given_on.isoformat(), user["id"], now_text()))
    log_access(conn, user["id"], "record_immunisation", f"{patient['ref']} {body.vaccine}")
    conn.commit()
    conn.close()
    return {"success": True}


@router.delete("/patients/{patient_id}/immunisations/{vaccine}")
def undo_dose(patient_id: int, vaccine: str, user=Depends(require_role("chv"))):
    """Correct a dose recorded by mistake."""
    conn = get_db()
    patient = own_patient(conn, patient_id, user)
    conn.execute("DELETE FROM immunisations WHERE patient_id = ? AND vaccine = ?", (patient_id, vaccine))
    log_access(conn, user["id"], "undo_immunisation", f"{patient['ref']} {vaccine}")
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/chv/immunisations-due")
def due_list(user=Depends(require_role("chv"))):
    """The CHV's children with a dose overdue or due in the next two weeks."""
    conn = get_db()
    children = conn.execute("SELECT id, ref, full_name, community, birth_date FROM patients "
                            "WHERE chv_id = ? AND birth_date IS NOT NULL", (user["id"],)).fetchall()
    result = []
    for child in children:
        if not is_child(child["birth_date"]):
            continue
        open_doses = [d for d in card(child["birth_date"], doses_given(conn, child["id"])) if d["status"] in ("overdue", "due")]
        if open_doses:
            result.append({"patient_id": child["id"], "ref": child["ref"], "full_name": child["full_name"],
                           "community": child["community"], "overdue": sum(d["status"] == "overdue" for d in open_doses),
                           "doses": [d["name"] for d in open_doses], "first_due": min(d["due_on"] for d in open_doses)})
    conn.close()
    return sorted(result, key=lambda c: (-c["overdue"], c["first_due"]))


@router.get("/surveillance/immunisation")
def coverage(user=Depends(require_role("ghs"))):
    """Per district: children under 5 tracked, and how many are up to date (no overdue dose)."""
    conn = get_db()
    # Only district + birth date + doses are read: no names, refs or ids leave this function
    children = conn.execute("SELECT id, district, birth_date FROM patients WHERE birth_date IS NOT NULL "
                            "AND district IS NOT NULL").fetchall()
    totals = {}
    for child in children:
        if not is_child(child["birth_date"]):
            continue
        doses = card(child["birth_date"], doses_given(conn, child["id"]))
        t = totals.setdefault(child["district"], {"tracked": 0, "up_to_date": 0, "measles_due": 0, "measles_given": 0})
        t["tracked"] += 1
        t["up_to_date"] += not any(d["status"] == "overdue" for d in doses)
        mr1 = next(d for d in doses if d["code"] == "mr1")
        if mr1["status"] in ("given", "overdue"):  # old enough to count for measles coverage
            t["measles_due"] += 1
            t["measles_given"] += mr1["status"] == "given"
    log_access(conn, user["id"], "view_immunisation_coverage")
    conn.commit()
    conn.close()
    pct = lambda part, whole: round(100 * part / whole) if whole >= SMALL_COUNT else None  # too few to be fair
    return [{"district": d, "tracked": hide_small(t["tracked"]), "up_to_date_pct": pct(t["up_to_date"], t["tracked"]),
             "measles_pct": pct(t["measles_given"], t["measles_due"])} for d, t in sorted(totals.items())]
