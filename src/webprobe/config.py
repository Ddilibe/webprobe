import os
from typing import Optional, List, Literal, Union
from dataclasses import dataclass
from urllib.parse import quote

from webprobe.logging import get_logger

# Type aliases for better type hints
SearchEngine = Literal[
    "bing",
    "duckduckgo",
    "exa",
    "brave",
    "baidu",
    "csdn",
    "linuxdo",
    "juejin",
    "startpage",
]
SearchMode = Literal["request", "auto", "playwright"]
PlaywrightPackage = Literal["auto", "playwright", "playwright-core"]


@dataclass
class AppConfig:
    # Search engine configuration
    default_search_engine: SearchEngine
    # List of allowed search engines (if empty, all engines are available)
    allowed_search_engines: List[str]
    # Search mode: request only, auto request then fallback, or force Playwright
    # Currently only affects Bing.
    search_mode: SearchMode
    # Proxy configuration
    proxy_url: Optional[str]
    use_proxy: bool
    fetch_web_allow_insecure_tls: bool
    # Playwright configuration
    playwright_package: PlaywrightPackage
    playwright_module_path: Optional[str]
    playwright_executable_path: Optional[str]
    playwright_ws_endpoint: Optional[str]
    playwright_cdp_endpoint: Optional[str]
    playwright_headless: bool
    playwright_navigation_timeout_ms: int
    # CORS configuration
    enable_cors: bool
    cors_origin: str
    # Server configuration (determined by MODE env var: 'both', 'http', or 'stdio')
    enable_http_server: bool


def read_optional_env(name: str) -> Optional[str]:
    """Read optional environment variable, return None if not set or empty"""
    value = os.environ.get(name)
    if value is not None:
        value = value.strip()
        return value if value else None
    return None


def parse_allowed_search_engines(env_value: Optional[str]) -> List[str]:
    """Parse comma-separated list of allowed search engines"""
    if env_value:
        return [e.strip() for e in env_value.split(",")]
    return []


# Valid search engines list
VALID_SEARCH_ENGINES = [
    "bing",
    "duckduckgo",
    "exa",
    "brave",
    "baidu",
    "csdn",
    "linuxdo",
    "juejin",
    "startpage",
]
VALID_SEARCH_MODES = ["request", "auto", "playwright"]
VALID_PLAYWRIGHT_PACKAGES = ["auto", "playwright", "playwright-core"]
QUIET_STARTUP_LOGS = os.environ.get("OPEN_WEBSEARCH_QUIET_STARTUP") == "true"

# Read from environment variables or use defaults
config = AppConfig(
    # Search engine configuration
    default_search_engine=os.environ.get("DEFAULT_SEARCH_ENGINE", "bing"),  # type: ignore
    # Parse comma-separated list of allowed search engines
    allowed_search_engines=parse_allowed_search_engines(
        os.environ.get("ALLOWED_SEARCH_ENGINES")
    ),
    search_mode=os.environ.get("SEARCH_MODE", "auto"),  # type: ignore
    # Proxy configuration
    proxy_url=os.environ.get("PROXY_URL", "http://127.0.0.1:7890"),
    use_proxy=os.environ.get("USE_PROXY") == "true",
    fetch_web_allow_insecure_tls=os.environ.get("FETCH_WEB_INSECURE_TLS") == "true",
    playwright_package=os.environ.get("PLAYWRIGHT_PACKAGE", "auto"),  # type: ignore
    playwright_module_path=read_optional_env("PLAYWRIGHT_MODULE_PATH"),
    playwright_executable_path=read_optional_env("PLAYWRIGHT_EXECUTABLE_PATH"),
    playwright_ws_endpoint=read_optional_env("PLAYWRIGHT_WS_ENDPOINT"),
    playwright_cdp_endpoint=read_optional_env("PLAYWRIGHT_CDP_ENDPOINT"),
    playwright_headless=os.environ.get("PLAYWRIGHT_HEADLESS") != "false",
    playwright_navigation_timeout_ms=int(
        os.environ.get("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS", 20000)
    ),
    # CORS configuration
    enable_cors=os.environ.get("ENABLE_CORS") == "true",
    cors_origin=os.environ.get("CORS_ORIGIN", "*"),
    # Server configuration - determined by MODE environment variable
    # Modes: 'both' (default), 'http', 'stdio'
    enable_http_server=(
        (os.environ.get("MODE", "both") in ["both", "http"])
        if os.environ.get("MODE")
        else True
    ),
)

logger = get_logger(__name__)

# Validate default search engine
if config.default_search_engine not in VALID_SEARCH_ENGINES:
    logger.warning(
        'Invalid DEFAULT_SEARCH_ENGINE: "%s", falling back to "bing"',
        config.default_search_engine,
    )
    config.default_search_engine = "bing"

if config.search_mode not in VALID_SEARCH_MODES:
    logger.warning(
        'Invalid SEARCH_MODE: "%s", falling back to "auto"',
        config.search_mode,
    )
    config.search_mode = "auto"

if config.playwright_package not in VALID_PLAYWRIGHT_PACKAGES:
    logger.warning(
        'Invalid PLAYWRIGHT_PACKAGE: "%s", falling back to "auto"',
        config.playwright_package,
    )
    config.playwright_package = "auto"

if not (
    isinstance(config.playwright_navigation_timeout_ms, (int, float))
    and config.playwright_navigation_timeout_ms > 0
):
    logger.warning(
        'Invalid PLAYWRIGHT_NAVIGATION_TIMEOUT_MS: "%s", falling back to 20000',
        os.environ.get("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS"),
    )
    config.playwright_navigation_timeout_ms = 20000

if config.playwright_ws_endpoint and config.playwright_cdp_endpoint:
    logger.warning(
        "Both PLAYWRIGHT_WS_ENDPOINT and PLAYWRIGHT_CDP_ENDPOINT are set, PLAYWRIGHT_WS_ENDPOINT will take precedence"
    )

if (
    config.playwright_ws_endpoint or config.playwright_cdp_endpoint
) and config.playwright_executable_path:
    logger.warning(
        "PLAYWRIGHT_EXECUTABLE_PATH is ignored when connecting to a remote browser endpoint"
    )

# Validate allowed search engines
if config.allowed_search_engines:
    # Filter out invalid engines
    invalid_engines = [
        engine
        for engine in config.allowed_search_engines
        if engine not in VALID_SEARCH_ENGINES
    ]
    if invalid_engines:
        logger.warning(
            "Invalid search engines detected and will be ignored: %s",
            ", ".join(invalid_engines),
        )

    config.allowed_search_engines = [
        engine
        for engine in config.allowed_search_engines
        if engine in VALID_SEARCH_ENGINES
    ]

    # If all engines were invalid, don't restrict (allow all engines)
    if not config.allowed_search_engines:
        logger.warning(
            "No valid search engines specified in the allowed list, all engines will be available"
        )
    # Check if default engine is in the allowed list
    elif config.default_search_engine not in config.allowed_search_engines:
        logger.warning(
            'Default search engine "%s" is not in the allowed engines list',
            config.default_search_engine,
        )
        # Update the default engine to the first allowed engine
        config.default_search_engine = config.allowed_search_engines[0]  # type: ignore
        logger.info(
            'Default search engine updated to "%s"',
            config.default_search_engine,
        )

if not QUIET_STARTUP_LOGS:
    # Log configuration
    logger.info("🔍 Default search engine: %s", config.default_search_engine)
    if config.allowed_search_engines:
        logger.info("🔍 Allowed search engines: %s", ", ".join(config.allowed_search_engines))
    else:
        logger.info("🔍 No search engine restrictions, all available engines can be used")
    logger.info(
        "🔍 Search mode: %s (currently only affects Bing)",
        config.search_mode.upper(),
    )

    if config.use_proxy:
        logger.info("🌐 Using proxy: %s", config.proxy_url)
    else:
        logger.info("🌐 No proxy configured (set USE_PROXY=true to enable)")

    if config.fetch_web_allow_insecure_tls:
        logger.warning(
            "⚠️ fetchWebContent TLS verification is disabled (FETCH_WEB_INSECURE_TLS=true)"
        )
    else:
        logger.info("🔐 fetchWebContent TLS verification is enabled")

    logger.info("🧭 Playwright client source: %s", config.playwright_package)
    if config.playwright_module_path:
        logger.info(
            "🧭 Playwright module path override: %s", config.playwright_module_path
        )
    if config.playwright_ws_endpoint:
        logger.info(
            "🧭 Playwright remote endpoint (ws): %s", config.playwright_ws_endpoint
        )
    elif config.playwright_cdp_endpoint:
        logger.info(
            "🧭 Playwright remote endpoint (cdp): %s", config.playwright_cdp_endpoint
        )
    elif config.playwright_executable_path:
        logger.info(
            "🧭 Playwright executable path: %s", config.playwright_executable_path
        )
    logger.info("🧭 Playwright headless: %s", config.playwright_headless)
    logger.info(
        "🧭 Playwright navigation timeout: %sms",
        config.playwright_navigation_timeout_ms,
    )

    # Determine server mode from config
    mode = os.environ.get("MODE") or ("both" if config.enable_http_server else "stdio")
    logger.info("🖥️ Server mode: %s", mode.upper())

    if config.enable_http_server:
        if config.enable_cors:
            logger.info("🔒 CORS enabled with origin: %s", config.cors_origin)
        else:
            logger.info("🔒 CORS disabled (set ENABLE_CORS=true to enable)")


def get_proxy_url() -> Optional[str]:
    """Helper function to get the proxy URL if proxy is enabled"""
    return quote(config.proxy_url) if config.use_proxy and config.proxy_url else None
