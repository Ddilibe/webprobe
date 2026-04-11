# http_client.py
import ssl
from typing import Optional, Dict, Any, Union, Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from mcpwebprobe.config import get_proxy_url


@dataclass
class BuildHttpRequestOptions:
    """Options for building HTTP request configuration"""

    allow_insecure_tls: bool = False
    decompress: Optional[bool] = None
    headers: Optional[Dict[str, str]] = None
    max_body_length: Optional[int] = None
    max_content_length: Optional[int] = None
    max_redirects: Optional[int] = None
    params: Optional[Dict[str, Any]] = None
    response_type: Optional[str] = None  # 'text', 'json', 'bytes', 'stream'
    timeout: Optional[float] = None
    validate_status: Optional[Callable[[int], bool]] = None


# Cache for HTTP clients and agents
_direct_http_clients: Dict[bool, httpx.Client] = {}
_proxy_clients: Dict[str, httpx.Client] = {}


def get_direct_http_client(allow_insecure_tls: bool) -> httpx.Client:
    """Get or create a direct HTTP client (no proxy)"""
    cache_key = allow_insecure_tls
    if cache_key in _direct_http_clients:
        return _direct_http_clients[cache_key]

    # Configure SSL context
    if allow_insecure_tls:
        verify = False
    else:
        verify = True

    client = httpx.Client(verify=verify)
    _direct_http_clients[cache_key] = client
    return client


def get_proxy_http_client(proxy_url: str, allow_insecure_tls: bool) -> httpx.Client:
    """Get or create a proxy HTTP client"""
    cache_key = f"{proxy_url}::{allow_insecure_tls}"

    if cache_key in _proxy_clients:
        return _proxy_clients[cache_key]

    # Configure SSL context
    if allow_insecure_tls:
        verify = False
    else:
        verify = True

    # Parse proxy URL for proper formatting
    parsed = urlparse(proxy_url)
    proxy_auth = None
    if parsed.username:
        proxy_auth = (parsed.username, parsed.password or "")

    # Build proxy URL without auth for the client
    proxy_server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        proxy_server += f":{parsed.port}"

    client = httpx.Client(proxies=proxy_server, verify=verify, proxy_auth=proxy_auth)

    _proxy_clients[cache_key] = client
    return client


def build_http_request_options(
    options: Optional[BuildHttpRequestOptions] = None,
) -> Dict[str, Any]:
    """
    Build HTTP request configuration for httpx

    Args:
        options: Request configuration options

    Returns:
        Dictionary with request configuration suitable for httpx.Client.request()
    """
    if options is None:
        options = BuildHttpRequestOptions()

    request_options: Dict[str, Any] = {}

    # Add headers if provided
    if options.headers:
        request_options["headers"] = options.headers

    # Add timeout if provided
    if options.timeout is not None:
        request_options["timeout"] = options.timeout

    # Add max redirects (httpx calls it follow_redirects with max redirects)
    if options.max_redirects is not None:
        request_options["follow_redirects"] = True
        request_options["max_redirects"] = options.max_redirects

    # Add response type handling (httpx handles this differently)
    if options.response_type:
        # httpx doesn't have a direct response_type parameter
        # Instead, we'll handle this in the calling code
        request_options["_response_type"] = options.response_type

    # Add max content length (httpx doesn't have built-in, but we can set limits)
    if options.max_content_length is not None:
        request_options["max_content_length"] = options.max_content_length

    # Add decompress (httpx decompresses by default)
    if options.decompress is not None:
        request_options["decompress"] = options.decompress

    # Add params (query parameters)
    if options.params is not None:
        request_options["params"] = options.params

    # Note: validate_status is not directly supported in httpx
    # We'll handle this in the calling code

    # Get effective proxy URL
    effective_proxy_url = get_proxy_url()

    # Store proxy/SSL info for the caller to use
    if effective_proxy_url:
        request_options["_proxy_url"] = effective_proxy_url
        request_options["_allow_insecure_tls"] = options.allow_insecure_tls
    else:
        request_options["_allow_insecure_tls"] = options.allow_insecure_tls

    return request_options


def get_http_client_for_request(
    options: Optional[BuildHttpRequestOptions] = None,
) -> httpx.Client:
    """
    Get the appropriate HTTP client based on proxy and TLS settings

    Args:
        options: Request configuration options

    Returns:
        Configured httpx.Client instance
    """
    if options is None:
        options = BuildHttpRequestOptions()

    effective_proxy_url = get_proxy_url()

    if effective_proxy_url:
        return get_proxy_http_client(effective_proxy_url, options.allow_insecure_tls)
    else:
        return get_direct_http_client(options.allow_insecure_tls)


# Alternative implementation using httpx.Client with per-request configuration
class HttpClient:
    """HTTP client wrapper with connection pooling and configuration"""

    def __init__(self):
        self._clients: Dict[str, httpx.Client] = {}

    def _get_client_key(
        self, proxy_url: Optional[str] = None, allow_insecure_tls: bool = False
    ) -> str:
        """Generate cache key for client"""
        if proxy_url:
            return f"proxy_{proxy_url}_{allow_insecure_tls}"
        return f"direct_{allow_insecure_tls}"

    def _create_client(
        self, proxy_url: Optional[str] = None, allow_insecure_tls: bool = False
    ) -> httpx.Client:
        """Create a new HTTP client"""
        verify = not allow_insecure_tls

        if proxy_url:
            parsed = urlparse(proxy_url)
            proxy_auth = None
            if parsed.username:
                proxy_auth = (parsed.username, parsed.password or "")

            proxy_server = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                proxy_server += f":{parsed.port}"

            return httpx.Client(
                proxies=proxy_server, verify=verify, proxy_auth=proxy_auth
            )
        else:
            return httpx.Client(verify=verify)

    def get_client(self, allow_insecure_tls: bool = False) -> httpx.Client:
        """Get or create a direct HTTP client"""
        key = self._get_client_key(allow_insecure_tls=allow_insecure_tls)
        if key not in self._clients:
            self._clients[key] = self._create_client(
                allow_insecure_tls=allow_insecure_tls
            )
        return self._clients[key]

    def get_proxy_client(
        self, proxy_url: str, allow_insecure_tls: bool = False
    ) -> httpx.Client:
        """Get or create a proxy HTTP client"""
        key = self._get_client_key(
            proxy_url=proxy_url, allow_insecure_tls=allow_insecure_tls
        )
        if key not in self._clients:
            self._clients[key] = self._create_client(
                proxy_url=proxy_url, allow_insecure_tls=allow_insecure_tls
            )
        return self._clients[key]

    def request(
        self,
        method: str,
        url: str,
        options: Optional[BuildHttpRequestOptions] = None,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with the appropriate client"""
        if options is None:
            options = BuildHttpRequestOptions()

        # Get the appropriate client
        proxy_url = get_proxy_url()
        if proxy_url:
            client = self.get_proxy_client(proxy_url, options.allow_insecure_tls)
        else:
            client = self.get_client(options.allow_insecure_tls)

        # Build request options
        request_kwargs = build_http_request_options(options)

        # Remove internal keys
        request_kwargs.pop("_proxy_url", None)
        request_kwargs.pop("_allow_insecure_tls", None)

        # Merge with additional kwargs
        request_kwargs.update(kwargs)

        # Make the request
        response = client.request(method, url, **request_kwargs)

        # Validate status if validator provided
        if options.validate_status and not options.validate_status(
            response.status_code
        ):
            response.raise_for_status()

        return response

    def close_all(self):
        """Close all client connections"""
        for client in self._clients.values():
            client.close()
        self._clients.clear()


# Singleton instance
_default_http_client = None


def get_default_http_client() -> HttpClient:
    """Get the default HTTP client instance"""
    global _default_http_client
    if _default_http_client is None:
        _default_http_client = HttpClient()
    return _default_http_client


# Convenience functions
def build_request_options(
    options: Optional[BuildHttpRequestOptions] = None,
) -> Dict[str, Any]:
    """Alias for build_http_request_options"""
    return build_http_request_options(options)


# Example usage with async support (using httpx.AsyncClient)
class AsyncHttpClient:
    """Async HTTP client wrapper"""

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}

    async def _create_client(
        self, proxy_url: Optional[str] = None, allow_insecure_tls: bool = False
    ) -> httpx.AsyncClient:
        """Create a new async HTTP client"""
        verify = not allow_insecure_tls

        if proxy_url:
            parsed = urlparse(proxy_url)
            proxy_auth = None
            if parsed.username:
                proxy_auth = (parsed.username, parsed.password or "")

            proxy_server = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                proxy_server += f":{parsed.port}"

            return httpx.AsyncClient(
                proxies=proxy_server, verify=verify, proxy_auth=proxy_auth
            )
        else:
            return httpx.AsyncClient(verify=verify)

    async def get_client(self, allow_insecure_tls: bool = False) -> httpx.AsyncClient:
        """Get or create a direct async HTTP client"""
        key = f"direct_{allow_insecure_tls}"
        if key not in self._clients:
            self._clients[key] = await self._create_client(
                allow_insecure_tls=allow_insecure_tls
            )
        return self._clients[key]

    async def request(
        self,
        method: str,
        url: str,
        options: Optional[BuildHttpRequestOptions] = None,
        **kwargs,
    ):
        """Make an async HTTP request"""
        if options is None:
            options = BuildHttpRequestOptions()

        proxy_url = get_proxy_url()
        if proxy_url:
            key = f"proxy_{proxy_url}_{options.allow_insecure_tls}"
            if key not in self._clients:
                self._clients[key] = await self._create_client(
                    proxy_url=proxy_url, allow_insecure_tls=options.allow_insecure_tls
                )
            client = self._clients[key]
        else:
            client = await self.get_client(options.allow_insecure_tls)

        request_kwargs = build_http_request_options(options)
        request_kwargs.pop("_proxy_url", None)
        request_kwargs.pop("_allow_insecure_tls", None)
        request_kwargs.update(kwargs)

        response = await client.request(method, url, **request_kwargs)

        if options.validate_status and not options.validate_status(
            response.status_code
        ):
            response.raise_for_status()

        return response
