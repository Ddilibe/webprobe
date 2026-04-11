"""Registry of supported search engines."""

from typing import Dict

from webprobe.engine.search_service import (
    SearchEngineExecutor,
    SearchExecutionResult,
    SearchService,
    SUPPORTED_SEARCH_ENGINES,
)
from webprobe.engines.baidu import search_baidu
from webprobe.engines.bing import search_bing
from webprobe.engines.brave import search_brave
from webprobe.engines.csdn import search_csdn
from webprobe.engines.duckduckgo import search_duckduckgo
from webprobe.engines.exa import search_exa
from webprobe.engines.juejin import search_juejin
from webprobe.engines.linuxdo import search_linuxdo
from webprobe.engines.startpage import search_startpage

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
