from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "change-me-in-production-min-32-chars"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://inexxio:password@localhost:5432/inexxio_local"
    database_url_sync: str = "postgresql://inexxio:password@localhost:5432/inexxio_local"

    firebase_project_id: str = "inexxio-dev"
    firebase_service_account_key: str = "{}"

    google_cloud_project: str = "inexxio-dev"
    google_cloud_region: str = "europe-west6"
    gcs_bucket_name: str = "inexxio-dev-storage"

    gmail_credentials: str = "{}"
    gmail_sender: str = "info.inexxio@gmail.com"

    anthropic_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    typesense_host: str = "localhost"
    typesense_port: int = 8108
    typesense_api_key: str = "inexxio-dev-key"

    hcaptcha_secret_key: str = ""

    class Config:
        env_file = ".env.local"
        case_sensitive = False


settings = Settings()
