"""Hackathon demo login. No stored passwords. No secrets in responses."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.demo_auth import router
from app.config import settings


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_continue_as_demo():
    response = _client().post("/api/v1/auth/demo", json={"continue_as_demo": True})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["user"]["email"] == settings.demo_user_email
    assert body["user"]["paper_trading"] is True
    assert body["user"]["dry_run"] is True
    assert body["user"]["live_trading"] is False
    assert "password" not in body
    assert "api_key" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_demo_email_login():
    response = _client().post(
        "/api/v1/auth/demo",
        json={"email": settings.demo_user_email, "password": "not-a-secret-ignored"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "demo"


def test_unknown_email_rejected():
    response = _client().post("/api/v1/auth/demo", json={"email": "other@example.com"})
    assert response.status_code == 401
