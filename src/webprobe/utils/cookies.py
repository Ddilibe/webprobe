# playwright_browser.py
import asyncio
import time
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urlparse, urlunparse

from webprobe.config import config, get_proxy_url
from webprobe.utils.playwright import load_playwright_client, open_playwright_browser

COOKIE_CACHE_TTL_MS = 10 * 60 * 1000  # 10 minutes
COOKIE_WARMUP_DELAY_MS = 1200  # 1.2 seconds
COOKIE_CONTEXT_OPTIONS = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "locale": "zh-CN",
    "viewport": {"width": 1440, "height": 960},
}

BOT_KEYWORDS = [
    "captcha",
    "verification",
    "verify you are human",
    "access denied",
    "blocked",
    "rate limit",
    "too many requests",
    "please enable javascript",
    "please verify",
    "请验证",
    "验证码",
    "人机验证",
    "安全验证",
]

# Cookie cache
_cookie_cache: Dict[str, Dict[str, Any]] = {}


class CookieCacheEntry:
    """Cookie cache entry"""

    def __init__(self, cookie_header: str, expires_at: float):
        self.cookie_header = cookie_header
        self.expires_at = expires_at


def build_cookie_cache_key(url: str) -> str:
    """Build cache key for cookie storage"""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    proxy_url = get_proxy_url() or "-"
    playwright_package = config.playwright_package
    playwright_module_path = config.playwright_module_path or "-"
    playwright_executable_path = config.playwright_executable_path or "-"
    playwright_ws_endpoint = config.playwright_ws_endpoint or "-"
    playwright_cdp_endpoint = config.playwright_cdp_endpoint or "-"

    return f"{origin}|{proxy_url}|{playwright_package}|{playwright_module_path}|{playwright_executable_path}|{playwright_ws_endpoint}|{playwright_cdp_endpoint}"


def serialize_cookie_header(cookies: List[Dict[str, Any]]) -> str:
    """Serialize cookies into a header string"""
    cookie_parts = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            cookie_parts.append(f"{name}={value}")
    return "; ".join(cookie_parts)


def looks_like_bot_challenge_page(html: str) -> bool:
    """Check if HTML page looks like a bot challenge page"""
    normalized = html.lower()
    return any(keyword in normalized for keyword in BOT_KEYWORDS)


async def create_cookie_collection_page(browser: Any):
    """Create a page for cookie collection from browser"""
    # Try creating a new context first
    if hasattr(browser, "new_context"):
        context = await browser.new_context(**COOKIE_CONTEXT_OPTIONS)
        page = await context.new_page()
        return {"page": page, "close": lambda: context.close()}

    # Try using existing contexts
    if hasattr(browser, "contexts"):
        contexts = browser.contexts
        if contexts and len(contexts) > 0 and hasattr(contexts[0], "new_page"):
            page = await contexts[0].new_page()
            return {"page": page, "close": lambda: page.close()}

    # Fall back to creating a page directly
    if hasattr(browser, "new_page"):
        page = await browser.new_page()
        return {"page": page, "close": lambda: page.close()}

    raise RuntimeError(
        "Connected Playwright browser does not support creating a page for cookie collection"
    )


async def read_cookies_from_page(page: Any, url: str) -> str:
    """Read cookies from page and return as header string"""
    if hasattr(page, "context"):
        context = page.context
        if context and hasattr(context, "cookies"):
            cookies = await context.cookies([url])
            return serialize_cookie_header(cookies)

    return ""


async def get_browser_cookie_header(
    url_input: str, force_refresh: bool = False
) -> Optional[str]:
    """
    Get cookie header for a URL using Playwright browser

    Args:
        url_input: Target URL
        force_refresh: Force refresh the cookie cache

    Returns:
        Cookie header string or None if not available
    """
    # Parse URL to get origin for cache key
    parsed = urlparse(url_input)
    url = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
    if parsed.query:
        url += f"?{parsed.query}"

    cache_key = build_cookie_cache_key(url_input)
    cached = _cookie_cache.get(cache_key)

    # Check cache
    if not force_refresh and cached:
        if (
            cached["expires_at"] > time.time() * 1000
        ):  # Convert to milliseconds for comparison
            return cached["cookie_header"]

    # Load Playwright client
    playwright = await load_playwright_client(silent=True)
    if not playwright:
        return None

    # Open browser session
    session = await open_playwright_browser(headless=True)

    try:
        # Create page for cookie collection
        page_info = await create_cookie_collection_page(session.browser)
        page = page_info["page"]

        try:
            # Navigate to URL
            timeout = max(config.playwright_navigation_timeout_ms, 15000)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except Exception:
                pass  # Ignore navigation errors

            # Wait for warmup delay
            if hasattr(page, "wait_for_timeout"):
                await page.wait_for_timeout(COOKIE_WARMUP_DELAY_MS)

            # Read cookies
            cookie_header = await read_cookies_from_page(page, url)
            if not cookie_header:
                return None

            # Cache the result
            _cookie_cache[cache_key] = {
                "cookie_header": cookie_header,
                "expires_at": time.time() * 1000 + COOKIE_CACHE_TTL_MS,
            }

            return cookie_header

        finally:
            # Close the page/context
            await page_info["close"]()

    finally:
        # Close the browser session
        await session.close()


async def fetch_page_html_with_browser(url_input: str) -> Dict[str, str]:
    """
    Fetch page HTML using Playwright browser

    Args:
        url_input: Target URL

    Returns:
        Dictionary with html, final_url, and title
    """
    # Load Playwright client
    playwright = await load_playwright_client(silent=True)
    if not playwright:
        raise RuntimeError("Playwright client is not available for browser HTML fetch")

    # Open browser session
    session = await open_playwright_browser(headless=True)

    try:
        # Create page for content fetching
        page_info = await create_cookie_collection_page(session.browser)
        page = page_info["page"]

        try:
            # Navigate to URL
            timeout = max(config.playwright_navigation_timeout_ms, 15000)
            await page.goto(url_input, wait_until="domcontentloaded", timeout=timeout)

            # Wait for network idle if available
            if hasattr(page, "wait_for_load_state"):
                try:
                    idle_timeout = min(
                        max(config.playwright_navigation_timeout_ms, 5000), 15000
                    )
                    await page.wait_for_load_state("networkidle", timeout=idle_timeout)
                except Exception:
                    pass  # Ignore timeout errors

            # Wait for warmup delay
            if hasattr(page, "wait_for_timeout"):
                await page.wait_for_timeout(COOKIE_WARMUP_DELAY_MS)

            # Extract content
            html = ""
            if hasattr(page, "content"):
                html = await page.content()

            final_url = url_input
            if hasattr(page, "url"):
                final_url = page.url

            title = ""
            if hasattr(page, "title"):
                try:
                    title = await page.title()
                except Exception:
                    title = ""

            return {
                "html": str(html or ""),
                "final_url": str(final_url or url_input),
                "title": str(title or ""),
            }

        finally:
            # Close the page/context
            await page_info["close"]()

    finally:
        # Close the browser session
        await session.close()


# Synchronous wrappers for convenience
def get_browser_cookie_header_sync(
    url_input: str, force_refresh: bool = False
) -> Optional[str]:
    """Synchronous wrapper for get_browser_cookie_header"""
    return asyncio.run(get_browser_cookie_header(url_input, force_refresh))


def fetch_page_html_with_browser_sync(url_input: str) -> Dict[str, str]:
    """Synchronous wrapper for fetch_page_html_with_browser"""
    return asyncio.run(fetch_page_html_with_browser(url_input))
