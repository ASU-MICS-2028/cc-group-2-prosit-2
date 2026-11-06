"""AWS Lambda entry point: send due SMS reminders (Week 7: serverless, event-driven).

EventBridge Scheduler calls handler() every 10 minutes. The work is in reminders.py,
the same code the API runs on a laptop.

Init phase (outside handler, once per cold start): load secrets and the database address.
Invoke phase (handler): claim and send due reminders.
If any SMS failed, handler() raises, so Lambda retries the run (2 more times) and, after
that, puts the event in the dead-letter queue, which sets off a CloudWatch alarm.
Retrying is safe: reminders already sent are never sent again (see reminders.py).
"""
import json

import config  # noqa: F401  secrets loaded here, in the init phase, not on every run
from reminders import send_due_reminders


def handler(event, context):
    counts = send_due_reminders()
    # Structured log line (one JSON object) so CloudWatch can search and count it
    print(json.dumps({"job": "send_reminders", "request_id": getattr(context, "aws_request_id", None), **counts}))
    if counts["retry"] or counts["failed"]:
        raise RuntimeError(f"{counts['retry'] + counts['failed']} reminder SMS failed; Lambda will retry")
    return counts
