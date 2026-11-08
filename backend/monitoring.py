"""System health for the admin: the state of the CloudWatch alarms (AWS).

The API server asks CloudWatch when the admin opens the screen. No patient data is
involved, which fits the admin role (accounts and system only, never patients).
The server's IAM role may only READ alarms; it cannot change or delete them.

On a laptop there is no AWS, so the route says the panel is only available in the cloud.
If the API server itself is down this screen cannot load, so a serious alarm should also
send an email (see docs/AWS_DEPLOYMENT.md, Step 10).
"""
import logging
import os
from functools import lru_cache

from fastapi import APIRouter, Depends

from auth import require_role
from database import get_db, log_access

router = APIRouter()
log = logging.getLogger("uvicorn.error")  # ends up in /var/log/healthconnect/api.log -> CloudWatch Logs

ALARM_PREFIX = "hc-"  # every HealthConnect alarm name starts with this


@lru_cache(maxsize=1)
def cloudwatch_client():
    # Made once and reused: it keeps its connection and the role's temporary credentials
    import boto3  # only needed in the cloud
    from botocore.config import Config

    return boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION"),
                        config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 3, "mode": "standard"}))


def read_alarms():
    response = cloudwatch_client().describe_alarms(AlarmNamePrefix=ALARM_PREFIX, AlarmTypes=["MetricAlarm"])
    return response["MetricAlarms"]


@router.get("/admin/system-health")
def system_health(user=Depends(require_role("admin"))):
    conn = get_db()
    log_access(conn, user["id"], "view_system_health")
    conn.commit()
    conn.close()

    # APP_SECRET_ID is only set on the cloud servers (see config.py)
    if not os.getenv("APP_SECRET_ID"):
        return {"available": False, "alarms": []}
    try:
        alarms = read_alarms()
    except Exception:
        # Never break the admin screen because monitoring is unreachable, but record why
        log.exception("System health: could not read CloudWatch alarms")
        return {"available": False, "alarms": [], "error": True}

    return {
        "available": True,
        "alarms": [
            {
                "name": a["AlarmName"],
                "description": a.get("AlarmDescription", ""),
                "state": a["StateValue"],  # OK | ALARM | INSUFFICIENT_DATA
                "reason": a.get("StateReason", ""),
                "since": a["StateUpdatedTimestamp"].strftime("%Y-%m-%d %H:%M"),
            }
            for a in sorted(alarms, key=lambda a: (a["StateValue"] != "ALARM", a["AlarmName"]))
        ],
    }
