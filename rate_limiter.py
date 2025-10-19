from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict


class RateLimitExceeded(RuntimeError):
    """Raised when an agent or the system exceeds configured limits."""


@dataclass(frozen=True)
class RateLimiterConfig:
    """Configuration options for the token bucket rate limiter."""

    max_concurrent_per_agent: int
    max_queries_per_minute: int
    window_seconds: int = 60


class RateLimiter:
    """Simple in-memory sliding window limiter with per-agent and global quotas."""

    def __init__(self, config: RateLimiterConfig) -> None:
        self._config = config
        self._agent_active: Dict[str, int] = defaultdict(int)
        self._global_window: Deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, agent_id: str) -> None:
        """Reserve capacity for the agent. Raises RateLimitExceeded on rejection."""
        async with self._lock:
            now = time.monotonic()
            self._prune(now)

            if self._agent_active[agent_id] >= self._config.max_concurrent_per_agent:
                raise RateLimitExceeded(
                    f"Agent {agent_id} exceeded concurrent allowance "
                    f"({self._config.max_concurrent_per_agent})."
                )

            if len(self._global_window) >= self._config.max_queries_per_minute:
                raise RateLimitExceeded(
                    "Global web search quota exceeded "
                    f"({self._config.max_queries_per_minute}/min)."
                )

            self._agent_active[agent_id] += 1
            self._global_window.append(now)

    async def release(self, agent_id: str) -> None:
        """Release the most recent slot for the agent."""
        async with self._lock:
            if self._agent_active[agent_id] > 0:
                self._agent_active[agent_id] -= 1

    def _prune(self, now: float) -> None:
        """Remove timestamps outside the sliding window."""
        window_start = now - self._config.window_seconds

        while self._global_window and self._global_window[0] < window_start:
            self._global_window.popleft()
