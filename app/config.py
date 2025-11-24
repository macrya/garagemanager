"""
Configuration settings for the Garage Management System.
Uses Pydantic for type-safe configuration management.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Garage Management System"
    app_version: str = "2.0.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://garage_user:garage_pass@db:5432/garage_db"
    database_url_sync: str = "postgresql://garage_user:garage_pass@db:5432/garage_db"

    # Security
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # API
    api_v1_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
