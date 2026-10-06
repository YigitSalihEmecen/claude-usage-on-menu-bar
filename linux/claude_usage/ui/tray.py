"""The system tray indicator: a progress ring, a label, and a menu.

Tray hosts only render menus, not arbitrary widgets, so the menu carries a text
summary and the "Open" item brings up the full panel.
"""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import Gtk

from .. import APP_ID, formatting
from ..palette import usage_tone
from ..store import FAILED, UsageStore
from .icons import TrayIcons

#: Widest label the tray will ever show; lets the host reserve room so the
#: panel does not jitter as the text changes.
LABEL_GUIDE = "100% · 99d23h · ctx 100%"


class Tray:
    def __init__(
        self, store: UsageStore, open_panel: Callable[[], None], quit_app: Callable[[], None]
    ) -> None:
        self._store = store
        self._open_panel = open_panel
        self._quit = quit_app
        self._icons = TrayIcons()
        self._drawn: tuple | None = None
        self._info_items: list[Gtk.MenuItem] = []

        icon = self._icons.name_for(None, "clay")
        self.indicator = AppIndicator.Indicator.new_with_path(
            APP_ID, icon, AppIndicator.IndicatorCategory.APPLICATION_STATUS, str(self._icons.directory)
        )
        self.indicator.set_title("Claude Usage")
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        self._menu = Gtk.Menu()
        self.indicator.set_menu(self._menu)
        self._build_menu([])

        store.subscribe(self.render)
        store.preferences.subscribe(lambda _name: self.render())
        self.render()

    # MARK: - Rendering

    def render(self) -> None:
        store, prefs = self._store, self._store.preferences
        snapshot = store.snapshot
        session = snapshot.session if snapshot else None
        fraction = session.fraction if session else None
        tone = usage_tone(fraction or 0.0, prefs.warn_threshold)

        parts: list[str] = []
        if not store.is_signed_in:
            parts.append("Sign in")
        else:
            if prefs.shows_percent and session:
                parts.append(f"{session.percent}%")
            if prefs.shows_time and session and session.resets_at:
                parts.append(formatting.countdown(session.resets_at, compact=True))
            if prefs.show_context_in_tray and store.context_usage:
                parts.append(f"ctx {store.context_usage.percent}%")
        text = " · ".join(parts)
        rows = self._summary()

        state = (fraction, tone, text, tuple(rows))
        if state == self._drawn:
            return
        self._drawn = state

        self.indicator.set_icon_full(self._icons.name_for(fraction, tone), "Claude usage")
        self.indicator.set_label(text, LABEL_GUIDE)
        self._set_rows(rows)

    def _summary(self) -> list[str]:
        store = self._store
        if not store.is_signed_in:
            return ["Not signed in"]
        rows: list[str] = []
        snapshot = store.snapshot
        if snapshot is None:
            rows.append(store.error if store.phase == FAILED and store.error else "Reading your usage…")
        else:
            for window in snapshot.windows:
                reset = f" · resets in {formatting.countdown(window.resets_at)}" if window.resets_at else ""
                rows.append(f"{window.title}  {window.percent}%{reset}")
            if not snapshot.windows:
                rows.append("No active usage windows")
        if store.context_usage:
            context = store.context_usage
            rows.append(
                f"Context ({context.project})  {context.percent}% · "
                f"{formatting.tokens(context.tokens)} of {formatting.compact_tokens(context.limit)}"
            )
        return rows

    # MARK: - Menu

    def _build_menu(self, rows: list[str]) -> None:
        for child in self._menu.get_children():
            self._menu.remove(child)
        self._info_items = []

        for text in rows:
            item = Gtk.MenuItem.new_with_label(text)
            item.connect("activate", lambda *_: self._open_panel())
            self._menu.append(item)
            self._info_items.append(item)
        if rows:
            self._menu.append(Gtk.SeparatorMenuItem())

        open_item = Gtk.MenuItem.new_with_label("Open Claude Usage")
        open_item.connect("activate", lambda *_: self._open_panel())
        self._menu.append(open_item)

        refresh = Gtk.MenuItem.new_with_label("Refresh now")
        refresh.connect("activate", lambda *_: self._store.refresh())
        self._menu.append(refresh)

        self._menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem.new_with_label("Quit")
        quit_item.connect("activate", lambda *_: self._quit())
        self._menu.append(quit_item)

        self._menu.show_all()
        self.indicator.set_secondary_activate_target(open_item)

    def _set_rows(self, rows: list[str]) -> None:
        if len(rows) != len(self._info_items):
            self._build_menu(rows)
        else:
            for item, text in zip(self._info_items, rows, strict=True):
                item.set_label(text)
