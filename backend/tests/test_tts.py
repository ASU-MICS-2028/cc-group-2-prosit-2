"""Spoken lessons: Abena AI is mocked (no credits used); audio is made once and then reused."""
import io
import wave

import tts


def tone(frames=800):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\x01\x00" * frames)
    return out.getvalue()


def test_pieces_respect_the_500_character_limit():
    text = ("Sleep under a mosquito net every night. " * 30).strip()
    parts = tts.pieces(text)
    assert len(parts) > 1 and all(len(p) <= tts.MAX_CHARS for p in parts)
    assert " ".join(parts) == text


def test_lesson_spoken_once_then_reused(client, login, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "speak", lambda text, voice: calls.append(voice) or tone())
    chv = login("chv1")
    lesson = {"topic": "malaria", "title": "Atiridii", "body": "Da ntontom ntaban ase anadwo biara.", "language": "tw"}
    assert client.post("/lessons", headers=chv, json=lesson).status_code == 200
    lid = next(l["id"] for l in client.get("/lessons", headers=chv).json() if l["title"] == "Atiridii")
    first = client.get(f"/lessons/{lid}/audio", headers=chv)
    assert first.status_code == 200 and first.headers["content-type"] == "audio/wav"
    assert calls == ["abena_twi_high"]
    with wave.open(io.BytesIO(first.content)) as w:
        assert w.getnframes() == 800
    assert client.get(f"/lessons/{lid}/audio", headers=chv).content == first.content
    assert calls == ["abena_twi_high"]  # second play: from the database, no new request


def test_no_voice_and_service_down(client, login, monkeypatch):
    chv = login("chv1")
    client.post("/lessons", headers=chv, json={"topic": "general", "title": "Ga lesson", "body": "Test body text for a Ga lesson.", "language": "gaa"})
    lessons = {l["title"]: l["id"] for l in client.get("/lessons", headers=chv).json()}
    assert client.get(f"/lessons/{lessons['Ga lesson']}/audio", headers=chv).status_code == 400

    def down(text, voice):
        raise tts.SpeechError("You have run out of credits.")
    monkeypatch.setattr(tts, "speak", down)
    english = next(i for t, i in lessons.items() if t == "Preventing malaria")
    res = client.get(f"/lessons/{english}/audio", headers=chv)
    assert res.status_code == 503 and "credits" in res.json()["detail"]
    assert client.get(f"/lessons/{english}/audio", headers=login("ghs1")).status_code == 403
