from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional, Set
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from mcpwebprobe.types import SearchResult
from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_BASE_URL = "https://www.startpage.com"
_SEARCH_URL = f"{_BASE_URL}/sp/search"
_SC_TTL = 30 * 60
_PAGE_SIZE = 10

_cached_sc_code: Optional[str] = None
_cached_sc_time = 0.0

_async_http_client = AsyncHttpClient()


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }


async def _get_homepage() -> str:
    response = await _async_http_client.request(
        "GET",
        _BASE_URL + "/",
        options=BuildHttpRequestOptions(
            headers={**_default_headers(), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=15.0,
            validate_status=lambda status: status < 400,
        ),
    )
    return response.text


def _is_captcha_page(html: str) -> bool:
    normalized = html.lower()
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.lower() if soup.title else ""

    if "/sp/captcha" in normalized:
        return True

    if soup.select_one("form[action*='/sp/captcha'], iframe[src*='captcha'], [id*='captcha'], [class*='captcha']"):
        return True

    keywords = ["verify you are human", "human verification", "security check"]
    return any(keyword in normalized or keyword in title for keyword in keywords)


def _extract_sc_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    input_el = soup.select_one("form[action='/sp/search'] input[name='sc']")
    if input_el and input_el.get("value"):
        return input_el["value"].strip()
    return None


async def _resolve_sc_code() -> str:
    global _cached_sc_code, _cached_sc_time
    now = time.time()
    if _cached_sc_code and now - _cached_sc_time < _SC_TTL:
        return _cached_sc_code

    html = await _get_homepage()
    if _is_captcha_page(html):
        raise RuntimeError("Startpage returned a verification page while fetching search token")

    sc_code = _extract_sc_from_html(html)
    if not sc_code:
        raise RuntimeError("Unable to extract Startpage search code (sc)")

    _cached_sc_code = sc_code
    _cached_sc_time = now
    return sc_code


def _extract_interstitial_payload(html: str) -> Optional[Dict[str, str]]:
    match = re.search(r"var\s+data\s*=\s*(\{[\s\S]*?\});", html)
    if not match:
        return None

    try:
        payload = json.loads(match.group(1))
        return {k: str(v) for k, v in payload.items() if isinstance(v, (str, int, float))}
    except json.JSONDecodeError:
        return None


async def _post_search(form: dict[str, str]) -> str:
    response = await _async_http_client.request(
        "POST",
        _SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers={
                **_default_headers(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": _BASE_URL,
                "Referer": _BASE_URL + "/",
            },
            timeout=20.0,
            validate_status=lambda status: status < 400,
        ),
        data=urlencode(form),
    )
    return response.text


def _parse_results(html: str) -> List[SearchResult]:
    if _is_captcha_page(html):
        raise RuntimeError("Startpage returned a captcha/interstitial page")

    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()
    results: List[SearchResult] = []

    for link in soup.select("a.result-title.result-link[href]"):
        url = link["href"].strip()
        title_el = link.select_one("h2")
        title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
        if not title or not url or url in seen:
            continue

        description_el = link.find_next_sibling("p", class_="description")
        description = description_el.get_text(strip=True) if description_el else ""
        seen.add(url)
        results.append(
            SearchResult(
                title=title,
                url=url,
                description=description,
                source=_BASE_URL,
                engine="startpage",
            )
        )

    return results


async def _search_page(query: str, page: int) -> List[SearchResult]:
    sc_code = await _resolve_sc_code()
    form_data = {
        "query": query,
        "cat": "web",
        "t": "device",
        "sc": sc_code,
        "abp": "1",
        "abd": "1",
        "abe": "1",
    }
    if page > 1:
        form_data["page"] = str(page)
        form_data["segment"] = "startpage.udog"

    html = await _post_search(form_data)
    payload = _extract_interstitial_payload(html)
    if payload:
        follow_up = await _post_search(payload)
        html = follow_up

    return _parse_results(html)


async def search_startpage(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    max_page = max(1, (limit + _PAGE_SIZE - 1) // _PAGE_SIZE)
    results: List[SearchResult] = []

    for page in range(1, max_page + 1):
        page_results = await _search_page(query, page)
        for result in page_results:
            if len(results) >= limit:
                break
            results.append(result)
        if len(results) >= limit or not page_results:
            break

    return results[:limit]
