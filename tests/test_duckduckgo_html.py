from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from search_client import SearchClient


@pytest.mark.asyncio
async def test_duckduckgo_html_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_html = Path("tests/mocks/duckduckgo_weather.html").read_text(encoding="utf-8")

    class StubResponse:
        status_code = 200
        text = sample_html

    class StubClient:
        async def get(self, *_args, **_kwargs):
            return StubResponse()

        async def aclose(self) -> None:  # pragma: no cover - not used in this test
            return None

    client = SearchClient(
        endpoint_url="https://html.duckduckgo.com/html/",
        api_key=None,
        provider="duckduckgo_html",
        use_stub_data=False,
        language="us-en",
    )

    client._client = StubClient()  # type: ignore[attr-defined]

    results = await client.search("Current weather in London", max_results=5)

    assert len(results) == 2
    first = results[0]
    second = results[1]

    assert first.title == "London Weather"
    assert first.url == "https://weather.example.com/london"
    assert "Current weather" in first.snippet

    assert second.title == "London Weather News"
    assert second.url == "https://news.example.com/london-weather"

    await client.close()


@pytest.mark.asyncio
async def test_duckduckgo_html_redirect_normalization() -> None:
    sample_html = Path("tests/mocks/duckduckgo_redirect.html").read_text(encoding="utf-8")

    class StubResponse:
        status_code = 200
        text = sample_html

    class StubClient:
        async def get(self, *_args, **_kwargs):
            return StubResponse()

        async def aclose(self) -> None:  # pragma: no cover - not used in this test
            return None

    client = SearchClient(
        endpoint_url="https://html.duckduckgo.com/html/",
        api_key=None,
        provider="duckduckgo_html",
        use_stub_data=False,
        language="us-en",
    )

    client._client = StubClient()  # type: ignore[attr-defined]

    results = await client.search("Example article", max_results=1)
    assert len(results) == 1
    assert results[0].url == "https://example.com/article"

    await client.close()
