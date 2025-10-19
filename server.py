from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from tools import WebSearchTool

logger = logging.getLogger(__name__)


def create_mcp_server(tool: WebSearchTool) -> FastMCP:
    server = FastMCP("mcp-web-search")

    @server.tool()
    async def web_search_query(query: str, max_results: int = 5, agent_id: str = "mcp") -> dict:
        result = await tool.execute(agent_id=agent_id, query=query, max_results=max_results)
        return {
            "overview": result.overview,
            "highlights": result.highlights,
            "sources": result.sources,
            "fetched_pages": result.fetched_pages,
        }

    @server.tool()
    async def web_search_fetch_page(url: str) -> dict:
        result = await tool.fetch_page(url)
        if result is None:
            return {
                "url": url,
                "status_code": None,
                "content_type": None,
                "text": None,
                "html": None,
            }
        return {
            "url": result.url,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "text": result.text,
            "html": result.html,
        }

    logger.info("Registered MCP tools: web_search_query, web_search_fetch_page")
    return server


def run_stdio_server(tool: WebSearchTool) -> None:
    server = create_mcp_server(tool)
    logger.info("Starting FastMCP stdio loop …")
    server.run(transport="stdio")
