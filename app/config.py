from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "CooperApp"
    debug: bool = True
    database_url: str = "sqlite:///./cooperapp.db"
    app_port: int = 8000
    uploads_path: str = "uploads"
    exports_path: str = "exports"
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    app_url: str = "http://localhost:8000"
    session_secret_key: str = "change-me-in-production"
    acme_email: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
