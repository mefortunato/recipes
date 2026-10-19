from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://localhost:8080", "*"],
        description="Allowed CORS origins",
    )
    frontend_url: str = Field(default="", description="Frontend URL for CORS / production redirects")

    # Google Cloud & Deployment Configuration
    gcp_project_id: str = Field(default="", description="Google Cloud Project ID")

    # Google OAuth 2.0 & JWT Authentication
    google_client_id: str = Field(default="", description="Google OAuth 2.0 Web Client ID")
    google_client_secret: Optional[str] = Field(default="", description="Google OAuth 2.0 Web Client Secret (optional)")
    dev_login_enabled: bool = Field(default=False, description="Enable quick development login profiles")
    jwt_secret: str = Field(default="super-secret-recipes-jwt-token-key-2026", description="Secret key for JWT")
    jwt_algorithm: str = Field(default="HS256", description="JWT encryption algorithm")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, description="Access token expiration (7 days)")
    # Role-based access control for recipe mutations (add, edit, delete, seed)
    # Comma-separated list of emails or '*' for any authenticated user
    allowed_editor_emails: str = Field(
        default="",
        description="Comma-separated emails allowed to add, edit, or delete recipes. Set to '*' to allow all signed-in users.",
    )

    # Auto-seed sample recipes if collection is empty
    auto_seed: bool = Field(default=True, description="Seed initial recipes on startup if DB is empty")

    @property
    def editor_emails_list(self) -> List[str]:
        if not self.allowed_editor_emails or self.allowed_editor_emails.strip() == "*":
            return ["*"]
        return [e.strip().lower() for e in self.allowed_editor_emails.split(",") if e.strip()]

    def is_privileged_email(self, email: Optional[str]) -> bool:
        """Checks if an email matches the bootstrap privileged emails configured in ALLOWED_EDITOR_EMAILS."""
        if not email:
            return False
        emails = self.editor_emails_list
        if "*" in emails:
            return True
        return email.strip().lower() in emails

    def can_user_edit(self, email: Optional[str]) -> bool:
        return self.is_privileged_email(email)

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
