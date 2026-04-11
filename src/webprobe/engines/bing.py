from __future__ import annotations

from typing import List, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from webprobe.types import SearchResult
from webprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_BING_SEARCH_URL = "https://www.bing.com/search"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


async def _request(params: dict[str, str]) -> str:
    response = await _async_http_client.request(
        "GET",
        _BING_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            validate_status=lambda status: status < 400,
        ),
        params=params,
    )
    return response.text


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _clean_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""

    candidate = raw_url.strip()
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/"):
        if candidate.startswith("/search") or candidate.startswith("/ck/a") or candidate.startswith("/newtabredir"):
            return ""
        candidate = f"https://cn.bing.com{candidate}"

    if not candidate.startswith("http://") and not candidate.startswith("https://"):
        return ""

    try:
        parsed = urlparse(candidate)
        hostname = parsed.hostname or ""
        path = (parsed.path or "").lower()
        if hostname.endswith("bing.com") and (
            path.startswith("/search") or path.startswith("/ck/a") or path.startswith("/newtabredir")
        ):
            return ""

        filtered_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in {"utm_source", "utm_medium", "utm_campaign", "ref", "source"}
        ]
        cleaned_query = urlencode(filtered_query)

        sanitized = parsed._replace(query=cleaned_query)
        return urlunparse(sanitized)
    except ValueError:
        return ""


def _extract_title(element: BeautifulSoup, fallback_url: str, index: int) -> str:
    title_element = element.select_one("h2 a, .b_title a, .b_tpcn a, a")
    if title_element:
        title_text = _normalize_whitespace(title_element.get_text())
        if title_text:
            return title_text[:200]

    if fallback_url:
        try:
            host = urlparse(fallback_url).hostname or ""
            if host:
                return f"Result from {host}"
        except ValueError:
            pass

    return f"Result {index+1}"


def _extract_description(element: BeautifulSoup, title: str) -> str:
    snippet = element.select_one(".b_caption p, .b_snippet, .b_lineclamp2, .b_lineclamp3")
    if snippet:
        return _normalize_whitespace(snippet.get_text())[:400]

    fallback = _normalize_whitespace(element.get_text().replace(title, ""))[:400]
    return fallback


def _extract_source(element: BeautifulSoup, url: str) -> str:
    source_el = element.select_one(".b_tpcn, .b_attribution cite, cite")
    if source_el:
        value = _normalize_whitespace(source_el.get_text())
        if value:
            return value[:200]

    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _collect_results(soup: BeautifulSoup, limit: int) -> List[SearchResult]:
    selectors = [
        "#b_results > li.b_algo",
        "#b_results > li.b_ans",
        ".b_algo",
        ".b_ans",
    ]

    seen: Set[str] = set()
    results: List[SearchResult] = []

    for selector in selectors:
        for index, node in enumerate(soup.select(selector)):
            if len(results) >= limit:
                break

            container = node
            link = container.select_one("h2 a, .b_title a, .b_tpcn a, a")
            if not link:
                continue

            raw_url = link.get("href")
            cleaned = _clean_url(raw_url)
            if not cleaned or cleaned in seen:
                continue

            title = _extract_title(container, cleaned, index)
            description = _extract_description(container, title)
            seen.add(cleaned)
            results.append(
                SearchResult(
                    title=title,
                    url=cleaned,
                    description=description,
                    source=_extract_source(container, cleaned),
                    engine="bing",
                )
            )
        if len(results) >= limit:
            break

    return results


async def search_bing(query: str, limit: int) -> List[SearchResult]:
    """Perform a Bing search and parse the first `limit` results."""
    if limit <= 0:
        return []

    results: List[SearchResult] = []
    offset = 0
    per_page = 10

    while len(results) < limit:
        params = {
            "q": query,
            "first": str(1 + offset),
            "count": str(per_page),
            "setlang": "zh-CN",
        }
        html = await _request(params)
        soup = BeautifulSoup(html, "html.parser")
        page_results = _collect_results(soup, limit - len(results))

        if not page_results:
            break

        results.extend(page_results)
        offset += per_page

    return results[:limit]
