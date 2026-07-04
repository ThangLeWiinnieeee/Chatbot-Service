"""Chuẩn hoá & tách token tiếng Việt phục vụ so khớp rule.

Bỏ dấu để so khớp bền hơn ("hoc phi" khớp "học phí"), hạ chữ thường, bỏ dấu câu.
"""
from __future__ import annotations

import re
import unicodedata

# 'đ'/'Đ' không tách bằng NFD nên xử lý tay.
_D_MAP = str.maketrans({"đ": "d", "Đ": "D"})
_TOKEN_RE = re.compile(r"[0-9a-z]+")

# Stopword tiếng Việt cho so khớp NỘI DUNG (keyword/faq). Gồm cả từ để hỏi
# generic ("bao nhiêu", "thế nào", "mấy") vì chúng dễ gây khớp nhầm intent.
# Data resolver KHÔNG dùng set này (nó dùng `tokenize`/`normalize`) nên "bao nhiêu",
# "mấy" vẫn dùng được để nhận diện câu số liệu.
STOPWORDS: frozenset[str] = frozenset(
    {
        "la", "va", "co", "cua", "cho", "voi", "de", "khi", "thi", "ma", "o",
        "cac", "nhung", "mot", "nhu", "toi", "ban", "minh", "a", "ah", "oi",
        "nhe", "nha", "vay", "the", "nay", "do", "duoc", "hay", "hoac", "tai",
        "trong", "ra", "vao", "len", "xuong", "ve", "den", "tu", "boi", "nen",
        "rat", "qua", "lam", "bi", "se", "dang", "da", "roi", "con", "cung",
        "gi", "sao", "dau", "khong", "bao", "nhieu", "nao", "may", "the",
    }
)


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ nguyên chữ cái cơ bản."""
    text = text.translate(_D_MAP)
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Về dạng: chữ thường, không dấu, không dấu câu, gộp khoảng trắng."""
    text = strip_accents(text or "").lower()
    text = re.sub(r"[^0-9a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    """Tách token từ chuỗi đã chuẩn hoá."""
    return _TOKEN_RE.findall(normalize(text))


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def content_tokens(text: str) -> list[str]:
    """Token đã bỏ stopword — dùng cho so khớp ngữ nghĩa nhẹ."""
    return [t for t in tokenize(text) if t not in STOPWORDS]


def content_set(text: str) -> set[str]:
    return set(content_tokens(text))
