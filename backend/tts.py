"""Spoken health lessons: Abena AI reads a lesson aloud in Twi, Ewe or Ghanaian English.

Why: many people in rural Ghana speak Twi or Ewe but cannot read them. A CHV plays the lesson
on the phone, so the household hears it in its own language.

- The Abena AI key stays on this server (ABENA_API_KEY); phones never see it.
- Each lesson is spoken ONCE and the audio is stored (lesson_audio), so every later listen is
  free and instant. If the lesson text changes, it is spoken again.
- Abena takes up to 500 characters per request, so a long lesson is split at sentence ends
  and the WAV pieces are joined into one file.
- Ga and Dagbani have no Abena voice yet, so those lessons have no audio.
"""
import base64
import hashlib
import io
import os
import re
import wave

import requests
from fastapi import APIRouter, Depends, HTTPException, Response

from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()
URL = "https://abena.mobobi.com/playground/api/v1/tts/synthesize/"
VOICES = {"tw": "abena_twi_high", "ee": "mawuli_ewe", "en": "akua_eng_high"}  # lesson language -> Abena voice
MAX_CHARS = 480  # Abena's limit is 500


class SpeechError(Exception):
    pass


def pieces(text):
    """Split at sentence ends into pieces Abena accepts."""
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    out, current = [], ""
    for sentence in sentences:
        while len(sentence) > MAX_CHARS:  # a very long sentence: cut at a comma or space
            cut = max(sentence.rfind(",", 0, MAX_CHARS), sentence.rfind(" ", 0, MAX_CHARS)) or MAX_CHARS
            out.append(sentence[:cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if current and len(current) + 1 + len(sentence) > MAX_CHARS:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    return [p for p in out + [current] if p]


def speak(text, voice):
    """One Abena request -> WAV bytes."""
    key = os.getenv("ABENA_API_KEY")
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
    try:
        res = requests.post(URL, json={"text": text, "voice": voice}, headers=headers, timeout=120)
        data = res.json()
    except (requests.RequestException, ValueError):
        raise SpeechError("Could not reach the speech service")
    if res.status_code != 200 or "audio_base64" not in data:
        print("ABENA STATUS:", res.status_code, data.get("error"))  # never print the key
        raise SpeechError(data.get("message") or "Speech service error")
    return base64.b64decode(data["audio_base64"])


def join_wavs(clips):
    """Join WAV clips of the same voice into one WAV file."""
    out = io.BytesIO()
    with wave.open(out, "wb") as joined:
        for i, clip in enumerate(clips):
            with wave.open(io.BytesIO(clip), "rb") as part:
                if i == 0:
                    joined.setparams(part.getparams())
                joined.writeframes(part.readframes(part.getnframes()))
    return out.getvalue()


@router.get("/lessons/{lesson_id}/audio")
def lesson_audio(lesson_id: int, user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    lesson = conn.execute("SELECT id, title, body, language FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        conn.close()
        raise HTTPException(status_code=404, detail="Lesson not found")
    voice = VOICES.get(lesson["language"])
    if not voice:
        conn.close()
        raise HTTPException(status_code=400, detail="No voice for this language yet")
    text = f"{lesson['title']}. {lesson['body']}"
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    saved = conn.execute("SELECT audio FROM lesson_audio WHERE lesson_id = ? AND voice = ? AND text_hash = ?",
                         (lesson_id, voice, text_hash)).fetchone()
    if saved:
        audio = bytes(saved["audio"])
    else:
        try:
            audio = join_wavs([speak(p, voice) for p in pieces(text)])
        except SpeechError as err:
            conn.close()
            raise HTTPException(status_code=503, detail=f"Audio not available right now: {err}")
        conn.execute("INSERT INTO lesson_audio (lesson_id, voice, text_hash, audio, created_at) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT (lesson_id, voice, text_hash) DO NOTHING", (lesson_id, voice, text_hash, audio, now_text()))
    log_access(conn, user["id"], "play_lesson_audio", f"lesson:{lesson_id}")
    conn.commit()
    conn.close()
    # Not patient data: the phone may keep it for a day, so a replay needs no signal
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})
