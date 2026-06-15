from pathlib import Path

from app.config import Settings, get_settings


def test_chroma_path_returns_absolute_path_unchanged():
    settings = Settings(openai_api_key=None, chroma_dir="/tmp/absolute_chroma")
    assert settings.chroma_path == Path("/tmp/absolute_chroma")


def test_chroma_path_resolves_relative_path():
    settings = Settings(openai_api_key=None, chroma_dir="./chroma_db")
    assert settings.chroma_path == settings.backend_dir / "chroma_db"


def test_app_dir_points_to_app_package():
    settings = Settings(openai_api_key=None)
    assert settings.app_dir.name == "app"
    assert settings.app_dir.is_dir()


def test_backend_dir_is_parent_of_app_dir():
    settings = Settings(openai_api_key=None)
    assert settings.backend_dir == settings.app_dir.parent


def test_data_dir_is_inside_backend_dir():
    settings = Settings(openai_api_key=None)
    assert settings.data_dir == settings.backend_dir / "data"


def test_get_settings_returns_cached_settings_instance():
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()
