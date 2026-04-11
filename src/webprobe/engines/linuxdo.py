from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from webprobe.config import config
from webprobe.types import SearchResult
from webprobe.engines.bing import search_bing
from webprobe.engines.brave import search_brave
from webprobe.engines.duckduckgo import search_duckduckgo


async def search_linuxdo(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    site_query = f"site:linux.do {query}"
    engine_fn = search_bing
    if config.default_search_engine == "duckduckgo":
        engine_fn = search_duckduckgo
    elif config.default_search_engine == "brave":
        engine_fn = search_brave

    results: List[SearchResult]
    try:
        results = await engine_fn(site_query, limit)
    except Exception:
        results = []

    if not results and config.default_search_engine != "brave":
        results = await search_brave(site_query, limit)

    filtered: List[SearchResult] = []
    for result in results:
        try:
            hostname = urlparse(result.url).hostname or ""
        except ValueError:
            continue

        if hostname.endswith("linux.do") or hostname == "linux.do":
            result.source = "linux.do"
            filtered.append(result)

    return filtered[:limit]
