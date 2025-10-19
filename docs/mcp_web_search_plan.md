# MCP Web Search Server – Architecture Plan

_Last updated: 2025-10-19_

## 1. Goal and Scope
- Provide agents with curated web search via DuckDuckGo HTML endpoint (no API key required).
- Offer two MCP tools:
  - `web_search.query` – return scored search highlights with optional page previews.
  - `web_search.fetch_page` – fetch full HTML/text for downstream processing.
- Ensure safe, rate-limited external access with observability hooks and clear security boundaries.

## 2. High-Level Architecture
```
Agent (Codex) ──MCP stdio──> FastMCP server (main.py) ──> Service layer
                                              │
                                              ├─> Rate limiter + telemetry
                                              ├─> Search client (DuckDuckGo HTML)
                                              └─> Crawler (httpx + BeautifulSoup)
```
- **FastMCP server (`server.py`)** registers tools and handles transport (`mcp.run(transport="stdio")`).
- **Service layer (`service.py`)** orchestrates rate limiting, telemetry timing, search + crawler calls, summarisation and caching.
- **Search client (`search_client.py`)** performs DuckDuckGo HTML scraping (BeautifulSoup) with link normalisation.
- **Crawler (`crawler.py`)** fetches arbitrary pages, returning metadata, full HTML and text extract.
- **Summariser (`summarizer.py`)** deduplicates/snippety and scores results (domain/keyword bonuses).
- **Telemetry** uses Prometheus metrics + structured logging (structlog/ logging module).

## 3. Resources & Data Flow
| Component | Inputs | Outputs | Notes |
|-----------|--------|---------|-------|
| `web_search.query` | `query` (string), `max_results`, `agent_id` | JSON summary, highlights, `sources[]`, optional `fetched_pages[]` | `fetched_pages` limited to top N (default 3). |
| `web_search.fetch_page` | `url` | HTML + text + HTTP status | Acts as standalone tool and as helper for query. |
| DuckDuckGo HTML endpoint | Query string (GET) | HTML search results | No API key; fallback `duckduckgo.com/html/` handles country `kl`. |
| Cache (`QueryCache`) | Normalised `(query,max_results)` | Cached response (Summary) | TTL configurable via `.env`. |
| Rate limiter (`RateLimiter`) | Agent/global token counts | Permit/deny | Config via `.env` (concurrent per agent + queries/min). |

## 4. Tool Schemas
- `web_search.query`
  - Required: `query: str`
  - Optional: `max_results: int (1-10, default 5)`
  - Optional: `agent_id: str` (defaults to `mcp` for rate limiter context).
  - Response includes:
    ```json
    {
      "overview": "...",
      "highlights": ["..."],
      "sources": [
        {"title": "...", "url": "...", "snippet": "..."}
      ],
      "fetched_pages": [
        {
          "url": "...",
          "status_code": 200,
          "content_type": "text/html",
          "text_preview": "..."
        }
      ]
    }
    ```
- `web_search.fetch_page`
  - Required: `url: str (http/https)`
  - Response:
    ```json
    {"url": "...", "status_code": 200, "content_type": "text/html", "text": "...", "html": "..."}
    ```

## 5. Security & Compliance Boundaries
- **Network access** limited to DuckDuckGo HTML and fetched URLs; respect robots/ ToS.
- **Rate limiting:** per-agent concurrency + org-wide queries/min (configurable).
- **Caching** avoids repeated external calls (TTL default 10 min).
- **Logging** omits sensitive data; storing only query strings and URLs.
- **Config** loaded via `.env` (`SEARCH_LANGUAGE`, rate limits etc.); no secrets stored in repo.
- **Observability:** 
  - Metrics: `web_search_queries_total`, `web_search_query_latency_seconds`, `web_search_rate_limiter_drops_total`, `web_search_pages_fetched_total`.
  - Structured logs for query start/finish and crawler failures.

## 6. Dependencies
- Python libs: `httpx`, `beautifulsoup4`, `mcp[cli]`, `anyio`, `prometheus-client`, `structlog`, `python-dotenv`.
- External: DuckDuckGo HTML endpoint; target URLs for fetch tool.
- Optional dev libs: `fastapi` + `uvicorn` for mock HTTP API.

## 7. Deployment & Integration
- CLI usage: `uv run main.py --serve-stdio` (or `.venv/bin/python ...`).
- Codex integration: `manifest.json` + config block invoking `uv run python main.py --serve-stdio`.
- WSL note: set `UV_CACHE_DIR=$PWD/.uvcache` and `UV_LINK_MODE=copy` to avoid permission issues.

## 8. Runbook / Next Steps
1. **Implement stdio transport (DONE)** – already using `FastMCP.run(transport="stdio")`.
2. **Optional WebSocket transport** – add `mcp.run(transport="websocket", host=..., port=...)` if needed.
3. **Enhance summariser** – consider ML scoring / dedup by domain clusters.
4. **Hardening** – add retry/backoff for HTTP 429/5xx, sanitise HTML with `bleach` if downstream requires.
5. **Documentation** – keep README + info pages updated; share lessons learned (see org info page).

## 9. Open Questions
- Do we need persistent storage for search logs / compliance audits?
- Should `web_search.fetch_page` support HTML selectors or attachments for large pages?
- Are there specific allowlists/deny lists for fetched domains (security policy)?

---
Prepared by: Aleksandra Nowicka (MCP Engineer)
