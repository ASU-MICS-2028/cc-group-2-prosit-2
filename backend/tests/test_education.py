"""Health education lessons: starter content, review rule and access."""

LESSON = {"topic": "malaria", "title": "Test lesson", "body": "A fake lesson body that is long enough.", "language": "tw"}


def test_starter_lessons_exist_and_start_unreviewed(client, login):
    lessons = client.get("/lessons", headers=login("chv1")).json()
    assert len(lessons) == 4
    assert all(lesson["reviewed_at"] is None and lesson["language"] == "en" for lesson in lessons)


def test_access(client, login):
    for user in ["pharm1", "ghs1", "admin1"]:
        assert client.get("/lessons", headers=login(user)).status_code == 403
    assert client.get("/lessons").status_code == 401
    assert client.post("/lessons/1/review", headers=login("chv1")).status_code == 403


def test_new_lesson_needs_review_by_someone_else(client, login):
    chv, nurse, doctor = login("chv1"), login("nurse1"), login("doctor1")
    lesson_id = client.post("/lessons", headers=nurse, json=LESSON).json()["id"]
    assert client.post(f"/lessons/{lesson_id}/review", headers=nurse).status_code == 403  # not your own
    assert client.post(f"/lessons/{lesson_id}/review", headers=doctor).status_code == 200
    assert client.post(f"/lessons/{lesson_id}/review", headers=doctor).status_code == 400  # only once
    saved = next(x for x in client.get("/lessons", headers=chv).json() if x["id"] == lesson_id)
    assert saved["reviewer_name"] == "Dr Emmanuel Abugri" and saved["reviewed_at"]


def test_validation_and_duplicates(client, login):
    chv = login("chv1")
    assert client.post("/lessons", headers=chv, json={**LESSON, "language": "fr"}).status_code == 422
    assert client.post("/lessons", headers=chv, json={**LESSON, "body": "short"}).status_code == 422
    assert client.post("/lessons", headers=chv, json=LESSON).status_code == 200
    assert client.post("/lessons", headers=chv, json=LESSON).status_code == 400
    assert client.post("/lessons/99999/review", headers=login("nurse1")).status_code == 404
