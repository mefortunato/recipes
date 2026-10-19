from datetime import datetime, timezone
import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager
from app.config import get_settings
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
async def test_admin_user_attributes():
    user, token = await create_test_user(
        email="lead_admin@example.com",
        role="admin",
        name="Lead Admin",
    )
    assert user["role"] == "admin"
    assert user["can_edit"] is True
    assert user["is_admin"] is True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["can_edit"] is True
        assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_can_list_users():
    _, admin_token = await create_test_user(
        email="list_admin@example.com",
        role="admin",
        name="List Admin",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        users_resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert users_resp.status_code == 200
        data = users_resp.json()
        assert "users" in data
        assert "total" in data
        assert "admin_count" in data
        assert data["admin_count"] >= 1


@pytest.mark.asyncio
async def test_admin_can_modify_user_permissions():
    _, admin_token = await create_test_user(
        email="perm_admin@example.com",
        role="admin",
        name="Perm Admin",
    )

    viewer_user, viewer_token = await create_test_user(
        email="managed_viewer@example.com",
        role="viewer",
        name="Managed Viewer",
    )
    viewer_id = viewer_user["id"]
    assert viewer_user["role"] == "viewer"
    assert viewer_user["can_edit"] is False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Viewer attempts to create a recipe -> Forbidden (403)
        recipe_payload = {
            "title": "Blocked Viewer Dish",
            "description": "A delicious dish to test permissions",
            "ingredients": [{"name": "Water", "amount": 1, "unit": "cup"}],
            "instructions": [{"step_number": 1, "instruction": "Boil"}],
        }
        blocked_resp = await client.post(
            "/api/v1/recipes",
            json=recipe_payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert blocked_resp.status_code == 403

        # 2. Admin promotes the viewer to 'editor'
        promote_resp = await client.patch(
            f"/api/v1/admin/users/{viewer_id}/permissions",
            json={"role": "editor"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert promote_resp.status_code == 200
        updated_viewer = promote_resp.json()
        assert updated_viewer["role"] == "editor"
        assert updated_viewer["can_edit"] is True
        assert updated_viewer["is_admin"] is False

        # 3. The user now attempts to create a recipe -> Success (201)
        created_resp = await client.post(
            "/api/v1/recipes",
            json=recipe_payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert created_resp.status_code == 201

        # 4. Admin demotes the user back to 'viewer'
        demote_resp = await client.patch(
            f"/api/v1/admin/users/{viewer_id}/permissions",
            json={"role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert demote_resp.status_code == 200
        assert demote_resp.json()["role"] == "viewer"
        assert demote_resp.json()["can_edit"] is False

        # 5. User is once again forbidden from creating recipes
        blocked_again = await client.post(
            "/api/v1/recipes",
            json=recipe_payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert blocked_again.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_api():
    _, viewer_token = await create_test_user(
        email="viewer_attempt@example.com",
        role="viewer",
    )
    _, editor_token = await create_test_user(
        email="editor_attempt@example.com",
        role="editor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Anonymous user -> 401
        anon_resp = await client.get("/api/v1/admin/users")
        assert anon_resp.status_code == 401

        # 2. Viewer user -> 403
        viewer_admin_resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert viewer_admin_resp.status_code == 403
        assert "Administrator access required" in viewer_admin_resp.json()["detail"]

        # 3. Editor user -> 403
        editor_admin_resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert editor_admin_resp.status_code == 403


@pytest.mark.asyncio
async def test_provision_and_delete_user():
    _, admin_token = await create_test_user(
        email="provision_admin@example.com",
        role="admin",
        name="Provisioning Admin",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pre-provision a new user
        provision_payload = {
            "email": "new_team_member@example.com",
            "name": "New Team Member",
            "role": "editor",
        }
        create_resp = await client.post(
            "/api/v1/admin/users",
            json=provision_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        created_user = create_resp.json()
        assert created_user["email"] == "new_team_member@example.com"
        assert created_user["role"] == "editor"
        assert created_user["can_edit"] is True

        # Delete the user
        user_id = created_user["id"]
        del_resp = await client.delete(
            f"/api/v1/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] == "User deleted successfully"


@pytest.mark.asyncio
async def test_bootstrap_admin_from_allowed_editor_emails():
    from app.services.auth_service import get_or_create_user, create_access_token

    settings = get_settings()
    # The first email in ALLOWED_EDITOR_EMAILS (from .env or config default)
    bootstrap_email = settings.editor_emails_list[0]
    if bootstrap_email == "*":
        bootstrap_email = "bootstrap_admin@example.com"

    # Simulate sign in / creation of the bootstrap user
    user = await get_or_create_user({
        "email": bootstrap_email,
        "name": "Bootstrap Privileged Owner",
        "google_id": "google-bootstrap-001",
    })
    assert user["role"] == "admin"
    assert user["can_edit"] is True
    assert user["is_admin"] is True
    assert user["is_bootstrap"] is True

    # Call /me with their token
    token = create_access_token({"sub": user["_id"], "email": bootstrap_email})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["role"] == "admin"
        assert data["can_edit"] is True
        assert data["is_admin"] is True
        assert data["is_bootstrap"] is True

        # Demote attempt on bootstrap user should be blocked
        _, other_admin_token = await create_test_user(
            email="another_admin@example.com",
            role="admin",
        )
        demote_resp = await client.patch(
            f"/api/v1/admin/users/{user['_id']}/permissions",
            json={"role": "viewer"},
            headers={"Authorization": f"Bearer {other_admin_token}"},
        )
        assert demote_resp.status_code == 400
        assert "ALLOWED_EDITOR_EMAILS" in demote_resp.json()["detail"]


@pytest.mark.asyncio
async def test_seed_recipes_authorization_and_verification():
    # 1. Non-admin editor user should be rejected (403 Forbidden)
    _, editor_token = await create_test_user(
        email="chef_editor@example.com",
        role="editor",
        name="Chef Editor",
    )

    # 2. Admin user
    _, admin_token = await create_test_user(
        email="super_admin@example.com",
        role="admin",
        name="Super Admin",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Editor cannot seed
        editor_resp = await client.post(
            "/api/v1/recipes/seed",
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert editor_resp.status_code == 403

        # Database currently has recipes from conftest
        total_in_db = await db_manager.db.recipes.count_documents({})
        assert total_in_db > 0

        # Admin attempting to seed without force should be rejected with 409 Conflict
        unverified_resp = await client.post(
            "/api/v1/recipes/seed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert unverified_resp.status_code == 409
        assert "Verification is required" in unverified_resp.json()["detail"]

        # Admin attempting to seed with force=True should succeed
        verified_resp = await client.post(
            "/api/v1/recipes/seed?force=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert verified_resp.status_code == 200
        assert "Successfully seeded" in verified_resp.json()["message"]

