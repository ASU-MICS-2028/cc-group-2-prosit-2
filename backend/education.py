"""Community health education: short lessons a CHV can read out or show, in local languages.

Anyone on the care team can write a lesson, but it stays "not reviewed" until a nurse or doctor
other than the author approves it, because wrong health advice can harm people.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()


class LessonCreate(BaseModel):
    topic: Literal["malaria", "maternal", "cholera", "general"]
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=20, max_length=2000)
    # App languages, plus the other languages Abena AI can speak (tts.py)
    language: Literal["en", "tw", "ee", "gaa", "dag", "gpe", "ha", "pcm", "yo", "sw"]


LESSON_COLUMNS = """l.id, l.topic, l.title, l.body, l.language, l.reviewed_at, l.created_at,
                    author.full_name AS author_name, reviewer.full_name AS reviewer_name"""
LESSON_JOINS = """FROM lessons l LEFT JOIN users author ON author.id = l.created_by
                  LEFT JOIN users reviewer ON reviewer.id = l.reviewed_by"""


@router.get("/lessons")
def list_lessons(user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    rows = conn.execute(f"SELECT {LESSON_COLUMNS} {LESSON_JOINS} ORDER BY l.topic, l.title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/lessons")
def add_lesson(body: LessonCreate, user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    if conn.execute("SELECT 1 FROM lessons WHERE title = ? AND language = ?", (body.title.strip(), body.language)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="A lesson with this title already exists in this language")
    lesson = conn.execute(
        "INSERT INTO lessons (topic, title, body, language, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        (body.topic, body.title.strip(), body.body.strip(), body.language, user["id"], now_text()),
    ).fetchone()
    log_access(conn, user["id"], "add_lesson", str(lesson["id"]))
    conn.commit()
    conn.close()
    return {"id": lesson["id"]}


@router.post("/lessons/{lesson_id}/review")
def review_lesson(lesson_id: int, user=Depends(require_role("nurse", "doctor"))):
    conn = get_db()
    lesson = conn.execute("SELECT created_by, reviewed_at FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        conn.close()
        raise HTTPException(status_code=404, detail="Lesson not found")
    if lesson["created_by"] == user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Another nurse or doctor must review your lesson")
    if lesson["reviewed_at"]:
        conn.close()
        raise HTTPException(status_code=400, detail="This lesson has already been reviewed")
    conn.execute("UPDATE lessons SET reviewed_by = ?, reviewed_at = ? WHERE id = ?", (user["id"], now_text(), lesson_id))
    log_access(conn, user["id"], "review_lesson", str(lesson_id))
    conn.commit()
    conn.close()
    return {"success": True}
