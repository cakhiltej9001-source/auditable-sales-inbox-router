from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./sales_router.sqlite3"
    frontend_origin: str = "http://localhost:5173"
    candidate_id: str = "cakhiltej9001@gmail.com"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_retries: int = Field(default=3, ge=1, le=5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
