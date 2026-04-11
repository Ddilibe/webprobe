"""Registry of supported search engines."""

from typing import Dict

from mcpwebprobe.engine.search_service import (
    SearchEngineExecutor,
    SearchExecutionResult,
    SearchService,
    SUPPORTED_SEARCH_ENGINES,
)
from mcpwebprobe.engines.baidu import search_baidu
from mcpwebprobe.engines.bing import search_bing
from mcpwebprobe.engines.brave import search_brave
from mcpwebprobe.engines.csdn import search_csdn
from mcpwebprobe.engines.duckduckgo import search_duckduckgo
from mcpwebprobe.engines.exa import search_exa
from mcpwebprobe.engines.juejin import search_juejin
from mcpwebprobe.engines.linuxdo import search_linuxdo
from mcpwebprobe.engines.startpage import search_startpage

EngineMap = Dict[str, SearchEngineExecutor]

ENGINE_MAP: EngineMap = {
    "baidu": search_baidu,
    "bing": search_bing,
    "brave": search_brave,
    "csdn": search_csdn,
    "duckduckgo": search_duckduckgo,
    "exa": search_exa,
    "juejin": search_juejin,
    "linuxdo": search_linuxdo,
    "startpage": search_startpage,
}

SEARCH_SERVICE = SearchService(ENGINE_MAP)
