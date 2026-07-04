"""TTL cache đơn giản cho câu hỏi lặp (giảm gọi AI trùng lặp)."""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar

V = TypeVar("V")


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[V]):
    """Cache LRU + TTL, giới hạn kích thước. Không thread-safe (đủ cho async 1 loop)."""

    def __init__(self, *, ttl_seconds: float = 3600, max_size: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max = max(1, max_size)
        self._store: OrderedDict[str, _Entry[V]] = OrderedDict()

    def get(self, key: str) -> V | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)  # LRU: vừa dùng thì đẩy về cuối
        return entry.value

    def set(self, key: str, value: V) -> None:
        self._store[key] = _Entry(value, time.monotonic() + self._ttl)
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)  # bỏ phần tử cũ nhất

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
