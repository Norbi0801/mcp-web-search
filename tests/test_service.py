from __future__ import annotations

from typing import List

import pytest

from cache import QueryCache
from rate_limiter import RateLimiter, RateLimiterConfig
from search_client import SearchResult
from service import QueryResponse, WebSearchService
from summarizer import Summarizer
from telemetry import Telemetry


class StubRateLimiter(RateLimiter):
    def __init__(self) -> None:
        super().__init__(
            RateLimiterConfig(
                max_concurrent_per_agent=10,
                max_queries_per_minute=100,
                window_seconds=60,
            )
        )


class StubSearchClient:
    def __init__(self, results: List[SearchResult]) -> None:
        self._results = results
        self.calls = 0

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        self.calls += 1
        return self._results[:max_results]


@pytest.mark.asyncio
async def test_service_returns_summary() -> None:
    results = [
        SearchResult(title="First", url="https://example.com/1", snippet="Overview snippet."),
        SearchResult(title="Second", url="https://example.com/2", snippet="Highlight A."),
    ]
    service = WebSearchService(
        rate_limiter=StubRateLimiter(),
        telemetry=Telemetry(),
        search_client=StubSearchClient(results),
        summarizer=Summarizer(),
        crawler=None,
    )

    response = await service.query(agent_id="agent-1", query="test", max_results=2)
    assert isinstance(response, QueryResponse)
    assert response.summary["overview"] == "Overview snippet."
    assert response.summary["highlights"] == ["Highlight A."]
    assert len(response.results) == 2
@pytest.mark.asyncio
async def test_service_uses_cache() -> None:
    results = [
        SearchResult(title="Cache", url="https://example.com/cache", snippet="Cache overview"),
    ]
    client = StubSearchClient(results)
    cache = QueryCache(ttl_seconds=60)
    service = WebSearchService(
        rate_limiter=StubRateLimiter(),
        telemetry=Telemetry(),
        search_client=client,
        summarizer=Summarizer(),
        crawler=None,
        query_cache=cache,
    )

    first = await service.query(agent_id="agent-1", query="cache test", max_results=1)
    second = await service.query(agent_id="agent-1", query="cache test", max_results=1)

    assert first.summary == second.summary
    assert client.calls == 1
