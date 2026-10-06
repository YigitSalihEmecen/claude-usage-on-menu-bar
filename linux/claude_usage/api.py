"""Client for Anthropic's OAuth usage endpoint."""

from __future__ import annotations

import json
import os

from . import http
from .snapshot import UsageSnapshot

#: Anthropic rate-limits this endpoint aggressively without a claude-code User-Agent.
USER_AGENT = "claude-code/2.0.0"

_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"


class UsageError(Exception):
    pass


class Unauthorized(UsageError):
    def __str__(self) -> str:
        return "Your session expired. Please sign in again."


class RateLimited(UsageError):
    def __str__(self) -> str:
        return "Anthropic is rate-limiting usage checks. Retrying shortly."


class RequestFailed(UsageError):
    def __init__(self, status: int):
        super().__init__(status)
        self.status = status

    def __str__(self) -> str:
        return f"Usage request failed (HTTP {self.status})."


def endpoint() -> str:
    # Overridable so the app can be pointed at a local fixture while developing.
    return os.environ.get("CLAUDE_USAGE_API_URL") or _ENDPOINT


def fetch(access_token: str) -> UsageSnapshot:
    """Fetches current usage. Raises UsageError, or http.NetworkError when offline."""
    response = http.request(
        endpoint(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        },
    )

    if response.status in (401, 403):
        raise Unauthorized()
    if response.status == 429:
        raise RateLimited()
    if not 200 <= response.status < 300:
        raise RequestFailed(response.status)

    try:
        payload = json.loads(response.body)
    except ValueError as error:
        raise UsageError("Anthropic returned a response this app could not read.") from error
    if not isinstance(payload, dict):
        raise UsageError("Anthropic returned a response this app could not read.")
    return UsageSnapshot.from_payload(payload)
