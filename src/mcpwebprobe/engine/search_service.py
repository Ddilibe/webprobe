"""Search execution helpers for multi-engine queries."""

import asyncio
import re
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Dict,
    List,
    MutableMapping,
    Sequence,
)

from mcpwebprobe.types import SearchResult

SearchEngineExecutor = Callable[[str, int], Awaitable[List[SearchResult]]]
SearchEngineExecutorMap = Dict[str, SearchEngineExecutor]

SUPPORTED_SEARCH_ENGINES = [
    "baidu",
    "bing",
    "linuxdo",
    "csdn",
    "duckduckgo",
    "exa",
    "brave",
    "juejin",
    "startpage",
]

SEARCH_ENGINE_SYNONYMS = {
    "bd": "baidu",
    "ddg": "duckduckgo",
    "sp": "startpage",
}


def normalize_engine_name(engine: str) -> str:
    """Normalize engine identifiers to canonical names."""
    cleaned = engine.strip().lower()
    compact = re.sub(r"[\s._-]+", "", cleaned)

    if compact in SEARCH_ENGINE_SYNONYMS:
        return SEARCH_ENGINE_SYNONYMS[compact]

    if compact in SUPPORTED_SEARCH_ENGINES:
        return compact

    return cleaned


def distribute_limit(total_limit: int, engine_count: int) -> List[int]:
    """Evenly distribute the requested limit across the chosen engines."""
    if engine_count <= 0:
        return []

    base = total_limit // engine_count
    remainder = total_limit % engine_count

    return [base + (1 if i < remainder else 0) for i in range(engine_count)]


def resolve_requested_engines(
    requested: Sequence[str], allowed: Sequence[str], default_engine: str
) -> List[str]:
    """Filter requested engines against the allowed list, falling back to defaults."""
    if not requested:
        return [default_engine]

    if not allowed:
        return list(requested)

    filtered = [engine for engine in requested if engine in allowed]
    return filtered if filtered else [default_engine]


@dataclass
class SearchExecutionFailure:
    engine: str
    code: str
    message: str


@dataclass
class SearchExecutionResult:
    query: str
    engines: List[str]
    total_results: int
    results: List[SearchResult]
    partial_failures: List[SearchExecutionFailure]


class SearchService:
    """Executor for multi-engine search requests."""

    def __init__(self, engine_map: SearchEngineExecutorMap):
        self.engine_map: MutableMapping[str, SearchEngineExecutor] = engine_map

    async def execute(
        self,
        *,
        query: str,
        engines: List[str],
        limit: int,
    ) -> SearchExecutionResult:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Search query must not be empty")

        if limit <= 0:
            raise ValueError("Limit must be greater than zero")

        if not engines:
            raise ValueError("At least one search engine is required")

        limits = distribute_limit(limit, len(engines))
        partial_failures: List[SearchExecutionFailure] = []
        tasks: List[Awaitable[List[SearchResult]]] = []

        for engine, engine_limit in zip(engines, limits):
            executor = self.engine_map.get(engine)
            if executor is None:
                partial_failures.append(
                    SearchExecutionFailure(
                        engine=engine,
                        code="unsupported_engine",
                        message=f"Unsupported search engine: {engine}",
                    )
                )
                continue

            async def _run(executor=executor, engine=engine, engine_limit=engine_limit):
                try:
                    return await executor(clean_query, engine_limit)
                except Exception as error:  # noqa: BLE001
                    partial_failures.append(
                        SearchExecutionFailure(
                            engine=engine,
                            code="engine_error",
                            message=str(error),
                        )
                    )
                    return []

            tasks.append(_run())

        gathered_results: List[SearchResult] = []
        if tasks:
            for chunk in await asyncio.gather(*tasks):
                gathered_results.extend(chunk)

        trimmed_results = gathered_results[:limit]
        return SearchExecutionResult(
            query=clean_query,
            engines=engines,
            total_results=len(trimmed_results),
            results=trimmed_results,
            partial_failures=partial_failures,
        )
