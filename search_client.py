from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import httpx
import logging
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup


@dataclass
class SearchResult:
    """Normalized representation of a search hit."""

    title: str
    url: str
    snippet: str


class SearchClient:
    """Thin wrapper around a search provider."""

    _API_KEY_REQUIRED = {"bing", "bing_api"}

    def __post_init__(self) -> None:
        pass

    def __init__(
        self,
        endpoint_url: str,
        api_key: str | None,
        provider: str = "duckduckgo_api",
        use_stub_data: bool = False,
        user_agent: str = "MCPWebSearch/0.1",
        timeout_seconds: int = 15,
        language: str = "us-en",
    ) -> None:
        self._endpoint_url = endpoint_url
        self._api_key = api_key
        self._provider = provider
        self._user_agent = user_agent
        self._timeout = timeout_seconds
        self._language = language

        requires_key = provider in self._API_KEY_REQUIRED
        self._use_stub = use_stub_data or (requires_key and not api_key)

        self._client: httpx.AsyncClient | None = None
        if not self._use_stub:
            headers = {"User-Agent": self._user_agent}
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
                follow_redirects=True,
            )

    async def search(self, query: str, *, max_results: int = 5) -> List[SearchResult]:
        """Execute query and return normalized results."""
        if self._use_stub:
            return self._search_stub(query, max_results)

        if not self._client:
            headers = {"User-Agent": self._user_agent}
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
                follow_redirects=True,
            )

        if self._provider == "duckduckgo_html":
            html_results = await self._search_duckduckgo_html(query, max_results)
            return html_results[:max_results]

        if self._provider in {"bing", "bing_api"}:
            params = {"q": query, "count": max_results}
            headers: Dict[str, str] = {}
            headers["Ocp-Apim-Subscription-Key"] = self._api_key or ""
            response = await self._client.get(self._endpoint_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return self._parse_results(data, max_results)

        raise RuntimeError(f"Unsupported provider: {self._provider}")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def _parse_results(self, payload: Dict[str, Any], limit: int) -> List[SearchResult]:
        """Convert provider payload to normalized results."""
        web_pages = payload.get("webPages", {}).get("value", [])
        results: List[SearchResult] = []
        for item in web_pages[:limit]:
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                )
            )
        return results

    def _search_stub(self, query: str, max_results: int) -> List[SearchResult]:
        q = query.lower()
        matches = [
            result
            for result in _DEFAULT_STUB_RESULTS
            if q in result.title.lower() or q in result.snippet.lower()
        ]
        selection = matches if matches else _DEFAULT_STUB_RESULTS
        return selection[:max_results]

    async def _search_duckduckgo_html(
        self, query: str, max_results: int
    ) -> List[SearchResult]:
        if not self._client:
            headers = {"User-Agent": self._user_agent}
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
                follow_redirects=True,
            )

        params = {"q": query, "kl": self._language}
        response = await self._client.get(self._endpoint_url, params=params)
        if response.status_code != 200:
            logging.getLogger(__name__).warning(
                "DuckDuckGo HTML request failed",
                extra={"query": query, "status_code": response.status_code},
            )
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: List[SearchResult] = []
        for result_div in soup.select("div.result"):
            link = result_div.select_one("a.result__a")
            if not link:
                continue
            title = link.get_text(strip=True)
            url = link.get("href") or ""
            url = self._normalize_url(url)
            snippet_tag = result_div.select_one("div.result__snippet") or result_div.select_one(
                "a.result__snippet"
            )
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

            if not url or not title:
                continue
            results.append(SearchResult(title=title, url=url, snippet=snippet))
            if len(results) >= max_results:
                break

        if not results:
            logging.getLogger(__name__).info(
                "DuckDuckGo HTML fallback returned no results", extra={"query": query}
            )
        return results

    def _normalize_url(self, raw_url: str) -> str:
        if not raw_url:
            return ""
        # DuckDuckGo often returns protocol-relative links
        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url
        parsed = urlparse(raw_url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            params = parse_qs(parsed.query)
            uddg = params.get("uddg")
            if uddg:
                return uddg[0]
        return raw_url


_DEFAULT_STUB_RESULTS: List[SearchResult] = [
    SearchResult(
        title="AI security best practices 2025",
        url="https://example.com/ai-security-best-practices",
        snippet="Overview of the latest security guidelines for AI models and agents.",
    ),
    SearchResult(
        title="Observability checklist for MCP servers",
        url="https://example.com/mcp-observability",
        snippet="How to implement metrics, logs, and traces for a multi-server MCP environment.",
    ),
    SearchResult(
        title="Scaling search agents with rate limiting",
        url="https://example.com/mcp-rate-limiters",
        snippet="Practical guidance on throttling queries and protecting search engine APIs.",
    ),
    SearchResult(
        title="Security review template for integration projects",
        url="https://example.com/security-review-template",
        snippet="Security checklist template for MCP integration projects.",
    ),
    SearchResult(
        title="OTEL instrumentation cookbook",
        url="https://example.com/otel-cookbook",
        snippet="OpenTelemetry instrumentation examples for Python services.",
    ),
]
