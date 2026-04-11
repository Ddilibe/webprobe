# csdn_fetcher.py
import asyncio
import re
from typing import Optional, Dict, Any, Tuple

import httpx
from bs4 import BeautifulSoup

from webprobe.logging import get_logger

from webprobe.utils.browser_cookies import (
    fetch_page_html_with_browser,
    get_browser_cookie_header,
    looks_like_bot_challenge_page,
)
from webprobe.utils.http_client import (
    BuildHttpRequestOptions,
    build_http_request_options,
    get_default_http_client,
)

logger = get_logger(__name__)


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted text by cleaning whitespace and special characters"""
    text = text.replace('\r\n', '\n')
    text = text.replace('\u00a0', ' ')  # Replace non-breaking spaces
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def build_request_options(cookie_header: Optional[str] = None) -> Dict[str, Any]:
    """Build HTTP request options for CSDN"""
    headers = {
        'Accept': '*/*',
        'Host': 'blog.csdn.net',
        'Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
    }
    
    if cookie_header:
        headers['Cookie'] = cookie_header
    
    return build_http_request_options(
        BuildHttpRequestOptions(headers=headers)
    )


def extract_article_content(html: str) -> str:
    """Extract article content from CSDN HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the article content div
    article = soup.find('div', id='content_views')
    if not article:
        article = soup.find('article', class_='blog-content-box')
    
    if not article:
        return ''
    
    # Remove unwanted elements
    for unwanted in article.find_all(['script', 'style', 'noscript']):
        unwanted.decompose()
    
    # Extract text and normalize
    text = article.get_text()
    return normalize_extracted_text(text)


def should_retry_with_browser(html: str, content: str) -> bool:
    """Determine if we should retry with browser-based fetching"""
    return not content or (looks_like_bot_challenge_page(html) and len(content) < 200)


async def fetch_csdn_article(url: str) -> Dict[str, str]:
    """
    Fetch CSDN article content with fallback strategies
    
    Args:
        url: CSDN article URL
    
    Returns:
        Dictionary with article content
    
    Raises:
        RuntimeError: If unable to extract article content
    """
    response = None
    html = ''
    content = ''
    
    http_client = get_default_http_client()
    
    try:
        # Try normal request first
        request_options = build_request_options()
        response = await http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
        html = response.text
        content = extract_article_content(html)
        
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        # Only handle authentication/rate limit errors
        if status not in [401, 403, 429]:
            raise
        
        # Try with cookies from browser
        cookie_header = await get_browser_cookie_header(url)
        if cookie_header:
            try:
                request_options = build_request_options(cookie_header)
                response = await http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
                html = response.text
                content = extract_article_content(html)
            except Exception:
                # Fall back to browser rendering
                browser_page = await fetch_page_html_with_browser(url)
                html = browser_page['html']
                content = extract_article_content(html)
        else:
            # Use browser rendering directly
            browser_page = await fetch_page_html_with_browser(url)
            html = browser_page['html']
            content = extract_article_content(html)
    
    except Exception:
        # For other errors, try browser rendering
        browser_page = await fetch_page_html_with_browser(url)
        html = browser_page['html']
        content = extract_article_content(html)
    
    # First retry check
    if should_retry_with_browser(html, content):
        cookie_header = await get_browser_cookie_header(url)
        if cookie_header:
            try:
                request_options = build_request_options(cookie_header)
                response = await http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
                html = response.text
                content = extract_article_content(html)
            except Exception:
                browser_page = await fetch_page_html_with_browser(url)
                html = browser_page['html']
                content = extract_article_content(html)
        
        # Second retry check
        if should_retry_with_browser(html, content):
            browser_page = await fetch_page_html_with_browser(url)
            html = browser_page['html']
            content = extract_article_content(html)
    
    if not content:
        raise RuntimeError('Failed to extract readable CSDN article content')
    
    return {'content': content}


# Synchronous wrapper for convenience
def fetch_csdn_article_sync(url: str) -> Dict[str, str]:
    """Synchronous wrapper for fetch_csdn_article"""
    return asyncio.run(fetch_csdn_article(url))


# Context manager version for better resource management
class CSDNArticleFetcher:
    """CSDN article fetcher with persistent HTTP client"""
    
    def __init__(self):
        self.http_client = None
    
    async def __aenter__(self):
        self.http_client = get_default_http_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # Client is managed by singleton
    
    async def fetch(self, url: str, use_browser_fallback: bool = True) -> Dict[str, str]:
        """Fetch article with configurable fallback options"""
        html = ''
        content = ''
        
        try:
            # Try normal request
            request_options = build_request_options()
            response = await self.http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
            html = response.text
            content = extract_article_content(html)
            
        except httpx.HTTPStatusError as error:
            if not use_browser_fallback:
                raise
            
            status = error.response.status_code
            if status not in [401, 403, 429]:
                raise
            
            # Try with cookies
            content = await self._fetch_with_cookies(url)
            if not content and use_browser_fallback:
                content = await self._fetch_with_browser(url)
        
        except Exception as error:
            if not use_browser_fallback:
                raise
            
            # Try browser fallback
            content = await self._fetch_with_browser(url)
        
        # Retry if content is insufficient
        if use_browser_fallback and should_retry_with_browser(html, content):
            content = await self._fetch_with_cookies(url)
            if not content or should_retry_with_browser(html, content):
                content = await self._fetch_with_browser(url)
        
        if not content:
            raise RuntimeError('Failed to extract readable CSDN article content')
        
        return {'content': content}
    
    async def _fetch_with_cookies(self, url: str) -> str:
        """Fetch using browser cookies"""
        cookie_header = await get_browser_cookie_header(url)
        if not cookie_header:
            return ''
        
        try:
            request_options = build_request_options(cookie_header)
            response = await self.http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
            return extract_article_content(response.text)
        except Exception:
            return ''
    
    async def _fetch_with_browser(self, url: str) -> str:
        """Fetch using full browser rendering"""
        try:
            browser_page = await fetch_page_html_with_browser(url)
            return extract_article_content(browser_page['html'])
        except Exception:
            return ''


# Improved version with better error handling and logging
class RobustCSDNArticleFetcher:
    """Robust CSDN article fetcher with multiple fallback strategies"""
    
    def __init__(self, enable_logging: bool = True):
        self.enable_logging = enable_logging
        self.http_client = None
    
    def _log(self, message: str, level: str = "INFO"):
        """Log message if logging is enabled"""
        if self.enable_logging:
            if hasattr(logger, level.lower()):
                getattr(logger, level.lower())("CSDN Fetcher: %s", message)
            else:
                logger.info("CSDN Fetcher: %s", message)
    
    async def fetch(self, url: str, max_retries: int = 3) -> Dict[str, str]:
        """
        Fetch article with multiple retry strategies
        
        Strategies in order:
        1. Direct HTTP request
        2. HTTP request with cookies
        3. Browser rendering
        """
        strategies = [
            ("Direct HTTP", self._fetch_direct),
            ("HTTP with cookies", self._fetch_with_cookies),
            ("Browser rendering", self._fetch_with_browser)
        ]
        
        for attempt in range(max_retries):
            for strategy_name, strategy_func in strategies:
                try:
                    self._log(f"Trying strategy: {strategy_name} (attempt {attempt + 1}/{max_retries})")
                    content = await strategy_func(url)
                    
                    if content and len(content) > 200:  # Minimum content length
                        self._log(f"Successfully fetched content using {strategy_name}, length: {len(content)} chars")
                        return {'content': content}
                    elif content:
                        self._log(f"Content too short using {strategy_name}: {len(content)} chars", "WARNING")
                    
                except Exception as error:
                    self._log(f"Strategy {strategy_name} failed: {error}", "WARNING")
                    continue
        
        raise RuntimeError('Failed to extract readable CSDN article content after all retries')
    
    async def _fetch_direct(self, url: str) -> str:
        """Direct HTTP fetch without cookies"""
        if not self.http_client:
            self.http_client = get_default_http_client()
        
        request_options = build_request_options()
        response = await self.http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
        return extract_article_content(response.text)
    
    async def _fetch_with_cookies(self, url: str) -> str:
        """Fetch with browser cookies"""
        if not self.http_client:
            self.http_client = get_default_http_client()
        
        cookie_header = await get_browser_cookie_header(url)
        if not cookie_header:
            raise ValueError("No cookie header available")
        
        request_options = build_request_options(cookie_header)
        response = await self.http_client.request("GET", url, options=BuildHttpRequestOptions(**request_options))
        return extract_article_content(response.text)
    
    async def _fetch_with_browser(self, url: str) -> str:
        """Fetch with full browser rendering"""
        browser_page = await fetch_page_html_with_browser(url)
        return extract_article_content(browser_page['html'])


# Convenience function with improved error handling
async def fetch_csdn_article_robust(url: str, enable_logging: bool = True) -> Dict[str, str]:
    """
    Fetch CSDN article with robust error handling
    
    Args:
        url: CSDN article URL
        enable_logging: Enable logging output
    
    Returns:
        Dictionary with article content
    """
    fetcher = RobustCSDNArticleFetcher(enable_logging=enable_logging)
    return await fetcher.fetch(url)


# Example usage and testing
async def test_csdn_fetcher():
    """Test function for CSDN fetcher"""
    test_url = "https://blog.csdn.net/example/article/details/12345678"
    
    try:
        # Method 1: Simple fetch
        result = await fetch_csdn_article(test_url)
        logger.info("Article length: %s characters", len(result["content"]))
        logger.info("First 200 chars: %s...", result["content"][:200])
        
        # Method 2: Using context manager
        async with CSDNArticleFetcher() as fetcher:
            result = await fetcher.fetch(test_url)
            logger.info("Fetched %s chars with context manager", len(result["content"]))
        
        # Method 3: Robust fetcher
        result = await fetch_csdn_article_robust(test_url, enable_logging=True)
        logger.info("Robust fetch: %s chars", len(result["content"]))
        
    except RuntimeError as error:
        logger.error("Failed to fetch article: %s", error)
