import argparse
import asyncio
import json
import sys
from typing import List

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


def _serialize_result(result: SearchExecutionResult) -> dict:
    return {
        "query": result.query,
        "engines": result.engines,
        "totalResults": result.total_results,
        "partialFailures": [
            {
                "engine": failure.engine,
                "code": failure.code,
                "message": failure.message,
            }
            for failure in result.partial_failures
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


async def _run_search(query: str, engines: List[str], limit: int) -> None:
    execution = await SEARCH_SERVICE.execute(
        query=query,
        engines=engines,
        limit=limit,
    )
    logger.info("Search completed with %s engines and %s results", len(engines), len(execution.results))
    print(json.dumps(_serialize_result(execution), ensure_ascii=False, indent=2))


async def _run_fetch(fn, url: str) -> None:
    content = await fn(url)
    if isinstance(content, dict):
        logger.info("Fetched content from %s (dict result)", url)
        print(json.dumps(content, ensure_ascii=False, indent=2))
    else:
        if content:
            logger.info("Fetched content from %s (%s chars)", url, len(content))
            print(content)
        else:
            logger.warning("No content returned for %s", url)


def _build_engine_list(raw_engines: str) -> List[str]:
    engines = []
    for raw in raw_engines.split(","):
        normalized = normalize_engine_name(raw)
        if normalized:
            engines.append(normalized)
    return engines


def _resolve_engines(requested: List[str]) -> List[str]:
    base_requested = requested or [config.default_search_engine]
    allowed = [
        normalize_engine_name(engine) for engine in config.allowed_search_engines
        if normalize_engine_name(engine)
    ]
    return resolve_requested_engines(
        base_requested,
        allowed,
        config.default_search_engine,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="webprobe",
        description="Search and fetch web content using open-webSearch Python port.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search multiple engines")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of combined results (1-50)",
    )
    search_parser.add_argument(
        "--engines",
        type=str,
        default="",
        help="Comma-separated list of engines to query",
    )

    fetch_csdn = subparsers.add_parser("fetch-csdn", help="Fetch a CSDN article")
    fetch_csdn.add_argument("url", help="CSDN article URL")

    fetch_linuxdo = subparsers.add_parser("fetch-linuxdo", help="Fetch a linux.do topic")
    fetch_linuxdo.add_argument("url", help="linux.do topic URL")

    fetch_juejin = subparsers.add_parser("fetch-juejin", help="Fetch a Juejin article")
    fetch_juejin.add_argument("url", help="Juejin article URL")

    fetch_github = subparsers.add_parser("fetch-github", help="Fetch a GitHub README")
    fetch_github.add_argument("url", help="GitHub repository URL")

    return parser.parse_args()


async def _run_async():
    args = _parse_args()

    if args.command == "search":
        if not (1 <= args.limit <= 50):
            raise ValueError("limit must be between 1 and 50")
        engines = _resolve_engines(_build_engine_list(args.engines))
        await _run_search(args.query, engines, args.limit)
    elif args.command == "fetch-csdn":
        await _run_fetch(fetch_csdn_article, args.url)
    elif args.command == "fetch-linuxdo":
        await _run_fetch(fetch_linuxdo_article, args.url)
    elif args.command == "fetch-juejin":
        await _run_fetch(fetch_juejin_article, args.url)
    elif args.command == "fetch-github":
        await _run_fetch(fetch_github_readme, args.url)
    else:
        raise ValueError("Unknown command")


def main():
    try:
        asyncio.run(_run_async())
    except Exception as error:
        logger.error("Unhandled exception: %s", error, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
