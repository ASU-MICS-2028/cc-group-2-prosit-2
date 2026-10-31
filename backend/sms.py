"""Sending SMS through Arkesel. Used for referral alerts and appointment reminders."""
import os

import requests


def to_international(phone):
    # Ghana numbers: 0241234567 -> 233241234567
    phone = (phone or "").strip().replace(" ", "").lstrip("+")
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    return phone


def send_sms(phone, message):
    """Returns True if Arkesel accepted the message. Never raises."""
    api_key = os.getenv("ARKESEL_API_KEY")
    if not api_key or not phone:
        return False
    try:
        response = requests.get(
            "https://sms.arkesel.com/sms/api",
            params={
                "action": "send-sms",
                "api_key": api_key,
                "to": to_international(phone),
                # Sender IDs must be registered with Arkesel before they work
                "from": os.getenv("ARKESEL_SENDER", "SafeArriv"),
                "sms": message,
            },
            timeout=15,
        )
        code = response.json().get("code")
    except (requests.RequestException, ValueError):
        code = "network_error"
    # Log only the status code; the full reply has account details we don't need
    print("ARKESEL STATUS:", code)
    return code == "ok"
