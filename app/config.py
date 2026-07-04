"""Cấu hình service — đọc từ biến môi trường / file `.env`."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Thư mục gốc của package `app` (dùng để định vị `app/data`).
APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Toàn bộ cấu hình có thể override qua `.env` hoặc biến môi trường."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- AI provider (Groq) ---
    groq_api_key: str = ""
    ai_model: str = "llama-3.3-70b-versatile"
    ai_temperature: float = 0.3
    ai_max_tokens: int = 512

    # --- Engine ---
    rule_confidence_threshold: float = 0.6
    faq_context_k: int = 3
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 512

    # --- Backend WebTutorCenter ---
    backend_base_url: str = "http://localhost:5002/api"
    internal_secret: str = ""
    request_timeout: float = 15.0

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = 8001
    # NoDecode: chặn pydantic-settings JSON-parse để validator dưới đây tự tách chuỗi phẩy.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Cho phép khai báo CORS dạng chuỗi ngăn cách bởi dấu phẩy trong `.env`."""
        if value is None or value == "":
            return ["*"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def data_dir(self) -> Path:
        return APP_DIR / "data"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Singleton cấu hình (cache theo tiến trình)."""
    return Settings()
