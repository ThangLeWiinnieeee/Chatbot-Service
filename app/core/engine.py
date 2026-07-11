"""Engine điều phối: cache → chuỗi resolver → AI fallback → log flywheel."""
from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .cache import TTLCache
from .normalizer import normalize
from .prompt import build_messages
from .providers.base import AIProvider, AIProviderError
from .resolvers.base import Resolver
from .resolvers.faq import FaqResolver
from .types import ChatContext, Resolution, Source

logger = logging.getLogger(__name__)

_EMPTY_MSG = "Bạn muốn hỏi gì về WebTutorCenter? Ví dụ: tìm gia sư, đăng ký, học phí..."
_FALLBACK_MSG = (
    "Xin lỗi, mình chưa hiểu rõ ý bạn. Bạn có thể hỏi về cách tìm gia sư, đăng ký tài khoản, "
    "học phí, hoặc nhắn 'gặp admin' để được hỗ trợ trực tiếp nhé."
)
# Rule dưới ngưỡng nhưng >= mức này vẫn dùng được khi AI không khả dụng
# (chỉ nhận near-miss thật sự, tránh khớp mờ do bỏ dấu trùng âm).
_CANDIDATE_FLOOR = 0.55


class ChatEngine:
    def __init__(
        self,
        *,
        resolvers: list[Resolver],
        faq_resolver: FaqResolver | None = None,
        provider: AIProvider | None = None,
        threshold: float = 0.6,
        faq_context_k: int = 3,
        cache: TTLCache | None = None,
        miss_log_path: str | Path | None = None,
    ) -> None:
        self._resolvers = resolvers
        self._faq = faq_resolver
        self._provider = provider
        self._threshold = threshold
        self._faq_k = faq_context_k
        self._cache: TTLCache[Resolution] = cache or TTLCache()
        self._miss_path = Path(miss_log_path) if miss_log_path else None

    async def answer(self, query: str, ctx: ChatContext | None = None) -> Resolution:
        ctx = ctx or ChatContext()
        text = (query or "").strip()
        if not text:
            return Resolution(_EMPTY_MSG, 1.0, Source.FALLBACK.value, intent="empty")

        key = normalize(text)
        cached = self._cache.get(key)
        if cached is not None:
            return dataclasses.replace(cached, meta={**cached.meta, "cache_hit": True})

        # --- Chuỗi resolver ---
        best_candidate: Resolution | None = None
        for resolver in self._resolvers:
            try:
                res = await resolver.resolve(text, ctx)
            except Exception:  # noqa: BLE001 - một resolver lỗi không được làm sập cả chuỗi
                logger.exception("Resolver '%s' lỗi", getattr(resolver, "name", "?"))
                continue
            if res is None:
                continue
            if res.confidence >= self._threshold:
                if res.cacheable:
                    self._cache.set(key, res)
                return res
            if best_candidate is None or res.confidence > best_candidate.confidence:
                best_candidate = res

        # --- AI fallback ---
        result = await self._ai_answer(text, ctx, best_candidate)
        if result.cacheable:
            self._cache.set(key, result)
        return result

    async def _ai_answer(
        self, query: str, ctx: ChatContext, candidate: Resolution | None
    ) -> Resolution:
        contexts = self._faq.top_contexts(query, self._faq_k) if self._faq else []

        if self._provider is None:
            self._log_miss(query, candidate, reason="ai_disabled")
            return self._degrade(candidate)

        messages = build_messages(query, ctx.history, contexts)
        try:
            answer = await self._provider.complete(messages)
        except AIProviderError:
            self._log_miss(query, candidate, reason="ai_error")
            return self._degrade(candidate)

        self._log_miss(query, candidate, reason="ai_used")
        return Resolution(
            answer=answer,
            confidence=0.5,
            source=Source.AI.value,
            intent=candidate.intent if candidate else None,
            # Câu có history phụ thuộc ngữ cảnh hội thoại → không cache theo query-only,
            # tránh trả đáp án của hội thoại khác cho follow-up ("còn môn Lý thì sao?").
            cacheable=not ctx.history,
            meta={"rag_contexts": len(contexts)},
        )

    @staticmethod
    def _degrade(candidate: Resolution | None) -> Resolution:
        """Không có AI: dùng rule dưới ngưỡng nếu đủ tốt, ngược lại câu xin lỗi."""
        if candidate is not None and candidate.confidence >= _CANDIDATE_FLOOR:
            return dataclasses.replace(
                candidate, meta={**candidate.meta, "low_confidence": True}
            )
        return Resolution(_FALLBACK_MSG, 0.0, Source.FALLBACK.value, intent="fallback")

    def _log_miss(self, query: str, candidate: Resolution | None, *, reason: str) -> None:
        """Flywheel: ghi lại câu rớt rule để sau này biến thành rule mới (0 token).

        Vừa log (chẩn đoán) vừa append JSONL (khai thác lại): mỗi câu rớt = 1 dòng
        để sau lọc/gom thành intent/FAQ mới.
        """
        conf = candidate.confidence if candidate else 0.0
        intent = candidate.intent if candidate else None
        logger.info(
            "chatbot.miss reason=%s best=%.3f intent=%s query=%r", reason, conf, intent, query
        )
        if self._miss_path is None:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "confidence": round(conf, 3),
            "intent": intent,
            "query": query,
        }
        try:
            self._miss_path.parent.mkdir(parents=True, exist_ok=True)
            # ponytail: append đồng bộ, 1 dòng/câu — đủ cho single-process.
            # Ghi lỗi không được làm sập chat → nuốt mọi exception.
            with self._miss_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001 - flywheel là phụ, không chặn câu trả lời
            logger.warning("Không ghi được flywheel log vào %s", self._miss_path)

    async def aclose(self) -> None:
        if self._provider is not None:
            await self._provider.aclose()
