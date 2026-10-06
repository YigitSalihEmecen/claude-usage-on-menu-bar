"""The pages shown inside the panel: usage, sign-in, and settings."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gtk

from .. import __version__, formatting
from ..palette import usage_tone
from ..preferences import DISPLAY_OPTIONS, REFRESH_OPTIONS
from ..snapshot import ExtraUsage, UsageSnapshot
from ..store import UsageStore
from .widgets import ContextRow, Ring, UsageBar, WindowRow, label

MARGIN = 16
MANAGE_PLAN_URL = "https://claude.ai/settings/usage"


def _separator() -> Gtk.Separator:
    return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)


def _padded(child: Gtk.Widget, vertical: int, horizontal: int = MARGIN) -> Gtk.Widget:
    box = Gtk.Box()
    box.set_margin_top(vertical)
    box.set_margin_bottom(vertical)
    box.set_margin_start(horizontal)
    box.set_margin_end(horizontal)
    box.pack_start(child, True, True, 0)
    return box


# MARK: - Usage


class SessionHeader(Gtk.Box):
    """The ring on the left, the countdown to the session reset on the right."""

    def __init__(self) -> None:
        super().__init__(spacing=18)
        self.ring = Ring()
        self._countdown = label("", "big-number")
        self._until = label("until reset", "dim")
        self._reset_at = label("", "caption")
        self._idle = label("No active window", "dim")
        self._idle_hint = label("Your 5-hour limit starts on your next message.", "caption")
        self._idle_hint.set_line_wrap(True)
        self._idle_hint.set_max_width_chars(24)
        self._active = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._inactive = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
        text.pack_start(label("Session", "section-title"), False, False, 0)
        for widget in (self._countdown, self._until, self._reset_at):
            self._active.pack_start(widget, False, False, 0)
        self._inactive.pack_start(self._idle, False, False, 0)
        self._inactive.pack_start(self._idle_hint, False, False, 0)
        text.pack_start(self._active, False, False, 0)
        text.pack_start(self._inactive, False, False, 0)
        for box in (self._active, self._inactive):
            box.show_all()
            box.set_no_show_all(True)  # toggled with set_visible from now on

        self.pack_start(self.ring, False, False, 0)
        self.pack_start(text, True, True, 0)

    def update(self, snapshot: UsageSnapshot, warn: float, now=None) -> None:
        session = snapshot.session
        fraction = session.fraction if session else 0.0
        self.ring.update(fraction, usage_tone(fraction, warn))

        resets_at = session.resets_at if session else None
        if resets_at:
            self._countdown.set_text(formatting.countdown(resets_at, now))
            self._reset_at.set_text(formatting.reset_time(resets_at))
        self._active.set_visible(resets_at is not None)
        self._inactive.set_visible(resets_at is None)


class ExtraUsageRow(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header = Gtk.Box(spacing=8)
        self._amount = label("", "caption", xalign=1.0)
        header.pack_start(label("Extra usage", "section-title"), True, True, 0)
        header.pack_end(self._amount, False, False, 0)
        self._bar = UsageBar()
        self.pack_start(header, False, False, 0)
        self.pack_start(self._bar, False, False, 0)

    def update(self, extra: ExtraUsage, warn: float) -> None:
        if extra.used_credits is not None and extra.monthly_limit is not None:
            self._amount.set_text(f"${extra.used_credits:.2f} of ${extra.monthly_limit:.0f}")
        self._bar.set_visible(extra.fraction is not None)
        if extra.fraction is not None:
            self._bar.update(extra.fraction, usage_tone(extra.fraction, warn))


class ReadyView(Gtk.Box):
    """Everything shown once usage has loaded. Widgets are reused between updates;
    the layout is rebuilt only when the set of windows changes, so a refresh never
    makes the panel flicker."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._layout: tuple | None = None
        self._header = SessionHeader()
        self._rows: dict[str, WindowRow] = {}
        self._context = ContextRow()
        self._extra = ExtraUsageRow()
        self._updated = label("", "caption")
        self._body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pack_start(self._body, False, False, 0)

    def update(self, store: UsageStore, now=None) -> None:
        snapshot = store.snapshot
        if snapshot is None:
            return
        warn = store.preferences.warn_threshold
        others = [w for w in snapshot.windows if w.kind != "session"]
        context = store.context_usage
        extra = snapshot.extra if snapshot.extra and snapshot.extra.is_enabled else None

        layout = (tuple(w.id for w in others), context is not None, extra is not None)
        if layout != self._layout:
            self._rebuild(others, context is not None, extra is not None)
            self._layout = layout

        self._header.update(snapshot, warn, now)
        for window in others:
            self._rows[window.id].update(window, warn, now)
        if context:
            self._context.update(context, warn)
        if extra:
            self._extra.update(extra, warn)
        if store.last_updated:
            self._updated.set_text(f"Updated {formatting.relative(store.last_updated, now)}")

    def _rebuild(self, others, has_context: bool, has_extra: bool) -> None:
        # Long-lived widgets must leave their old padding boxes before being re-packed.
        for widget in (self._header, self._context, self._extra, self._updated):
            if widget.get_parent() is not None:
                widget.get_parent().remove(widget)
        for child in self._body.get_children():
            self._body.remove(child)
        self._rows = {w.id: WindowRow() for w in others}

        self._body.pack_start(_padded(self._header, 16), False, False, 0)

        if others:
            self._body.pack_start(_separator(), False, False, 0)
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            for window in others:
                column.pack_start(self._rows[window.id], False, False, 0)
            self._body.pack_start(_padded(column, 14), False, False, 0)
        if has_context:
            self._body.pack_start(_separator(), False, False, 0)
            self._body.pack_start(_padded(self._context, 12), False, False, 0)
        if has_extra:
            self._body.pack_start(_separator(), False, False, 0)
            self._body.pack_start(_padded(self._extra, 12), False, False, 0)

        footer = Gtk.Box()
        footer.pack_start(self._updated, True, True, 0)
        link = Gtk.LinkButton.new_with_label(MANAGE_PLAN_URL, "Manage plan")
        link.get_style_context().add_class("caption")
        footer.pack_end(link, False, False, 0)
        self._body.pack_start(_separator(), False, False, 0)
        self._body.pack_start(_padded(footer, 6), False, False, 0)
        self._body.show_all()


class Placeholder(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_top(34)
        self.set_margin_bottom(34)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.spinner = Gtk.Spinner()
        self.message = label("", "dim", xalign=0.5)
        self.message.set_line_wrap(True)
        self.message.set_justify(Gtk.Justification.CENTER)
        self.retry = Gtk.Button(label="Try again")
        self.retry.set_halign(Gtk.Align.CENTER)
        for widget in (self.spinner, self.message, self.retry):
            self.pack_start(widget, False, False, 0)
        for widget in (self.spinner, self.retry):
            widget.set_no_show_all(True)  # toggled with set_visible from now on

    def show_loading(self) -> None:
        self.spinner.start()
        self.message.set_text("Reading your usage…")
        self.spinner.show()
        self.message.show()
        self.retry.hide()

    def show_error(self, text: str) -> None:
        self.spinner.stop()
        self.message.set_text(text)
        self.spinner.set_visible(False)
        self.retry.set_visible(True)


# MARK: - Sign-in


class SignInView(Gtk.Box):
    """Browser OAuth, with a paste-the-code fallback."""

    def __init__(self, store: UsageStore, open_url: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._store = store
        self._open_url = open_url
        self._manual_session = None

        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        intro.set_margin_top(22)
        intro.set_margin_bottom(16)
        intro.set_margin_start(24)
        intro.set_margin_end(24)
        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic", Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class("dim")
        intro.pack_start(icon, False, False, 0)
        intro.pack_start(label("Connect your Claude account", "section-title", xalign=0.5), False, False, 0)
        blurb = label(
            "Sign in to see how much of your session and weekly limits you have used.",
            "dim",
            xalign=0.5,
        )
        blurb.set_line_wrap(True)
        blurb.set_justify(Gtk.Justification.CENTER)
        blurb.set_max_width_chars(34)
        intro.pack_start(blurb, False, False, 0)
        self.pack_start(intro, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        buttons.set_margin_start(MARGIN)
        buttons.set_margin_end(MARGIN)

        self._browser = Gtk.Button()
        self._browser.get_style_context().add_class("clay")
        self._spinner = Gtk.Spinner()
        self._browser_label = Gtk.Label(label="Sign in with browser")
        inner = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        inner.pack_start(self._spinner, False, False, 0)
        inner.pack_start(self._browser_label, False, False, 0)
        self._browser.add(inner)
        self._browser.connect("clicked", lambda *_: store.sign_in_with_browser(open_url))
        buttons.pack_start(self._browser, False, False, 0)

        self._import = Gtk.Button(label="Use my Claude Code login")
        self._import.connect("clicked", lambda *_: store.import_claude_code_login())
        buttons.pack_start(self._import, False, False, 0)

        self._cancel = Gtk.Button(label="Cancel")
        self._cancel.get_style_context().add_class("flat")
        self._cancel.connect("clicked", lambda *_: store.cancel_sign_in())
        buttons.pack_start(self._cancel, False, False, 0)
        self.pack_start(buttons, False, False, 0)

        self._error = label("", "caption", "warning-text", xalign=0.5)
        self._error.set_line_wrap(True)
        self._error.set_justify(Gtk.Justification.CENTER)
        self._error.set_margin_top(10)
        self._error.set_margin_start(20)
        self._error.set_margin_end(20)
        self.pack_start(self._error, False, False, 0)

        self._fallback = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self._fallback.set_margin_top(12)
        self._fallback.set_margin_bottom(16)
        self._fallback.set_margin_start(MARGIN)
        self._fallback.set_margin_end(MARGIN)

        self._manual_button = Gtk.Button(label="Browser did not open?")
        self._manual_button.get_style_context().add_class("flat")
        self._manual_button.connect("clicked", self._begin_manual)
        self._fallback.pack_start(self._manual_button, False, False, 0)

        self._manual_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self._manual_box.pack_start(label("Paste the code Claude showed you.", "caption"), False, False, 0)
        row = Gtk.Box(spacing=6)
        self._code = Gtk.Entry(placeholder_text="Authorization code", hexpand=True)
        self._code.connect("activate", self._submit)
        self._done = Gtk.Button(label="Done")
        self._done.connect("clicked", self._submit)
        row.pack_start(self._code, True, True, 0)
        row.pack_start(self._done, False, False, 0)
        self._manual_box.pack_start(row, False, False, 0)
        self._fallback.pack_start(self._manual_box, False, False, 0)
        self.pack_start(self._fallback, False, False, 0)

        self.show_all()
        for widget in (self._spinner, self._import, self._cancel, self._error, self._manual_box):
            widget.set_no_show_all(True)  # toggled with set_visible from now on
        self._manual_box.hide()  # revealed by "Browser did not open?"
        self.update()

    def update(self) -> None:
        store = self._store
        signing_in = store.is_signing_in
        self._browser.set_sensitive(not signing_in)
        self._browser_label.set_text("Waiting for browser…" if signing_in else "Sign in with browser")
        self._spinner.set_visible(signing_in)
        if signing_in:
            self._spinner.start()
        else:
            self._spinner.stop()
        self._import.set_visible(store.import_available and not signing_in)
        self._cancel.set_visible(signing_in)
        self._done.set_sensitive(not signing_in)
        self._error.set_text(store.sign_in_error or "")
        self._error.set_visible(bool(store.sign_in_error))

    def _begin_manual(self, *_) -> None:
        self._manual_session = self._store.begin_manual_sign_in()
        self._open_url(self._manual_session.url)
        self._manual_button.hide()
        self._manual_box.set_no_show_all(False)
        self._manual_box.show_all()
        self._code.grab_focus()

    def _submit(self, *_) -> None:
        code = self._code.get_text().strip()
        if not code or self._manual_session is None or self._store.is_signing_in:
            return
        self._code.set_text("")
        self._store.complete_manual_sign_in(code, self._manual_session)


# MARK: - Settings


class SettingsView(Gtk.Box):
    def __init__(self, store: UsageStore, quit_app: Callable[[], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._store = store
        prefs = store.preferences
        self._prefs = prefs

        grid = Gtk.Grid(row_spacing=12, column_spacing=12)
        grid.set_margin_top(14)
        grid.set_margin_bottom(14)
        grid.set_margin_start(MARGIN)
        grid.set_margin_end(MARGIN)

        self._display = Gtk.ComboBoxText()
        for key, text in DISPLAY_OPTIONS.items():
            self._display.append(key, text)
        self._display.set_active_id(prefs.display)
        self._display.connect("changed", lambda c: setattr(prefs, "display", c.get_active_id()))

        self._refresh = Gtk.ComboBoxText()
        for seconds in REFRESH_OPTIONS:
            self._refresh.append(str(seconds), f"{seconds} sec" if seconds < 60 else f"{seconds // 60} min")
        self._refresh.set_active_id(str(prefs.refresh_interval))
        self._refresh.connect("changed", lambda c: setattr(prefs, "refresh_interval", int(c.get_active_id())))

        self._warn = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 95, 5)
        self._warn.set_draw_value(False)
        self._warn.set_value(round(prefs.warn_threshold * 100))
        self._warn.set_hexpand(True)
        self._warn_value = label(f"{round(prefs.warn_threshold * 100)}%", "dim", xalign=1.0)
        self._warn_value.set_width_chars(4)
        self._warn.connect("value-changed", self._warn_changed)
        warn_box = Gtk.Box(spacing=6)
        warn_box.pack_start(self._warn, True, True, 0)
        warn_box.pack_start(self._warn_value, False, False, 0)

        self._context = Gtk.Switch(active=prefs.show_context_in_tray, halign=Gtk.Align.START)
        self._context.connect(
            "notify::active", lambda s, _: setattr(prefs, "show_context_in_tray", s.get_active())
        )

        self._login = Gtk.Switch(active=prefs.launch_at_login, halign=Gtk.Align.START)
        self._login.connect("notify::active", lambda s, _: setattr(prefs, "launch_at_login", s.get_active()))

        rows = [
            ("Tray label", self._display),
            ("Refresh", self._refresh),
            ("Warn above", warn_box),
            ("Context in tray", self._context),
            ("Start at login", self._login),
        ]
        for index, (title, widget) in enumerate(rows):
            grid.attach(label(title), 0, index, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, index, 1, 1)
        self.pack_start(grid, False, False, 0)
        self.pack_start(_separator(), False, False, 0)

        account = Gtk.Box()
        self._account = label("", "section-title")
        self._sign_out = Gtk.Button(label="Sign out")
        self._sign_out.set_no_show_all(True)  # toggled with set_visible
        self._sign_out.connect("clicked", lambda *_: store.sign_out())
        account.pack_start(self._account, True, True, 0)
        account.pack_end(self._sign_out, False, False, 0)
        self.pack_start(_padded(account, 12), False, False, 0)
        self.pack_start(_separator(), False, False, 0)

        footer = Gtk.Box()
        footer.pack_start(label(f"Claude Usage {__version__}", "caption"), True, True, 0)
        quit_button = Gtk.LinkButton.new_with_label("", "Quit")
        quit_button.connect("activate-link", lambda *_: quit_app() or True)
        footer.pack_end(quit_button, False, False, 0)
        self.pack_start(_padded(footer, 6), False, False, 0)

        self.update()

    def _warn_changed(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        self._warn_value.set_text(f"{value}%")
        self._prefs.warn_threshold = value / 100

    def update(self) -> None:
        self._account.set_text("Signed in" if self._store.is_signed_in else "Not signed in")
        self._sign_out.set_visible(self._store.is_signed_in)
