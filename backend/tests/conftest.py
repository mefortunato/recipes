import pytest
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from app.main import app
from app.database import db_manager, init_db_indexes
from app.services.recipe_service import RecipeService


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Inject an in-memory AsyncMongoMockClient for test isolation without requiring a live MongoDB server."""
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_recipe_book"]

    db_manager.client = mock_client
    db_manager.db = mock_db

    await init_db_indexes(mock_db)

    # Seed with sample data
    service = RecipeService(mock_db)
    await service.seed_recipes(force=True)

    yield mock_db

    db_manager.client = None
    db_manager.db = None


from app.dependencies.auth import require_editor_user


@pytest.fixture
async def async_client():
    # By default, provide authorized editor credentials for base test suite
    app.dependency_overrides[require_editor_user] = lambda: {
        "_id": "507f1f77bcf86cd799439011",
        "email": "chef@gourmetvault.com",
        "name": "Test Head Chef",
        "role": "editor",
        "can_edit": True,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(require_editor_user, None)

