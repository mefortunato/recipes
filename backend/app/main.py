import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.database import connect_to_mongo, close_mongo_connection, db_manager
from app.routers import health_router, recipes_router, auth_router, admin_router
from app.services.recipe_service import RecipeService

settings = get_settings()

# Setup logging
log_format = (
    '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    if settings.log_format == "json"
    else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format=log_format,
    stream=sys.stdout,
)
logger = logging.getLogger("recipe_book.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan: Manage database connection and initial boot tasks."""
    logger.info("Starting up %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
    await connect_to_mongo()

    # Auto-seed database if enabled and database is available
    if settings.auto_seed and db_manager.db is not None:
        try:
            service = RecipeService(db_manager.db)
            await service.seed_recipes(force=False)
        except Exception as exc:
            logger.warning("Auto-seed encountered an issue (will retry on next startup): %s", exc)

    yield

    logger.info("Shutting down %s...", settings.app_name)
    await close_mongo_connection()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A modern, cloud-native ready RESTful API for recipe collection management and scaling.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
cors_origins = list(settings.cors_origins)
if settings.frontend_url and settings.frontend_url not in cors_origins:
    cors_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Measure request latency and add standard X-Process-Time header."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


# Include Routers
# Mount health checks at root for Cloud Run conventions
app.include_router(health_router)
# Mount the versioned API (recipes, health, auth, admin) under /api/v1
for api_router in (recipes_router, health_router, auth_router, admin_router):
    app.include_router(api_router, prefix=settings.api_prefix)


# Static file serving & Single Page Application (SPA) fallback
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ASSETS_DIR = STATIC_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/", summary="API Root / SPA Entrypoint")
async def root(request: Request):
    index_file = STATIC_DIR / "index.html"
    accept = request.headers.get("accept", "")
    # Serve SPA index.html when accessed via a browser
    if "text/html" in accept and index_file.is_file():
        return FileResponse(index_file)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs_url": "/docs",
        "api_v1_prefix": settings.api_prefix,
        "health_endpoint": "/health/ready",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # Don't intercept API or health endpoints, or documentation
    if (
        full_path.startswith("api/")
        or full_path.startswith("health")
        or full_path in ("docs", "redoc", "openapi.json")
    ):
        return Response(status_code=404, content='{"detail":"Not Found"}', media_type="application/json")

    # Check if a specific static file was requested (e.g. favicon.svg, robots.txt)
    # Resolve and confine to STATIC_DIR so encoded '../' segments can't escape it
    requested_file = (STATIC_DIR / full_path).resolve()
    if full_path and requested_file.is_relative_to(STATIC_DIR.resolve()) and requested_file.is_file():
        return FileResponse(requested_file)

    # Otherwise serve index.html for Svelte client-side routing
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    return Response(status_code=404, content='{"detail":"Not Found"}', media_type="application/json")
