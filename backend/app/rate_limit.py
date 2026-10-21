"""Project adapter over the shared rate-limit engine.

The engine (`rate_limit_engine.py`) is vendored unmodified from
`DOCS/shared/rate-limit/engine/fastapi/`. This adapter supplies HiddenInk's slug and
one bucket per LLM-calling action; the engine handles caching, X-Forwarded-For,
event mode, the kill switch (503) and fail-open.
"""
from __future__ import annotations

from fastapi import Request

from . import config
from .rate_limit_engine import RateLimiter

limiter = RateLimiter(
    # Slug = full project folder name (canonical identifier across code + control sheet).
    project="ail-ay2627-s1-lokesh-hiddenink",
    buckets={
        "scan": config.RATE_LIMIT_SCAN_MAX,
        "screen": config.RATE_LIMIT_SCREEN_MAX,
        "redteam": config.RATE_LIMIT_REDTEAM_MAX,
    },
    redis_url=config.UPSTASH_REDIS_URL,
    redis_token=config.UPSTASH_REDIS_TOKEN,
    default_window=config.RATE_LIMIT_WINDOW_SECONDS,
)


def check_rate_limit(request: Request, bucket: str) -> None:
    limiter.enforce(request, bucket)
