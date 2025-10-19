from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from urllib.parse import urlparse

from search_client import SearchResult


@dataclass
class Summary:
    """Structured summary returned to MCP agents."""

    overview: str
    highlights: List[str]


class Summarizer:
    """Combines search snippets into a lightweight summary."""

    def build_summary(self, results: Iterable[SearchResult]) -> Summary:
        scored_snippets: List[Tuple[float, str]] = []
        seen = set()
        for result in results:
            snippet = (result.snippet or "").strip()
            if not snippet:
                continue
            normalized = snippet.lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            score = self._score_snippet(snippet, result.url)
            scored_snippets.append((score, snippet))

        if not scored_snippets:
            return Summary(overview="No concise results matched this query.", highlights=[])

        scored_snippets.sort(key=lambda item: item[0], reverse=True)

        overview = scored_snippets[0][1]
        highlights = [snippet for _score, snippet in scored_snippets[1:4]]
        return Summary(overview=overview, highlights=highlights)

    def _score_snippet(self, snippet: str, url: str) -> float:
        score = len(snippet)
        domain = urlparse(url).netloc.lower()
        boosts = {
            "weather.com": 150.0,
            "bbc.com": 120.0,
            "accuweather.com": 100.0,
            "reuters.com": 90.0,
            "guardian": 80.0,
        }
        for keyword, bonus in boosts.items():
            if keyword in domain:
                score += bonus
                break
        if "forecast" in snippet.lower():
            score += 40.0
        if "current" in snippet.lower():
            score += 20.0
        return score
