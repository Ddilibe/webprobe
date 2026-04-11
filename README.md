# WebProbe (Python port of open-webSearch)

This project replicates the core search and fetch capabilities of [Aas-ee/open-webSearch](https://github.com/Aas-ee/open-webSearch) using Python. It exposes a CLI that can:

- Search multiple engines (Bing, DuckDuckGo, Baidu, Brave, Exa, Startpage, CSDN, Juejin, Linux.do)
- Fetch full-length articles from CSDN, Linux.do, and Juejin
- Download GitHub `README.*` files without hitting the API

## Installation

```bash
python -m pip install --upgrade pip
pip install -e .
```

## Package usage

Install the project locally and consume the `webprobe` package directly:

```python
from webprobe import WebProbeServer, search, fetch_csdn

print(search("visible web", limit=5))
print(fetch_csdn("https://blog.csdn.net/example/article/details/xxxxx"))

# Start the bundled HTTP server (serves /search and /fetch?kind=csdn)
server = WebProbeServer(host="0.0.0.0", port=3210)
try:
    server.serve_forever()
finally:
    server.shutdown()
```

The HTTP server exposes `/search?query=...&limit=...&engines=...` and `/fetch?kind=<csdn|linuxdo|juejin|github>&url=...`.

## CLI

Run `python main.py --help` to see available commands. Key subcommands:

### `search`

```bash
python main.py search "open websearch" --limit 12 --engines bing,duckduckgo
```

### Article fetchers

Each fetcher prints JSON or plain text:

- `python main.py fetch-csdn <url>`
- `python main.py fetch-linuxdo <url>`
- `python main.py fetch-juejin <url>`
- `python main.py fetch-github <repo-url>`

## Configuration

Environment variables mirror the TypeScript version:

| Variable | Default | Description |
| --- | --- | --- |
| `DEFAULT_SEARCH_ENGINE` | `bing` | Default search engine |
| `ALLOWED_SEARCH_ENGINES` | (empty) | Comma-separated whitelist |
| `USE_PROXY` / `PROXY_URL` | `false` / `http://127.0.0.1:7890` | HTTP proxy for requests |

Set `USE_PROXY=true` to route all HTTP traffic through `PROXY_URL`.

## Architecture

- `src/engine/search_service.py` orchestrates multi-engine searches with distribution logic.
- `src/engines/*` implement individual search/fetch adapters for each provider.
- `src/utils/` contains HTTP helpers, Playwright bridges for future browser fallbacks, and shared fetch logic for CSDN articles.

## Next steps

1. Wire this CLI into an MCP server similar to the TypeScript runtime.
2. Add Playwright-backed fallbacks for blocked search pages and protected articles.
3. Extend fetchers with generic web extraction (`fetch_web_content`) as in the original repo.
