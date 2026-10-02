"""Token bucket em memória (por processo). Para várias réplicas, o limite global fica no gateway."""

from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, per_minute: int, burst: int | None = None) -> None:
        self.rate = per_minute / 60.0
        self.cap = float(burst or per_minute)
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.cap, now))
        tokens = min(self.cap, tokens + (now - last) * self.rate)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            ok, retry = True, 0.0
        else:
            self._buckets[key] = (tokens, now)
            ok, retry = False, (1 - tokens) / self.rate
        if len(self._buckets) > 10_000:  # evita crescimento ilimitado (DoS de memória)
            cutoff = now - 120
            self._buckets = {k: v for k, v in self._buckets.items() if v[1] > cutoff}
        return ok, retry
