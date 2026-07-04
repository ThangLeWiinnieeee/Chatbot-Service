"""Resolver FAQ — truy hồi câu trả lời từ kho tri thức (faq.json).

Điểm = trộn Jaccard + coverage giữa câu hỏi người dùng và các biến thể câu hỏi mẫu;
trùng cụm nguyên vẹn hoặc trúng keyword → nâng điểm. Cũng cung cấp `top_matches`
để engine nhét FAQ liên quan vào prompt AI (RAG-lite).
"""
from __future__ import annotations

from ..normalizer import content_set, normalize
from ..types import ChatContext, Resolution, Source
from .base import Resolver, compute_generic, coverage, jaccard


class FaqResolver(Resolver):
    name = "faq"

    def __init__(self, faqs: list[dict]) -> None:
        self._entries: list[dict] = []
        for entry in faqs:
            questions = [
                {"tokens": content_set(q), "norm": normalize(q), "raw": q}
                for q in entry.get("questions", [])
            ]
            questions = [q for q in questions if q["tokens"] or q["norm"]]
            self._entries.append(
                {
                    "id": entry.get("id"),
                    "questions": questions,
                    "answer": entry.get("answer", ""),
                    "keywords": [normalize(k) for k in entry.get("keywords", [])],
                    "suggestions": entry.get("suggestions", []),
                }
            )

        # Token phổ biến trên toàn kho FAQ (mỗi entry = 1 "tài liệu").
        docs = [
            set().union(*[q["tokens"] for q in e["questions"]]) if e["questions"] else set()
            for e in self._entries
        ]
        self._generic = compute_generic(docs)

    def _score_entry(self, entry: dict, q_content: set[str], q_norm: str) -> float:
        score = 0.0
        for question in entry["questions"]:
            qs = question["tokens"]
            if qs:
                inter = qs & q_content
                # Cần ít nhất một token đặc trưng khớp (không chỉ 'gia sư'...).
                if inter and (inter - self._generic):
                    blended = 0.5 * jaccard(qs, q_content) + 0.5 * coverage(qs, q_content)
                    score = max(score, blended)
            qn = question["norm"]
            if qn and (qn in q_norm or q_norm in qn):
                score = max(score, 0.9)
        for kw in entry["keywords"]:
            if kw and kw in q_norm:
                score = max(score, 0.8)
        return score

    def _ranked(self, query: str) -> list[tuple[float, dict]]:
        q_content = content_set(query)
        q_norm = normalize(query)
        if not q_content and not q_norm:
            return []
        scored = [(self._score_entry(e, q_content, q_norm), e) for e in self._entries]
        scored = [pair for pair in scored if pair[0] > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored

    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        ranked = self._ranked(query)
        if not ranked:
            return None
        score, entry = ranked[0]
        return Resolution(
            answer=entry["answer"],
            confidence=round(score, 3),
            source=Source.FAQ.value,
            intent=entry["id"],
            suggestions=entry.get("suggestions", []),
        )

    def top_contexts(self, query: str, k: int = 3) -> list[str]:
        """Trả về k đoạn FAQ liên quan nhất để nhét vào prompt AI (RAG-lite)."""
        contexts: list[str] = []
        for _score, entry in self._ranked(query)[:k]:
            question = entry["questions"][0]["raw"] if entry["questions"] else entry["id"]
            contexts.append(f"Hỏi: {question} → Đáp: {entry['answer']}")
        return contexts
