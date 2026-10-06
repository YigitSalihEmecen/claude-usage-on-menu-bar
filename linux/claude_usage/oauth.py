"""Authorization Code + PKCE sign-in against claude.ai.

There is a loopback redirect for the browser flow and a paste-the-code fallback.
Anthropic offers no public OAuth client for third-party apps, so this uses
Claude Code's client ID, which is why the consent screen says "Claude Code".
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from . import api, http
from .credentials import Credentials
from .loopback import LoopbackCancelled, LoopbackError, LoopbackServer, LoopbackTimeout

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
SCOPES = "user:profile user:inference"
LOOPBACK_PORT = 54545
SIGN_IN_TIMEOUT = 180

AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
TOKEN_URLS = [
    "https://platform.claude.com/v1/oauth/token",
    "https://console.anthropic.com/v1/oauth/token",
]
LOOPBACK_REDIRECT = f"http://localhost:{LOOPBACK_PORT}/callback"
MANUAL_REDIRECT = "https://platform.claude.com/oauth/code/callback"


class AuthError(Exception):
    pass


class SignInCancelled(AuthError):
    pass


@dataclass(frozen=True)
class Session:
    verifier: str
    state: str
    redirect_uri: str
    url: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _random() -> str:
    return _b64url(secrets.token_bytes(32))


def challenge_for(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode()).digest())


def make_session(manual: bool) -> Session:
    verifier, state = _random(), _random()
    redirect = MANUAL_REDIRECT if manual else LOOPBACK_REDIRECT
    query = urlencode(
        {
            "code": "true",
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect,
            "scope": SCOPES,
            "code_challenge": challenge_for(verifier),
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return Session(verifier, state, redirect, f"{AUTHORIZE_URL}?{query}")


class BrowserSignIn:
    """One browser sign-in attempt. Create it on any thread, ``run`` it on a worker,
    and call ``cancel`` from anywhere to abort the wait."""

    def __init__(self) -> None:
        self.session = make_session(manual=False)
        try:
            self._server = LoopbackServer(LOOPBACK_PORT)
        except LoopbackError as error:
            raise AuthError(str(error)) from error

    def run(self) -> Credentials:
        try:
            query = self._server.wait_for_callback(SIGN_IN_TIMEOUT)
        except LoopbackTimeout as error:
            raise AuthError("Sign-in timed out. Please try again.") from error
        except LoopbackCancelled as error:
            raise SignInCancelled() from error

        code = query.get("code")
        if not code:
            raise AuthError("Claude did not return an authorization code.")
        if query.get("state") != self.session.state:
            raise AuthError("The sign-in response did not match this request.")
        return _exchange(code, self.session)

    def cancel(self) -> None:
        self._server.cancel()


def sign_in_with_pasted_code(raw: str, session: Session) -> Credentials:
    """Completes the paste-the-code fallback. Claude renders the value as ``code#state``."""
    code, _, state = raw.strip().partition("#")
    if not code:
        raise AuthError("Claude did not return an authorization code.")
    if state and state != session.state:
        raise AuthError("The sign-in response did not match this request.")
    return _exchange(code, session)


def refresh(credentials: Credentials) -> Credentials:
    if not credentials.refresh_token:
        raise AuthError("Could not complete sign-in. No refresh token stored.")
    return _post(
        {
            "grant_type": "refresh_token",
            "refresh_token": credentials.refresh_token,
            "client_id": CLIENT_ID,
        },
        fallback_refresh_token=credentials.refresh_token,
    )


def _exchange(code: str, session: Session) -> Credentials:
    return _post(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": session.redirect_uri,
            "client_id": CLIENT_ID,
            "code_verifier": session.verifier,
            "state": session.state,
        },
        fallback_refresh_token=None,
    )


def _post(body: dict[str, str], fallback_refresh_token: str | None) -> Credentials:
    last_error = "The server did not respond."

    for url in TOKEN_URLS:
        try:
            response = http.request(
                url,
                method="POST",
                headers={"Content-Type": "application/json", "User-Agent": api.USER_AGENT},
                body=json.dumps(body).encode(),
            )
        except http.NetworkError as error:
            last_error = str(error)
            continue

        if not 200 <= response.status < 300:
            last_error = _message(response)
            continue

        try:
            token = json.loads(response.body)
            access_token = token["access_token"]
        except (ValueError, KeyError, TypeError):
            last_error = "The server sent an unexpected response."
            continue

        expires_in = token.get("expires_in")
        scope = token.get("scope")
        return Credentials(
            access_token=access_token,
            refresh_token=token.get("refresh_token") or fallback_refresh_token,
            expires_at=time.time() + expires_in if isinstance(expires_in, (int, float)) else None,
            scopes=scope.split() if isinstance(scope, str) else None,
        )

    raise AuthError(f"Could not complete sign-in. {last_error}")


def _message(response: http.Response) -> str:
    try:
        data = json.loads(response.body)
        detail = data.get("error_description") or data.get("error")
    except (ValueError, AttributeError):
        detail = None
    return detail if isinstance(detail, str) else f"HTTP {response.status}."
