from datetime import datetime, timezone
import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager
from app.dependencies.auth import require_editor_user
from app.services.auth_service import create_access_token


async def create_test_user(email: str, role: str = "viewer", name: str = "Test User"):
    user_doc = {
        "_id": ObjectId(),
        "email": email,
        "name": name,
        "role": role,
        "can_edit": role in ("editor", "admin"),
        "is_admin": role == "admin",
        "is_bootstrap": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db_manager.db.users.insert_one(user_doc)
    token = create_access_token({"sub": str(user_doc["_id"]), "email": email})
    user_doc["id"] = str(user_doc["_id"])
    return user_doc, token


@pytest.mark.asyncio
async def test_auth_config_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "google_client_id" in data
        assert "dev_login_enabled" in data
        assert data["dev_login_enabled"] is False
        # Admin emails must not be exposed to anonymous callers
        assert "allowed_editor_emails" not in data


@pytest.mark.asyncio
async def test_health_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

        resp_live = await client.get("/health/live")
        assert resp_live.status_code == 200
        assert resp_live.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_google_verify_without_client_secret():
    """Verify Google Identity Services ID token verification does NOT require GOOGLE_CLIENT_SECRET."""
    from unittest.mock import patch

    # Claims as returned by google-auth after it has verified the token's signature
    claims = {
        "sub": "google-user-12345",
        "email": "gourmet.chef@example.com",
        "email_verified": True,
        "name": "Chef Auguste",
        "picture": "https://example.com/avatar.jpg",
        "aud": "test-client-id.apps.googleusercontent.com",
        "iss": "https://accounts.google.com",
    }

    transport = ASGITransport(app=app)
    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=claims):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/google/verify",
                json={"credential": "header.payload.signature"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "gourmet.chef@example.com"
        assert data["user"]["name"] == "Chef Auguste"
        assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_demo_login_endpoint_is_removed():
    """Verify demo-login route was completely removed as a security vulnerability."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/demo-login?as_editor=true")
        assert resp.status_code in (404, 405)


@pytest.mark.asyncio
async def test_authenticated_editor_and_me():
    user, token = await create_test_user(
        email="test_editor@example.com",
        role="editor",
        name="Test Editor User",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Call /me with Bearer token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["can_edit"] is True
        assert me_data["role"] == "editor"
        assert me_data["email"] == "test_editor@example.com"


@pytest.mark.asyncio
async def test_authenticated_viewer():
    user, token = await create_test_user(
        email="test_viewer@example.com",
        role="viewer",
        name="Test Viewer User",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["can_edit"] is False
        assert me_data["role"] == "viewer"


@pytest.mark.asyncio
async def test_anonymous_user_cannot_create_recipe():
    # Ensure no dependency override is present
    app.dependency_overrides.pop(require_editor_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        recipe_payload = {
            "title": "Unauthorized Recipe",
            "description": "This should be rejected",
            "ingredients": [{"name": "Sugar", "amount": 1, "unit": "cup"}],
            "instructions": [{"step_number": 1, "instruction": "Mix ingredients"}],
        }
        resp = await client.post("/api/v1/recipes", json=recipe_payload)
        # Should be rejected with 401 Unauthorized
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unauthorized_viewer_cannot_create_recipe():
    app.dependency_overrides.pop(require_editor_user, None)

    user, token = await create_test_user(
        email="viewer_blocked@example.com",
        role="viewer",
        name="Test Viewer",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        recipe_payload = {
            "title": "Viewer Attempted Recipe",
            "description": "This should be rejected as forbidden",
            "ingredients": [{"name": "Salt", "amount": 1, "unit": "pinch"}],
            "instructions": [{"step_number": 1, "instruction": "Season well"}],
        }
        resp = await client.post(
            "/api/v1/recipes",
            json=recipe_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Forbidden" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_authorized_editor_can_create_recipe():
    user, token = await create_test_user(
        email="editor_chef@example.com",
        role="editor",
        name="Editor Chef",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        recipe_payload = {
            "title": "Chef Special Pasta",
            "description": "Authentic fresh pasta",
            "cuisine": "Italian",
            "ingredients": [{"name": "Semolina", "amount": 200, "unit": "g"}],
            "instructions": [{"step_number": 1, "instruction": "Knead dough"}],
        }
        resp = await client.post(
            "/api/v1/recipes",
            json=recipe_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Chef Special Pasta"
