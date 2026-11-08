"""SDG 3 impact dashboard for GHS: is care reaching people, and is that improving?

Compares the last 4 weeks with the 4 weeks before. District totals only, never names.
These are indicators of activity (outputs), not proof that health has improved (outcomes).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from auth import require_role
from database import get_db, log_access
from surveillance import DB_TIME, SMALL_COUNT, hide_small

router = APIRouter()

WINDOW_DAYS = 28  # one "period" = the last 4 weeks


def share(part, whole):
    """A count out of a total. No percentage from tiny numbers: 2 of 3 could identify someone."""
    percent = round(100 * part / whole) if part >= SMALL_COUNT and whole >= SMALL_COUNT else None
    return {"count": hide_small(part), "total": hide_small(whole), "percent": percent}


def hours_between(start, end):
    a, b = (datetime.strptime(t[:19], DB_TIME) for t in (start, end))
    return (b - a).total_seconds() / 3600


def measures(rows):
    """Turn one area's raw rows for one period into the numbers shown on screen."""
    completed = [r for r in rows["referrals"] if r["status"] == "completed" and r["updated_at"]]
    waits = [hours_between(r["created_at"], r["updated_at"]) for r in completed]
    attended = sum(r["status"] == "attended" for r in rows["appointments"])
    return {
        "visits": hide_small(rows["visits"]),
        "antenatal": share(sum(r["checked"] for r in rows["pregnant"]), len(rows["pregnant"])),
        "referrals": share(len(completed), len(rows["referrals"])),
        "avg_hours_to_complete": round(sum(waits) / len(waits)) if len(waits) >= SMALL_COUNT else None,
        "appointments": share(attended, len(rows["appointments"])),
    }


def empty():
    return {"visits": 0, "pregnant": [], "referrals": [], "appointments": []}


@router.get("/surveillance/impact")
def impact(user=Depends(require_role("ghs"))):
    now = datetime.now(timezone.utc)
    current_start = (now - timedelta(days=WINDOW_DAYS)).strftime(DB_TIME)
    previous_start = (now - timedelta(days=2 * WINDOW_DAYS)).strftime(DB_TIME)
    today = now.strftime(DB_TIME)

    conn = get_db()
    # Only district, dates and status are read. No name, reference, id or notes leave these queries.
    visits = conn.execute("""
        SELECT p.district, o.created_at FROM observations o JOIN patients p ON p.id = o.patient_id
        WHERE o.created_at >= ? AND p.district IS NOT NULL
    """, (previous_start,)).fetchall()
    pregnant = conn.execute("""
        SELECT p.district, p.created_at,
               CASE WHEN EXISTS (SELECT 1 FROM observations o
                                 WHERE o.patient_id = p.id AND o.visit_type = 'antenatal') THEN 1 ELSE 0 END AS checked
        FROM patients p WHERE p.pregnant = 1 AND p.created_at >= ? AND p.district IS NOT NULL
    """, (previous_start,)).fetchall()
    referrals = conn.execute("""
        SELECT p.district, r.created_at, r.updated_at, r.status
        FROM referrals r JOIN patients p ON p.id = r.patient_id
        WHERE r.parent_id IS NULL AND r.created_at >= ? AND p.district IS NOT NULL
    """, (previous_start,)).fetchall()
    appointments = conn.execute("""
        SELECT p.district, a.scheduled_at, a.status
        FROM appointments a JOIN patients p ON p.id = a.patient_id
        WHERE a.status IN ('attended', 'missed') AND a.scheduled_at >= ? AND a.scheduled_at <= ?
          AND p.district IS NOT NULL
    """, (previous_start, today)).fetchall()
    log_access(conn, user["id"], "view_impact", f"last {2 * WINDOW_DAYS} days")
    conn.commit()
    conn.close()

    # groups["current" or "previous"][district] = that area's raw rows
    groups = {"current": defaultdict(empty), "previous": defaultdict(empty)}
    period = lambda when: "current" if when >= current_start else "previous"
    for r in visits:
        groups[period(r["created_at"])][r["district"]]["visits"] += 1
    for r in pregnant:
        groups[period(r["created_at"])][r["district"]]["pregnant"].append(r)
    for r in referrals:
        groups[period(r["created_at"])][r["district"]]["referrals"].append(r)
    for r in appointments:
        groups[period(r["scheduled_at"])][r["district"]]["appointments"].append(r)

    def national(which):
        total = empty()
        for area in groups[which].values():
            total["visits"] += area["visits"]
            for key in ("pregnant", "referrals", "appointments"):
                total[key] += area[key]
        return measures(total)

    districts = sorted(set(groups["current"]) | set(groups["previous"]))
    # Gap between districts: only those with enough visits to show
    seen = [(groups["current"][d]["visits"], d) for d in districts if groups["current"][d]["visits"] >= SMALL_COUNT]
    gap = None
    if len(seen) >= 2:
        (low, low_name), (high, high_name) = min(seen), max(seen)
        gap = {"highest": {"district": high_name, "visits": high}, "lowest": {"district": low_name, "visits": low},
               "difference": high - low}

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "window_days": WINDOW_DAYS,
        "current": national("current"),
        "previous": national("previous"),
        "gap": gap,
        "districts": [{"district": d, **measures(groups["current"][d])} for d in districts],
    }
