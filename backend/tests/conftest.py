"""Shared test setup. Run from backend/:  pytest

Every test gets a fresh, empty database with the 7 demo accounts, so tests never
touch healthconnect.db and never depend on each other.

SQLite (default): a new file in a temporary folder for each test.
PostgreSQL: set TEST_DATABASE_URL to an EMPTY database you can wipe, e.g.
    TEST_DATABASE_URL=postgresql://localhost/healthconnect_test pytest
Each test then drops and re-creates its tables. GitHub Actions runs the tests both ways.
"""
import os
import runpy
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # seed.py and the data files use paths relative to backend/

# Set before the app is imported: fixed test secret, and never send a real SMS
os.environ["JWT_SECRET"] = "test-only-" + "0" * 54  # 64 characters: HS256 wants at least 32 bytes
os.environ["ARKESEL_API_KEY"] = ""
# Never point tests at a real database by accident: only TEST_DATABASE_URL is used
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("DB_SECRET_ID", None)
os.environ.pop("APP_SECRET_ID", None)
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import database  # noqa: E402


def empty_postgres():
    import psycopg

    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")


# main.py creates tables when imported, so point it at a throwaway database first
if TEST_DATABASE_URL:
    empty_postgres()
else:
    database.DB_PATH = os.path.join(tempfile.mkdtemp(), "import.db")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

PASSWORD = "Demo@1234"


@pytest.fixture
def client(tmp_path, monkeypatch):
    if TEST_DATABASE_URL:
        empty_postgres()
    else:
        monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    runpy.run_path("seed.py")  # tables + demo accounts
    return TestClient(main.app)


@pytest.fixture
def login(client):
    """login("chv1") -> headers with that user's token."""
    def _login(username, password=PASSWORD):
        res = client.post("/auth/login", json={"username": username, "password": password})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['token']}"}
    return _login


@pytest.fixture
def audit():
    """audit() -> list of actions in the audit log, oldest first."""
    def _audit():
        conn = database.get_db()
        rows = [r["action"] for r in conn.execute("SELECT action FROM access_log ORDER BY id")]
        conn.close()
        return rows
    return _audit


@pytest.fixture
def make_patient(client):
    """make_patient(headers, age=40, ...) -> a new fake patient registered by that CHV."""
    def _make(headers, **extra):
        body = {"full_name": "Test Patient A", "age": 30, "sex": "female", "consent": True, **extra}
        res = client.post("/patients", headers=headers, json=body)
        assert res.status_code == 200, res.text
        return res.json()
    return _make
