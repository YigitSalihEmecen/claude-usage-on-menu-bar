import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from claude_usage.ui.icons import TrayIcons, render_svg


class TrayIconTests(unittest.TestCase):
    def test_every_percentage_renders_well_formed_svg(self):
        for percent in [None, 0, 1, 50, 99, 100]:
            for tone in ("clay", "amber", "ember"):
                with self.subTest(percent=percent, tone=tone):
                    root = ET.fromstring(render_svg(percent, tone))
                    self.assertTrue(root.tag.endswith("svg"))

    def test_empty_ring_is_a_dot_not_an_arc(self):
        self.assertNotIn("stroke-dasharray", render_svg(None, "clay"))
        self.assertNotIn("stroke-dasharray", render_svg(0, "clay"))
        self.assertIn("stroke-dasharray", render_svg(1, "clay"))

    def test_icons_are_written_once_and_named_by_state(self):
        with tempfile.TemporaryDirectory() as directory:
            icons = TrayIcons(Path(directory))

            name = icons.name_for(0.424, "amber")

            self.assertEqual(name, "claude-usage-ring-42-amber")
            self.assertTrue((Path(directory) / f"{name}.svg").is_file())
            self.assertEqual(icons.name_for(0.424, "amber"), name)
            self.assertEqual(icons.name_for(None, "clay"), "claude-usage-ring-idle-clay")

    def test_out_of_range_fractions_are_clamped(self):
        with tempfile.TemporaryDirectory() as directory:
            icons = TrayIcons(Path(directory))

            self.assertEqual(icons.name_for(7.0, "ember"), "claude-usage-ring-100-ember")
            self.assertEqual(icons.name_for(-1.0, "clay"), "claude-usage-ring-0-clay")


if __name__ == "__main__":
    unittest.main()
