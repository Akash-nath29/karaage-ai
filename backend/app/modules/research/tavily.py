"""Tavily web search (docs/decisions.md Q4). Plain HTTP. Tavily returns each page's extracted text
(`raw_content`), so we never fetch pages ourselves (D10)."""

from dataclasses import dataclass
from functools import cache

import httpx

from app.ai.providers.base import ProviderError, with_retries
from app.config import settings

URL = "https://api.tavily.com/search"
# Video, social and paywalled sites: nothing a lesson can cite as text.
EXCLUDED_DOMAINS = [
    "youtube.com", "facebook.com", "instagram.com", "pinterest.com", "tiktok.com", "x.com", "twitter.com",
    "linkedin.com", "scribd.com", "coursehero.com", "chegg.com", "brainly.in", "brainly.com",
]


@dataclass
class WebResult:
    url: str
    title: str
    snippet: str  # Tavily's query-relevant excerpt
    content: str  # whole-page text ("" when Tavily couldn't extract it)
    score: float  # Tavily relevance, 0–1
    published_date: str | None


def _transient(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code == 429 or e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)


@cache
def _http() -> httpx.Client:
    return httpx.Client(timeout=60)


def search(query: str, max_results: int) -> list[WebResult]:
    if not settings.tavily_api_key:
        raise ProviderError("TAVILY_API_KEY is not set")

    def call() -> dict:  # type: ignore[type-arg]
        res = _http().post(
            URL,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json={
                "query": query[:400],
                "search_depth": "basic",  # 1 credit
                "max_results": max_results,
                "include_raw_content": "text",
                "exclude_domains": EXCLUDED_DOMAINS,
            },
        )
        res.raise_for_status()
        return res.json()

    return [
        WebResult(
            url=r.get("url", ""),
            title=(r.get("title") or "")[:500],
            snippet=r.get("content") or "",
            content=r.get("raw_content") or "",
            score=float(r.get("score") or 0),
            published_date=r.get("published_date"),
        )
        for r in with_retries(call, _transient).get("results", [])
    ]
