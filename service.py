from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from httpx import HTTPError

from cache import QueryCache
from crawler import Crawler, FetchedPage
from rate_limiter import RateLimitExceeded, RateLimiter
from search_client import SearchClient, SearchResult
from summarizer import Summarizer
from telemetry import Telemetry

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Response structure returned to MCP agents."""

    summary: Dict[str, Any]
    results: List[Dict[str, Any]]
    fetched_pages: Optional[List[Dict[str, Any]]] = None


class WebSearchService:
    """Coordinator orchestrating search, crawling, summarisation, and telemetry."""

    def __init__(
        self,
        *,
        rate_limiter: RateLimiter,
        telemetry: Telemetry,
        search_client: SearchClient,
        summarizer: Summarizer,
        crawler: Optional[Crawler] = None,
        query_cache: Optional[QueryCache] = None,
        max_pages_to_fetch: int = 3,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._telemetry = telemetry
        self._search_client = search_client
        self._summarizer = summarizer
        self._crawler = crawler
        self._cache = query_cache
        self._max_pages_to_fetch = max_pages_to_fetch

    async def query(
        self,
        *,
        agent_id: str,
        query: str,
        max_results: int = 5,
    ) -> QueryResponse:
        """Execute the search workflow for an MCP agent."""
        cache_key = self._build_cache_key(query=query, max_results=max_results)
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Cache hit for query='%s'", query)
                return cached

        try:
            await self._rate_limiter.acquire(agent_id)
        except RateLimitExceeded:
            logger.warning("Rate limit exceeded for agent=%s", agent_id)
            self._telemetry.record_rate_limit_drop("rate_limiter")
            raise

        results: List[SearchResult] = []
        fetched_pages: List[FetchedPage] = []

        try:
            with self._telemetry.measure_query(agent_id):
                results = await self._search_client.search(query, max_results=max_results)
                if self._crawler:
                    fetched_pages = await self._fetch_top_results(results)
        except HTTPError as exc:
            logger.error("Search provider error: %s", exc, exc_info=True)
            raise
        finally:
            await self._rate_limiter.release(agent_id)

        summary = self._summarizer.build_summary(results)
        response = QueryResponse(
            summary={
                "overview": summary.overview,
                "highlights": summary.highlights,
            },
            results=[
                {"title": item.title, "url": item.url, "snippet": item.snippet}
                for item in results
            ],
            fetched_pages=[
                {
                    "url": page.url,
                    "status_code": page.status_code,
                    "content_type": page.content_type,
                    "text_preview": (page.text[:8000] if page.text else None),
                }
                for page in fetched_pages
            ]
            if fetched_pages
            else None,
        )
        if self._cache:
            self._cache.set(cache_key, response)
        return response

    async def _fetch_top_results(self, results: List[SearchResult]) -> List[FetchedPage]:
        if not self._crawler:
            return []

        pages: List[FetchedPage] = []
        for result in results[: self._max_pages_to_fetch]:
            try:
                page = await self._crawler.fetch(result.url)
                pages.append(page)
            except HTTPError as exc:
                logger.warning("Failed to fetch URL %s: %s", result.url, exc)
        return pages

    async def fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        if not self._crawler:
            return None
        page = await self._crawler.fetch(url)
        return {
            "url": page.url,
            "status_code": page.status_code,
            "content_type": page.content_type,
            "text": page.text[:200000] if page.text else None,
            "html": page.html[:200000] if page.html else None,
        }

    @staticmethod
    def _build_cache_key(*, query: str, max_results: int) -> str:
        return f"{query.lower().strip()}::{max_results}"
