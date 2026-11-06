"""GHS surveillance dashboard: anonymised district totals, never names.

What GHS gets:  counts per district, per condition, per week, plus outbreak alerts.
What GHS never gets: names, references, patient ids, phone numbers, notes.

Weeks are counted back from now: week 0 = last 7 days, week 1 = 8-14 days ago, ...
"""
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from auth import require_role
from database import get_db, log_access
from forecast import forecast

router = APIRouter()

CONDITIONS = ["malaria", "cholera", "meningitis", "measles", "pneumonia", "hypertension"]
SMALL_COUNT = 5  # 1-4 shown as "<5": tiny numbers in a village can identify a person
ALERT_MIN_CASES = 5  # an alert needs at least this many cases this week...
ALERT_FACTOR = 2  # ...and at least double the usual weekly level
BASELINE_WEEKS = 4  # "usual" = average of the 4 weeks before this one
FORECAST_CONDITIONS = ["malaria", "cholera", "meningitis", "measles", "pneumonia"]  # infectious only
MIN_CHANCE_SHOWN = 0.1  # forecasts below 10% are left out

# Map position = the district capital (approximate). We never map where patients live.
DISTRICT_CENTRES = {
    "Bolgatanga Municipal": (10.7856, -0.8514),
    "Tamale Metropolitan": (9.4008, -0.8393),
    "Wa Municipal": (10.0601, -2.5099),
    "Kumasi Metropolitan": (6.6885, -1.6244),
    "Cape Coast Metropolitan": (5.1053, -1.2466),
}


def hide_small(count):
    return f"<{SMALL_COUNT}" if 0 < count < SMALL_COUNT else count


DB_TIME = "%Y-%m-%d %H:%M:%S"  # how every timestamp is stored (UTC text, see database.py)


def week_index(created_at, now):
    seen = datetime.strptime(created_at, DB_TIME).replace(tzinfo=timezone.utc)
    return (now - seen).days // 7


@router.get("/surveillance/summary")
def summary(weeks: int = Query(8, ge=5, le=26), user=Depends(require_role("ghs"))):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=weeks * 7)).strftime(DB_TIME)
    week_ago = (now - timedelta(days=7)).strftime(DB_TIME)
    conn = get_db()
    # Only these four columns are read. No name, ref, id or notes ever leave this query.
    rows = conn.execute("""
        SELECT p.district, o.created_at, o.risk_level, o.possible_conditions
        FROM observations o JOIN patients p ON p.id = o.patient_id
        WHERE o.created_at >= ? AND p.district IS NOT NULL
    """, (since,)).fetchall()
    referrals = conn.execute("""
        SELECT p.district, COUNT(*) AS n FROM referrals r JOIN patients p ON p.id = r.patient_id
        WHERE r.parent_id IS NULL AND r.created_at >= ? AND p.district IS NOT NULL
        GROUP BY p.district
    """, (week_ago,)).fetchall()
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

    # 2-week outlook (forecast.py): statistics, not machine learning
    forecasts = []
    for d in districts:
        for c in FORECAST_CONDITIONS:
            weekly = cases[d][c]
            usual = sum(weekly[:BASELINE_WEEKS]) / BASELINE_WEEKS  # the 4 weeks before next week
            outbreak_level = max(ALERT_MIN_CASES, math.ceil(ALERT_FACTOR * max(usual, 1)))
            outlook = forecast(weekly, outbreak_level)
            if outlook["chance"] >= MIN_CHANCE_SHOWN:
                outlook["expected_next_2_weeks"] = hide_small(outlook["expected_next_2_weeks"])
                forecasts.append({"district": d, "condition": c, "outbreak_level": outbreak_level, **outlook})
    forecasts.sort(key=lambda f: f["chance"], reverse=True)

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
        "forecasts": forecasts,
        "districts": [
            {
                "district": d,
                "centre": DISTRICT_CENTRES.get(d),  # [lat, lng] or None if unknown
                "visits_this_week": hide_small(visits[d][0]),
                "high_risk_this_week": hide_small(high[d][0]),
                "referrals_this_week": hide_small(referrals_by_district.get(d, 0)),
                # newest week first, small numbers hidden
                "conditions": {c: [hide_small(n) for n in cases[d][c]] for c in CONDITIONS},
            }
            for d in districts
        ],
    }


# ---------- DHIMS2 export (SIMULATED: produces the file, sends nothing) ----------
# DHIMS2 runs on DHIS2. DHIS2 accepts aggregate data as a "dataValueSet".
# Real integration needs the official IDs (UIDs) from GHS's DHIMS2 metadata;
# these placeholders show the shape only.
DHIMS2_DATASET = "PLACEHOLDER_DATASET_IDSR_WEEKLY"
# "Cape Coast Metropolitan" -> PLACEHOLDER_OU_CAPE_COAST
DHIMS2_ORG_UNITS = {d: "PLACEHOLDER_OU_" + d.rsplit(" ", 1)[0].upper().replace(" ", "_") for d in DISTRICT_CENTRES}
DHIMS2_DATA_ELEMENTS = {c: f"PLACEHOLDER_DE_{c.upper()}_SUSPECTED" for c in CONDITIONS}


@router.get("/surveillance/dhims2-export")
def dhims2_export(user=Depends(require_role("ghs"))):
    # Last COMPLETE week, Monday-Sunday (DHIS2 weekly periods are ISO weeks, e.g. "2026W43")
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=today.weekday() + 7)
    end = start + timedelta(days=7)
    year, week, _ = start.isocalendar()

    conn = get_db()
    rows = conn.execute("""
        SELECT p.district, o.possible_conditions
        FROM observations o JOIN patients p ON p.id = o.patient_id
        WHERE o.created_at >= ? AND o.created_at < ? AND p.district IS NOT NULL
    """, (start.isoformat(), end.isoformat())).fetchall()
    log_access(conn, user["id"], "dhims2_export", f"{year}W{week:02d}")
    conn.commit()
    conn.close()

    counts = defaultdict(int)
    for r in rows:
        for c in (r["possible_conditions"] or "").split(","):
            if c in CONDITIONS:
                counts[(r["district"], c)] += 1

    # Official reporting uses exact counts (public-health reporting duty); still aggregate only, no names.
    data_values = [
        {"dataElement": DHIMS2_DATA_ELEMENTS[c], "orgUnit": DHIMS2_ORG_UNITS.get(d, "UNMAPPED_" + d), "value": str(n)}
        for (d, c), n in sorted(counts.items())
    ]
    return {
        "_note": "SIMULATED export for PROSIT 2. Not sent to DHIMS2. Replace PLACEHOLDER ids with official DHIMS2 UIDs.",
        "dataSet": DHIMS2_DATASET,
        "period": f"{year}W{week:02d}",
        "completeDate": today.isoformat(),
        "dataValues": data_values,
    }
