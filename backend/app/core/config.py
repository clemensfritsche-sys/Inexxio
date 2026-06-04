from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "Inexxio ECS API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/inexxio_local"

    # Firebase
    firebase_project_id: str = ""
    firebase_service_account_path: Optional[str] = None

    # Security
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://inexxio.web.app",
        "https://inexxio.com",
    ]

    # Storage
    gcs_bucket: str = ""

    # Email
    gmail_api_credentials: Optional[str] = None

    # Bootstrap
    initial_admin_email: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
