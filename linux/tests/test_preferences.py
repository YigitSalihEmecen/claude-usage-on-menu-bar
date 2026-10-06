import json
import tempfile
import unittest
from pathlib import Path

from claude_usage.preferences import Preferences


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def make(self) -> Preferences:
        return Preferences(self.dir / "settings.json", self.dir / "autostart" / "claude-usage.desktop")

    def test_defaults(self):
        prefs = self.make()

        self.assertEqual(prefs.display, "percentAndTime")
        self.assertEqual(prefs.refresh_interval, 60)
        self.assertEqual(prefs.warn_threshold, 0.8)
        self.assertFalse(prefs.show_context_in_tray)
        self.assertFalse(prefs.launch_at_login)

    def test_changes_persist_across_instances(self):
        prefs = self.make()
        prefs.display = "percent"
        prefs.refresh_interval = 300
        prefs.warn_threshold = 0.65
        prefs.show_context_in_tray = True

        again = self.make()

        self.assertEqual(again.display, "percent")
        self.assertEqual(again.refresh_interval, 300)
        self.assertEqual(again.warn_threshold, 0.65)
        self.assertTrue(again.show_context_in_tray)

    def test_invalid_values_are_ignored(self):
        prefs = self.make()
        prefs.display = "bogus"
        prefs.refresh_interval = 7

        self.assertEqual(prefs.display, "percentAndTime")
        self.assertEqual(prefs.refresh_interval, 60)

    def test_warn_threshold_is_clamped(self):
        prefs = self.make()
        prefs.warn_threshold = 5
        self.assertEqual(prefs.warn_threshold, 0.95)
        prefs.warn_threshold = 0
        self.assertEqual(prefs.warn_threshold, 0.5)

    def test_corrupt_settings_fall_back_to_defaults(self):
        (self.dir / "settings.json").write_text(
            json.dumps(
                {"display": 3, "refresh_interval": "x", "warn_threshold": "y", "show_context_in_tray": "yes"}
            )
        )

        prefs = self.make()

        self.assertEqual(
            (prefs.display, prefs.refresh_interval, prefs.warn_threshold), ("percentAndTime", 60, 0.8)
        )
        self.assertFalse(prefs.show_context_in_tray)

    def test_unparseable_settings_fall_back_to_defaults(self):
        (self.dir / "settings.json").write_text("{nope")
        self.assertEqual(self.make().refresh_interval, 60)

    def test_observers_hear_about_changes_only(self):
        prefs = self.make()
        heard = []
        prefs.subscribe(heard.append)

        prefs.display = "time"
        prefs.display = "time"  # unchanged

        self.assertEqual(heard, ["display"])

    def test_launch_at_login_writes_and_removes_an_autostart_entry(self):
        prefs = self.make()

        prefs.launch_at_login = True
        entry = prefs.autostart_file.read_text()
        self.assertIn("Exec=claude-usage --background", entry)
        self.assertTrue(prefs.launch_at_login)

        prefs.launch_at_login = False
        self.assertFalse(prefs.autostart_file.exists())
        prefs.launch_at_login = False  # removing twice is harmless

    def test_display_helpers(self):
        prefs = self.make()
        for display, percent, time_ in [
            ("percentAndTime", True, True),
            ("percent", True, False),
            ("time", False, True),
            ("iconOnly", False, False),
        ]:
            prefs.display = display
            self.assertEqual((prefs.shows_percent, prefs.shows_time), (percent, time_), display)


if __name__ == "__main__":
    unittest.main()
