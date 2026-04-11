from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from mcpwebprobe.types import SearchResult
from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_BAIDU_SEARCH_URL = "https://www.baidu.com/s"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    }


async def _request(params: dict[str, str]) -> str:
    response = await _async_http_client.request(
        "GET",
        _BAIDU_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            validate_status=lambda status: status < 400,
        ),
        params=params,
    )
    return response.text


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _parse_results(html: str) -> List[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: List[SearchResult] = []

    for container in soup.select("div.result.c-container, div.result-op"):
        title_el = container.select_one("h3, .c-title")
        link_el = title_el.select_one("a") if title_el else container.select_one("a")
        if not link_el:
            continue

        href = link_el.get("href") or ""
        if not href.startswith("http"):
            continue

        title = _normalize_text(title_el.get_text() if title_el else link_el.get_text())
        snippet_el = container.select_one(".c-abstract, .c-span18")
        source_el = container.select_one(".c-showurl, .f13, cite")

        description = _normalize_text(snippet_el.get_text()) if snippet_el else ""
        source = _normalize_text(source_el.get_text()) if source_el else ""

        results.append(
            SearchResult(
                title=title,
                url=href,
                description=description,
                source=source or (urlparse(href).hostname or ""),
                engine="baidu",
            )
        )

    return results


async def search_baidu(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    results: List[SearchResult] = []
    pn = 0

    while len(results) < limit:
        params = {
            "wd": query,
            "pn": str(pn),
            "ie": "utf-8",
            "tn": "98012088_4_pg",
        }

        html = await _request(params)
        page_results = _parse_results(html)

        if not page_results:
            break

        for result in page_results:
            if len(results) >= limit:
                break
            results.append(result)

        pn += 10

    return results[:limit]
