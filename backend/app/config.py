from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    chroma_dir: str = "./chroma_db"
    collection_name: str = "travel-sense-docs"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
