"""A small blocking HTTP client built on the standard library.

Everything here is called from worker threads. Network failures surface as
``NetworkError`` so callers need not know about urllib.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

TIMEOUT = 20


class NetworkError(Exception):
    """The server could not be reached at all."""


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


def request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = TIMEOUT,
) -> Response:
    """Performs a request; HTTP error statuses are returned, not raised."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return Response(response.status, response.read())
    except urllib.error.HTTPError as error:
        try:
            return Response(error.code, error.read())
        finally:
            error.close()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NetworkError(str(getattr(error, "reason", error))) from error
