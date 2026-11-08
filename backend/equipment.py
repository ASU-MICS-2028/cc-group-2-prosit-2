"""Health supply chain: medical equipment at each facility (medicines are in pharmacy.py).

Staff record how many of each device work and how many are broken. GHS sees district
totals, so a district with no working blood pressure monitor can be supplied first.
Counts of devices only, never patient data.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text
from surveillance import DISTRICT_CENTRES

router = APIRouter()

EQUIPMENT = ["bp_monitor", "thermometer", "weighing_scale"]  # the devices a CHV or clinic checks vitals with


class EquipmentCount(BaseModel):
    working: int = Field(ge=0, le=1000)
    broken: int = Field(ge=0, le=1000)


def facility_rows(conn, facility):
    saved = {r["item"]: r for r in conn.execute(
        "SELECT item, working, broken, updated_at FROM equipment WHERE facility = ?", (facility,)).fetchall()}
    return [
        {"item": item, "working": saved[item]["working"] if item in saved else 0,
         "broken": saved[item]["broken"] if item in saved else 0,
         "updated_at": saved[item]["updated_at"] if item in saved else None}
        for item in EQUIPMENT
    ]


@router.get("/equipment")
def my_equipment(user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    rows = facility_rows(conn, user["facility"])
    conn.close()
    return rows


@router.post("/equipment/{item}")
def update_equipment(item: str, body: EquipmentCount, user=Depends(require_role("nurse", "doctor"))):
    if item not in EQUIPMENT:
        raise HTTPException(status_code=404, detail="Unknown equipment")
    conn = get_db()
    conn.execute(
        "INSERT INTO equipment (facility, item, working, broken, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (facility, item) DO UPDATE SET working = excluded.working, broken = excluded.broken, "
        "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
        (user["facility"], item, body.working, body.broken, user["id"], now_text()),
    )
    log_access(conn, user["id"], "update_equipment", f"{item} working={body.working} broken={body.broken}")
    conn.commit()
    rows = facility_rows(conn, user["facility"])
    conn.close()
    return rows


@router.get("/surveillance/equipment")
def equipment_by_district(user=Depends(require_role("ghs"))):
    conn = get_db()
    # A facility's district comes from its staff accounts
    facility_district = {}
    for r in conn.execute("SELECT DISTINCT facility, district FROM users "
                          "WHERE facility IS NOT NULL AND district IS NOT NULL ORDER BY facility"):
        facility_district.setdefault(r["facility"], r["district"])
    rows = conn.execute("SELECT facility, item, working, broken FROM equipment").fetchall()
    log_access(conn, user["id"], "view_equipment_by_district")
    conn.commit()
    conn.close()

    districts = {}
    for r in rows:
        district = facility_district.get(r["facility"])
        if district not in DISTRICT_CENTRES:
            continue
        d = districts.setdefault(district, {"facilities": set(), "items": {
            item: {"item": item, "working": 0, "broken": 0, "facilities_without": 0} for item in EQUIPMENT}})
        d["facilities"].add(r["facility"])
        entry = d["items"][r["item"]]
        entry["working"] += r["working"]
        entry["broken"] += r["broken"]
        entry["facilities_without"] += r["working"] == 0

    return {"districts": [
        {"district": name, "facilities": len(d["facilities"]), "items": list(d["items"].values())}
        for name, d in sorted(districts.items())
    ]}
