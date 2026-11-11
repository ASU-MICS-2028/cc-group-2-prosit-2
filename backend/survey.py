"""Community health survey: a CHV asks a household six yes/no questions.

No names, no patient record: one row per household, with the community and district.
GHS sees the share of households per district (small numbers hidden), so it can see where
nets, safe water or latrines are missing, and where TB or diarrhoea warning signs cluster.
"""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text
from surveillance import SMALL_COUNT, hide_small

router = APIRouter()

# code, question, the answer that is GOOD for health (True = "yes" is good)
QUESTIONS = [
    ("bed_nets", "Does everyone sleep under a mosquito net?", True),
    ("safe_water", "Is the drinking water from a safe source (borehole, pipe, sachet)?", True),
    ("latrine", "Does the household have a latrine or toilet?", True),
    ("long_cough", "Has anyone had a cough for more than 2 weeks?", False),
    ("child_no_net", "Is any child under 5 sleeping without a net?", False),
    ("diarrhoea", "Has anyone had diarrhoea in the last 2 weeks?", False),
]
CODES = [code for code, _, _ in QUESTIONS]


class SurveyIn(BaseModel):
    community: str = Field(default="", max_length=100)
    people: int = Field(ge=1, le=50)
    answers: dict[str, bool]


@router.get("/surveys/questions")
def questions(user=Depends(require_role("chv", "ghs"))):
    return [{"code": c, "question": q, "good_answer": g} for c, q, g in QUESTIONS]


@router.post("/surveys")
def submit(body: SurveyIn, user=Depends(require_role("chv"))):
    if sorted(body.answers) != sorted(CODES):
        raise HTTPException(status_code=400, detail="Please answer every question")
    conn = get_db()
    conn.execute("INSERT INTO surveys (chv_id, district, community, people, answers, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (user["id"], user["district"], body.community.strip(), body.people, json.dumps(body.answers), now_text()))
    log_access(conn, user["id"], "submit_survey", body.community.strip() or None)
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/chv/surveys")
def my_surveys(user=Depends(require_role("chv"))):
    """How many households this CHV has surveyed in the last 30 days."""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    n = conn.execute("SELECT count(*) AS n FROM surveys WHERE chv_id = ? AND created_at >= ?", (user["id"], since)).fetchone()["n"]
    conn.close()
    return {"last_30_days": n}


@router.get("/surveillance/surveys")
def results(days: int = Query(90, ge=7, le=365), user=Depends(require_role("ghs"))):
    """Per district: households surveyed and the share answering 'yes' to each question."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    rows = conn.execute("SELECT district, answers FROM surveys WHERE created_at >= ? AND district IS NOT NULL", (since,)).fetchall()
    log_access(conn, user["id"], "view_survey_results")
    conn.commit()
    conn.close()
    totals = {}
    for r in rows:
        t = totals.setdefault(r["district"], {"households": 0, **{c: 0 for c in CODES}})
        t["households"] += 1
        for code, yes in json.loads(r["answers"]).items():
            t[code] += bool(yes)
    out = []
    for district, t in sorted(totals.items()):
        enough = t["households"] >= SMALL_COUNT
        out.append({"district": district, "households": hide_small(t["households"]),
                    "yes_pct": {c: round(100 * t[c] / t["households"]) if enough else None for c in CODES}})
    return {"questions": [{"code": c, "question": q, "good_answer": g} for c, q, g in QUESTIONS], "districts": out}
