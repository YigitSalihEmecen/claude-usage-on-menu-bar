"""Smoke tests for the GTK widgets. Skipped when there is no display or no GTK."""

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gio, Gtk

    HAVE_DISPLAY = Gtk.init_check()[0]
except (ImportError, ValueError):
    HAVE_DISPLAY = False

from claude_usage import api
from claude_usage.credentials import Credentials, CredentialStore
from claude_usage.preferences import Preferences
from claude_usage.snapshot import UsageSnapshot
from claude_usage.store import FAILED, READY, UsageStore
from tests.test_credentials import Memory

_APP = None


def application():
    """One registered Gtk.Application for the whole run; D-Bus allows a single export."""
    global _APP
    if _APP is None:
        _APP = Gtk.Application(
            application_id="io.github.YigitSalihEmecen.ClaudeUsageTest", flags=Gio.ApplicationFlags.NON_UNIQUE
        )
        _APP.register(None)
    return _APP


def snapshot(session=42, resets=True, extra=False, scoped=False):
    when = (datetime.now(timezone.utc) + timedelta(hours=2, minutes=14)).isoformat()
    limits = [{"kind": "session", "percent": session, **({"resets_at": when} if resets else {})}]
    limits.append({"kind": "weekly_all", "percent": 38, "resets_at": when})
    if scoped:
        limits.append(
            {
                "kind": "weekly_scoped",
                "percent": 12,
                "resets_at": when,
                "scope": {"model": {"display_name": "Opus"}},
            }
        )
    payload = {"limits": limits}
    if extra:
        payload["extra_usage"] = {
            "is_enabled": True,
            "monthly_limit": 50,
            "used_credits": 4.25,
            "utilization": 8.5,
        }
    return UsageSnapshot.from_payload(payload)


def texts(widget):
    """Every visible label's text under a widget."""
    found = []

    def walk(node):
        if isinstance(node, Gtk.Label) and node.get_visible():
            found.append(node.get_text())
        if isinstance(node, Gtk.Container):
            for child in node.get_children():
                if child.get_visible():
                    walk(child)

    walk(widget)
    return found


@unittest.skipUnless(HAVE_DISPLAY, "needs a display (run under xvfb-run)")
class UiCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        env = mock.patch.dict(
            os.environ,
            {
                "CLAUDE_CONFIG_DIR": self._tmp.name,
                "XDG_CONFIG_HOME": self._tmp.name,
                "XDG_CACHE_HOME": self._tmp.name,
            },
        )
        env.start()
        self.addCleanup(env.stop)

        self.backend = Memory()
        self.backend.value = Credentials("at", "rt", time.time() + 3600).to_json()
        prefs = Preferences(Path(self._tmp.name) / "s.json", Path(self._tmp.name) / "a.desktop")
        self.store = UsageStore(
            prefs, CredentialStore([self.backend]), post=lambda fn: fn(), spawn=lambda fn: fn()
        )
        self.opened = []

    def fetch(self, snap):
        with mock.patch.object(api, "fetch", return_value=snap):
            self.store.refresh()

    def make_panel(self):
        from claude_usage.ui import style
        from claude_usage.ui.panel import Panel

        style.install()
        panel = Panel(application(), self.store, self.opened.append)
        self.addCleanup(panel.destroy)
        return panel


class PanelTests(UiCase):
    def test_shows_each_phase_on_the_right_page(self):
        panel = self.make_panel()
        stack = panel._usage_stack

        self.assertEqual(stack.get_visible_child_name(), "loading")  # stored login, nothing fetched yet

        self.fetch(snapshot())
        self.assertEqual(stack.get_visible_child_name(), READY)

        with mock.patch.object(api, "fetch", side_effect=api.RateLimited()):
            self.store.refresh()
        self.assertEqual(self.store.phase, FAILED)
        self.assertTrue(panel._placeholder.retry.get_visible())
        self.assertIn("rate-limiting", texts(panel._placeholder)[0])

        self.store.sign_out()
        self.assertEqual(stack.get_visible_child_name(), "signedOut")

    def test_ready_view_shows_usage_details(self):
        panel = self.make_panel()
        self.fetch(snapshot(session=42, extra=True, scoped=True))

        shown = texts(panel._ready)

        for expected in ("Session", "Weekly", "Weekly · Opus", "42", "38%", "Extra usage", "$4.25 of $50"):
            self.assertIn(expected, shown)
        self.assertTrue(any(t.startswith("2h 1") for t in shown), shown)

    def test_session_without_a_reset_explains_itself(self):
        panel = self.make_panel()
        self.fetch(snapshot(session=0, resets=False))

        shown = texts(panel._ready)

        self.assertIn("No active window", shown)
        self.assertNotIn("until reset", shown)

    def test_refreshing_reuses_widgets_unless_the_layout_changes(self):
        panel = self.make_panel()
        self.fetch(snapshot())
        first = panel._ready._body.get_children()[:]

        self.fetch(snapshot(session=55))
        self.assertEqual(panel._ready._body.get_children(), first)
        self.assertIn("55", texts(panel._ready))

        self.fetch(snapshot(scoped=True))
        self.assertNotEqual(panel._ready._body.get_children(), first)

    def test_warning_colours_follow_the_threshold(self):
        panel = self.make_panel()
        self.fetch(snapshot(session=85))
        self.assertEqual(panel._ready._header.ring._tone, "amber")

        self.fetch(snapshot(session=97))
        self.assertEqual(panel._ready._header.ring._tone, "ember")

        self.store.preferences.warn_threshold = 0.95
        self.fetch(snapshot(session=85))
        self.assertEqual(panel._ready._header.ring._tone, "clay")

    def test_settings_page_and_navigation(self):
        panel = self.make_panel()
        self.fetch(snapshot())

        panel._settings_button.clicked()
        self.assertEqual(panel._stack.get_visible_child_name(), "settings")
        self.assertTrue(panel._back.get_visible())
        self.assertFalse(panel._refresh_button.get_visible())

        panel._back.clicked()
        self.assertEqual(panel._stack.get_visible_child_name(), "usage")
        self.assertTrue(panel._refresh_button.get_visible())

    def test_settings_controls_write_through_to_preferences(self):
        panel = self.make_panel()
        settings, prefs = panel._settings, self.store.preferences

        settings._display.set_active_id("iconOnly")
        settings._refresh.set_active_id("300")
        settings._warn.set_value(65)
        settings._context.set_active(True)
        settings._login.set_active(True)

        self.assertEqual(prefs.display, "iconOnly")
        self.assertEqual(prefs.refresh_interval, 300)
        self.assertEqual(prefs.warn_threshold, 0.65)
        self.assertTrue(prefs.show_context_in_tray)
        self.assertTrue(prefs.autostart_file.is_file())

    def test_signing_out_from_settings(self):
        panel = self.make_panel()
        self.fetch(snapshot())

        panel._settings._sign_out.clicked()

        self.assertFalse(self.store.is_signed_in)
        self.assertFalse(panel._settings._sign_out.get_visible())

    def test_sign_in_page_reflects_progress_and_errors(self):
        self.store.sign_out()
        panel = self.make_panel()
        sign_in = panel._sign_in

        self.assertTrue(sign_in._browser.get_sensitive())
        self.assertFalse(sign_in._cancel.get_visible())
        self.assertFalse(sign_in._error.get_visible())
        self.assertFalse(sign_in._manual_box.get_visible())

        self.store.is_signing_in = True
        sign_in.update()
        self.assertFalse(sign_in._browser.get_sensitive())
        self.assertTrue(sign_in._cancel.get_visible())

        self.store.is_signing_in = False
        self.store.sign_in_error = "Port 54545 is in use."
        sign_in.update()
        self.assertEqual(sign_in._error.get_text(), "Port 54545 is in use.")
        self.assertTrue(sign_in._error.get_visible())

    def test_manual_fallback_opens_the_browser_and_reveals_the_code_field(self):
        self.store.sign_out()
        panel = self.make_panel()
        sign_in = panel._sign_in

        sign_in._manual_button.clicked()

        self.assertTrue(sign_in._manual_box.get_visible())
        self.assertFalse(sign_in._manual_button.get_visible())
        self.assertEqual(len(self.opened), 1)
        self.assertIn("claude.ai/oauth/authorize", self.opened[0])

    def test_closing_hides_instead_of_quitting(self):
        panel = self.make_panel()
        panel.show()

        self.assertTrue(panel._on_delete())
        self.assertFalse(panel.get_visible())


class TrayTests(UiCase):
    def make_tray(self):
        try:
            from claude_usage.ui.tray import Tray
        except (ImportError, ValueError):
            self.skipTest("AyatanaAppIndicator3 typelib not installed")
        tray = Tray(self.store, lambda: self.opened.append("panel"), lambda: self.opened.append("quit"))
        return tray

    def test_label_and_menu_follow_the_usage(self):
        tray = self.make_tray()
        self.fetch(snapshot(session=42, scoped=True))

        self.assertRegex(tray.indicator.get_label(), r"^42% · 2h1\dm$")
        self.assertEqual(
            [i.get_label()[:16] for i in tray._info_items][:2],
            ["Session  42% · resets"[:16], "Weekly  38% · re"[:16]],
        )

    def test_label_honours_the_display_preference(self):
        tray = self.make_tray()
        self.fetch(snapshot(session=42))

        for display, pattern in [
            ("percent", r"^42%$"),
            ("time", r"^2h1\dm$"),
            ("iconOnly", r"^$"),
        ]:
            with self.subTest(display=display):
                self.store.preferences.display = display
                self.assertRegex(tray.indicator.get_label() or "", pattern)

    def test_signed_out_prompts_to_sign_in(self):
        tray = self.make_tray()
        self.store.sign_out()

        self.assertEqual(tray.indicator.get_label(), "Sign in")
        self.assertEqual([i.get_label() for i in tray._info_items], ["Not signed in"])

    def test_menu_actions(self):
        tray = self.make_tray()
        self.fetch(snapshot())
        items = {i.get_label(): i for i in tray._menu.get_children() if isinstance(i, Gtk.MenuItem)}

        items["Open Claude Usage"].activate()
        items["Quit"].activate()

        self.assertEqual(self.opened, ["panel", "quit"])

    def test_icon_tracks_the_session_and_warning_tone(self):
        tray = self.make_tray()
        self.fetch(snapshot(session=85))

        self.assertEqual(tray.indicator.get_icon(), "claude-usage-ring-85-amber")


if __name__ == "__main__":
    unittest.main()
