from __future__ import annotations

from typing import List

from mcpwebprobe.types import SearchResult
from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_JUEJIN_SEARCH_URL = "https://api.juejin.cn/search_api/v1/search"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Host": "api.juejin.cn",
        "Connection": "keep-alive",
        "content-type": "application/json",
        "pragma": "no-cache",
    }


async def _request(params: dict[str, str | int]) -> dict:
    response = await _async_http_client.request(
        "GET",
        _JUEJIN_SEARCH_URL,
        options=BuildHttpRequestOptions(
            headers=_default_headers(),
            timeout=30.0,
            response_type="json",
            validate_status=lambda status: status < 400,
        ),
        params=params,
    )
    return response.json()


async def search_juejin(query: str, limit: int) -> List[SearchResult]:
    if limit <= 0:
        return []

    results: List[SearchResult] = []
    cursor = "0"

    while len(results) < limit:
        params = {
            "aid": "2608",
            "uuid": "7259393293459605051",
            "spider": "0",
            "query": query,
            "id_type": "0",
            "cursor": cursor,
            "limit": min(20, limit - len(results)),
            "search_type": "0",
            "sort_type": "0",
            "version": "1",
        }

        data = await _request(params)
        err_no = data.get("err_no") or 0
        if err_no != 0:
            break

        items = data.get("data") or []
        if not items:
            break

        for entry in items:
            if len(results) >= limit:
                break

            result_model = entry.get("result_model", {})
            article_info = result_model.get("article_info", {})
            author = result_model.get("author_user_info", {})
            category = result_model.get("category", {})
            tags = result_model.get("tags", [])

            title = (entry.get("title_highlight") or article_info.get("title") or "").replace("<em>", "").replace(
                "</em>", ""
            )

            description_parts = []
            content_highlight = (entry.get("content_highlight") or "").replace("<em>", "").replace("</em>", "")
            if content_highlight:
                description_parts.append(content_highlight)
            if category.get("category_name"):
                description_parts.append(f"分类: {category['category_name']}")
            if tags:
                tag_names = ", ".join(tag.get("tag_name", "") for tag in tags if tag.get("tag_name"))
                if tag_names:
                    description_parts.append(f"标签: {tag_names}")
            view_count = article_info.get("view_count")
            if view_count is not None:
                description_parts.append(f"阅读: {view_count}")
            digg_count = article_info.get("digg_count")
            if digg_count is not None:
                description_parts.append(f"👍 {digg_count}")

            results.append(
                SearchResult(
                    title=title or article_info.get("title", "Juejin result"),
                    url=f"https://juejin.cn/post/{result_model.get('article_id')}",
                    description=" | ".join(description_parts),
                    source=author.get("user_name", ""),
                    engine="juejin",
                )
            )

        cursor = data.get("cursor") or ""
        if not data.get("has_more") or not cursor:
            break

    return results[:limit]
