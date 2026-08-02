from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    chroma_dir: str = "./chroma_db"
    collection_name: str = "travel-sense-docs"
    # Comma-separated list of allowed frontend origins for CORS.
    cors_origins: str = "http://localhost:3000"

    # Firebase Admin credentials for verifying ID tokens. Prefer a mounted
    # service-account file (e.g. a Render Secret File) over the inline JSON
    # blob; the JSON blob is meant for local .env use only.
    firebase_project_id: Optional[str] = None
    firebase_service_account_path: Optional[str] = None
    firebase_service_account_json: Optional[str] = None

    # backend/data/personal/*.md is one specific person's private travel
    # notes, not shared seed content. It's excluded from retrieval entirely
    # until this is set to that person's real Firebase UID (captured after
    # they sign in once).
    legacy_personal_owner_user_id: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def app_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def backend_dir(self) -> Path:
        return self.app_dir.parent

    @property
    def data_dir(self) -> Path:
        return self.backend_dir / "data"

    @property
    def chroma_path(self) -> Path:
        chroma = Path(self.chroma_dir)
        if chroma.is_absolute():
            return chroma
        return self.backend_dir / chroma


@lru_cache
def get_settings() -> Settings:
    return Settings()
