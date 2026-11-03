from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def eventually(fn: Callable[[], T], predicate: Callable[[T], bool], message: str,
               timeout: float = 10.0, interval: float = 0.2) -> T:
    """Poll an eventually-consistent condition (async notifications, queues) instead of sleeping."""
    deadline = time.monotonic() + timeout
    value = fn()
    while not predicate(value):
        if time.monotonic() > deadline:
            raise AssertionError(f"Timed out after {timeout}s waiting for: {message}. Last value: {value!r}")
        time.sleep(interval)
        value = fn()
    return value
