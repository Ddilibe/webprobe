from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_JUEJIN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Connection": "keep-alive",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
    "application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_SELECTORS: List[str] = [
    ".markdown-body",
    ".article-content",
    ".content",
    "[data-v-md-editor-preview]",
    ".bytemd-preview",
    ".article-area .content",
    ".main-area .article-area",
    ".article-wrapper .content",
]


async def fetch_juejin_article(url: str) -> Dict[str, str]:
    response = await _async_http_client.request(
        "GET",
        url,
        options=BuildHttpRequestOptions(
            headers=_JUEJIN_HEADERS,
            timeout=30.0,
            validate_status=lambda status: status < 400,
        ),
    )

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    content = ""
    for selector in _SELECTORS:
        element = soup.select_one(selector)
        if not element:
            continue

        element = BeautifulSoup(str(element), "html.parser")
        for bad in element.select("script, style, .code-block-extension, .hljs-ln-numbers"):
            bad.decompose()

        candidate = element.get_text(separator="\n").strip()
        if len(candidate) > 100:
            content = candidate
            break

    if not content or len(content) < 100:
        for bad in soup.select("script, style, nav, header, footer, .sidebar, .comment"):
            bad.decompose()
        content = soup.get_text(separator="\n").strip()

    if not content:
        raise RuntimeError("Failed to extract content from Juejin article")

    return {"content": content}
