"""Community health alerts: GHS sends one SMS to a whole district.

Who gets it:
- every health facility in the district (its phone), so staff and CHVs pass it on in person;
- residents who AGREED to health alerts when registered (patients.health_alerts = 1).
  Their phone was given for appointment reminders; using it for alerts needs its own consent
  (Act 843, purpose limitation).
GHS never sees a phone number: only how many messages were sent and delivered.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text
from sms import send_sms

router = APIRouter()
MAX_RECIPIENTS = 500  # a prototype limit: a real national alert would use a bulk SMS service


class AlertIn(BaseModel):
    district: str
    message: str = Field(min_length=10, max_length=300)


def phones_for(conn, district):
    facilities = {r["facility_phone"] for r in conn.execute(
        "SELECT DISTINCT facility_phone FROM users WHERE district = ? AND active = 1 AND facility_phone IS NOT NULL",
        (district,))}
    residents = {r["phone"] for r in conn.execute(
        "SELECT DISTINCT phone FROM patients WHERE district = ? AND health_alerts = 1 AND phone IS NOT NULL", (district,))}
    return facilities, residents - facilities


@router.get("/alerts/community/preview")
def preview(district: str, user=Depends(require_role("ghs"))):
    conn = get_db()
    facilities, residents = phones_for(conn, district)
    conn.close()
    return {"district": district, "facilities": len(facilities), "residents": len(residents)}


@router.post("/alerts/community")
def send(body: AlertIn, user=Depends(require_role("ghs"))):
    conn = get_db()
    facilities, residents = phones_for(conn, body.district)
    phones = sorted(facilities | residents)
    if not phones:
        conn.close()
        raise HTTPException(status_code=400, detail="Nobody in this district can receive alerts yet")
    if len(phones) > MAX_RECIPIENTS:
        conn.close()
        raise HTTPException(status_code=400, detail="Too many recipients for this prototype")
    text = f"HealthConnect GHS alert ({body.district}): {body.message.strip()}"
    delivered = sum(send_sms(phone, text) for phone in phones)
    conn.execute("INSERT INTO community_alerts (district, message, sent_by, recipients, delivered, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (body.district, body.message.strip(), user["id"], len(phones), delivered, now_text()))
    log_access(conn, user["id"], "send_community_alert", f"{body.district} recipients={len(phones)} delivered={delivered}")
    conn.commit()
    conn.close()
    return {"recipients": len(phones), "delivered": delivered}


@router.get("/alerts/community")
def history(user=Depends(require_role("ghs"))):
    conn = get_db()
    rows = conn.execute("SELECT a.district, a.message, a.recipients, a.delivered, a.created_at, u.full_name AS sent_by "
                        "FROM community_alerts a JOIN users u ON u.id = a.sent_by ORDER BY a.id DESC LIMIT 20").fetchall()
    conn.close()
    return [dict(r) for r in rows]
