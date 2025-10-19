from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query

from service import WebSearchService
from tools import WebSearchTool


def create_app(service: WebSearchService) -> FastAPI:
    app = FastAPI(title="MCP Web Search Mock API")
    tool = WebSearchTool(service)
    logger = logging.getLogger("mock_api")

    @app.get("/healthz")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/web-search")
    async def web_search(
        query: str = Query(..., description="Query string to search for"),
        agent_id: str = Query("mock-http", description="Agent identifier"),
        max_results: int = Query(5, description="Maximum results to fetch"),
    ) -> Dict[str, Any]:
        try:
            result = await tool.execute(agent_id=agent_id, query=query, max_results=max_results)
        except Exception as exc:  # broad for mock server, log and wrap
            logger.exception("Mock search failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "overview": result.overview,
            "highlights": result.highlights,
            "sources": result.sources,
        }

    @app.get("/web-search/page")
    async def web_search_page(url: str = Query(..., description="URL to fetch")) -> Dict[str, Any]:
        try:
            result = await tool.fetch_page(url)
        except Exception as exc:
            logger.exception("Mock fetch failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Crawler not configured")
        return {
            "url": result.url,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "text": result.text,
            "html": result.html,
        }

    return app
