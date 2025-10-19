from __future__ import annotations

import pytest

from rate_limiter import RateLimitExceeded, RateLimiter, RateLimiterConfig


@pytest.mark.asyncio
async def test_acquire_and_release_under_limits() -> None:
    limiter = RateLimiter(
        RateLimiterConfig(max_concurrent_per_agent=2, max_queries_per_minute=10)
    )

    await limiter.acquire("agent")
    await limiter.acquire("agent")
    await limiter.release("agent")
    await limiter.release("agent")


@pytest.mark.asyncio
async def test_concurrent_limit_per_agent() -> None:
    limiter = RateLimiter(
        RateLimiterConfig(max_concurrent_per_agent=1, max_queries_per_minute=10)
    )

    await limiter.acquire("agent")
    with pytest.raises(RateLimitExceeded):
        await limiter.acquire("agent")
    await limiter.release("agent")


@pytest.mark.asyncio
async def test_global_rate_limit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(
        RateLimiterConfig(
            max_concurrent_per_agent=2,
            max_queries_per_minute=1,
            window_seconds=60,
        )
    )

    timestamps = iter([100.0, 161.0])
    monkeypatch.setattr("rate_limiter.time.monotonic", lambda: next(timestamps))

    await limiter.acquire("agent")
    await limiter.release("agent")
    await limiter.acquire("agent")
