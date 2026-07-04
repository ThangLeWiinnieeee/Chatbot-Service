"""Resolver phân loại ý định điều hướng theo từ khoá (intents.json, type='intent').

Điểm = tỉ lệ keyword của pattern xuất hiện trong câu (coverage); cụm pattern là
substring của câu → nâng điểm. Để tránh khớp nhầm do token quá phổ biến
(vd "gia sư" xuất hiện ở rất nhiều intent), chỉ chấp nhận khi có ÍT NHẤT MỘT
token ĐẶC TRƯNG khớp — "đặc trưng" = xuất hiện ở dưới ~20% số intent (tự hiệu
chỉnh theo dữ liệu, không magic-number theo từng câu).
"""
from __future__ import annotations

import random

from ..normalizer import content_set, normalize, tokenize
from ..types import ChatContext, Resolution, Source
from .base import Resolver, compute_generic, coverage


class KeywordResolver(Resolver):
    name = "keyword"

    def __init__(self, intents: list[dict]) -> None:
        self._items: list[dict] = []
        for intent in intents:
            if intent.get("type") != "intent":
                continue
            patterns = []
            for raw in intent.get("patterns", []):
                tokens = content_set(raw) or set(tokenize(raw))
                if tokens:
                    patterns.append({"tokens": tokens, "phrase": normalize(raw)})
            if patterns:
                self._items.append(
                    {
                        "tag": intent.get("tag"),
                        "patterns": patterns,
                        "responses": intent.get("responses") or [""],
                        "suggestions": intent.get("suggestions", []),
                    }
                )

        # Token phổ biến trên toàn bộ intent (mỗi intent = 1 "tài liệu").
        docs = [set().union(*[p["tokens"] for p in item["patterns"]]) for item in self._items]
        self._generic = compute_generic(docs)

    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        q_content = content_set(query)
        q_norm = normalize(query)
        if not q_content:
            return None

        best: dict | None = None
        # Khoá so sánh: (điểm, số token khớp) → hoà điểm thì pattern cụ thể hơn thắng.
        best_key = (0.0, 0)
        for item in self._items:
            item_key = (0.0, 0)
            for pattern in item["patterns"]:
                matched = pattern["tokens"] & q_content
                if not matched:
                    continue
                phrase_hit = (
                    len(pattern["tokens"]) >= 2
                    and pattern["phrase"]
                    and pattern["phrase"] in q_norm
                )
                # Chỉ khớp token phổ biến (không có token đặc trưng nào) → bỏ qua,
                # trừ khi cả cụm pattern xuất hiện nguyên vẹn trong câu.
                if not (matched - self._generic) and not phrase_hit:
                    continue
                score = coverage(pattern["tokens"], q_content)
                if phrase_hit:
                    score = max(score, 0.95)
                item_key = max(item_key, (score, len(matched)))
            if item_key > best_key:
                best_key, best = item_key, item

        if best is None or best_key[0] <= 0:
            return None
        return Resolution(
            answer=random.choice(best["responses"]),
            confidence=round(best_key[0], 3),
            source=Source.KEYWORD.value,
            intent=best["tag"],
            suggestions=best.get("suggestions", []),
        )
