import asyncio
import json
from typing import Iterable, List, Optional, Sequence

from webprobe.config import config
from webprobe.engine.registry import SEARCH_SERVICE
from webprobe.engine.search_service import (
    normalize_engine_name,
    resolve_requested_engines,
    SearchExecutionResult,
)
from webprobe.engines.fetch_csdn import fetch_csdn_article
from webprobe.engines.fetch_juejin import fetch_juejin_article
from webprobe.engines.fetch_linuxdo import fetch_linuxdo_article
from webprobe.engines.github import fetch_github_readme
from webprobe.logging import get_logger

logger = get_logger(__name__)


def _normalize_requested_engines(engines: Optional[Sequence[str]]) -> List[str]:
    requested = []
    if not engines:
        return requested
    for engine in engines:
        normalized = normalize_engine_name(engine)
        if normalized:
            requested.append(normalized)
    return requested


def _serialize_search(result: SearchExecutionResult) -> dict:
    return {
        "query": result.query,
        "engines": result.engines,
        "totalResults": result.total_results,
        "partialFailures": [
            {
                "engine": f.engine,
                "code": f.code,
                "message": f.message,
            }
            for f in result.partial_failures
        ],
        "results": [
            {
                "title": entry.title,
                "url": entry.url,
                "description": entry.description,
                "source": entry.source,
                "engine": entry.engine,
            }
            for entry in result.results
        ],
    }


def search(
    query: str,
    limit: int = 10,
    engines: Optional[Iterable[str]] = None,
) -> dict:
    """
    Run a search across the configured engines.
    """
    if not query or not query.strip():
        raise ValueError("query is required")

    if not (1 <= limit <= 50):
        raise ValueError("limit must be between 1 and 50")

    requested = list(_normalize_requested_engines(engines))
    resolved = resolve_requested_engines(
        requested or [config.default_search_engine],
        [normalize_engine_name(engine) for engine in config.allowed_search_engines],
        config.default_search_engine,
    )
    result = asyncio.run(
        SEARCH_SERVICE.execute(
            query=query,
            engines=resolved,
            limit=limit,
        )
    )
    logger.debug(
        "Ran search for query=%s limit=%s engines=%s", query, limit, resolved
    )

    return _serialize_search(result)


def fetch_csdn(url: str) -> dict:
    logger.debug("Fetching CSDN article %s", url)
    return asyncio.run(fetch_csdn_article(url))


def fetch_linuxdo(url: str) -> dict:
    logger.debug("Fetching linux.do topic %s", url)
    return asyncio.run(fetch_linuxdo_article(url))


def fetch_juejin(url: str) -> dict:
    logger.debug("Fetching Juejin article %s", url)
    return asyncio.run(fetch_juejin_article(url))


def fetch_github(url: str) -> Optional[str]:
    logger.debug("Fetching GitHub README %s", url)
    return asyncio.run(fetch_github_readme(url))
