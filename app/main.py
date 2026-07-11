"""FastAPI app: lifespan dựng/đóng engine, mount routes, CORS, /health."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import build_engine
from .api.routes import router
from .config import get_settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    engine, backend = build_engine(settings)
    app.state.engine = engine
    app.state.backend = backend
    app.state.ai_enabled = settings.ai_enabled
    log = logging.getLogger(__name__)
    if not settings.internal_secret:
        # Không có secret → verify_secret bỏ qua auth, mà app bind 0.0.0.0:8001.
        # Cổng lộ ra ngoài = proxy Groq mở + gọi được BE. Đặt INTERNAL_SECRET ở production.
        log.warning(
            "INTERNAL_SECRET trống → endpoint /api/chat KHÔNG xác thực. "
            "Đặt INTERNAL_SECRET (khớp CHATBOT_INTERNAL_SECRET ở BE) hoặc firewall cổng %s.",
            settings.port,
        )
    log.info(
        "Chatbot sẵn sàng (ai=%s, model=%s, backend=%s)",
        settings.ai_enabled,
        settings.ai_model,
        settings.backend_base_url,
    )
    try:
        yield
    finally:
        await engine.aclose()
        await backend.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WebTutorCenter Chatbot",
        version="0.1.0",
        description="Hybrid chatbot (rule-based + AI fallback) cho WebTutorCenter.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "ai": getattr(app.state, "ai_enabled", settings.ai_enabled)}

    app.include_router(router)
    return app


app = create_app()
