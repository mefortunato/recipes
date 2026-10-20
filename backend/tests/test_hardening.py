"""Regression tests for voting, filtering, user-account and OAuth hardening."""
import asyncio
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.config import get_settings
from app.database import db_manager
from app.main import app
from app.repositories.recipe_repository import RecipeRepository
from app.services.auth_service import get_or_create_user
from tests.test_auth_and_permissions import create_test_user


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def first_recipe() -> dict:
    return await db_manager.db.recipes.find_one({})


# --- Voting -------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_upvotes_are_all_counted(monkeypatch):
    recipe = await first_recipe()
    repo = RecipeRepository(db_manager.db)
    voters = [str(ObjectId()) for _ in range(25)]

    # mongomock never yields mid-request; force a yield after each read so concurrent votes
    # interleave between reading and writing, as they do against a real server
    original_find_one = repo.collection.find_one

    async def find_one_then_yield(*args, **kwargs):
        doc = await original_find_one(*args, **kwargs)
        await asyncio.sleep(0)
        return doc

    monkeypatch.setattr(repo.collection, "find_one", find_one_then_yield)

    await asyncio.gather(*(repo.vote(str(recipe["_id"]), uid, 1) for uid in voters))

    doc = await db_manager.db.recipes.find_one({"_id": recipe["_id"]})
    assert sorted(doc["upvoted_by"]) == sorted(voters)
    assert doc["upvotes_count"] == recipe["upvotes_count"] + 25
    assert doc["aggregate_rating"] == doc["upvotes_count"] - doc["downvotes_count"]


@pytest.mark.asyncio
async def test_switching_and_toggling_votes_keeps_counts_consistent():
    recipe = await first_recipe()
    repo = RecipeRepository(db_manager.db)
    rid, uid = str(recipe["_id"]), str(ObjectId())
    base_up, base_down = recipe["upvotes_count"], recipe["downvotes_count"]

    r = await repo.vote(rid, uid, 1)
    assert (r.upvotes_count, r.downvotes_count, r.user_vote) == (base_up + 1, base_down, 1)
    r = await repo.vote(rid, uid, 1)  # repeat without toggle is a no-op
    assert (r.upvotes_count, r.downvotes_count) == (base_up + 1, base_down)
    r = await repo.vote(rid, uid, -1)  # switch sides
    assert (r.upvotes_count, r.downvotes_count, r.user_vote) == (base_up, base_down + 1, -1)
    r = await repo.vote(rid, uid, -1, toggle=True)  # toggle off
    assert (r.upvotes_count, r.downvotes_count, r.user_vote) == (base_up, base_down, 0)
    assert r.aggregate_rating == base_up - base_down


@pytest.mark.asyncio
async def test_vote_initializes_counters_on_legacy_documents():
    legacy_voter = str(ObjectId())
    result = await db_manager.db.recipes.insert_one({"title": "Legacy", "description": "", "upvoted_by": [legacy_voter]})
    repo = RecipeRepository(db_manager.db)

    r = await repo.vote(str(result.inserted_id), str(ObjectId()), 1)
    assert (r.upvotes_count, r.downvotes_count, r.aggregate_rating) == (2, 0, 2)


@pytest.mark.asyncio
async def test_clients_cannot_set_vote_counts(async_client):
    payload = {
        "title": "Inflated Recipe",
        "description": "Tries to set its own score",
        "upvotes_count": 9999,
        "downvotes_count": 0,
        "aggregate_rating": 9999,
        "is_favorite": True,
    }
    created = (await async_client.post("/api/v1/recipes", json=payload)).json()
    assert (created["upvotes_count"], created["aggregate_rating"], created["is_favorite"]) == (0, 0, False)

    updated = (await async_client.put(f"/api/v1/recipes/{created['id']}", json={"aggregate_rating": 50})).json()
    assert updated["aggregate_rating"] == 0


# --- Listing / filtering ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_is_kept_when_filtering_favorites():
    user, token = await create_test_user(email="fav@example.com")
    repo = RecipeRepository(db_manager.db)
    recipes = await db_manager.db.recipes.find({}).to_list(length=None)
    # Upvote every recipe so the favorites filter alone would match all of them
    for r in recipes:
        await repo.vote(str(r["_id"]), user["id"], 1)

    async with client() as c:
        resp = await c.get(
            "/api/v1/recipes",
            params={"search": recipes[0]["title"], "is_favorite": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
    titles = [r["title"] for r in resp.json()["recipes"]]
    assert titles == [recipes[0]["title"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("sort_order", ["0", "2", "-5"])
async def test_invalid_sort_order_is_rejected(sort_order):
    async with client() as c:
        resp = await c.get("/api/v1/recipes", params={"sort_order": sort_order})
    assert resp.status_code == 422


# --- Users & permissions ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_first_sign_in_creates_one_user():
    info = {"email": "Racer@Example.com", "name": "Racer", "google_id": "g-1"}
    users = await asyncio.gather(*(get_or_create_user(db_manager.db, info) for _ in range(5)))
    assert len({u["_id"] for u in users}) == 1
    assert await db_manager.db.users.count_documents({"email": "racer@example.com"}) == 1


@pytest.mark.asyncio
async def test_legacy_permission_flags_migrate_to_role():
    result = await db_manager.db.users.insert_one(
        {"email": "legacy@example.com", "name": "Legacy", "role": "viewer", "can_edit": True}
    )
    user = await get_or_create_user(db_manager.db, {"email": "legacy@example.com"})
    assert (user["role"], user["can_edit"], user["is_admin"]) == ("editor", True, False)

    stored = await db_manager.db.users.find_one({"_id": result.inserted_id})
    assert stored["role"] == "editor"
    assert "can_edit" not in stored


@pytest.mark.asyncio
async def test_demoting_legacy_editor_revokes_edit_rights():
    target = await db_manager.db.users.insert_one(
        {"email": "old_editor@example.com", "name": "Old", "role": "viewer", "can_edit": True}
    )
    _, admin_token = await create_test_user(email="demoting_admin@example.com", role="admin")
    async with client() as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{target.inserted_id}/permissions",
            json={"role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


@pytest.mark.asyncio
async def test_admin_user_search_escapes_regex_and_counts_all_roles():
    _, admin_token = await create_test_user(email="counting_admin@example.com", role="admin")
    await create_test_user(email="counting_editor@example.com", role="editor")
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with client() as c:
        bad_regex = await c.get("/api/v1/admin/users", params={"search": "(unclosed["}, headers=headers)
        assert bad_regex.status_code == 200
        assert bad_regex.json()["users"] == []

        admins_tab = (await c.get(
            "/api/v1/admin/users", params={"search": "counting_", "role": "admin"}, headers=headers
        )).json()
    assert [u["email"] for u in admins_tab["users"]] == ["counting_admin@example.com"]
    # "All" tab count still covers every matching user, not just the selected role
    assert admins_tab["total"] == 2
    assert (admins_tab["admin_count"], admins_tab["editor_count"]) == (1, 1)


@pytest.mark.asyncio
async def test_unversioned_api_alias_is_gone():
    async with client() as c:
        assert (await c.get("/api/auth/config")).status_code == 404
        assert (await c.get("/api/v1/auth/config")).status_code == 200


# --- Session cookie & OAuth ---------------------------------------------------------------------

VERIFIED_CLAIMS = {"sub": "g-42", "email": "cookie@example.com", "email_verified": True, "name": "Cookie"}


@pytest.mark.asyncio
@pytest.mark.parametrize("environment,secure", [("production", True), ("development", False)])
async def test_session_cookie_secure_flag(monkeypatch, environment, secure):
    monkeypatch.setattr(get_settings(), "environment", environment)
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=VERIFIED_CLAIMS):
        async with client() as c:
            resp = await c.post("/api/v1/auth/google/verify", json={"credential": "x.y.z"})
    set_cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert ("secure" in set_cookie) is secure


@pytest.fixture
def oauth_code_flow(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "frontend_url", "http://test")
    profile = {"google_id": "g-7", "email": "oauth@example.com", "name": "OAuth User", "picture": None}
    with patch("app.routers.auth.exchange_google_code", new=AsyncMock(return_value=profile)) as exchange:
        yield exchange


@pytest.mark.asyncio
async def test_oauth_login_round_trip_with_matching_state(oauth_code_flow):
    async with client() as c:
        login = await c.get("/api/v1/auth/google/login")
        state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
        assert c.cookies.get("oauth_state") == state

        callback = await c.get("/api/v1/auth/google/callback", params={"code": "abc", "state": state})
    assert callback.headers["location"].endswith("?auth_success=1")
    assert "access_token" in callback.cookies
    oauth_code_flow.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"code": "abc"}, {"code": "abc", "state": "forged"}, {"error": "access_denied"}])
async def test_oauth_callback_rejects_missing_or_forged_state(oauth_code_flow, params):
    async with client() as c:
        await c.get("/api/v1/auth/google/login")
        callback = await c.get("/api/v1/auth/google/callback", params=params)
    assert callback.headers["location"].endswith("?error=oauth_failed")
    assert "access_token" not in callback.cookies
    oauth_code_flow.assert_not_awaited()
