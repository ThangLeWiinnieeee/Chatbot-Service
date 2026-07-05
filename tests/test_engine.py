"""Test engine: Chain of Responsibility, AI fallback, cache."""
from __future__ import annotations


async def test_greeting_answered_without_ai(engine, fake_provider):
    res = await engine.answer("xin chào")
    assert res.source == "greeting"
    assert fake_provider.calls == []  # rule đủ tự tin → không gọi AI


async def test_intent_answered_by_rule(engine, fake_provider):
    res = await engine.answer("làm sao để đăng ký tài khoản")
    assert res.source in ("keyword", "faq")
    assert res.intent in ("register", "register_account")
    assert fake_provider.calls == []


async def test_ai_fallback_when_no_rule(engine, fake_provider):
    res = await engine.answer("kể cho tôi nghe một câu chuyện cười đi")
    assert res.source == "ai"
    assert res.answer == fake_provider.reply
    assert len(fake_provider.calls) == 1


async def test_ai_result_is_cached(engine, fake_provider):
    query = "đố vui một cộng một bằng bao nhiêu nhỉ"
    first = await engine.answer(query)
    second = await engine.answer(query)
    assert first.source == "ai"
    assert len(fake_provider.calls) == 1  # lần 2 lấy từ cache, không gọi lại AI
    assert second.meta.get("cache_hit") is True


async def test_empty_message_returns_prompt(engine, fake_provider):
    res = await engine.answer("   ")
    assert res.intent == "empty"
    assert fake_provider.calls == []


async def test_rule_only_engine_degrades_gracefully(data_dir):
    """Không có AI provider: câu lạ trả về câu xin lỗi thay vì lỗi."""
    from app.core.engine import ChatEngine
    from app.core.resolvers.registry import build_resolvers

    resolvers, faq = build_resolvers(data_dir, backend=None)
    engine = ChatEngine(resolvers=resolvers, faq_resolver=faq, provider=None, threshold=0.6)
    res = await engine.answer("kể chuyện cười ngoài lề đi bạn ơi")
    assert res.source == "fallback"
