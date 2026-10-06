"""The window opened from the tray: usage, sign-in, and settings."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gdk, GLib, Gtk

from .. import APP_ID
from ..store import LOADING, READY, SIGNED_OUT, UsageStore
from .pages import Placeholder, ReadyView, SettingsView, SignInView


class Panel(Gtk.ApplicationWindow):
    WIDTH = 330

    def __init__(
        self,
        application: Gtk.Application,
        store: UsageStore,
        open_url: Callable[[str], None],
        has_tray: bool = True,
    ) -> None:
        super().__init__(application=application, title="Claude Usage")
        self._store = store
        self._has_tray = has_tray
        self.set_resizable(False)
        self.set_default_size(self.WIDTH, 1)
        self.set_icon_name(APP_ID)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self._build_header(application)

        self._ready = ReadyView()
        self._placeholder = Placeholder()
        self._placeholder.retry.connect("clicked", lambda *_: store.refresh())
        self._sign_in = SignInView(store, open_url)

        self._usage_stack = Gtk.Stack()
        self._usage_stack.add_named(self._sign_in, SIGNED_OUT)
        self._usage_stack.add_named(self._placeholder, LOADING)
        self._usage_stack.add_named(self._ready, READY)
        self._usage_stack.set_vhomogeneous(False)
        self._usage_stack.set_hhomogeneous(True)

        self._settings = SettingsView(store, quit_app=application.quit)

        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=150)
        self._stack.set_vhomogeneous(False)
        self._stack.add_named(self._usage_stack, "usage")
        self._stack.add_named(self._settings, "settings")
        self.add(self._stack)
        self.set_size_request(self.WIDTH, -1)

        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key)
        self.connect("show", lambda *_: self._on_show())
        self._tick_source = 0

        store.subscribe(self.render)
        # A Gtk.Stack ignores requests to show a child that is not yet visible, so
        # realise every page before the first render.
        self.show_all()
        self.render()
        self.hide()

    # MARK: - Chrome

    def _build_header(self, application: Gtk.Application) -> None:
        bar = Gtk.HeaderBar(show_close_button=True, title="Claude Usage")
        self._back = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self._back.set_tooltip_text("Back")
        self._back.connect("clicked", lambda *_: self._show_settings(False))
        bar.pack_start(self._back)

        self._settings_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON)
        self._settings_button.set_tooltip_text("Settings")
        self._settings_button.connect("clicked", lambda *_: self._show_settings(True))
        bar.pack_end(self._settings_button)

        self._refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self._refresh_button.set_tooltip_text("Refresh now")
        self._refresh_button.connect("clicked", lambda *_: self._store.refresh())
        bar.pack_end(self._refresh_button)

        self._bar = bar
        self.set_titlebar(bar)
        bar.show_all()
        for button in (self._back, self._refresh_button):
            button.set_no_show_all(True)  # toggled with set_visible

    def _show_settings(self, visible: bool) -> None:
        self._stack.set_visible_child_name("settings" if visible else "usage")
        self._bar.set_title("Settings" if visible else "Claude Usage")
        self._back.set_visible(visible)
        self._settings_button.set_visible(not visible)
        self._refresh_button.set_visible(not visible and self._store.is_signed_in)
        self.set_focus(None)  # don't leave a focus ring on whichever control comes first

    # MARK: - State

    def render(self) -> None:
        store = self._store
        phase = store.phase

        if phase == READY:
            self._ready.update(store)
            self._usage_stack.set_visible_child_name(READY)
        elif phase == SIGNED_OUT:
            self._sign_in.update()
            self._usage_stack.set_visible_child_name(SIGNED_OUT)
        elif phase == LOADING:
            self._placeholder.show_loading()
            self._usage_stack.set_visible_child_name(LOADING)
        else:  # FAILED
            self._placeholder.show_error(store.error or "Something went wrong.")
            self._usage_stack.set_visible_child_name(LOADING)

        self._settings.update()
        self._refresh_button.set_visible(
            self._stack.get_visible_child_name() == "usage" and store.is_signed_in
        )
        self._refresh_button.set_sensitive(phase != LOADING)

    def tick(self) -> bool:
        """Keeps countdowns live while the panel is open."""
        if self._store.phase == READY:
            self._ready.update(self._store)
        return self.get_visible()

    # MARK: - Visibility

    def open(self) -> None:
        self._show_settings(False)
        self._store.refresh_if_stale()
        self.present()
        self._place()  # after present: the window manager ignores moves before the window is mapped

    def _on_show(self) -> None:
        if not self._tick_source:
            self._tick_source = GLib.timeout_add_seconds(1, self._tick_once)

    def _tick_once(self) -> bool:
        keep = self.tick()
        if not keep:
            self._tick_source = 0
        return keep

    def _place(self) -> None:
        """On X11, tuck the window under the tray, top right. Wayland compositors
        choose placement themselves, so there is nothing to do there."""
        display = Gdk.Display.get_default()
        if "X11" not in type(display).__name__:
            return
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor is None:
            return
        area = monitor.get_workarea()
        self.move(area.x + area.width - self.WIDTH - 12, area.y + 8)

    def _on_delete(self, *_) -> bool:
        if not self._has_tray:
            return False  # nothing to return to: closing the window ends the app
        self.hide()
        return True  # keep running in the tray

    def _on_key(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False
