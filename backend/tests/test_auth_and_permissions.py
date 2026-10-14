import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.dependencies.auth import require_editor_user
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_auth_config_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "google_client_id" in data
        assert "dev_login_enabled" in data
        assert "allowed_editor_emails" in data


@pytest.mark.asyncio
async def test_demo_login_editor_and_me():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as demo editor
        resp = await client.post("/api/v1/auth/demo-login?as_editor=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["can_edit"] is True
        assert data["user"]["role"] == "editor"

        token = data["access_token"]

        # 2. Call /me with Bearer token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["can_edit"] is True
        assert me_data["email"] == "chef@gourmetvault.com"


@pytest.mark.asyncio
async def test_demo_login_viewer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as demo viewer
        resp = await client.post("/api/v1/auth/demo-login?as_editor=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["can_edit"] is False
        assert data["user"]["role"] == "viewer"


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as viewer
        login_resp = await client.post("/api/v1/auth/demo-login?as_editor=false")
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Attempt to create recipe as viewer
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as editor
        login_resp = await client.post("/api/v1/auth/demo-login?as_editor=true")
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

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
