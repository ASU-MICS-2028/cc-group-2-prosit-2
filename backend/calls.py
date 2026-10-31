"""Video consult signalling (the "introducer" for WebRTC calls).

The video itself goes directly between the two browsers (WebRTC, peer-to-peer).
This server only passes small setup messages between them:
  offer  -> "here is how I can send video"
  answer -> "OK, here is how I can send mine"
  ice    -> "here is a network address you can reach me on"
  bye    -> "I hung up"

One call room per patient referral chain (CHV -> health centre -> hospital).
Who may join: the patient's CHV, or staff at a facility in that chain (need-to-know).
Calls are 1-to-1: two people at a time.

Rooms live in memory, which is fine for one server. With several cloud servers you would
keep them in a shared store (e.g. Redis) or use API Gateway WebSockets instead.
"""
import threading
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import get_db, log_access

router = APIRouter()

STALE_SECONDS = 15  # someone who stops polling for 15 s (closed tab, lost signal) is removed
rooms = {}  # root referral id -> {user id: {"name", "role", "seen", "inbox": [messages]}}
lock = threading.Lock()  # requests run in parallel threads; only one may change rooms at a time


class Signal(BaseModel):
    type: Literal["offer", "answer", "ice", "bye"]
    data: Any = None


def check_member(referral_id, user, log_denied=True):
    """Return (room id, patient ref, patient name) if this user may join, else 404."""
    conn = get_db()
    referral = conn.execute("SELECT id, parent_id FROM referrals WHERE id = ?", (referral_id,)).fetchone()
    allowed = False
    if referral:
        root_id = referral["parent_id"] or referral["id"]
        chain = conn.execute(
            "SELECT r.facility, r.chv_id, p.ref, p.full_name FROM referrals r "
            "JOIN patients p ON p.id = r.patient_id WHERE r.id = ? OR r.parent_id = ?",
            (root_id, root_id),
        ).fetchall()
        if user["role"] == "chv":
            allowed = chain[0]["chv_id"] == user["id"]
        elif user["role"] in ("nurse", "doctor"):
            allowed = any(row["facility"] == user["facility"] for row in chain)
    if not allowed:
        if log_denied:
            log_access(conn, user["id"], "access_denied", f"call:{referral_id}")
            conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Call not found")
    conn.close()
    return root_id, chain[0]["ref"], chain[0]["full_name"]


def prune(room):
    now = time.time()
    for uid in [uid for uid, p in room.items() if now - p["seen"] > STALE_SECONDS]:
        del room[uid]


def other_person(room, user_id):
    for uid, p in room.items():
        if uid != user_id:
            return {"name": p["name"], "role": p["role"]}
    return None


def audit(user_id, action, resource):
    conn = get_db()
    log_access(conn, user_id, action, resource)
    conn.commit()
    conn.close()


@router.get("/calls/active")
def active_calls(user=Depends(get_current_user)):
    """Calls someone has started that this user may join (for the 'incoming call' banner)."""
    with lock:
        waiting = []
        for room_id, room in rooms.items():
            prune(room)
            if room and user["id"] not in room and len(room) < 2:
                waiting.append((room_id, other_person(room, user["id"])))
    calls = []
    for room_id, caller in waiting:
        try:
            _, ref, name = check_member(room_id, user, log_denied=False)
        except HTTPException:
            continue  # not this user's patient: don't even reveal the call exists
        calls.append({"referral_id": room_id, "caller": caller, "ref": ref, "full_name": name})
    return calls


@router.post("/calls/{referral_id}/join")
def join_call(referral_id: int, user=Depends(get_current_user)):
    room_id, ref, _ = check_member(referral_id, user)
    with lock:
        room = rooms.setdefault(room_id, {})
        prune(room)
        if user["id"] not in room and len(room) >= 2:
            raise HTTPException(status_code=409, detail="Call busy: two people are already on this call")
        peer = other_person(room, user["id"])
        room[user["id"]] = {"name": user["full_name"], "role": user["role"], "seen": time.time(), "inbox": []}
    audit(user["id"], "call_join", ref)
    # The second person to arrive starts the call (creates the WebRTC offer)
    return {"room": room_id, "start_call": peer is not None, "peer": peer}


@router.post("/calls/{referral_id}/signal")
def send_signal(referral_id: int, body: Signal, user=Depends(get_current_user)):
    room_id, _, _ = check_member(referral_id, user)
    with lock:
        room = rooms.get(room_id, {})
        if user["id"] not in room:
            raise HTTPException(status_code=409, detail="Join the call first")
        for uid, p in room.items():
            if uid != user["id"]:
                p["inbox"].append({"type": body.type, "data": body.data})
    return {"success": True}


@router.get("/calls/{referral_id}/signal")
def poll_signal(referral_id: int, user=Depends(get_current_user)):
    room_id, _, _ = check_member(referral_id, user)
    with lock:
        room = rooms.get(room_id, {})
        me = room.get(user["id"])
        if not me:
            return {"in_call": False, "messages": [], "peer": None}
        me["seen"] = time.time()  # "I'm still here"
        prune(room)
        messages, me["inbox"] = me["inbox"], []
        return {"in_call": True, "messages": messages, "peer": other_person(room, user["id"])}


@router.post("/calls/{referral_id}/leave")
def leave_call(referral_id: int, user=Depends(get_current_user)):
    room_id, ref, _ = check_member(referral_id, user)
    with lock:
        room = rooms.get(room_id, {})
        if room.pop(user["id"], None) is not None:
            for p in room.values():
                p["inbox"].append({"type": "bye", "data": None})
        if not room:
            rooms.pop(room_id, None)
    audit(user["id"], "call_leave", ref)
    return {"success": True}
