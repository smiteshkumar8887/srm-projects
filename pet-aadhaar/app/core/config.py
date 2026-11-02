from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "PawAadhaar"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-paw-aadhaar-dev-secret"
    database_url: str = "sqlite:///./storage/pet_aadhaar.db"
    upload_dir: str = "storage/uploads"
    qr_dir: str = "storage/qr"
    base_url: str = "http://127.0.0.1:8000"

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def qr_path(self) -> Path:
        return Path(self.qr_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
