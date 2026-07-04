"""Vỏ HTTP (FastAPI) — tách khỏi lõi `app/core`."""

from .routes import router

__all__ = ["router"]
