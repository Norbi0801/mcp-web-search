from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from httpx import HTTPError, RemoteProtocolError

from cache import QueryCache
from config import AppConfig
from crawler import Crawler
from rate_limiter import RateLimitExceeded, RateLimiter, RateLimiterConfig
from search_client import SearchClient
from service import WebSearchService
from server import create_mcp_server, run_stdio_server
from summarizer import Summarizer
from telemetry import Telemetry
from tools import WebSearchTool

def configure_logging() -> None:
    """Initialise structured logging for the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@dataclass
class AppContext:
    """Bundle for the main application components."""

    config: AppConfig
    rate_limiter: RateLimiter
    telemetry: Telemetry
    search_client: SearchClient
    crawler: Crawler
    summarizer: Summarizer
    service: WebSearchService
    query_cache: QueryCache | None


async def run() -> None:
    """Bootstrap coroutine for the MCP web search server."""
    load_dotenv()
    configure_logging()
    config = AppConfig()

    context = await create_context(config)
    parser = build_parser()
    args = parser.parse_args()
    logging.info(
        "MCP web search server initialised",
        extra={
            "provider": config.search_provider,
            "max_concurrent_per_agent": config.max_concurrent_per_agent,
            "max_queries_per_minute": config.max_queries_per_minute,
        },
    )

    try:
        if args.fetch_url:
            await run_fetch_url(context, args.fetch_url)
        elif args.serve_http:
            await run_http_server(context)
        elif args.serve_stdio:
            await run_stdio_transport(context)
        elif args.query:
            await run_cli_query(context, args)
        else:
            logging.info("Server bootstrap complete. Add MCP transport integration next.")
    finally:
        await graceful_shutdown(context)


async def create_context(config: AppConfig) -> AppContext:
    """Instantiate application components."""
    telemetry = Telemetry()
    rate_limiter = RateLimiter(
        RateLimiterConfig(
            max_concurrent_per_agent=config.max_concurrent_per_agent,
            max_queries_per_minute=config.max_queries_per_minute,
        )
    )
    search_client = SearchClient(
        endpoint_url=config.search_api_url.unicode_string(),
        api_key=config.search_api_key,
        provider=config.search_provider,
        use_stub_data=config.use_stub_data,
        user_agent=config.search_user_agent,
        timeout_seconds=config.request_timeout_seconds,
        language=config.search_language,
    )
    crawler = Crawler(timeout_seconds=config.request_timeout_seconds)
    summarizer = Summarizer()
    query_cache = QueryCache(config.cache_ttl_seconds) if config.enable_query_cache else None
    service = WebSearchService(
        rate_limiter=rate_limiter,
        telemetry=telemetry,
        search_client=search_client,
        summarizer=summarizer,
        crawler=crawler,
        query_cache=query_cache,
        max_pages_to_fetch=3,
    )
    return AppContext(
        config=config,
        rate_limiter=rate_limiter,
        telemetry=telemetry,
        search_client=search_client,
        crawler=crawler,
        summarizer=summarizer,
        service=service,
        query_cache=query_cache,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP Web Search Server CLI")
    parser.add_argument("--query", help="Search query to execute")
    parser.add_argument("--agent-id", default="cli-agent", help="Agent identifier for limiting")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum search results to return")
    parser.add_argument(
        "--serve-http",
        action="store_true",
        help="Run mock HTTP server for developer preview (requires uvicorn).",
    )
    parser.add_argument(
        "--serve-stdio",
        action="store_true",
        help="Run MCP server over stdio (requires the `mcp` Python package).",
    )
    parser.add_argument(
        "--fetch-url",
        help="Fetch a single web page and print structured content.",
    )
    return parser


async def run_cli_query(context: AppContext, args: argparse.Namespace) -> None:
    """Execute a single search query and print JSON payload."""
    try:
        response = await context.service.query(
            agent_id=args.agent_id,
            query=args.query,
            max_results=args.max_results,
        )
    except RateLimitExceeded:
        logging.error("Rate limit hit for agent_id=%s", args.agent_id)
        sys.exit(1)
    except HTTPError as exc:
        logging.error("Search provider error: %s", exc)
        sys.exit(1)

    payload = {
        "summary": response.summary,
        "results": response.results,
    }
    if response.fetched_pages is not None:
        payload["fetched_pages"] = response.fetched_pages
    print(json.dumps(payload, indent=2, ensure_ascii=False))


async def run_fetch_url(context: AppContext, url: str) -> None:
    result = await context.service.fetch_page(url)
    if result is None:
        logging.error("Crawler not configured; cannot fetch page")
        sys.exit(1)
    payload = {
        "url": result["url"],
        "status_code": result["status_code"],
        "content_type": result["content_type"],
        "text": result.get("text"),
        "html": result.get("html"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


async def run_http_server(context: AppContext) -> None:
    """Start mock HTTP server using uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - optional dependency
        logging.error("Unable to start HTTP server: uvicorn not installed (%s)", exc)
        sys.exit(1)

    from app import create_app

    app = create_app(context.service)
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
        log_level="info",
    )
    server = uvicorn.Server(config)
    logging.info("Starting mock HTTP server on http://0.0.0.0:8000")
    await server.serve()


async def graceful_shutdown(context: AppContext) -> None:
    """Tear down long-lived resources."""
    try:
        await context.search_client.close()
        await context.crawler.close()
    except (RemoteProtocolError, OSError) as exc:
        logging.warning("Shutdown encountered a network error: %s", exc)


async def run_stdio_transport(context: AppContext) -> None:
    """Start MCP server via stdio transport if SDK is available."""
    tool = WebSearchTool(context.service)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, run_stdio_server, tool)
    except RuntimeError as exc:
        logging.error("Unable to start MCP server: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
