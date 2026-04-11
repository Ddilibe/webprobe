"""Backward-compatible browser cookie helpers."""

from .cookies import (
    fetch_page_html_with_browser,
    fetch_page_html_with_browser_sync,
    get_browser_cookie_header,
    get_browser_cookie_header_sync,
    looks_like_bot_challenge_page,
)

__all__ = [
    "fetch_page_html_with_browser",
    "get_browser_cookie_header",
    "fetch_page_html_with_browser_sync",
    "get_browser_cookie_header_sync",
    "looks_like_bot_challenge_page",
]
