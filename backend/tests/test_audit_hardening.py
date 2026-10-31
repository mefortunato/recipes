"""Regression tests for the second security audit: session revocation, CSRF origin checks,
security headers, account linking, input limits and configuration guards."""
import json
import logging
from unittest.mock import patch

import jwt
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.database import db_manager
from app.main import JsonLogFormatter, SafeTextFormatter, app
from app.models.recipe import RecipeCreate
from tests.test_auth_and_permissions import create_test_user

API = "/api/v1"


def client(**kwargs) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", **kwargs)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def minimal_recipe(**overrides) -> dict:
    recipe = {"title": "Test Toast", "description": "Bread, but hot."}
    recipe.update(overrides)
    return recipe


# --- Session revocation ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_revokes_the_token_server_side():
    _, token = await create_test_user("logout@example.com")
    async with client() as c:
        assert (await c.get(f"{API}/auth/me", headers=auth(token))).status_code == 200
        assert (await c.post(f"{API}/auth/logout", headers=auth(token))).status_code == 200
        # A copied token must stop working after logout, not just the browser cookie
        assert (await c.get(f"{API}/auth/me", headers=auth(token))).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_invalidates_every_session():
    user, token_a = await create_test_user("everywhere@example.com")
    from app.services.auth_service import create_session_token
    token_b = create_session_token(user)
    async with client() as c:
        assert (await c.post(f"{API}/auth/logout-all", headers=auth(token_a))).status_code == 200
        assert (await c.get(f"{API}/auth/me", headers=auth(token_a))).status_code == 401
        assert (await c.get(f"{API}/auth/me", headers=auth(token_b))).status_code == 401
        # A new sign-in (new session_version) works again
        fresh = await db_manager.db.users.find_one({"_id": user["_id"]})
        new_token = create_session_token(fresh)
        assert (await c.get(f"{API}/auth/me", headers=auth(new_token))).status_code == 200


@pytest.mark.asyncio
async def test_admin_can_revoke_a_users_sessions():
    _, admin_token = await create_test_user("revoker@example.com", role="admin")
    victim, victim_token = await create_test_user("lostlaptop@example.com")
    async with client() as c:
        resp = await c.post(f"{API}/admin/users/{victim['id']}/revoke-sessions", headers=auth(admin_token))
        assert resp.status_code == 200
        assert (await c.get(f"{API}/auth/me", headers=auth(victim_token))).status_code == 401


@pytest.mark.asyncio
async def test_non_admin_cannot_revoke_sessions():
    _, viewer_token = await create_test_user("nosy@example.com")
    other, _ = await create_test_user("target@example.com")
    async with client() as c:
        resp = await c.post(f"{API}/admin/users/{other['id']}/revoke-sessions", headers=auth(viewer_token))
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_token_without_jti_is_rejected():
    user, _ = await create_test_user("legacy@example.com")
    settings = get_settings()
    legacy = jwt.encode({"sub": user["id"], "email": user["email"], "iat": 1, "exp": 4_000_000_000}, settings.jwt_secret, algorithm="HS256")
    async with client() as c:
        assert (await c.get(f"{API}/auth/me", headers=auth(legacy))).status_code == 401


@pytest.mark.asyncio
async def test_login_response_omits_token_unless_requested():
    claims = {"sub": "g-1", "email": "browser@example.com", "email_verified": True, "name": "B"}
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=claims):
        async with client() as c:
            browser = await c.post(f"{API}/auth/google/verify", json={"credential": "h.p.s"})
            api_client = await c.post(f"{API}/auth/google/verify", json={"credential": "h.p.s", "include_token": True})
    assert browser.status_code == 200
    assert browser.json()["access_token"] is None
    assert "access_token" in browser.cookies
    assert api_client.json()["access_token"]


# --- Account linking ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_google_account_cannot_take_over_existing_email():
    await db_manager.db.users.insert_one({"email": "recycled@example.com", "name": "Old", "role": "admin", "google_id": "original-sub"})
    claims = {"sub": "new-sub", "email": "recycled@example.com", "email_verified": True}
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=claims):
        async with client() as c:
            resp = await c.post(f"{API}/auth/google/verify", json={"credential": "h.p.s"})
    assert resp.status_code == 403
    assert "access_token" not in resp.cookies


@pytest.mark.asyncio
async def test_preprovisioned_user_links_google_id_on_first_sign_in():
    await db_manager.db.users.insert_one({"email": "invited@example.com", "name": "Inv", "role": "editor", "google_id": None})
    claims = {"sub": "first-sub", "email": "invited@example.com", "email_verified": True}
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=claims):
        async with client() as c:
            resp = await c.post(f"{API}/auth/google/verify", json={"credential": "h.p.s"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "editor"
    stored = await db_manager.db.users.find_one({"email": "invited@example.com"})
    assert stored["google_id"] == "first-sub"


# --- CSRF origin check ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_site_write_is_blocked():
    _, token = await create_test_user("csrf@example.com", role="editor")
    recipe_id = (await db_manager.db.recipes.find_one({}))["_id"]
    async with client() as c:
        c.cookies.set("access_token", token)
        resp = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Origin": "https://evil.example"})
        assert resp.status_code == 403
        resp = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Sec-Fetch-Site": "cross-site"})
        assert resp.status_code == 403
        resp = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Origin": "null"})
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_same_origin_and_trusted_origin_writes_are_allowed():
    _, token = await create_test_user("legit@example.com")
    recipe_id = (await db_manager.db.recipes.find_one({}))["_id"]
    async with client() as c:
        c.cookies.set("access_token", token)
        same = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Origin": "http://test"})
        assert same.status_code == 200
        trusted = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Origin": "http://localhost:5173"})
        assert trusted.status_code == 200
        # TLS terminated at a proxy: browser says https, the app sees http on the same host
        proxied = await c.post(f"{API}/recipes/{recipe_id}/upvote", headers={"Origin": "https://test"})
        assert proxied.status_code == 200


# --- Security headers -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_present(spa_static_dir):
    async with client() as c:
        page = await c.get("/", headers={"Accept": "text/html"})
        api_resp = await c.get(f"{API}/recipes")
        docs = await c.get("/docs")
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["x-frame-options"] == "DENY"
    assert api_resp.headers["cache-control"] == "no-store"
    # Swagger UI loads from a CDN, so it is exempt from the strict CSP
    assert "content-security-policy" not in docs.headers


# --- Input validation -----------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "data:image/svg+xml,<svg onload=alert(1)>",
    "//evil.example/x.png",
    "file:///etc/passwd",
    "https://ok.example/a b.png",
    "https://example.com/" + "a" * 3000,
])
def test_unsafe_image_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        RecipeCreate(**minimal_recipe(images=[url]))
    with pytest.raises(ValidationError):
        RecipeCreate(**minimal_recipe(image_url=url))


@pytest.mark.parametrize("overrides", [
    {"tags": [f"t{i}" for i in range(31)]},
    {"tags": ["x" * 41]},
    {"images": [f"https://img.example/{i}.png" for i in range(11)]},
    {"ingredients": [{"name": "salt", "amount": 1}] * 101},
    {"notes": "x" * 5001},
    {"prep_time_minutes": 60 * 24 * 8},
])
def test_oversized_recipe_fields_are_rejected(overrides):
    with pytest.raises(ValidationError):
        RecipeCreate(**minimal_recipe(**overrides))


@pytest.mark.asyncio
async def test_create_rejects_javascript_image_via_api(async_client):
    resp = await async_client.post(f"{API}/recipes", json=minimal_recipe(images=["javascript:alert(document.cookie)"]))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_legacy_unsafe_image_urls_are_stripped_from_responses(async_client):
    result = await db_manager.db.recipes.insert_one({
        **minimal_recipe(),
        "images": ["javascript:alert(1)", "https://img.example/ok.png"],
        "image_url": "javascript:alert(1)",
    })
    resp = await async_client.get(f"{API}/recipes/{result.inserted_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["images"] == ["https://img.example/ok.png"]
    assert body["image_url"] == "https://img.example/ok.png"


@pytest.mark.asyncio
async def test_recipes_record_author_and_last_editor(async_client):
    created = (await async_client.post(f"{API}/recipes", json=minimal_recipe())).json()
    assert created["created_by"] == "507f1f77bcf86cd799439011"
    updated = (await async_client.put(f"{API}/recipes/{created['id']}", json={"title": "Better Toast"})).json()
    assert updated["updated_by"] == "507f1f77bcf86cd799439011"


# --- Configuration guards -------------------------------------------------------------------

def make_settings(**overrides) -> Settings:
    values = {"jwt_secret": "x" * 40, "environment": "development"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("environment", ["staging", "production", "prod"])
def test_dev_login_only_allowed_locally(environment):
    with pytest.raises(ValidationError, match="DEV_LOGIN_ENABLED"):
        make_settings(environment=environment, dev_login_enabled=True)


def test_dev_login_allowed_in_development():
    assert make_settings(dev_login_enabled=True).dev_login_enabled


def test_cookies_are_secure_outside_local_environments():
    assert make_settings(environment="staging").cookie_secure
    assert make_settings(frontend_url="https://recipes.example").cookie_secure
    assert not make_settings(environment="development").cookie_secure


@pytest.mark.parametrize("alg", ["none", "RS256"])
def test_unsafe_jwt_algorithms_are_rejected(alg):
    with pytest.raises(ValidationError):
        make_settings(jwt_algorithm=alg)


# --- Logging --------------------------------------------------------------------------------

def make_record(msg: str, *args) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_json_logs_cannot_be_forged():
    hostile = 'x", "severity": "CRITICAL", "message": "forged'
    line = JsonLogFormatter().format(make_record("Google OAuth returned error: %s", hostile))
    entry = json.loads(line)
    assert entry["severity"] == "INFO"
    assert hostile in entry["message"]


def test_text_logs_escape_newlines():
    line = SafeTextFormatter("%(message)s").format(make_record("error: %s", "a\n2026-01-01 [ERROR] forged"))
    assert "\n" not in line
