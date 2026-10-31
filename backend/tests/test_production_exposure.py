"""Production must not publish API docs or fingerprint the deployment through health checks."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings, get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def make_settings(**overrides) -> Settings:
    values = {"jwt_secret": "x" * 40, "environment": "development"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("environment,expected", [
    ("development", True),
    ("test", True),
    ("staging", True),
    ("production", False),
    ("Production", False),
])
def test_docs_default_by_environment(environment, expected):
    assert make_settings(environment=environment).docs_enabled is expected


def test_docs_can_be_overridden():
    assert make_settings(environment="production", api_docs_enabled=True).docs_enabled
    assert not make_settings(environment="development", api_docs_enabled=False).docs_enabled


def test_production_app_has_no_docs_routes():
    """FastAPI wires the docs routes at import, so build the app in a fresh production interpreter."""
    env = {
        **os.environ,
        "ENVIRONMENT": "production",
        "JWT_SECRET": "p" * 48,
        "CORS_ORIGINS": '["https://recipes.example.com"]',
    }
    env.pop("API_DOCS_ENABLED", None)
    code = (
        "from app.main import app; "
        "paths = {getattr(r, 'path', None) for r in app.routes}; "
        "print(sorted(p for p in paths if p in ('/docs', '/redoc', '/openapi.json')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().splitlines()[-1] == "[]"


@pytest.mark.asyncio
async def test_docs_served_outside_production(async_client):
    assert (await async_client.get("/docs")).status_code == 200
    assert (await async_client.get("/openapi.json")).status_code == 200


@pytest.mark.asyncio
async def test_readiness_details_outside_production(async_client):
    body = (await async_client.get("/health/ready")).json()
    assert body["status"] == "ready"
    assert body["database"]["status"] == "connected"
    assert body["docs_url"] == "/docs"


@pytest.mark.asyncio
async def test_readiness_is_minimal_in_production(async_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    resp = await async_client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}

    api_resp = await async_client.get("/api/v1/health/ready")
    assert api_resp.json() == {"status": "ready"}

    root = (await async_client.get("/")).json()
    assert root == {"name": get_settings().app_name, "status": "online"}
