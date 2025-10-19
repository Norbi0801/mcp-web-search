from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup


@dataclass
class FetchedPage:
    """Representation of a fetched web page."""

    url: str
    status_code: int
    content: bytes
    content_type: Optional[str]
    text: Optional[str] = None
    html: Optional[str] = None


class Crawler:
    """Minimal asynchronous HTTP client for following search results."""

    def __init__(self, timeout_seconds: int = 10) -> None:
        self._client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)

    async def fetch(self, url: str) -> FetchedPage:
        response = await self._client.get(url)
        content_type = response.headers.get("content-type")
        text: Optional[str] = None
        html: Optional[str] = None
        try:
            if content_type and "text" in content_type:
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(" ", strip=True)
        except Exception:
            html = response.text
            text = html[:10000]

        return FetchedPage(
            url=str(response.url),
            status_code=response.status_code,
            content=response.content,
            content_type=content_type,
            text=text,
            html=html,
        )

    async def close(self) -> None:
        await self._client.aclose()
