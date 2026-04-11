from __future__ import annotations

from typing import List

from mcpwebprobe.types import SearchResult
from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_CSDN_SEARCH_URL = "https://so.csdn.net/api/v3/search"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Accept": "*/*",
        "Host": "so.csdn.net",
        "Connection": "keep-alive",
    }


async def _request(params: dict[str, str | int]) -> dict:
    response = await _async_http_client.request(
        "GET",
        _CSDN_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            response_type="json",
            validate_status=lambda status: status < 400,
        ),
        params=params,
    )
    return response.json()


async def search_csdn(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    results: List[SearchResult] = []
    page = 1

    while len(results) < limit:
        data = await _request({"q": query, "p": page})
        items = data.get("result_vos") or []
        if not isinstance(items, list) or not items:
            break

        for item in items:
            if len(results) >= limit:
                break

            title = item.get("title") or ""
            description = item.get("digest") or ""
            url = item.get("url_location") or ""
            source = item.get("nickname") or ""

            if not title or not url:
                continue

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=description,
                    source=source,
                    engine="csdn",
                )
            )

        page += 1

    return results[:limit]
