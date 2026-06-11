from __future__ import annotations

"""Rate limiter with bucket eviction and proxy support."""

import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    """Token bucket rate limiter per IP with stale bucket eviction (M2 fix)."""

    def __init__(self, requests_per_minute: int = 120, max_buckets: int = 10000):
        self.rpm = requests_per_minute
        self.max_buckets = max_buckets
        self._buckets: dict = {}
        self._last_eviction = time.time()

    def check(self, key: str) -> bool:
        now = time.time()

        # M2: Evict stale buckets every 5 minutes
        if now - self._last_eviction > 300:
            cutoff = now - 600
            self._buckets = {k: v for k, v in self._buckets.items() if v["last"] > cutoff}
            self._last_eviction = now

        # Hard cap on bucket count
        if key not in self._buckets and len(self._buckets) >= self.max_buckets:
            # Evict oldest
            oldest = min(self._buckets, key=lambda k: self._buckets[k]["last"])
            del self._buckets[oldest]

        if key not in self._buckets:
            self._buckets[key] = {"tokens": self.rpm, "last": now}

        bucket = self._buckets[key]
        elapsed = now - bucket["last"]
        bucket["last"] = now
        bucket["tokens"] = min(self.rpm, bucket["tokens"] + elapsed * (self.rpm / 60.0))

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


_limiter = RateLimiter(requests_per_minute=120)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/css/") or path.startswith("/js/") or path == "/":
            return await call_next(request)

        # M1: Support X-Forwarded-For for reverse proxy setups
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Take the first (original client) IP only
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        if not _limiter.check(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        return await call_next(request)
