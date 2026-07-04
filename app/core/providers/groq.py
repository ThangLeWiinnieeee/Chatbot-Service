"""Provider Groq (OpenAI-compatible, free tier).

Import SDK `groq` được để lười (lazy) trong `__init__` để phần lõi vẫn test được
khi chưa cài `groq`.
"""
from __future__ import annotations

import logging

from .base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 512,
        timeout: float = 15.0,
    ) -> None:
        if not api_key:
            raise AIProviderError("Thiếu GROQ_API_KEY")
        try:
            from groq import AsyncGroq
        except ImportError as exc:  # pragma: no cover
            raise AIProviderError(
                "Chưa cài SDK 'groq'. Chạy: pip install groq"
            ) from exc

        self._client = AsyncGroq(api_key=api_key, timeout=timeout)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:  # SDK ném nhiều loại lỗi mạng/api khác nhau
            logger.warning("Groq call failed: %s", exc)
            raise AIProviderError(str(exc)) from exc

        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise AIProviderError("Groq trả về nội dung rỗng")
        return content

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:  # pragma: no cover - best effort
                pass
