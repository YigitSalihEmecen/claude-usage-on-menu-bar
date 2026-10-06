"""Draws the tray's progress ring as SVG files.

Tray hosts load icons by name from disk, so each (percent, colour) pair is
written once to the cache directory and reused.
"""

from __future__ import annotations

import math
from pathlib import Path

from .. import paths
from ..palette import TONES
from ..snapshot import round_half_up

_RADIUS = 8.5
_CIRCUMFERENCE = 2 * math.pi * _RADIUS

_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="{r}" fill="none" stroke="{color}" stroke-opacity="0.3" stroke-width="3"/>
  {progress}
</svg>
"""
_ARC = (
    '<circle cx="12" cy="12" r="{r}" fill="none" stroke="{color}" stroke-width="3" '
    'stroke-linecap="round" stroke-dasharray="{arc:.2f} {circumference:.2f}" '
    'transform="rotate(-90 12 12)"/>'
)
_DOT = '<circle cx="12" cy="12" r="1.5" fill="{color}" fill-opacity="0.6"/>'


def render_svg(percent: int | None, tone: str) -> str:
    color = TONES[tone].hex
    if percent is None or percent <= 0:
        progress = _DOT.format(color=color)
    else:
        arc = _CIRCUMFERENCE * min(percent, 100) / 100
        progress = _ARC.format(r=_RADIUS, color=color, arc=arc, circumference=_CIRCUMFERENCE)
    return _TEMPLATE.format(r=_RADIUS, color=color, progress=progress)


class TrayIcons:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or paths.cache_dir() / "icons"
        self.directory.mkdir(parents=True, exist_ok=True)

    def name_for(self, fraction: float | None, tone: str) -> str:
        """Icon name for a usage fraction; creates the file on first use."""
        percent = None if fraction is None else min(max(round_half_up(fraction * 100), 0), 100)
        name = f"claude-usage-ring-{'idle' if percent is None else percent}-{tone}"
        file = self.directory / f"{name}.svg"
        if not file.exists():
            temporary = file.with_suffix(".tmp")
            temporary.write_text(render_svg(percent, tone))
            temporary.replace(file)
        return name
