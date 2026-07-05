"""Fixtures dùng chung — engine chạy với AI giả (không gọi mạng)."""
from __future__ import annotations

import pytest

from app.config import APP_DIR
from app.core.engine import ChatEngine
from app.core.providers.base import AIProvider
from app.core.resolvers.registry import build_resolvers, load_faqs, load_intents


class FakeProvider(AIProvider):
    """AI provider giả: trả câu cố định, ghi lại số lần được gọi."""

    def __init__(self, reply: str = "[AI] Mình sẽ cố gắng hỗ trợ bạn.") -> None:
        self.reply = reply
        self.calls: list[list[dict]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.reply


class FakeBackend:
    """Backend giả cho data resolver."""

    def __init__(self, subjects=None, total=0) -> None:
        self._subjects = subjects if subjects is not None else ["Toán", "Vật lý", "Tiếng Anh"]
        self._total = total

    async def get_subjects(self):
        return list(self._subjects)

    async def search_tutors(self, *, subject=None, name=None, limit=3):
        return {"tutors": [], "total": self._total}

    # --- endpoint cá nhân (nhận token; giá trị canned cho test MineResolver) ---
    async def get_my_profile(self, token):
        return {
            "fullName": "Nguyễn Văn A",
            "email": "a@example.com",
            "role": "user",
            "phone": "0900000000",
        }

    async def get_my_posts(self, token):
        return {
            "classes": [{"subject": "Toán", "status": "open", "summary": "Lớp 10"}],
            "pagination": {"totalItems": 1},
        }

    async def get_my_applications(self, token):
        return {
            "applications": [],
            "counts": {"all": 2, "pending": 1, "approved": 1},
            "pagination": {"totalItems": 2},
        }

    async def get_my_invitations(self, token):
        return {"invitations": [], "pagination": {"totalItems": 0}}


@pytest.fixture
def data_dir():
    return APP_DIR / "data"


@pytest.fixture
def intents(data_dir):
    return load_intents(data_dir)


@pytest.fixture
def faqs(data_dir):
    return load_faqs(data_dir)


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def engine(data_dir, fake_provider):
    resolvers, faq_resolver = build_resolvers(data_dir, backend=None)
    return ChatEngine(
        resolvers=resolvers,
        faq_resolver=faq_resolver,
        provider=fake_provider,
        threshold=0.6,
        faq_context_k=3,
    )


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient

    from app.api.deps import get_engine
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)
