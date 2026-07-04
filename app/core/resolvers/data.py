"""Resolver dữ liệu sống — gọi NGƯỢC về BE cho câu cần số liệu thật.

Hai năng lực:
  A. Liệt kê môn đang dạy      ("trung tâm có những môn gì", "dạy môn nào")
  B. Đếm/tra gia sư theo môn   ("có bao nhiêu gia sư", "gia sư môn Toán")

Chỉ kích hoạt khi có trigger rõ ràng; mọi lỗi (BE sập, không có backend) → None
để rơi xuống AI, không làm hỏng luồng chat. Kết quả `cacheable=False` (dữ liệu sống).
"""
from __future__ import annotations

import time

from ..normalizer import normalize, tokenize
from ..types import ChatContext, Resolution, Source
from .base import Resolver

# Cụm nhiều từ báo hiệu "đếm/liệt kê".
_COUNT_PHRASES = ("bao nhieu", "danh sach", "liet ke")
# Token đơn báo hiệu đếm.
_COUNT_TOKENS = {"may"}
_SUBJECTS_TTL = 300.0  # cache danh sách môn 5 phút để đỡ gọi BE mỗi câu


class DataResolver(Resolver):
    name = "data"

    def __init__(self, backend, settings=None) -> None:
        self._backend = backend
        self._subjects_cache: list[str] | None = None
        self._subjects_at = 0.0

    async def _subjects(self) -> list[str]:
        now = time.monotonic()
        if self._subjects_cache is not None and now - self._subjects_at < _SUBJECTS_TTL:
            return self._subjects_cache
        subjects = await self._backend.get_subjects()
        if subjects is not None:
            self._subjects_cache = subjects
            self._subjects_at = now
        return subjects or []

    def _detect_subject(self, subjects: list[str], q_tokens: set[str], q_norm: str) -> str | None:
        """Khớp tên môn (không dấu) trong câu; ưu tiên tên dài (nhiều token) hơn."""
        best: str | None = None
        best_len = 0
        for subject in subjects:
            s_norm = normalize(subject)
            if not s_norm:
                continue
            s_tokens = set(tokenize(subject))
            hit = s_norm in q_norm if " " in s_norm else s_tokens <= q_tokens
            if hit and len(s_norm) > best_len:
                best, best_len = subject, len(s_norm)
        return best

    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        if self._backend is None:
            return None

        q_norm = normalize(query)
        q_tokens = set(tokenize(query))
        has_count = any(p in q_norm for p in _COUNT_PHRASES) or bool(_COUNT_TOKENS & q_tokens)

        # --- B: gia sư (có ưu tiên hơn A khi cùng nhắc tới "môn") ---
        if "gia" in q_tokens and "su" in q_tokens:
            subjects = await self._subjects()
            subject = self._detect_subject(subjects, q_tokens, q_norm) if subjects else None
            if not (has_count or subject):
                return None  # "gia sư có kinh nghiệm không" → không phải câu số liệu
            result = await self._backend.search_tutors(subject=subject)
            if not result:
                return None
            total = result.get("total")
            if total is None:
                total = len(result.get("tutors") or [])
            if subject:
                answer = (
                    f"Hiện có {total} gia sư dạy môn {subject} trên WebTutorCenter. "
                    "Bạn xem hồ sơ và liên hệ tại trang Tìm gia sư nhé."
                )
            else:
                answer = (
                    f"Hiện có {total} gia sư đang hoạt động trên WebTutorCenter. "
                    "Bạn có thể lọc theo môn, khu vực tại trang Tìm gia sư."
                )
            return Resolution(
                answer=answer,
                confidence=0.9,
                source=Source.DATA.value,
                intent="tutor_count",
                cacheable=False,
                suggestions=["Làm sao để tìm gia sư?", "Học phí như thế nào?"],
                meta={"subject": subject, "total": total},
            )

        # --- A: danh sách môn ---
        if "mon" in q_tokens and (has_count or {"nao", "gi", "day", "hoc"} & q_tokens):
            subjects = await self._subjects()
            if not subjects:
                return None
            preview = ", ".join(subjects[:15])
            more = "..." if len(subjects) > 15 else ""
            answer = (
                f"WebTutorCenter hiện có {len(subjects)} môn: {preview}{more}. "
                "Bạn muốn tìm gia sư môn nào?"
            )
            return Resolution(
                answer=answer,
                confidence=0.9,
                source=Source.DATA.value,
                intent="subject_list",
                cacheable=False,
                suggestions=["Có bao nhiêu gia sư môn Toán?", "Làm sao để tìm gia sư?"],
                meta={"count": len(subjects)},
            )

        return None
