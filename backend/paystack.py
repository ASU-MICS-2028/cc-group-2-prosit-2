"""Talks to Paystack, the payment provider. Any future payment (e.g. consultation fees) reuses this.

A live key moves REAL money, so it is ignored unless PAYSTACK_ALLOW_LIVE=on is also set.
The customer's mobile money number is typed on Paystack's own page and never reaches us (Act 843).
"""
import os

import requests
from fastapi import HTTPException

BASE_URL = "https://api.paystack.co"
TIMEOUT_SECONDS = 15


def secret_key():
    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if key.startswith("sk_test_") or (key.startswith("sk_live_") and os.getenv("PAYSTACK_ALLOW_LIVE") == "on"):
        return key
    return ""


def is_configured():
    return bool(secret_key())


def is_live():
    return secret_key().startswith("sk_live_")


def call(method, path, **kwargs):
    try:
        res = requests.request(method, BASE_URL + path, timeout=TIMEOUT_SECONDS,
                               headers={"Authorization": f"Bearer {secret_key()}"}, **kwargs)
        return res.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail="Could not reach Paystack. Please try again") from None


def start_payment(reference, amount_ghs):
    """Returns the Paystack page where the payer completes the payment."""
    body = {
        "reference": reference,
        "amount": amount_ghs * 100,  # Paystack counts in pesewas
        "currency": "GHS",
        "channels": ["mobile_money"],
        "email": f"{reference.lower()}@example.com",  # required by Paystack; a placeholder so no identity is sent
    }
    answer = call("POST", "/transaction/initialize", json=body)
    if not answer.get("status"):
        raise HTTPException(status_code=502, detail=answer.get("message") or "Paystack refused this payment")
    return answer["data"]["authorization_url"]


def is_paid(reference, amount_ghs):
    """Ask Paystack directly. The phone's word is never trusted, and the amount must match in full."""
    answer = call("GET", f"/transaction/verify/{reference}")
    data = answer.get("data") or {}
    return (data.get("status") == "success" and data.get("amount") == amount_ghs * 100
            and data.get("currency") == "GHS")
