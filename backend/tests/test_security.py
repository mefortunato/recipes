"""Regression tests for authentication and file-serving vulnerabilities."""
import base64
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.database import db_manager
from app.main import app
from tests.test_auth_and_permissions import create_test_user


def forged_google_token(email: str) -> str:
    """An unsigned token that merely claims to be from Google."""
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'none'})}.{b64({'email': email, 'email_verified': True, 'sub': 'x'})}.sig"


async def post_credential(credential: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/auth/google/verify", json={"credential": credential})


@pytest.mark.asyncio
async def test_forged_google_token_is_rejected():
    """A token that fails signature verification must not fall back to trusting its claims."""
    with patch(
        "app.services.auth_service.id_token.verify_oauth2_token",
        side_effect=ValueError("Could not verify token signature."),
    ):
        resp = await post_credential(forged_google_token("bootstrap_admin@example.com"))

    assert resp.status_code == 400
    assert "access_token" not in resp.cookies
    assert await db_manager.db.users.count_documents({}) == 0


@pytest.mark.asyncio
async def test_google_token_with_unverified_email_is_rejected():
    claims = {"sub": "123", "email": "someone@example.com", "email_verified": False}
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=claims):
        resp = await post_credential("header.payload.signature")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_google_verify_requires_client_id(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    with patch("app.services.auth_service.id_token.verify_oauth2_token") as verify:
        resp = await post_credential(forged_google_token("someone@example.com"))
    assert resp.status_code == 400
    verify.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/..%2F..%2Fpyproject.toml", "/..%2F..%2F..%2Fetc%2Fpasswd"])
async def test_spa_fallback_does_not_serve_files_outside_static_dir(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(path)
    assert "[project]" not in resp.text
    assert "root:" not in resp.text


def make_settings(**overrides) -> Settings:
    values = {"jwt_secret": "x" * 40, "environment": "development"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_empty_allowed_editor_emails_grants_nobody_admin():
    settings = make_settings(allowed_editor_emails="")
    assert settings.editor_emails_list == []
    assert not settings.is_privileged_email("anyone@example.com")
    assert not settings.all_users_can_edit


def test_wildcard_grants_edit_but_never_admin():
    settings = make_settings(allowed_editor_emails="*, Owner@Example.com")
    assert settings.all_users_can_edit
    assert settings.editor_emails_list == ["owner@example.com"]
    assert settings.is_privileged_email("owner@example.com")
    assert not settings.is_privileged_email("anyone@example.com")


@pytest.mark.asyncio
async def test_wildcard_viewer_can_edit_but_not_administer(monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_editor_emails", "*")
    _, token = await create_test_user(email="wildcard_viewer@example.com", role="viewer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        me = (await client.get("/api/v1/auth/me", headers=headers)).json()
        assert me["can_edit"] is True
        assert me["is_admin"] is False
        assert (await client.get("/api/v1/admin/users", headers=headers)).status_code == 403


@pytest.mark.parametrize("secret", ["", "short", "super-secret-recipes-jwt-token-key-2026"])
def test_production_rejects_insecure_jwt_secret(secret):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make_settings(environment="production", jwt_secret=secret)


def test_development_replaces_insecure_jwt_secret():
    settings = make_settings(jwt_secret="super-secret-recipes-jwt-token-key-2026")
    assert settings.jwt_secret != "super-secret-recipes-jwt-token-key-2026"
    assert len(settings.jwt_secret) >= 32


def test_production_rejects_cors_wildcard_and_dev_login():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        make_settings(environment="production", cors_origins=["*"])
    with pytest.raises(ValidationError, match="DEV_LOGIN_ENABLED"):
        make_settings(environment="production", dev_login_enabled=True)


def test_production_accepts_strong_settings():
    settings = make_settings(environment="production", jwt_secret="a" * 64)
    assert settings.jwt_secret == "a" * 64
