"""Tests run against a throwaway SQLite database and never call a real AI provider."""
import json
import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp(prefix="hamstar-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{os.path.join(_tmp, 'test.db').replace(os.sep, '/')}",
    "UPLOAD_DIR": os.path.join(_tmp, "uploads"),
    "JWT_SECRET": "test-secret-that-is-long-enough-for-hs256-signing",
    "MISTRAL_API_KEY": "",
    "GROQ_API_KEY": "",
    "MAX_UPLOAD_SIZE_MB": "1",
    "REMINDERS_ENABLED": "false",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.groq_service import get_groq  # noqa: E402
from app.services.mistral_service import get_mistral  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


class Student:
    """A signed-in test user with small helpers around the API."""

    def __init__(self, client: TestClient):
        self.client = client
        self.email = f"{uuid.uuid4().hex[:10]}@test.dev"
        r = client.post("/api/auth/register", json={"email": self.email, "password": "squeak123"})
        assert r.status_code == 201, r.text
        self.headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}
        self.id = r.json()["data"]["user"]["id"]

    def get(self, path):
        return self.client.get(path, headers=self.headers)

    def post(self, path, body=None, **kw):
        return self.client.post(path, headers=self.headers, json=body, **kw)

    def data(self, response):
        assert response.json()["success"], response.text
        return response.json()["data"]

    def answer(self, question_id, option, **extra):
        return self.data(self.post("/api/attempts/evaluate", {"question_id": question_id, "selected_option": option, **extra}))

    def set(self, **fields):
        """Put the account into a given state directly (e.g. one answer away from a badge)."""
        with SessionLocal() as db:
            user = db.get(User, self.id)
            for k, v in fields.items():
                setattr(user, k, v)
            db.commit()

    def diagnose(self, session_id, respond):
        """Answer follow-ups with `respond(followup) -> option` until the diagnosis is stated."""
        view = None
        for _ in range(4):
            f = self.data(self.post(f"/api/diagnostics/{session_id}/followup"))
            if not f.get("question"):
                return f["diagnostic"]
            view = self.data(self.post(f"/api/diagnostics/{session_id}/evaluate-followup", {"answer": respond(f)}))
            if view["diagnosis"]:
                return view
        return view


@pytest.fixture
def student(client):
    return Student(client)


@pytest.fixture
def other(client):
    return Student(client)


def chat(obj) -> dict:
    """A chat-completions reply carrying `obj` as its JSON content."""
    return {"choices": [{"message": {"content": obj if isinstance(obj, str) else json.dumps(obj)}}]}


@pytest.fixture
def fake_ai(monkeypatch):
    """
    Stand-ins for Mistral and Groq. `replies` maps a word found in the prompt to the reply;
    tests add what they need. Every call is recorded in `calls`.
    """
    mistral, groq = get_mistral(), get_groq()
    state = {"replies": {"From the material below": chat({"title": "", "concepts": ["Photosynthesis"], "sections": []})}, "calls": []}
    # by default the maths check has nothing to say; tests that are about it set their own reply
    state["replies"]["You check the answer keys"] = chat({"results": []})
    state["replies"]["Decide which ONE kind of mistake"] = chat({"mistake_type": "CARELESS_SLIP", "reason": "A small slip."})

    def post(provider):
        def _post(path, payload):
            state["calls"].append((provider, path))
            if path == "/ocr":
                return state["replies"].get("ocr", {"pages": [{"markdown": "Photosynthesis turns light, water and carbon dioxide into glucose and oxygen."}]})
            prompt = payload["messages"][-1]["content"]
            if isinstance(prompt, list):  # text plus an image
                prompt = prompt[0]["text"]
            for needle, reply in state["replies"].items():
                if needle != "ocr" and needle in prompt:
                    return reply(prompt) if callable(reply) else reply
            raise AssertionError(f"no fake reply for prompt starting: {prompt[:80]!r}")
        return _post

    monkeypatch.setattr(mistral, "api_key", "test-key")
    monkeypatch.setattr(groq, "api_key", "test-key")
    monkeypatch.setattr(mistral, "_post", post("mistral"))
    monkeypatch.setattr(groq, "_post", post("groq"))
    return state
