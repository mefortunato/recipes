import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.database import connect_to_mongo, close_mongo_connection, db_manager
from app.routers import health_router, recipes_router, auth_router, admin_router
from app.services.recipe_service import RecipeService

settings = get_settings()

class JsonLogFormatter(logging.Formatter):
    """Serialize records with json.dumps so attacker-controlled text (OAuth error params, emails)
    can't break out of the message field and forge log entries."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class SafeTextFormatter(logging.Formatter):
    """Escape newlines so one log record can't masquerade as several."""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record).replace("\r", "\\r").replace("\n", "\\n")


log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(
    JsonLogFormatter() if settings.log_format == "json"
    else SafeTextFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[log_handler])
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
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# CORS configuration
cors_origins = list(settings.cors_origins)
if settings.frontend_url and settings.frontend_url not in cors_origins:
    cors_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

# The SPA loads Google Identity Services and Google Fonts; recipe images can come from any https host.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://accounts.google.com/gsi/client",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com/gsi/style",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https:",
    "connect-src 'self' https://accounts.google.com/gsi/",
    "frame-src https://accounts.google.com/gsi/",
    "form-action 'self' https://accounts.google.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])


def request_origin_allowed(request: Request) -> bool:
    """CSRF defense in depth for cookie-authenticated browsers.

    Browsers send Origin (and Sec-Fetch-Site) on state-changing requests; reject those coming from
    a site we don't trust. Non-browser API clients send neither and authenticate with a bearer token.
    """
    origin = request.headers.get("origin")
    if origin == "null":
        return False
    if origin:
        origin = origin.rstrip("/")
        if origin in settings.trusted_origins:
            return True
        # Same-origin requests: compare hosts, not schemes, since TLS usually ends at the load
        # balancer and the app itself sees plain http. A page can't forge its own Host header.
        return urlparse(origin).netloc.lower() == request.headers.get("host", "").lower()
    return request.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "same-site", "none")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Block cross-site writes, then add security headers and the X-Process-Time latency header."""
    if (
        settings.csrf_origin_check_enabled
        and request.method in UNSAFE_METHODS
        and request.url.path.startswith(settings.api_prefix)
        and not request_origin_allowed(request)
    ):
        logger.warning("Blocked cross-site %s %s from origin %r", request.method, request.url.path, request.headers.get("origin"))
        return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked."})

    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start_time:.4f}s"

    if settings.security_headers_enabled:
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # GIS popups need to talk back to the opener window
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        if settings.cookie_secure:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Swagger/ReDoc pages pull their bundles from a CDN with inline bootstrapping; leave them out of the CSP
        if not request.url.path.startswith(DOCS_PATHS):
            headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if request.url.path.startswith(settings.api_prefix):
            # API responses are per-user (votes, roles); never let shared caches keep them
            headers.setdefault("Cache-Control", "no-store")
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
    info = {"name": settings.app_name, "status": "online"}
    if settings.expose_health_details:
        info.update(
            version=settings.app_version,
            api_v1_prefix=settings.api_prefix,
            health_endpoint="/health/ready",
        )
    if settings.docs_enabled:
        info["docs_url"] = "/docs"
    return info


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
