from __future__ import annotations

from datetime import datetime
from typing import List
from urllib.parse import urlparse

from mcpwebprobe.types import SearchResult
from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_EXA_SEARCH_URL = "https://exa.ai/search/api/search-fast"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


async def search_exa(query: str, limit: int) -> List[SearchResult]:
    """Search the Exa.ai API."""
    if limit <= 0:
        return []

    payload = {
        "numResults": limit,
        "query": query,
        "type": "auto",
        "useAutoprompt": True,
        "domainFilterType": "include",
        "text": True,
        "density": "compact",
        "resolvedSearchType": "neural",
        "moderation": True,
        "fastMode": False,
        "rerankerType": "default",
    }

    response = await _async_http_client.request(
        "POST",
        _EXA_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            response_type="json",
            validate_status=lambda status: status < 400,
        ),
        json=payload,
    )

    data = response.json()
    entries = data.get("results") or []

    results: List[SearchResult] = []
    for item in entries[:limit]:
        if not item:
            continue

        title = item.get("title") or "Untitled result"
        url = item.get("url") or ""
        description_parts: list[str] = []
        author = item.get("author")
        if author:
            description_parts.append(f"Author: {author}")
        published_date = item.get("publishedDate")
        if published_date:
            try:
                dt = datetime.fromisoformat(published_date)
                description_parts.append(f"Published: {dt.date().isoformat()}")
            except ValueError:
                pass

        description = description_parts and " • ".join(description_parts) or ""

        host = ""
        if url:
            try:
                host = urlparse(url).hostname or ""
            except ValueError:
                host = ""

        results.append(
            SearchResult(
                title=title,
                url=url,
                description=description,
                source=host or "",
                engine="exa",
            )
        )

    return results[:limit]
