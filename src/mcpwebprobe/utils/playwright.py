import os
# playwright_client_sync.py
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, unquote

from mcpwebprobe.logging import get_logger

from mcpwebprobe.config import config, get_proxy_url

logger = get_logger(__name__)

PLAYWRIGHT_CONNECT_TIMEOUT_MS = max(config.playwright_navigation_timeout_ms, 30000)

# Global state
_playwright_module = None
_playwright_module_source: Optional[str] = None
_playwright_unavailable_message: Optional[str] = None
_has_emitted_playwright_unavailable_warning = False


def build_playwright_proxy() -> Optional[Dict[str, str]]:
    """Build proxy configuration for Playwright"""
    effective_proxy_url = get_proxy_url()
    if not effective_proxy_url:
        return None
    
    try:
        parsed = urlparse(effective_proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server += f":{parsed.port}"
        
        proxy_config = {"server": server}
        
        if parsed.username:
            proxy_config["username"] = unquote(parsed.username)
        if parsed.password:
            proxy_config["password"] = unquote(parsed.password)
        
        return proxy_config
    except Exception as error:
        logger.warning(
            "Invalid proxy URL for Playwright, falling back without browser proxy: %s",
            error,
        )
        return None


def normalize_loaded_playwright_module(loaded: Any) -> Optional[Any]:
    """Normalize loaded Playwright module to ensure it has chromium attribute"""
    if hasattr(loaded, 'chromium'):
        return loaded
    if hasattr(loaded, 'default') and hasattr(loaded.default, 'chromium'):
        return loaded.default
    return None


def get_playwright_module_candidates() -> List[Tuple[str, str]]:
    """Get list of candidate modules to try loading"""
    candidates = []
    seen_specifiers = set()
    
    def push_candidate(label: str, specifier: str):
        if specifier in seen_specifiers:
            return
        seen_specifiers.add(specifier)
        candidates.append((label, specifier))
    
    if config.playwright_module_path:
        module_path = config.playwright_module_path
        if not os.path.isabs(module_path):
            module_path = os.path.join(os.getcwd(), module_path)
        push_candidate(f"PLAYWRIGHT_MODULE_PATH ({module_path})", module_path)
    
    if config.playwright_package == 'auto':
        push_candidate('playwright package', 'playwright')
        push_candidate('playwright-core package', 'playwright-core')
    else:
        push_candidate(f"{config.playwright_package} package", config.playwright_package)
    
    return candidates


def get_playwright_module_source() -> Optional[str]:
    """Get the source of the loaded Playwright module"""
    return _playwright_module_source


def emit_playwright_unavailable_warning(silent: bool = False) -> None:
    """Emit warning if Playwright is unavailable"""
    global _has_emitted_playwright_unavailable_warning
    
    if silent or not _playwright_unavailable_message or _has_emitted_playwright_unavailable_warning:
        return
    
    _has_emitted_playwright_unavailable_warning = True
    logger.warning(_playwright_unavailable_message)


def load_playwright_client(silent: bool = False) -> Optional[Any]:
    """Load Playwright client module (synchronous version)"""
    global _playwright_module, _playwright_module_source, _playwright_unavailable_message, _has_emitted_playwright_unavailable_warning
    
    if _playwright_module is None:
        attempts = []
        
        for label, specifier in get_playwright_module_candidates():
            try:
                # Handle file paths vs package names
                if os.path.exists(specifier) or specifier.endswith('.py'):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("playwright_module", specifier)
                    if spec and spec.loader:
                        loaded = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(loaded)
                    else:
                        raise ImportError(f"Cannot load module from {specifier}")
                else:
                    loaded = __import__(specifier)
                
                normalized = normalize_loaded_playwright_module(loaded)
                if not normalized:
                    attempts.append(f"{label}: loaded module does not expose chromium")
                    continue
                
                _playwright_module_source = label
                _playwright_unavailable_message = None
                _has_emitted_playwright_unavailable_warning = False
                logger.info("🧭 Playwright client resolved from %s", label)
                _playwright_module = normalized
                return _playwright_module
                
            except Exception as error:
                message = str(error)
                attempts.append(f"{label}: {message}")
        
        _playwright_unavailable_message = (
            f"Playwright client is unavailable, falling back to HTTP-only behavior.\n"
            f"Install `playwright` or `playwright-core`, or expose an existing client with PLAYWRIGHT_MODULE_PATH.\n"
            f"Attempts: {' | '.join(attempts)}"
        )
        _playwright_module = None
    
    if not _playwright_module:
        emit_playwright_unavailable_warning(silent)
    
    return _playwright_module


def open_playwright_browser(headless: bool, launch_args: List[str] = None):
    """Open a Playwright browser session (synchronous version)"""
    if launch_args is None:
        launch_args = []
    
    playwright = load_playwright_client()
    if not playwright:
        raise RuntimeError(
            'Playwright client is not available. Install `playwright`/`playwright-core` manually or configure PLAYWRIGHT_MODULE_PATH.'
        )
    
    from playwright.sync_api import sync_playwright
    
    # Connect via WebSocket endpoint
    if config.playwright_ws_endpoint:
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.connect(
            ws_endpoint=config.playwright_ws_endpoint,
            timeout=PLAYWRIGHT_CONNECT_TIMEOUT_MS
        )
        return browser
    
    # Connect via CDP endpoint
    if config.playwright_cdp_endpoint:
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.connect_over_cdp(
            config.playwright_cdp_endpoint,
            timeout=PLAYWRIGHT_CONNECT_TIMEOUT_MS
        )
        return browser
    
    # Launch new browser
    launch_options = {
        "headless": headless,
        "args": launch_args
    }
    
    proxy_config = build_playwright_proxy()
    if proxy_config:
        launch_options["proxy"] = proxy_config
    
    if config.playwright_executable_path:
        launch_options["executable_path"] = config.playwright_executable_path
    
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.launch(**launch_options)
    return browser
