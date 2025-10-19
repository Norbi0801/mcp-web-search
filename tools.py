from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from service import QueryResponse, WebSearchService


@dataclass
class WebSearchToolResult:
    """Structured payload suitable for MCP tool responses."""

    overview: str
    highlights: List[str]
    sources: List[Dict[str, Any]]
    fetched_pages: Optional[List[Dict[str, Any]]]


@dataclass
class WebPageContentResult:
    url: str
    status_code: int
    content_type: Optional[str]
    text: Optional[str]
    html: Optional[str]


class WebSearchTool:
    """Adapter to expose WebSearchService as an MCP-style tool."""

    def __init__(self, service: WebSearchService) -> None:
        self._service = service

    async def execute(
        self,
        *,
        agent_id: str,
        query: str,
        max_results: int = 5,
    ) -> WebSearchToolResult:
        response: QueryResponse = await self._service.query(
            agent_id=agent_id,
            query=query,
            max_results=max_results,
        )
        return WebSearchToolResult(
            overview=response.summary["overview"],
            highlights=response.summary.get("highlights", []),
            sources=response.results,
            fetched_pages=response.fetched_pages,
        )

    async def fetch_page(self, url: str) -> Optional[WebPageContentResult]:
        page = await self._service.fetch_page(url)
        if not page:
            return None
        return WebPageContentResult(
            url=page["url"],
            status_code=page["status_code"],
            content_type=page["content_type"],
            text=page["text"],
            html=page["html"],
        )
