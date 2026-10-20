import logging
import secrets
from functools import lru_cache
from typing import List, Optional
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
    jwt_algorithm: str = Field(default="HS256", description="JWT encryption algorithm")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, description="Access token expiration (7 days)")
    # Bootstrap administrators. Comma-separated list of emails that are always admins.
    # Empty means no bootstrap admins. A '*' entry lets every signed-in user edit recipes
    # (it never grants admin).
    allowed_editor_emails: str = Field(
        default="",
        description="Comma-separated bootstrap admin emails. Add '*' to let all signed-in users edit recipes.",
    )

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

    @property
    def cookie_secure(self) -> bool:
        """Send session cookies over HTTPS only, except in local development."""
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def check_security_settings(self):
        is_production = self.environment.lower() == "production"
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
        if is_production and self.dev_login_enabled:
            raise ValueError("DEV_LOGIN_ENABLED must be false in production.")
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
