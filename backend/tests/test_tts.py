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


def test_all_abena_languages_and_voice_choice(client, login, monkeypatch):
    used = []
    monkeypatch.setattr(tts, "speak", lambda text, voice: used.append(voice) or tone())
    chv = login("chv1")
    for code in ["gpe", "ha", "pcm", "yo", "sw"]:
        body = {"topic": "general", "title": f"Lesson {code}", "body": "A short test lesson body here.", "language": code}
        assert client.post("/lessons", headers=chv, json=body).status_code == 200
    lessons = {l["title"]: l["id"] for l in client.get("/lessons", headers=chv).json()}
    for code in ["gpe", "ha", "pcm", "yo", "sw"]:
        assert client.get(f"/lessons/{lessons['Lesson ' + code]}/audio", headers=chv).status_code == 200
    assert used == ["kobby_gpe_high", "abubakar_hau", "james_pcm_high", "folami_yor", "amani_swh"]
    english = lessons["Preventing malaria"]
    client.get(f"/lessons/{english}/audio?gender=male", headers=chv)
    assert used[-1] == "kwabena_eng_high"


def test_busy_service_is_retried(monkeypatch):
    replies = [(503, {"retry_after_seconds": 0}), (503, {"retry_after_seconds": 0}), (200, {"audio_base64": "UklGRg=="})]

    class Reply:
        def __init__(self, code, data):
            self.status_code, self._data = code, data

        def json(self):
            return self._data

    monkeypatch.setattr(tts.requests, "post", lambda *a, **k: Reply(*replies.pop(0)))
    monkeypatch.setattr(tts.time, "sleep", lambda s: None)
    assert tts.speak("Hello", "akua_eng_high") == b"RIFF"
