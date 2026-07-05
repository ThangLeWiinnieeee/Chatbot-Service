"""Lắp ráp chuỗi resolver theo thứ tự ưu tiên."""
from __future__ import annotations

from pathlib import Path

from .base import Resolver, load_json
from .data import DataResolver
from .faq import FaqResolver
from .greeting import GreetingResolver
from .keyword import KeywordResolver
from .mine import MineResolver


def load_intents(data_dir: Path) -> list[dict]:
    return load_json(Path(data_dir) / "intents.json").get("intents", [])


def load_faqs(data_dir: Path) -> list[dict]:
    return load_json(Path(data_dir) / "faq.json").get("faqs", [])


def build_resolvers(
    data_dir: Path,
    *,
    backend=None,
) -> tuple[list[Resolver], FaqResolver]:
    """Trả về (danh sách resolver theo thứ tự, faq_resolver để engine dùng cho RAG).

    Thứ tự: greeting → mine → data → keyword → faq.
    - greeting đầu tiên cho phản hồi xã giao tức thì.
    - mine trước data: câu "của tôi" phải trả bằng dữ liệu cá nhân, không lẫn số liệu chung.
    - data trước keyword/faq để câu hỏi số liệu được trả bằng dữ liệu sống.
    - faq cuối cùng làm kho tri thức tổng quát trước khi rơi xuống AI.
    """
    intents = load_intents(data_dir)
    faqs = load_faqs(data_dir)
    faq_resolver = FaqResolver(faqs)
    resolvers: list[Resolver] = [
        GreetingResolver(intents),
        MineResolver(backend),
        DataResolver(backend),
        KeywordResolver(intents),
        faq_resolver,
    ]
    return resolvers, faq_resolver
