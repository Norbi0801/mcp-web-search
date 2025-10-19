# MCP Web Search Server – Architecture Draft

## Project Goal
Provide MCP agents with a way to obtain up-to-date information from the public web so they can answer questions in real time. The service is designed to live inside the current workspace as a standalone `mcp-web-search` directory and to be deployable via Docker Compose.

## Scope and Assumptions
- Initial integration targets the public DuckDuckGo HTML endpoint (no API key) by parsing search result pages; the provider can be swapped later if needed.
- Queries are planned and executed sequentially: submit search form → download results page → follow selected links and extract key facts.
- Initial, configurable limits:
  - 5 concurrent queries per agent.
  - 60 queries per minute globally.
- Only metadata is logged: query text, agent identifier, visited URLs, HTTP status codes, latency. Metadata retention is capped at 30 days.
- Full result bodies are never persisted outside of an in-memory cache (TTL < 1 hour).
- Transport must be encrypted (HTTPS for the search engine and fetched pages; TLS at the MCP server ingress).

## Components and Modules
| Module | Role |
| --- | --- |
| `main.py` | MCP entry point (Model Context Protocol) holding the tool and resource registry. |
| `search_client.py` | Search provider client handling auth flows and quotas. |
| `crawler.py` | Fetches and sanitises result pages while respecting robots.txt and request limits. |
| `summarizer.py` | Combines results into summaries (e.g., extractive overview plus highlights). |
| `rate_limiter.py` | Per-agent and global token-bucket limits with metrics integration. |
| `telemetry.py` | Prometheus metrics, JSON logs (stdout), and optional OTEL traces. |
| `config.py` | Loads configuration from `.env` (API keys, limits, timeouts). |
| `service.py` | Coordinates the workflow (limits → search client → crawler → summary). |
| `cache.py` | Simple query cache with a configurable TTL (10 minutes by default). |
| `tools.py` | Adapts `WebSearchService` to MCP tool responses. |
| `app.py` | Mock HTTP server (FastAPI) exposing a demonstration endpoint. |
| `server.py` | Integration point for the official MCP SDK (optional, requires the `mcp` package). |
| `storage.py` (optional) | Lightweight metadata store for future Postgres/pgvector retention. |

Planned directory layout:
```
mcp-web-search/
├── README.md
├── main.py
├── search_client.py
├── crawler.py
├── summarizer.py
├── rate_limiter.py
├── telemetry.py
├── config.py
├── tests/
│   └── __init__.py
├── docker/
│   └── Dockerfile
├── docker-compose.yml (symlinked at the workspace root)
├── .env.example
└── pyproject.toml
```

## Request Flow
1. The agent invokes the `web_search.query` tool with the query text and optional parameters (language, max results).
2. `main.py` enforces per-agent and global limits and hands off to `search_client`.
3. `search_client` queries the search engine and receives a list of top results.
4. `crawler` fetches selected results (in parallel, with per-domain limits and timeouts).
5. `summarizer` stitches snippets into a summary plus a list of citations/URLs.
6. The response is returned to the agent and metadata is recorded for logging/metrics.

## Telemetry and Observability
- **Logs**: JSON on stdout (INFO/ERROR) with the query identifier and visited URLs.
- **Metrics** (Prometheus):
  - `web_search_queries_total{agent}`
  - `web_search_query_latency_seconds`
  - `web_search_pages_fetched_total{domain}`
  - `web_search_rate_limiter_drops_total{reason}`
- **Alerts**: SLO of 99% queries under 8 seconds; page on-call if throughput drops below two successful queries/minute (tune post-deployment).
- **Traces** (optional): integrate with an OTEL exporter if end-to-end tracing is required.

### Additional Documentation
- `docs/mcp_web_search_plan.md` – detailed architecture plan for the web search server.

## CLI Usage (temporary)
To quickly validate the skeleton you can run a single query:
```bash
uv pip install -e .
python main.py --query "latest ai security research" --max-results 3
# or fetch the full contents of a page:
python main.py --fetch-url "https://example.com"
# When using `uv` on WSL, set a local cache if you see cache/link issues:
# mkdir -p .uvcache
# export UV_CACHE_DIR="$PWD/.uvcache"
# export UV_LINK_MODE=copy
# uv sync
```
The default agent identifier is `cli-agent`; override it with `--agent-id` if required.
Queries are issued against DuckDuckGo HTML (`https://html.duckduckgo.com/html/`). Set `USE_STUB_DATA=true` to avoid network traffic entirely and rely on built-in test fixtures.

#### Search Provider
- `SEARCH_PROVIDER=duckduckgo_html` – uses DuckDuckGo HTML (`https://html.duckduckgo.com/html/`) without an API key.
- `SEARCH_API_URL` – defaults to `https://html.duckduckgo.com/html/`; replace when using a custom proxy.
- `SEARCH_USER_AGENT` – user agent header for search HTTP requests.
- `SEARCH_LANGUAGE` – `kl` parameter (e.g. `us-en`, `pl-pl`) passed to both API and HTML endpoints.
- Alternative providers (e.g., Bing) require a key (`SEARCH_API_KEY`) and updating `SEARCH_PROVIDER`.

#### Page Retrieval
- The MCP tool `web_search.fetch_page` returns status, content type, full HTML, and a plaintext rendition of the page.
- The CLI caches responses (`CACHE_TTL_SECONDS`) and exposes `fetched_pages[...].text_preview` for the top three results.

#### Result Cache
- `ENABLE_QUERY_CACHE` (default `true`) – enables the in-memory query cache.
- `CACHE_TTL_SECONDS` (default `600`) – maximum cache entry lifetime; set to `0` to effectively disable caching or call `QueryCache.clear()` to flush.

### Running the MCP server (stdio, experimental)
1. Create/activate a virtual environment:
   ```bash
   cd /mnt/c/Users/norbe/Documents/AI Organisation/sandbox/mcp-web-search
   python -m venv .venv       # or uv venv .venv
   source .venv/bin/activate  # Scripts/activate.bat on Windows
   ```
2. Install the package with MCP extras:
   ```bash
   pip install -e .[mcp]
   ```
3. Start the stdio server locally (works with both `uv run` and the local Python binary):
   ```bash
   uv run main.py --serve-stdio
   # or
   .venv/bin/python main.py --serve-stdio
   ```
   (Look for the `Starting MCP stdio server` log line.)
4. Configure Codex by editing `~/.codex/config.toml` as shown in the “Connecting to Codex” section.
5. If the MCP SDK does not expose stdio transport, extend `server.py` with a dedicated alternative (e.g., WebSocket) per the `mcp` package documentation.

### Mock HTTP API (demo)
```bash
uv pip install uvicorn[standard]
python main.py --serve-http
```
The server listens on `http://localhost:8000/web-search?query=...` and returns JSON using stubbed data until you configure a real provider.

## Tests
```bash
uv pip install -e .[dev]
# if pytest is missing on PATH (e.g. system Python), install it locally:
# python -m pip install pytest
pytest --maxfail=1 --disable-warnings
```

## MCP Integration (optional)
- Install the SDK: `uv pip install -e .[mcp]`.
- Extend `server.py:create_mcp_server` with the desired transport (e.g., WebSocket, stdio) as described in the `mcp` documentation.
- Exposed tools:
  - `web_search.query(query: str, max_results: int = 5, agent_id: str = "mcp")`
  - `web_search.fetch_page(url: str)`
- Once the server is running, point Codex to this tool identifier (see the Codex CLI repository for configuration details).

### MCP transport integration plan
1. Pick a transport compatible with Codex (stdio or WebSocket) and install the recommended version of the `mcp` package.
2. In `server.py`, implement the event loop (e.g., `server.run_stdio()` or a bespoke WebSocket loop) and wire it into `main.py` behind `--serve-stdio` or a new `--serve-ws` flag.
3. Configure the tool registry (`web_search.query`, `web_search.fetch_page`) with appropriate `schema`/`description` blocks so clients can validate parameters.
4. Prepare a tool manifest/descriptor for Codex (JSON/YAML) if necessary and expose it via Docker Compose or CLI configuration.

### Connecting to Codex (configuration example)
1. **Dependencies:** `uv pip install -e .[mcp]`
2. **Manifest:** the `manifest.json` file describes both tools; provide its path in the Codex configuration if required.
3. **Configuration in `~/.codex/config.toml`:**
   ```toml
   [mcp_servers.mcp-web-search]
   command = "uv"
   args = ["run", "python", "main.py", "--serve-stdio"]
   cwd = "*****/mcp-web-search"
   startup_timeout_sec = 30
   manifest_path = "*****/mcp-web-search/manifest.json"
   env = { SEARCH_LANGUAGE = "us-en" }
   ```
4. **Restart Codex:** after saving, restart the client; the `mcp-web-search` server will expose the `web_search.query` and `web_search.fetch_page` tools.

## Security and Compliance
- Allow outbound connections only to trusted domains (configurable allow list).
- Mask sensitive data in logs (e.g., authentication parameters in URLs).
- Retain logs for 30 days; rotate and anonymise agent identifiers when required.
- Collect permissions/licenses for search API usage (store keys in `.env`, never in the repository).
