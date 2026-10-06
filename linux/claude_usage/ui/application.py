"""The Gtk.Application: single instance, tray, panel, and the refresh timers."""

from __future__ import annotations

import logging
import signal
from pathlib import Path

from gi.repository import Gio, GLib, Gtk

from .. import APP_ID
from ..preferences import Preferences
from ..store import UsageStore
from . import style
from .panel import Panel

log = logging.getLogger(__name__)

#: How often the tray label is redrawn, so countdowns stay current between fetches.
REFRESH_TRAY_SECONDS = 15


def open_url(url: str) -> None:
    try:
        Gio.AppInfo.launch_default_for_uri(url, None)
    except GLib.Error as error:
        log.warning("could not open %s: %s", url, error.message)


def _post(fn) -> None:
    """Runs `fn` on the GLib main loop; safe to call from any thread."""
    GLib.idle_add(lambda: fn() or False)


class ClaudeUsageApplication(Gtk.Application):
    def __init__(self, background: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._background = background
        self._refresh_source = 0
        self.tray = None

    # MARK: - Lifecycle

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        for signum in (signal.SIGINT, signal.SIGTERM):  # Ctrl-C and `kill` quit cleanly
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._on_signal)
        style.install()
        self._add_dev_icon_path()

        self.preferences = Preferences()
        self.store = UsageStore(self.preferences, post=_post)

        try:
            from .tray import Tray
        except (ImportError, ValueError):
            Tray = None  # noqa: N806
            log.warning(
                "AyatanaAppIndicator3 is not installed, so there is no tray icon. "
                "Install gir1.2-ayatanaappindicator3-0.1 (Debian/Ubuntu)."
            )

        self.panel = Panel(self, self.store, open_url, has_tray=Tray is not None)
        if Tray is not None:
            self.hold()  # the app lives in the tray, not in a window
            self.tray = Tray(self.store, self.panel.open, self.quit)
            GLib.timeout_add_seconds(REFRESH_TRAY_SECONDS, self._tick_tray)

        self.preferences.subscribe(self._on_preference)
        self._schedule_refresh()
        self.store.refresh()
        self.store.refresh_context()

    def do_activate(self) -> None:
        # First launch: show the panel unless we were started silently at login.
        # Any later launch (from the app grid, say) brings the panel forward.
        log.debug("activate (background=%s)", self._background)
        if self._background and self.tray is not None:
            self._background = False
            return
        self.panel.open()

    def _on_signal(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    # MARK: - Timers

    def _schedule_refresh(self) -> None:
        if self._refresh_source:
            GLib.source_remove(self._refresh_source)
        self._refresh_source = GLib.timeout_add_seconds(
            self.preferences.refresh_interval, self._on_refresh_timer
        )

    def _on_refresh_timer(self) -> bool:
        self.store.refresh()
        self.store.refresh_context()
        return True

    def _tick_tray(self) -> bool:
        self.tray.render()
        return True

    def _on_preference(self, name: str) -> None:
        if name == "refresh_interval":
            self._schedule_refresh()

    # MARK: - Development

    @staticmethod
    def _add_dev_icon_path() -> None:
        """When run from a source checkout the icon is not installed system-wide."""
        icons = Path(__file__).resolve().parents[2] / "packaging" / "icons"
        if icons.is_dir():
            Gtk.IconTheme.get_default().append_search_path(str(icons))
