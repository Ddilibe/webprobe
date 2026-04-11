from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from webprobe.api import (
    fetch_csdn,
    fetch_github,
    fetch_juejin,
    fetch_linuxdo,
    search,
)
from webprobe.logging import get_logger

logger = get_logger(__name__)


class WebProbeRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: HTTPStatus, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        try:
            if parsed.path == "/search":
                response = self._handle_search(query_params)
            elif parsed.path == "/fetch":
                response = self._handle_fetch(query_params)
            else:
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"error": f"{parsed.path} is not a recognized endpoint"},
                )
                return

            self._send_json(HTTPStatus.OK, response)
        except Exception as error:  # noqa: BLE001
            logger.exception("Request failed: %s", error)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": str(error)},
            )

    def _handle_search(self, params: Dict[str, list[str]]) -> dict:
        query = params.get("q") or params.get("query")
        if not query:
            raise ValueError("query parameter is required")
        limit = int(params.get("limit", ["10"])[0])
        engine_csv = params.get("engines", [""])[0]
        engines = [e.strip() for e in engine_csv.split(",") if e.strip()]
        return search(query[0], limit=limit, engines=engines)

    def _handle_fetch(self, params: Dict[str, list[str]]) -> dict:
        kind = (params.get("kind") or ["csdn"])[0]
        url = (params.get("url") or [None])[0]
        if not url:
            raise ValueError("url parameter is required")

        if kind == "csdn":
            return fetch_csdn(url)
        if kind == "linuxdo":
            return fetch_linuxdo(url)
        if kind == "juejin":
            return fetch_juejin(url)
        if kind in {"github", "readme"}:
            return {"content": fetch_github(url)}

        raise ValueError(f"Unsupported fetch kind: {kind}")

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.client_address[0], format % args)


class WebProbeServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3210,
        handler_factory: Optional[
            Callable[
                [Tuple[str, int], ThreadingHTTPServer],
                BaseHTTPRequestHandler,
            ]
        ] = None,
    ):
        handler = handler_factory or WebProbeRequestHandler
        self._server = ThreadingHTTPServer((host, port), handler)

    def serve_forever(self) -> None:
        logger.info("Starting WebProbe server on %s:%s", *self._server.server_address)
        self._server.serve_forever()

    def shutdown(self) -> None:
        logger.info("Shutting down WebProbe server")
        self._server.shutdown()
