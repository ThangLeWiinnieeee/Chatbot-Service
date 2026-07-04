"""Resolver chào hỏi / smalltalk — mắt xích đầu, độ chính xác cao.

Chỉ trả lời khi câu gần như CHỈ gồm lời chào (không còn nội dung nghiệp vụ khác),
tránh việc "chào bạn, làm sao đăng ký?" bị nuốt bởi câu chào.
"""
from __future__ import annotations

import random

from ..normalizer import STOPWORDS, tokenize
from ..types import ChatContext, Resolution, Source
from .base import Resolver


class GreetingResolver(Resolver):
    name = "greeting"

    def __init__(self, intents: list[dict]) -> None:
        # Chỉ lấy intent type == "smalltalk" (greeting/goodbye/thanks/bot_identity...).
        self._items: list[dict] = []
        for intent in intents:
            if intent.get("type") != "smalltalk":
                continue
            patterns = [set(tokenize(p)) for p in intent.get("patterns", [])]
            self._items.append(
                {
                    "tag": intent.get("tag"),
                    "patterns": [p for p in patterns if p],
                    "responses": intent.get("responses") or [""],
                    "suggestions": intent.get("suggestions", []),
                }
            )

    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        q_tokens = tokenize(query)
        if not q_tokens:
            return None
        q_set = set(q_tokens)

        best: dict | None = None
        best_conf = 0.0
        for item in self._items:
            matched: set[str] = set()
            exact = False
            for pattern in item["patterns"]:
                if pattern <= q_set:
                    matched |= pattern
                    if q_set == pattern:
                        exact = True
            if not matched:
                continue
            leftover = [t for t in q_tokens if t not in matched and t not in STOPWORDS]
            if exact:
                conf = 1.0
            elif not leftover:
                conf = 0.9  # chỉ còn từ chào + stopword
            else:
                conf = 0.3  # còn nội dung khác → nhường resolver sau
            if conf > best_conf:
                best_conf, best = conf, item

        if best is None:
            return None
        return Resolution(
            answer=random.choice(best["responses"]),
            confidence=best_conf,
            source=Source.GREETING.value,
            intent=best["tag"],
            suggestions=best.get("suggestions", []),
        )
