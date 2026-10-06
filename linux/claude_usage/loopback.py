"""Minimal one-shot HTTP listener used as the OAuth redirect target.

It binds to 127.0.0.1 only, so the callback is never reachable from the network,
serves a single response for ``/callback`` and then shuts down.
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

CALLBACK_PATH = "/callback"


class LoopbackError(Exception):
    pass


class LoopbackTimeout(LoopbackError):
    pass


class LoopbackCancelled(LoopbackError):
    pass


def _page(title: str, message: str, glyph: str) -> bytes:
    return f"""<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
         font:15px/1.5 system-ui,sans-serif; background:#f6f5f4; color:#1f1e1d; }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#232220; color:#f6f5f4; }} }}
  .card {{ text-align:center; padding:48px 40px; max-width:360px; }}
  .glyph {{ font-size:44px; line-height:1; color:#D97757; }}
  h1 {{ font-size:20px; margin:20px 0 8px; letter-spacing:-0.01em; }}
  p {{ margin:0; opacity:0.6; }}
</style>
<div class="card"><div class="glyph">{glyph}</div><h1>{title}</h1><p>{message}</p></div>
""".encode()


SUCCESS_PAGE = _page("Signed in", "You can close this tab and return to Claude Usage.", "&#10003;")
FAILURE_PAGE = _page("Sign-in failed", "No authorization code was returned. Please try again.", "&#9888;")


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    # A browser may open a speculative connection and send nothing; don't wait on it.
    timeout = 1

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        url = urlsplit(self.path)
        if url.path != CALLBACK_PATH:
            # Browsers probe for /favicon.ico and the like; ignore those and keep waiting.
            self._respond(404, b"")
            return

        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        succeeded = "code" in query
        self._respond(200 if succeeded else 400, SUCCESS_PAGE if succeeded else FAILURE_PAGE)
        self.server.deliver(query)

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass  # keep the authorization code out of any log


class _Server(HTTPServer):
    allow_reuse_address = True
    timeout = 0.25  # handle_request wakes this often so cancellation is prompt

    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), _Handler)
        self.result: dict[str, str] | None = None

    def deliver(self, query: dict[str, str]) -> None:
        self.result = query


class LoopbackServer:
    def __init__(self, port: int):
        try:
            self._server = _Server(port)
        except OSError as error:
            raise LoopbackError(
                f"Port {port} is in use. Close whatever is using it, or use the code option."
            ) from error
        self._cancelled = threading.Event()

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def cancel(self) -> None:
        self._cancelled.set()

    def wait_for_callback(self, timeout: float) -> dict[str, str]:
        """Blocks until the browser is redirected here. Run it on a worker thread."""
        deadline = time.monotonic() + timeout
        try:
            while self._server.result is None:
                if self._cancelled.is_set():
                    raise LoopbackCancelled()
                if time.monotonic() >= deadline:
                    raise LoopbackTimeout()
                self._server.handle_request()
            return self._server.result
        finally:
            self._server.server_close()
