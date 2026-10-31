import logging
import secrets
from functools import lru_cache
from typing import List, Literal, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("recipe_book.config")

# Secrets that have been published in this repo and must never sign real sessions
INSECURE_JWT_SECRETS = {
    "",
    "super-secret-recipes-jwt-token-key-2026",
    "your-random-jwt-secret-replace-in-production",
}
MIN_JWT_SECRET_LENGTH = 32
# Environments where developer conveniences (quick dev login, plain-HTTP cookies) are allowed
LOCAL_ENVIRONMENTS = {"development", "test"}


class Settings(BaseSettings):
    app_name: str = "Recipe Book API"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", description="development, staging, or production")
    debug: bool = Field(default=False)
    api_prefix: str = "/api/v1"

    # MongoDB connection details
    # Default is localhost for local run, 'mongodb' for Docker Compose service
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string (e.g. mongodb://mongodb:27017 or mongodb+srv://... for Atlas)",
    )
    mongodb_db_name: str = Field(default="recipe_book", description="MongoDB database name")
    mongodb_max_pool_size: int = Field(default=20, description="Max database connection pool size")
    mongodb_min_pool_size: int = Field(default=2, description="Min database connection pool size")

    # Cloud-Native Observability & Logging
    log_level: str = Field(default="INFO", description="DEBUG, INFO, WARNING, ERROR")
    log_format: str = Field(default="text", description="'text' or 'json' for cloud log collectors")

    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    frontend_url: str = Field(default="", description="Frontend URL for CORS / production redirects")

    # Google Cloud & Deployment Configuration
    gcp_project_id: str = Field(default="", description="Google Cloud Project ID")

    # Google OAuth 2.0 & JWT Authentication
    google_client_id: str = Field(default="", description="Google OAuth 2.0 Web Client ID")
    google_client_secret: Optional[str] = Field(default="", description="Google OAuth 2.0 Web Client Secret (optional)")
    dev_login_enabled: bool = Field(default=False, description="Enable quick development login profiles")
    jwt_secret: str = Field(
        default="",
        description="Secret key for signing session JWTs. Required in production (min 32 random characters).",
    )
    # Only HMAC algorithms make sense with a shared secret; never allow 'none' or asymmetric confusion
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, ge=5, description="Access token expiration (7 days)")
    # Bootstrap administrators. Comma-separated list of emails that are always admins.
    # Empty means no bootstrap admins. A '*' entry lets every signed-in user edit recipes
    # (it never grants admin).
    allowed_editor_emails: str = Field(
        default="",
        description="Comma-separated bootstrap admin emails. Add '*' to let all signed-in users edit recipes.",
    )

    # Uploaded recipe photos are re-encoded and scaled down before they are stored in MongoDB
    image_upload_max_bytes: int = Field(default=15 * 1024 * 1024, ge=1024, description="Largest accepted upload, before processing")
    image_max_dimension: int = Field(default=1600, ge=200, le=8000, description="Longest edge (px) of a stored image")
    image_max_stored_bytes: int = Field(default=600 * 1024, ge=50 * 1024, description="Size budget for a stored, processed image")
    image_max_source_pixels: int = Field(default=60_000_000, ge=1_000_000, description="Reject decompression bombs above this many pixels")
    image_orphan_ttl_seconds: int = Field(default=24 * 60 * 60, ge=60, description="Uploads never attached to a recipe are purged after this long")

    # Auto-seed sample recipes if collection is empty
    auto_seed: bool = Field(default=True, description="Seed initial recipes on startup if DB is empty")

    @property
    def editor_emails_list(self) -> List[str]:
        """Explicit bootstrap admin emails (the '*' wildcard is excluded)."""
        return [
            e.strip().lower()
            for e in self.allowed_editor_emails.split(",")
            if e.strip() and e.strip() != "*"
        ]

    @property
    def all_users_can_edit(self) -> bool:
        return any(e.strip() == "*" for e in self.allowed_editor_emails.split(","))

    def is_privileged_email(self, email: Optional[str]) -> bool:
        """Checks if an email is a bootstrap administrator configured in ALLOWED_EDITOR_EMAILS."""
        if not email:
            return False
        return email.strip().lower() in self.editor_emails_list

    # HTTP security headers (CSP, HSTS, framing, sniffing) on every response
    security_headers_enabled: bool = Field(default=True, description="Send hardened HTTP security headers")
    # Reject state-changing requests whose Origin/Sec-Fetch-Site shows they came from another site
    csrf_origin_check_enabled: bool = Field(default=True, description="Block cross-site unsafe requests (CSRF defense in depth)")
    # Swagger UI, ReDoc and /openapi.json map the whole API surface; off in production unless explicitly enabled
    api_docs_enabled: Optional[bool] = Field(default=None, description="Serve /docs, /redoc and /openapi.json (default: on outside production)")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return not self.is_production

    @property
    def expose_health_details(self) -> bool:
        """Version, environment and database details in health responses are for local debugging only."""
        return not self.is_production

    @property
    def is_local_environment(self) -> bool:
        return self.environment.lower() in LOCAL_ENVIRONMENTS

    @property
    def cookie_secure(self) -> bool:
        """Send session cookies over HTTPS only, except in local development/test over plain HTTP."""
        if self.frontend_url.lower().startswith("https://"):
            return True
        return not self.is_local_environment

    @property
    def trusted_origins(self) -> List[str]:
        """Browser origins allowed to make credentialed, state-changing requests."""
        origins = [o.rstrip("/") for o in self.cors_origins if o and o != "*"]
        if self.frontend_url:
            origins.append(self.frontend_url.rstrip("/"))
        return list(dict.fromkeys(origins))

    @model_validator(mode="after")
    def check_security_settings(self):
        is_production = self.is_production
        if self.jwt_secret in INSECURE_JWT_SECRETS or len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            if is_production:
                raise ValueError(
                    f"JWT_SECRET must be a random value of at least {MIN_JWT_SECRET_LENGTH} characters "
                    "in production (generate one with `openssl rand -hex 32`)."
                )
            logger.warning(
                "JWT_SECRET is missing or insecure; using a random per-process secret. "
                "Sessions will not survive restarts."
            )
            self.jwt_secret = secrets.token_urlsafe(48)
        if self.dev_login_enabled and not self.is_local_environment:
            # Dev login lets anyone sign in as any email (including bootstrap admins) without Google,
            # so it must never be reachable on a shared staging or production deployment.
            raise ValueError("DEV_LOGIN_ENABLED is only allowed when ENVIRONMENT is 'development' or 'test'.")
        if is_production and not self.frontend_url:
            logger.warning(
                "FRONTEND_URL is not set in production; OAuth redirects will be derived from the request Host header."
            )
        if is_production and "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must not contain '*' in production.")
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
