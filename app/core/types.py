"""Kiểu dữ liệu lõi — thuần Python, không phụ thuộc FastAPI/pydantic."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Source(StrEnum):
    """Nguồn tạo ra câu trả lời."""

    GREETING = "greeting"
    KEYWORD = "keyword"
    FAQ = "faq"
    DATA = "data"
    MINE = "mine"
    AI = "ai"
    FALLBACK = "fallback"


@dataclass
class Message:
    """Một lượt hội thoại."""

    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class ChatContext:
    """Ngữ cảnh của một request chat."""

    history: list[Message] = field(default_factory=list)
    user: dict | None = None
    session_id: str | None = None
    locale: str = "vi"
    # JWT của người dùng (Bearer) — forward xuống BE để trả lời câu hỏi cá nhân
    # ("bài đăng của tôi", "hồ sơ của tôi"). None = khách chưa đăng nhập.
    auth_token: str | None = None


@dataclass
class Resolution:
    """Kết quả một resolver (hoặc AI) trả về.

    `confidence` trong [0, 1]. Engine so với ngưỡng để quyết định dùng rule hay
    rơi xuống AI. `cacheable=False` cho câu phụ thuộc dữ liệu sống (data resolver).
    """

    answer: str
    confidence: float
    source: str
    intent: str | None = None
    suggestions: list[str] = field(default_factory=list)
    cacheable: bool = True
    meta: dict = field(default_factory=dict)
