"""OAuth token storage.

Tokens go to the desktop keyring (Secret Service, e.g. GNOME Keyring or KWallet)
through libsecret. If no keyring is available they fall back to a file readable
only by the current user. The store can also adopt an existing Claude Code login
so you do not have to authenticate twice.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import paths

log = logging.getLogger(__name__)

SERVICE = "com.claudeusage.menubar"
ACCOUNT = "oauth"


@dataclass(frozen=True)
class Credentials:
    access_token: str
    refresh_token: str | None = None
    #: Absolute expiry as a Unix timestamp; None when the server did not say.
    expires_at: float | None = None
    scopes: list[str] | None = None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at - time.time() < 60

    def to_json(self) -> str:
        return json.dumps(
            {
                "accessToken": self.access_token,
                "refreshToken": self.refresh_token,
                "expiresAt": self.expires_at,
                "scopes": self.scopes,
            }
        )

    @classmethod
    def from_json(cls, text: str) -> Credentials | None:
        try:
            data = json.loads(text)
            token = data["accessToken"]
        except (ValueError, KeyError, TypeError):
            return None
        if not isinstance(token, str) or not token:
            return None
        return cls(
            access_token=token,
            refresh_token=data.get("refreshToken"),
            expires_at=data.get("expiresAt"),
            scopes=data.get("scopes"),
        )


class Backend(Protocol):
    def read(self) -> str | None: ...
    def write(self, value: str) -> bool: ...
    def delete(self) -> None: ...


class FileBackend:
    """Plain file with 0600 permissions: the fallback when no keyring exists."""

    def __init__(self, path: Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or paths.config_dir() / "credentials.json"

    def read(self) -> str | None:
        try:
            return self.path.read_text()
        except OSError:
            return None

    def write(self, value: str) -> bool:
        path = self.path
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = path.with_suffix(".tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                handle.write(value)
            os.replace(temporary, path)
            return True
        except OSError as error:
            log.warning("could not write %s: %s", path, error)
            return False

    def delete(self) -> None:
        with contextlib.suppress(OSError):
            self.path.unlink()


class KeyringBackend:
    """Secret Service through libsecret. Unavailable without PyGObject bindings."""

    def __init__(self) -> None:
        import gi

        gi.require_version("Secret", "1")
        from gi.repository import GLib, Secret

        self._secret = Secret
        self._glib_error = GLib.Error
        self._schema = Secret.Schema.new(
            SERVICE,
            Secret.SchemaFlags.NONE,
            {
                "service": Secret.SchemaAttributeType.STRING,
                "account": Secret.SchemaAttributeType.STRING,
            },
        )
        self._attributes = {"service": SERVICE, "account": ACCOUNT}

    def read(self) -> str | None:
        try:
            return self._secret.password_lookup_sync(self._schema, self._attributes, None)
        except self._glib_error as error:
            log.warning("keyring read failed: %s", error.message)
            return None

    def write(self, value: str) -> bool:
        try:
            return bool(
                self._secret.password_store_sync(
                    self._schema,
                    self._attributes,
                    self._secret.COLLECTION_DEFAULT,
                    "Claude Usage",
                    value,
                    None,
                )
            )
        except self._glib_error as error:
            log.warning("keyring write failed: %s", error.message)
            return False

    def delete(self) -> None:
        try:
            self._secret.password_clear_sync(self._schema, self._attributes, None)
        except self._glib_error as error:
            log.warning("keyring delete failed: %s", error.message)


def default_backends() -> list[Backend]:
    backends: list[Backend] = []
    try:
        backends.append(KeyringBackend())
    except (ImportError, ValueError) as error:
        log.info("no keyring support (%s); using a private file instead", error)
    backends.append(FileBackend())
    return backends


class CredentialStore:
    """Reads from the first backend that has a token; writes to the first that works."""

    def __init__(self, backends: list[Backend] | None = None):
        self._backends = backends if backends is not None else default_backends()

    def load(self) -> Credentials | None:
        for backend in self._backends:
            value = backend.read()
            if value and (credentials := Credentials.from_json(value)):
                return credentials
        return None

    def save(self, credentials: Credentials) -> None:
        value = credentials.to_json()
        for index, backend in enumerate(self._backends):
            if backend.write(value):
                # A stale copy in a lower-priority backend would resurrect an old login.
                for other in self._backends[index + 1 :]:
                    other.delete()
                return
        log.error("could not store credentials in any backend")

    def clear(self) -> None:
        for backend in self._backends:
            backend.delete()


def claude_code_credentials_file() -> Path:
    return paths.claude_code_dir() / ".credentials.json"


def import_from_claude_code() -> Credentials | None:
    """Reads Claude Code's own login from ``~/.claude/.credentials.json``."""
    try:
        data = json.loads(claude_code_credentials_file().read_text())
        oauth = data["claudeAiOauth"]
        token = oauth["accessToken"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(token, str) or not token:
        return None

    expires = oauth.get("expiresAt")
    return Credentials(
        access_token=token,
        refresh_token=oauth.get("refreshToken"),
        # Claude Code stores milliseconds.
        expires_at=expires / 1000 if isinstance(expires, (int, float)) else None,
        scopes=oauth.get("scopes"),
    )


def claude_code_login_available() -> bool:
    return claude_code_credentials_file().is_file()
