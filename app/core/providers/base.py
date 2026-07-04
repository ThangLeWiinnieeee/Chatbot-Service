"""Interface cho AI provider — engine chỉ phụ thuộc abstraction này.

Đổi Groq -> Gemini/self-host chỉ cần cài đặt lại `complete()`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIProviderError(RuntimeError):
    """Lỗi khi gọi AI provider."""


class AIProvider(ABC):
    """Sinh câu trả lời từ danh sách message dạng OpenAI/Groq."""

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]]) -> str:
        """Trả về nội dung text của câu trả lời. Ném `AIProviderError` khi lỗi."""
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover - mặc định no-op
        """Đóng tài nguyên (nếu có)."""
        return None
