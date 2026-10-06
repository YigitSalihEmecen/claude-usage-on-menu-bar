"""Claude's warm palette: one source for the panel meters and the tray icon."""

from __future__ import annotations

from typing import NamedTuple


class Hue(NamedTuple):
    red: int
    green: int
    blue: int

    @property
    def hex(self) -> str:
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"

    @property
    def rgb(self) -> tuple[float, float, float]:
        return self.red / 255, self.green / 255, self.blue / 255


#: Claude clay: the resting accent for usage meters.
CLAY = Hue(0xD9, 0x77, 0x57)
#: Amber: past the warn threshold.
AMBER = Hue(0xE3, 0x96, 0x2E)
#: Warm red: nearly exhausted. Kept in the same family as clay.
EMBER = Hue(0xD2, 0x45, 0x3D)

TONES = {"clay": CLAY, "amber": AMBER, "ember": EMBER}


def usage_tone(fraction: float, warn_threshold: float) -> str:
    """Name of the colour a usage fraction should be drawn in."""
    if fraction >= 0.95:
        return "ember"
    if fraction >= warn_threshold:
        return "amber"
    return "clay"


def usage_hue(fraction: float, warn_threshold: float) -> Hue:
    return TONES[usage_tone(fraction, warn_threshold)]
