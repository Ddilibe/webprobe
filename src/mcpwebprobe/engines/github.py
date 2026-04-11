from __future__ import annotations

import re
from typing import List, Optional

from mcpwebprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()
_README_CANDIDATES: List[str] = [
    "README.md",
    "README.mdx",
    "README.markdown",
    "README",
    "README.txt",
    "readme.md",
    "readme.mdx",
    "readme.markdown",
    "readme",
    "readme.txt",
]


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "GitHub-README-Fetcher/1.0",
        "Accept": "text/plain,text/markdown,*/*",
        "Connection": "keep-alive",
    }


def _extract_owner_repo(url: str) -> Optional[tuple[str, str]]:
    trimmed = url.strip()
    patterns = [
        re.compile(r"(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+)", re.IGNORECASE),
        re.compile(r"git@github\.com:([^/\s]+)/([^/\s]+)\.git", re.IGNORECASE),
    ]

    for pattern in patterns:
        match = pattern.search(trimmed)
        if match:
            owner = match.group(1).strip()
            repo = match.group(2).strip()
            repo = re.sub(r"(?:[?#].*$|\.git$|/.*$)", "", repo)
            if owner and repo:
                return owner, repo
    return None


async def _fetch_readme(owner: str, repo: str) -> Optional[str]:
    for candidate in _README_CANDIDATES:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{candidate}"
        response = await _async_http_client.request(
            "GET",
            raw_url,
            options=BuildHttpRequestOptions(
                headers=_default_headers(),
                timeout=10.0,
                validate_status=lambda status: status in {200, 404},
            ),
        )
        if response.status_code == 404:
            continue

        text = response.text
        if text and text.strip():
            return text

    return None


async def fetch_github_readme(url: str) -> Optional[str]:
    repo_info = _extract_owner_repo(url)
    if not repo_info:
        raise ValueError(f"Unable to parse GitHub repository from URL: {url}")

    owner, repo = repo_info
    return await _fetch_readme(owner, repo)
