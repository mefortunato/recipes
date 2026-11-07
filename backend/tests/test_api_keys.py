"""Personal API keys let agents submit recipes as their owner, with a narrower scope than a session."""
import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import db_manager
from app.services.api_key_service import hash_api_key
from tests.test_auth_and_permissions import create_test_user

RECIPE = {
    "title": "Agent Fried Rice",
    "description": "Co-authored with an agent.",
    "servings": 2,
    "difficulty": "Easy",
    "ingredients": [{"name": "rice", "amount": 3, "unit": "cups"}],
    "instructions": [{"step_number": 1, "instruction": "Fry the rice."}],
}


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def make_key(client, session_token, name="My agent"):
    resp = await client.post("/api/v1/auth/api-keys", json={"name": name}, headers=bearer(session_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_editor_creates_key_and_agent_submits_recipe(client):
    editor, token = await create_test_user("chef@example.com", role="editor")
    created = await make_key(client, token)
    assert created["key"].startswith("rbk_")
    assert created["key"].startswith(created["prefix"])

    resp = await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(created["key"]))
    assert resp.status_code == 201, resp.text
    recipe = resp.json()
    assert recipe["created_by"] == str(editor["_id"])

    resp = await client.put(f"/api/v1/recipes/{recipe['id']}", json={"servings": 3}, headers=bearer(created["key"]))
    assert resp.status_code == 200
    assert resp.json()["servings"] == 3

    listed = (await client.get("/api/v1/auth/api-keys", headers=bearer(token))).json()["keys"]
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0] and "key_hash" not in listed[0]
    assert listed[0]["last_used_at"] is not None


@pytest.mark.asyncio
async def test_only_digest_is_stored(client):
    _, token = await create_test_user("chef@example.com", role="editor")
    created = await make_key(client, token)
    doc = await db_manager.db.api_keys.find_one({"_id": ObjectId(created["id"])})
    assert doc["key_hash"] == hash_api_key(created["key"])
    assert created["key"] not in str(doc)


@pytest.mark.asyncio
async def test_viewer_cannot_create_keys(client):
    _, token = await create_test_user("viewer@example.com", role="viewer")
    resp = await client.post("/api/v1/auth/api-keys", json={"name": "x"}, headers=bearer(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_key_cannot_escalate(client):
    _, token = await create_test_user("admin2@example.com", role="admin")
    key = (await make_key(client, token))["key"]
    recipe_id = (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(key))).json()["id"]

    assert (await client.delete(f"/api/v1/recipes/{recipe_id}", headers=bearer(key))).status_code == 403
    assert (await client.get("/api/v1/admin/users", headers=bearer(key))).status_code == 403
    assert (await client.post("/api/v1/auth/api-keys", json={"name": "y"}, headers=bearer(key))).status_code == 403
    assert (await client.get("/api/v1/auth/api-keys", headers=bearer(key))).status_code == 403
    assert (await client.post("/api/v1/auth/logout-all", headers=bearer(key))).status_code == 403
    # The owner's own session can still delete
    assert (await client.delete(f"/api/v1/recipes/{recipe_id}", headers=bearer(token))).status_code == 204


@pytest.mark.asyncio
async def test_revoked_or_bogus_key_rejected(client):
    _, token = await create_test_user("chef@example.com", role="editor")
    created = await make_key(client, token)
    assert (await client.delete(f"/api/v1/auth/api-keys/{created['id']}", headers=bearer(token))).status_code == 204
    assert (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(created["key"]))).status_code == 401
    assert (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer("rbk_not-a-real-key"))).status_code == 401


@pytest.mark.asyncio
async def test_cannot_revoke_someone_elses_key(client):
    _, token_a = await create_test_user("a@example.com", role="editor")
    _, token_b = await create_test_user("b@example.com", role="editor")
    created = await make_key(client, token_a)
    assert (await client.delete(f"/api/v1/auth/api-keys/{created['id']}", headers=bearer(token_b))).status_code == 404
    assert (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(created["key"]))).status_code == 201


@pytest.mark.asyncio
async def test_demoted_owner_key_stops_editing(client):
    editor, token = await create_test_user("chef@example.com", role="editor")
    key = (await make_key(client, token))["key"]
    await db_manager.db.users.update_one({"_id": editor["_id"]}, {"$set": {"role": "viewer", "can_edit": False}})
    assert (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(key))).status_code == 403


@pytest.mark.asyncio
async def test_key_in_cookie_is_ignored(client):
    _, token = await create_test_user("chef@example.com", role="editor")
    key = (await make_key(client, token))["key"]
    client.cookies.set("access_token", key)
    assert (await client.post("/api/v1/recipes", json=RECIPE)).status_code == 401


@pytest.mark.asyncio
async def test_admin_revoke_sessions_also_revokes_keys(client):
    editor, token = await create_test_user("chef@example.com", role="editor")
    key = (await make_key(client, token))["key"]
    # Bootstrap admin from conftest (ALLOWED_EDITOR_EMAILS)
    _, admin_token = await create_test_user("bootstrap_admin@example.com", role="viewer")
    resp = await client.post(f"/api/v1/admin/users/{editor['_id']}/revoke-sessions", headers=bearer(admin_token))
    assert resp.status_code == 200
    assert (await client.post("/api/v1/recipes", json=RECIPE, headers=bearer(key))).status_code == 401


@pytest.mark.asyncio
async def test_agent_guide_is_public_and_has_base_url(client):
    resp = await client.get("/api/v1/agents/guide")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "http://test/api/v1/recipes" in resp.text
    assert "{{API_BASE}}" not in resp.text
