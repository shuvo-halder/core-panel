import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized CorePanel Application Configuration.
    Loads from environment variables or defaults.
    """

    # Application Metadata
    APP_NAME: str = "CorePanel"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(
        default="development", description="Environment: development or production"
    )
    DEBUG: bool = Field(default=False, description="Debug mode flag")

    # Networking / Binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Storage & Paths
    DATA_DIR: Path = Path(os.getenv("COREPANEL_DATA_DIR", "data"))
    DB_FILENAME: str = "panel.db"
    LOG_PATH: Path = Path(os.getenv("COREPANEL_LOG_PATH", "logs/corepanel.log"))

    # Unix Socket for Privileged Agent IPC
    AGENT_SOCKET_PATH: Path = Path(os.getenv("COREPANEL_AGENT_SOCKET", "/run/corepanel/agent.sock"))

    # Security Settings
    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production-min32char", min_length=32
    )
    TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    SESSION_COOKIE_NAME: str = "corepanel_session"
    SESSION_COOKIE_SAMESITE: str = "lax"
    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 900

    # First-Admin Bootstrap (Optional, for zero-touch initialization)
    BOOTSTRAP_ADMIN_USERNAME: str | None = Field(
        default=None, description="Username for initial admin"
    )
    BOOTSTRAP_ADMIN_PASSWORD: str | None = Field(
        default=None, description="Password for initial admin"
    )
    BOOTSTRAP_ADMIN_EMAIL: str | None = Field(default=None, description="Email for initial admin")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="COREPANEL_", extra="ignore")

    @property
    def db_path(self) -> Path:
        return self.DATA_DIR / self.DB_FILENAME

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


# Singleton instance
settings = Settings()
