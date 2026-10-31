"""GHS surveillance dashboard: anonymised district totals, never names.

What GHS gets:  counts per district, per condition, per week, plus outbreak alerts.
What GHS never gets: names, references, patient ids, phone numbers, notes.

Weeks are counted back from now: week 0 = last 7 days, week 1 = 8-14 days ago, ...
"""
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth import require_role
from database import get_db, log_access

router = APIRouter()

CONDITIONS = ["malaria", "cholera", "meningitis", "measles", "pneumonia", "hypertension"]
SMALL_COUNT = 5  # 1-4 shown as "<5": tiny numbers in a village can identify a person
ALERT_MIN_CASES = 5  # an alert needs at least this many cases this week...
ALERT_FACTOR = 2  # ...and at least double the usual weekly level
BASELINE_WEEKS = 4  # "usual" = average of the 4 weeks before this one


def hide_small(count):
    return f"<{SMALL_COUNT}" if 0 < count < SMALL_COUNT else count


def week_index(created_at, now):
    seen = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return (now - seen).days // 7


@router.get("/surveillance/summary")
def summary(weeks: int = Query(8, ge=5, le=26), user=Depends(require_role("ghs"))):
    now = datetime.now(timezone.utc)
    conn = get_db()
    # Only these four columns are read. No name, ref, id or notes ever leave this query.
    rows = conn.execute("""
        SELECT p.district, o.created_at, o.risk_level, o.possible_conditions
        FROM observations o JOIN patients p ON p.id = o.patient_id
        WHERE o.created_at >= datetime('now', ?) AND p.district IS NOT NULL
    """, (f"-{weeks * 7} days",)).fetchall()
    referrals = conn.execute("""
        SELECT p.district, COUNT(*) AS n FROM referrals r JOIN patients p ON p.id = r.patient_id
        WHERE r.parent_id IS NULL AND r.created_at >= datetime('now', '-7 days') GROUP BY p.district
    """).fetchall()
    log_access(conn, user["id"], "view_surveillance", f"last {weeks} weeks")
    conn.commit()
    conn.close()

    # cases[district][condition][week] = count
    cases = defaultdict(lambda: defaultdict(lambda: [0] * weeks))
    visits = defaultdict(lambda: [0] * weeks)
    high = defaultdict(lambda: [0] * weeks)
    for r in rows:
        w = week_index(r["created_at"], now)
        if w >= weeks:
            continue
        visits[r["district"]][w] += 1
        if r["risk_level"] == "HIGH":
            high[r["district"]][w] += 1
        for condition in (r["possible_conditions"] or "").split(","):
            if condition in CONDITIONS:
                cases[r["district"]][condition][w] += 1

    districts = sorted(visits)
    alerts = []
    for d in districts:
        for c in CONDITIONS:
            series = cases[d][c]
            this_week = series[0]
            usual = sum(series[1:1 + BASELINE_WEEKS]) / BASELINE_WEEKS
            if this_week >= ALERT_MIN_CASES and this_week >= ALERT_FACTOR * max(usual, 1):
                alerts.append({"district": d, "condition": c, "this_week": this_week, "usual": round(usual, 1)})
    alerts.sort(key=lambda a: a["this_week"] / max(a["usual"], 1), reverse=True)

    referrals_by_district = {r["district"]: r["n"] for r in referrals}
    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "weeks": weeks,
        "totals_this_week": {
            "visits": hide_small(sum(v[0] for v in visits.values())),
            "high_risk": hide_small(sum(h[0] for h in high.values())),
            "referrals": hide_small(sum(referrals_by_district.values())),
            "alerts": len(alerts),
        },
        "alerts": alerts,
        "districts": [
            {
                "district": d,
                "visits_this_week": hide_small(visits[d][0]),
                "high_risk_this_week": hide_small(high[d][0]),
                "referrals_this_week": hide_small(referrals_by_district.get(d, 0)),
                # newest week first, small numbers hidden
                "conditions": {c: [hide_small(n) for n in cases[d][c]] for c in CONDITIONS},
            }
            for d in districts
        ],
    }
