"""Reusable usage indicators: the large session ring and the compact window bars."""

from __future__ import annotations

import math

import cairo
from gi.repository import Gtk, Pango

from .. import formatting
from ..context import ContextUsage
from ..palette import TONES, usage_tone
from ..snapshot import UsageWindow


def label(text: str = "", *classes: str, xalign: float = 0.0, ellipsize: bool = False) -> Gtk.Label:
    widget = Gtk.Label(label=text, xalign=xalign)
    for name in classes:
        widget.get_style_context().add_class(name)
    if ellipsize:
        widget.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    return widget


class Ring(Gtk.Overlay):
    """The large session ring with the percentage in the middle."""

    SIZE = 96
    LINE = 9

    def __init__(self) -> None:
        super().__init__()
        self._fraction = 0.0
        self._tone = "clay"

        area = Gtk.DrawingArea()
        area.set_size_request(self.SIZE, self.SIZE)
        area.connect("draw", self._draw)
        self.add(area)

        self._number = label("0", "ring-number", xalign=0.5)
        self._caption = label("PERCENT", "ring-caption", xalign=0.5)
        center = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER
        )
        center.pack_start(self._number, False, False, 0)
        center.pack_start(self._caption, False, False, 0)
        self.add_overlay(center)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.CENTER)

    def update(self, fraction: float, tone: str) -> None:
        self._fraction, self._tone = fraction, tone
        self._number.set_text(str(int(fraction * 100 + 0.5)))
        self.get_child().queue_draw()

    def _draw(self, area: Gtk.DrawingArea, cr: cairo.Context) -> bool:
        width, height = area.get_allocated_width(), area.get_allocated_height()
        radius = (min(width, height) - self.LINE) / 2
        cx, cy = width / 2, height / 2

        foreground = area.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        cr.set_line_width(self.LINE)
        cr.set_source_rgba(foreground.red, foreground.green, foreground.blue, 0.12)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()

        fraction = max(self._fraction, 0.001)
        red, green, blue = TONES[self._tone].rgb
        cr.set_source_rgb(red, green, blue)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        start = -math.pi / 2
        cr.arc(cx, cy, radius, start, start + 2 * math.pi * min(fraction, 1))
        cr.stroke()
        return False


class UsageBar(Gtk.ProgressBar):
    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True)
        self._tone: str | None = None

    def update(self, fraction: float, tone: str) -> None:
        self.set_fraction(fraction)
        if tone != self._tone:
            context = self.get_style_context()
            if self._tone:
                context.remove_class(self._tone)
            context.add_class(tone)
            self._tone = tone


class _Row(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.header = Gtk.Box(spacing=8)
        self.bar = UsageBar()
        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.bar, False, False, 0)


class WindowRow(_Row):
    """One usage window: title, percentage, bar, and when it resets."""

    def __init__(self) -> None:
        super().__init__()
        self._title = label("", "section-title")
        self._percent = label("", "dim", xalign=1.0)
        self._reset = label("", "caption")
        self._reset.set_no_show_all(True)  # shown only when there is a reset time
        self.header.pack_start(self._title, True, True, 0)
        self.header.pack_end(self._percent, False, False, 0)
        self.pack_start(self._reset, False, False, 0)

    def update(self, window: UsageWindow, warn: float, now=None) -> None:
        self._title.set_text(window.title)
        self._percent.set_text(f"{window.percent}%")
        self.bar.update(window.fraction, usage_tone(window.fraction, warn))
        if window.resets_at:
            self._reset.set_text(
                f"Resets in {formatting.countdown(window.resets_at, now)} · "
                f"{formatting.reset_time(window.resets_at)}"
            )
        self._reset.set_visible(window.resets_at is not None)


class ContextRow(_Row):
    """Context window of the most recent Claude Code session. Unlike the usage
    windows this is read from disk, so it carries the project it came from."""

    def __init__(self) -> None:
        super().__init__()
        self._amount = label("", "caption", xalign=1.0)
        self._percent = label("", "dim", xalign=1.0)
        self._project = label("", "caption", ellipsize=True)
        self.header.pack_start(label("Context", "section-title"), True, True, 0)
        self.header.pack_end(self._percent, False, False, 0)
        self.header.pack_end(self._amount, False, False, 0)
        self.pack_start(self._project, False, False, 0)

    def update(self, context: ContextUsage, warn: float) -> None:
        self._amount.set_text(
            f"{formatting.tokens(context.tokens)} / {formatting.compact_tokens(context.limit)}"
        )
        self._percent.set_text(f"{context.percent}%")
        self.bar.update(context.fraction, usage_tone(context.fraction, warn))
        self._project.set_text(context.project)
