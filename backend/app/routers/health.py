import logging
import time
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from app.config import get_settings
from app.database import db_manager

logger = logging.getLogger("recipe_book.health")

router = APIRouter(prefix="/health", tags=["Health & Observability"])


@router.get("", summary="General health probe")
async def health_check() -> Dict[str, str]:
    """Returns 200 OK healthy status for Cloud Run and automated test suites."""
    return {"status": "healthy", "service": "recipes"}


@router.get("/live", summary="Liveness probe for container orchestrators")
async def liveness_probe() -> Dict[str, str]:
    """Returns 200 OK if the web server process is running and accepting HTTP requests."""
    return {"status": "ok", "probe": "liveness"}


@router.get("/ready", summary="Readiness probe verifying database connectivity")
async def readiness_probe() -> Dict[str, Any]:
    """Pings MongoDB to ensure the application is ready to process database requests."""
    settings = get_settings()

    if db_manager.client is None or db_manager.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "database": "disconnected", "reason": "No client configured"},
        )

    start_time = time.time()
    try:
        await db_manager.client.admin.command("ping")
        latency_ms = round((time.time() - start_time) * 1000, 2)
        if not settings.expose_health_details:
            # Production: answer the probe without fingerprinting the app version, environment or database
            return {"status": "ready"}
        return {
            "status": "ready",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "database": {
                "status": "connected",
                "name": settings.mongodb_db_name,
                "latency_ms": latency_ms,
            },
            **({"docs_url": "/docs"} if settings.docs_enabled else {}),
        }
    except Exception as exc:
        # Log the driver error server-side; it can include hostnames, so don't return it to callers
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "database": "unreachable",
            },
        ) from exc


@router.get("/startup", summary="Startup probe for slow initialization")
async def startup_probe() -> Dict[str, str]:
    """Verifies that the application has completed its boot sequence."""
    return {"status": "ok", "probe": "startup"}
