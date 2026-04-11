from __future__ import annotations

from typing import List

from bs4 import BeautifulSoup
from httpx import Response

from webprobe.types import SearchResult
from webprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


async def _duckduckgo_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    **kwargs,
) -> Response:
    options = BuildHttpRequestOptions(
        headers={**_default_headers(), **(headers or {})},
        timeout=timeout,
        validate_status=lambda status: status < 400,
    )
    return await _async_http_client.request(method, url, options=options, **kwargs)


def _parse_html_results(html: str) -> List[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: List[SearchResult] = []

    for item in soup.select("div.result"):
        classes = item.get("class", [])
        if "result--ad" in classes:
            continue

        title_el = item.select_one("a.result__a")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        url = title_el.get("href") or ""

        snippet_el = item.select_one(".result__snippet")
        source_el = item.select_one(".result__url")

        if not title or not url:
            continue

        results.append(
            SearchResult(
                title=title,
                url=url,
                description=snippet_el.get_text(strip=True) if snippet_el else "",
                source=source_el.get_text(strip=True) if source_el else "",
                engine="duckduckgo",
            )
        )

    return results


async def search_duckduckgo(query: str, limit: int) -> List[SearchResult]:
    """Search using DuckDuckGo HTML endpoint."""
    if limit <= 0:
        return []

    base_url = "https://html.duckduckgo.com/html/"
    results: List[SearchResult] = []
    offset = 0

    while len(results) < limit:
        payload = {"q": query}
        if offset > 0:
            payload.update(
                {
                    "s": str(offset),
                    "dc": str(offset),
                    "v": "l",
                    "o": "json",
                    "api": "d.js",
                }
            )

        response = await _duckduckgo_request(
            "POST",
            base_url,
            data=payload,
        )

        page_results = _parse_html_results(response.text)
        if not page_results:
            break

        for entry in page_results:
            if len(results) >= limit:
                break
            if entry.url and entry.title:
                results.append(entry)

        offset += len(page_results)

        offset += len(page_results)

    return results[:limit]


def search_duckduckgo_sync(query: str, limit: int) -> List[SearchResult]:
    """Synchronous wrapper."""
    import asyncio

    return asyncio.run(search_duckduckgo(query, limit))
