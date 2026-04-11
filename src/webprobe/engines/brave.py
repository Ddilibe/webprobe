from __future__ import annotations

from typing import List

from bs4 import BeautifulSoup

from webprobe.types import SearchResult
from webprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_BRAVE_SEARCH_URL = "https://search.brave.com/search"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


async def _request(params: dict[str, str]) -> str:
    response = await _async_http_client.request(
        "GET",
        _BRAVE_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            validate_status=lambda status: status < 400,
        ),
        params=params,
    )
    return response.text


def _parse_results(html: str) -> List[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: List[SearchResult] = []

    for item in soup.select("#results .snippet, .snippet"):
        content = item.select_one(".result-content")
        if content is None:
            continue

        link = content.find("a", recursive=False)
        if link is None:
            link = content.select_one("a")
        if link is None:
            continue

        title_el = link.select_one(".search-snippet-title")
        title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
        description_el = content.select_one(".generic-snippet")
        description = description_el.get_text(strip=True) if description_el else ""
        source_el = link.select_one(".site-name-wrapper")
        source = source_el.get_text(strip=True) if source_el else ""
        url = link.get("href") or ""

        if not url or not title:
            continue

        results.append(
            SearchResult(
                title=title,
                url=url,
                description=description,
                source=source,
                engine="brave",
            )
        )

    return results


async def search_brave(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    results: List[SearchResult] = []
    offset = 0
    per_page = 10

    while len(results) < limit:
        params = {
            "q": query,
            "source": "web",
            "offset": str(offset),
        }

        html = await _request(params)
        page_results = _parse_results(html)

        if not page_results:
            break

        for entry in page_results:
            if len(results) >= limit:
                break
            results.append(entry)

        offset += per_page

    return results[:limit]
