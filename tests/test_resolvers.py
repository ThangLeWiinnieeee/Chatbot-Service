"""Test từng resolver rule-based + normalizer."""
from __future__ import annotations

import pytest

from app.core.normalizer import content_set, normalize, strip_accents
from app.core.resolvers.data import DataResolver
from app.core.resolvers.faq import FaqResolver
from app.core.resolvers.greeting import GreetingResolver
from app.core.resolvers.keyword import KeywordResolver
from app.core.resolvers.mine import MineResolver
from app.core.types import ChatContext, Message

from .conftest import FakeBackend

CTX = ChatContext()
_GIBBERISH = "asdf qwer zxcv"  # không khớp rule nào → rơi xuống AI


# --- normalizer ---

def test_strip_accents_vietnamese():
    assert strip_accents("Học phí") == "Hoc phi"
    assert strip_accents("Đăng ký") == "Dang ky"


def test_normalize_drops_punctuation_and_case():
    assert normalize("Học phí thế nào???") == "hoc phi the nao"


def test_content_set_removes_stopwords():
    assert "hoc" in content_set("làm sao để học phí")


# --- greeting ---

async def test_greeting_exact_high_confidence(intents):
    res = await GreetingResolver(intents).resolve("xin chào", CTX)
    assert res is not None
    assert res.source == "greeting"
    assert res.confidence >= 0.9


async def test_greeting_defers_when_message_has_real_content(intents):
    # "chào bạn, làm sao đăng ký?" KHÔNG được nuốt bởi câu chào.
    res = await GreetingResolver(intents).resolve("chào bạn cho mình hỏi cách đăng ký", CTX)
    assert res is None or res.confidence < 0.6


async def test_greeting_none_for_unrelated(intents):
    assert await GreetingResolver(intents).resolve("học phí bao nhiêu", CTX) is None


# --- keyword (intents) ---

@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("làm sao đăng ký tài khoản", "register"),
        ("tôi muốn trở thành gia sư", "become_tutor"),
        ("mã ưu đãi dùng thế nào", "voucher"),
        ("tôi quên mật khẩu", "forgot_password"),
    ],
)
async def test_keyword_matches_intent(intents, query, expected_intent):
    res = await KeywordResolver(intents).resolve(query, CTX)
    assert res is not None
    assert res.intent == expected_intent
    assert res.confidence >= 0.6


async def test_keyword_none_for_gibberish(intents):
    assert await KeywordResolver(intents).resolve("asdf qwer zxcv", CTX) is None


# --- faq ---

async def test_faq_matches_natural_question(faqs):
    res = await FaqResolver(faqs).resolve("làm thế nào để tôi tìm được gia sư dạy kèm", CTX)
    assert res is not None
    assert res.source == "faq"
    assert res.confidence > 0


def test_faq_top_contexts_for_rag(faqs):
    contexts = FaqResolver(faqs).top_contexts("học phí tính thế nào", k=2)
    assert 1 <= len(contexts) <= 2
    assert all("Đáp:" in c for c in contexts)


# --- data ---

async def test_data_returns_none_without_backend():
    resolver = DataResolver(backend=None)
    assert await resolver.resolve("có bao nhiêu gia sư môn Toán", CTX) is None


async def test_data_counts_tutors_by_subject():
    resolver = DataResolver(backend=FakeBackend(total=7))
    res = await resolver.resolve("có bao nhiêu gia sư môn Toán", CTX)
    assert res is not None
    assert res.source == "data"
    assert res.cacheable is False
    assert "7" in res.answer
    assert "Toán" in res.answer


async def test_data_lists_subjects():
    resolver = DataResolver(backend=FakeBackend(subjects=["Toán", "Hóa"]))
    res = await resolver.resolve("trung tâm có những môn nào", CTX)
    assert res is not None
    assert res.intent == "subject_list"
    assert "Toán" in res.answer


async def test_data_ignores_non_data_tutor_question():
    resolver = DataResolver(backend=FakeBackend(total=7))
    # Không có từ đếm và không nêu môn → không phải câu số liệu.
    assert await resolver.resolve("gia sư có kinh nghiệm không", CTX) is None


# --- mine (dữ liệu cá nhân) ---

_AUTHED = ChatContext(auth_token="jwt-abc", user={"role": "user"})
_AUTHED_TUTOR = ChatContext(auth_token="jwt-xyz", user={"role": "tutor"})


async def test_mine_returns_none_without_backend():
    assert await MineResolver(backend=None).resolve("hồ sơ của tôi", _AUTHED) is None


async def test_mine_ignores_non_personal_query():
    # "tôi muốn tìm gia sư" có "tôi" nhưng không phải câu dữ liệu cá nhân.
    resolver = MineResolver(backend=FakeBackend())
    assert await resolver.resolve("tôi muốn tìm gia sư môn Toán", _AUTHED) is None


async def test_mine_requires_login():
    resolver = MineResolver(backend=FakeBackend())
    res = await resolver.resolve("hồ sơ của tôi", ChatContext())  # chưa đăng nhập
    assert res is not None
    assert res.intent == "auth_required"
    assert res.cacheable is False
    assert "đăng nhập" in res.answer.lower()


async def test_mine_profile():
    resolver = MineResolver(backend=FakeBackend())
    res = await resolver.resolve("cho tôi xem hồ sơ của tôi", _AUTHED)
    assert res is not None
    assert res.source == "mine"
    assert res.intent == "profile"
    assert res.cacheable is False
    assert "Nguyễn Văn A" in res.answer
    assert "a@example.com" in res.answer


async def test_mine_posts():
    resolver = MineResolver(backend=FakeBackend())
    res = await resolver.resolve("bài đăng của tôi có những gì", _AUTHED)
    assert res is not None
    assert res.intent == "posts"
    assert "1 bài đăng" in res.answer
    assert "Toán" in res.answer


async def test_mine_applications_for_tutor():
    resolver = MineResolver(backend=FakeBackend())
    res = await resolver.resolve("đơn ứng tuyển của tôi thế nào", _AUTHED_TUTOR)
    assert res is not None
    assert res.intent == "applications"
    assert "2 lớp" in res.answer


async def test_mine_blocks_tutor_only_intent_for_student():
    resolver = MineResolver(backend=FakeBackend())
    res = await resolver.resolve("lời mời dạy của tôi", _AUTHED)  # role=user
    assert res is not None
    assert res.intent == "invitations"
    assert "gia sư" in res.answer.lower()


async def test_mine_graceful_on_backend_error():
    class Broken(FakeBackend):
        async def get_my_profile(self, token):
            return None

    res = await MineResolver(backend=Broken()).resolve("hồ sơ của tôi", _AUTHED)
    assert res is not None
    assert res.intent == "profile"
    assert "thử lại" in res.answer.lower()


# --- engine: cache AI theo ngữ cảnh ---

async def test_engine_caches_ai_answer_without_history(engine, fake_provider):
    await engine.answer(_GIBBERISH, ChatContext())
    await engine.answer(_GIBBERISH, ChatContext())
    assert len(fake_provider.calls) == 1  # lần 2 ăn cache, không gọi lại AI


async def test_engine_skips_cache_for_ai_answer_with_history(engine, fake_provider):
    ctx = ChatContext(history=[Message(role="user", content="chào bạn")])
    await engine.answer(_GIBBERISH, ctx)
    await engine.answer(_GIBBERISH, ctx)
    assert len(fake_provider.calls) == 2  # có history → không cache, gọi AI lại
