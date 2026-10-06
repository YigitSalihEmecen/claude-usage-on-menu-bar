"""Single source of truth for the tray and panel.

Owns the credentials and the latest snapshot. Network and disk work runs on
worker threads; results are applied through ``post``, which the app points at the
GLib main loop so observers always run on the UI thread. Tests pass synchronous
``post`` and ``spawn`` callables to stay deterministic.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from . import api, context, http, oauth
from . import credentials as creds
from .preferences import Preferences
from .snapshot import UsageSnapshot

log = logging.getLogger(__name__)

SIGNED_OUT = "signedOut"
LOADING = "loading"
READY = "ready"
FAILED = "failed"


def _spawn_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True, name="claude-usage-worker").start()


class UsageStore:
    def __init__(
        self,
        preferences: Preferences,
        credential_store: creds.CredentialStore | None = None,
        post: Callable[[Callable[[], None]], None] | None = None,
        spawn: Callable[[Callable[[], None]], None] | None = None,
    ):
        self.preferences = preferences
        self._credential_store = credential_store or creds.CredentialStore()
        self._post = post or (lambda fn: fn())
        self._spawn = spawn or _spawn_thread
        self._observers: list[Callable[[], None]] = []

        self.phase = SIGNED_OUT
        self.snapshot: UsageSnapshot | None = None
        self.error: str | None = None
        self.last_updated: datetime | None = None
        #: Context window of the most recent Claude Code session; read from disk,
        #: independent of the usage API and of being signed in.
        self.context_usage: context.ContextUsage | None = None
        self.is_signing_in = False
        self.sign_in_error: str | None = None

        self._lock = threading.Lock()  # guards the fields below; held only briefly
        self._refresh_lock = threading.Lock()  # serialises token refreshes
        self._refreshing = False
        #: Bumped whenever the account changes, so a slow request from a previous
        #: login cannot overwrite the state of the current one.
        self._epoch = 0
        self._browser_sign_in: oauth.BrowserSignIn | None = None

        self._credentials = self._credential_store.load()
        if self._credentials is not None:
            self.phase = LOADING

    # MARK: - Observation

    def subscribe(self, observer: Callable[[], None]) -> None:
        self._observers.append(observer)

    def _commit(self, epoch: int | None = None, **changes: Any) -> None:
        """Applies state changes on the UI thread, then notifies observers."""

        def apply() -> None:
            if epoch is not None and epoch != self._epoch:
                return
            for name, value in changes.items():
                setattr(self, name, value)
            for observer in list(self._observers):
                observer()

        self._post(apply)

    # MARK: - Derived state

    @property
    def is_signed_in(self) -> bool:
        return self._credentials is not None

    @property
    def import_available(self) -> bool:
        """True when a Claude Code login exists that we can adopt."""
        return creds.claude_code_login_available()

    # MARK: - Data

    def refresh(self) -> None:
        """Fetches usage in the background. Overlapping calls are coalesced."""
        with self._lock:
            if self._refreshing or self._credentials is None:
                return
            self._refreshing = True
        self._spawn(self._refresh_worker)

    def refresh_if_stale(self, max_age: float = 15) -> None:
        """Called when the panel opens; avoids hammering a rate-limited endpoint."""
        # Context comes from disk and moves faster than the usage windows, so it
        # is re-read every time rather than being age-gated.
        self.refresh_context()
        if self.last_updated is not None:
            age = (datetime.now(timezone.utc) - self.last_updated).total_seconds()
            if age < max_age:
                return
        self.refresh()

    def refresh_context(self) -> None:
        def work() -> None:
            self._commit(context_usage=context.current_session())

        self._spawn(work)

    def _refresh_worker(self) -> None:
        try:
            self._perform_refresh()
        except Exception:  # never let a worker die silently with _refreshing set
            log.exception("usage refresh crashed")
            self._commit(phase=FAILED, error="Something went wrong reading your usage.")
        finally:
            with self._lock:
                self._refreshing = False

    def _perform_refresh(self) -> None:
        with self._lock:
            credentials, epoch = self._credentials, self._epoch
        if credentials is None:
            self._commit(epoch, phase=SIGNED_OUT)
            return
        if self.snapshot is None:
            self._commit(epoch, phase=LOADING)

        try:
            token = self._valid_token(credentials)
            snapshot = api.fetch(token)
            self._commit(
                epoch, phase=READY, snapshot=snapshot, error=None, last_updated=datetime.now(timezone.utc)
            )
        except api.Unauthorized:
            self._handle_unauthorized(credentials, epoch)
        except (api.UsageError, oauth.AuthError) as error:
            self._commit(epoch, phase=FAILED, error=str(error))
        except http.NetworkError:
            self._commit(epoch, phase=FAILED, error="Can't reach Anthropic. Check your connection.")

    def _valid_token(self, credentials: creds.Credentials) -> str:
        if not credentials.is_expired or not credentials.refresh_token:
            return credentials.access_token
        return self._refreshed(credentials).access_token

    def _refreshed(self, stale: creds.Credentials) -> creds.Credentials:
        """Refresh tokens rotate, so two concurrent refreshes would spend the same
        one and sign the user out. Serialise them, and reuse a newer token if
        another caller already refreshed."""
        with self._refresh_lock:
            with self._lock:
                current = self._credentials
            if current is not None and current.access_token != stale.access_token:
                return current
            refreshed = oauth.refresh(stale)
            with self._lock:
                if self._credentials is not None:  # not signed out meanwhile
                    self._adopt(refreshed)
            return refreshed

    def _handle_unauthorized(self, credentials: creds.Credentials, epoch: int) -> None:
        if credentials.refresh_token:
            try:
                refreshed = self._refreshed(credentials)
                snapshot = api.fetch(refreshed.access_token)
            except (api.UsageError, oauth.AuthError, http.NetworkError):
                pass
            else:
                self._commit(
                    epoch, phase=READY, snapshot=snapshot, error=None, last_updated=datetime.now(timezone.utc)
                )
                return
        self._post(self.sign_out)

    # MARK: - Auth

    def sign_in_with_browser(self, open_url: Callable[[str], None]) -> None:
        """Opens the browser and waits for the redirect. `open_url` runs on the caller's thread."""
        if self.is_signing_in:
            return
        try:
            attempt = oauth.BrowserSignIn()
        except oauth.AuthError as error:
            self._commit(sign_in_error=str(error))
            return

        self._browser_sign_in = attempt
        self._commit(is_signing_in=True, sign_in_error=None)
        open_url(attempt.session.url)

        def work() -> None:
            self._finish_sign_in(attempt.run)

        self._spawn(work)

    def cancel_sign_in(self) -> None:
        if self._browser_sign_in is not None:
            self._browser_sign_in.cancel()

    def begin_manual_sign_in(self) -> oauth.Session:
        return oauth.make_session(manual=True)

    def complete_manual_sign_in(self, code: str, session: oauth.Session) -> None:
        self._commit(is_signing_in=True, sign_in_error=None)
        self._spawn(lambda: self._finish_sign_in(lambda: oauth.sign_in_with_pasted_code(code, session)))

    def _finish_sign_in(self, authorize: Callable[[], creds.Credentials]) -> None:
        try:
            credentials = authorize()
        except oauth.SignInCancelled:
            self._commit(is_signing_in=False)
            return
        except (oauth.AuthError, http.NetworkError) as error:
            self._commit(is_signing_in=False, sign_in_error=str(error))
            return
        except Exception:
            log.exception("sign-in crashed")
            self._commit(is_signing_in=False, sign_in_error="Something went wrong signing in.")
            return

        self._adopt_new_login(credentials)
        self._commit(is_signing_in=False)
        self._refresh_worker_blocking()

    def import_claude_code_login(self) -> bool:
        imported = creds.import_from_claude_code()
        if imported is None:
            self._commit(sign_in_error="No Claude Code login found on this machine.")
            return False
        self._adopt_new_login(imported)
        self._commit(sign_in_error=None)
        self.refresh()
        return True

    def sign_out(self) -> None:
        with self._lock:
            self._credentials = None
            self._epoch += 1
        self._credential_store.clear()
        self._commit(phase=SIGNED_OUT, snapshot=None, error=None, last_updated=None, sign_in_error=None)

    def _adopt(self, credentials: creds.Credentials) -> None:
        self._credentials = credentials
        self._credential_store.save(credentials)

    def _adopt_new_login(self, credentials: creds.Credentials) -> None:
        with self._lock:
            self._epoch += 1
            self._adopt(credentials)
        self._commit(phase=LOADING, snapshot=None, error=None)

    def _refresh_worker_blocking(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        self._refresh_worker()
