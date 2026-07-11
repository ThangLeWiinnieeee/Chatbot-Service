"""Dependency injection + factory dựng engine cho tầng HTTP."""
from __future__ import annotations

import logging

from fastapi import Depends, Header, HTTPException, Request, status

from ..clients.backend import BackendClient
from ..config import Settings, get_settings
from ..core.cache import TTLCache
from ..core.engine import ChatEngine
from ..core.providers.base import AIProvider, AIProviderError
from ..core.resolvers.registry import build_resolvers

logger = logging.getLogger(__name__)


def _build_provider(settings: Settings) -> AIProvider | None:
    """Tạo Groq provider nếu có key; lỗi/thiếu key → None (chạy rule-only)."""
    if not settings.ai_enabled:
        logger.warning("GROQ_API_KEY trống → chatbot chạy rule-only, không có AI fallback.")
        return None
    try:
        from ..core.providers.groq import GroqProvider

        return GroqProvider(
            settings.groq_api_key,
            model=settings.ai_model,
            temperature=settings.ai_temperature,
            max_tokens=settings.ai_max_tokens,
            timeout=settings.request_timeout,
        )
    except AIProviderError as exc:
        logger.warning("Không khởi tạo được Groq provider: %s → rule-only.", exc)
        return None


def build_engine(settings: Settings) -> tuple[ChatEngine, BackendClient]:
    """Dựng engine + backend client. Caller chịu trách nhiệm đóng chúng khi shutdown."""
    backend = BackendClient(
        settings.backend_base_url,
        secret=settings.internal_secret,
        timeout=settings.request_timeout,
    )
    resolvers, faq_resolver = build_resolvers(settings.data_dir, backend=backend)
    engine = ChatEngine(
        resolvers=resolvers,
        faq_resolver=faq_resolver,
        provider=_build_provider(settings),
        threshold=settings.rule_confidence_threshold,
        faq_context_k=settings.faq_context_k,
        cache=TTLCache(ttl_seconds=settings.cache_ttl_seconds, max_size=settings.cache_max_size),
        miss_log_path=settings.flywheel_log or None,
    )
    return engine, backend


def get_engine(request: Request) -> ChatEngine:
    """Lấy engine singleton đã dựng ở lifespan (app.state.engine)."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:  # pragma: no cover - chỉ xảy ra nếu lifespan chưa chạy
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chatbot engine chưa sẵn sàng",
        )
    return engine


def verify_secret(
    x_internal_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Nếu cấu hình INTERNAL_SECRET, request phải kèm header khớp."""
    expected = settings.internal_secret
    if expected and x_internal_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai hoặc thiếu internal secret"
        )
