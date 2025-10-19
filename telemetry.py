from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator, Optional

from prometheus_client import Counter, Histogram


QUERY_TOTAL = Counter(
    "web_search_queries_total",
    "Total number of web search queries executed.",
    ["agent_id"],
)

QUERY_LATENCY = Histogram(
    "web_search_query_latency_seconds",
    "Latency of web search queries.",
    buckets=(0.5, 1, 2, 4, 6, 8, 10, 15, 30),
)

RATE_LIMIT_DROPS = Counter(
    "web_search_rate_limiter_drops_total",
    "Number of requests rejected by the rate limiter.",
    ["reason"],
)


class Telemetry:
    """Facade around Prometheus metrics helpers."""

    def record_rate_limit_drop(self, reason: str) -> None:
        RATE_LIMIT_DROPS.labels(reason=reason).inc()

    def record_query(self, agent_id: str, duration_seconds: float) -> None:
        QUERY_TOTAL.labels(agent_id=agent_id).inc()
        QUERY_LATENCY.observe(duration_seconds)

    @contextmanager
    def measure_query(self, agent_id: Optional[str] = None) -> Iterator[None]:
        """Context manager to time a web search query."""
        start = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - start
            if agent_id:
                self.record_query(agent_id, duration)
