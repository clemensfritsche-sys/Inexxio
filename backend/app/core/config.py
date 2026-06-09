from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Inexxio ECS API"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: str = "postgresql://postgres:postgres@localhost:5432/inexxio_local"

    firebase_project_id: str = ""
    firebase_service_account_path: Optional[str] = None

    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://inexxio-dev.web.app",
        "https://inexxio.web.app",
        "https://inexxio.com",
    ]

    initial_admin_email: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
