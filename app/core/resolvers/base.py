"""Interface resolver + helper so khớp dùng chung.

Chain of Responsibility: engine chạy từng resolver theo thứ tự; resolver trả về
`Resolution` (kèm confidence) hoặc `None` để nhường mắt xích sau. AI là mắt xích cuối.
"""
from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from pathlib import Path

from ..types import ChatContext, Resolution


class Resolver(ABC):
    """Một mắt xích trong chuỗi xử lý."""

    name: str = "resolver"

    @abstractmethod
    async def resolve(self, query: str, ctx: ChatContext) -> Resolution | None:
        """Trả `Resolution` nếu xử lý được, `None` để nhường resolver kế tiếp."""
        raise NotImplementedError


# --- helper so khớp token ---

def jaccard(a: set[str], b: set[str]) -> float:
    """|A ∩ B| / |A ∪ B|."""
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def coverage(needle: set[str], haystack: set[str]) -> float:
    """Tỉ lệ token của `needle` xuất hiện trong `haystack`."""
    if not needle:
        return 0.0
    return len(needle & haystack) / len(needle)


def compute_generic(docs: list[set[str]], *, ratio: float = 0.2, floor: int = 3) -> set[str]:
    """Token 'phổ biến' = xuất hiện ở >= `ratio` số tài liệu (tối thiểu `floor`).

    Dùng để chặn khớp chỉ dựa vào token quá thường gặp trong corpus (vd 'gia sư'
    xuất hiện ở hầu hết intent/FAQ) — những token này không đủ đặc trưng để định
    hướng câu trả lời.
    """
    n = len(docs)
    if not n:
        return set()
    df: dict[str, int] = {}
    for doc in docs:
        for token in doc:
            df[token] = df.get(token, 0) + 1
    cutoff = max(floor, math.ceil(ratio * n))
    return {token for token, count in df.items() if count >= cutoff}


def load_json(path: Path) -> dict:
    """Đọc file JSON UTF-8."""
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)
