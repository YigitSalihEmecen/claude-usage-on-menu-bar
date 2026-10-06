"""Compact duration and timestamp formatting for the tray and panel."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def countdown(to: datetime, now: datetime | None = None, compact: bool = False) -> str:
    """'2h 14m', '48m', '<1m': tuned to stay short in the tray."""
    remaining = int((to - (now or _now())).total_seconds())
    if remaining <= 0:
        return "now"

    hours, minutes = remaining // 3600, (remaining % 3600) // 60
    gap = "" if compact else " "

    if hours >= 24:
        return f"{hours // 24}d{gap}{hours % 24}h"
    if hours > 0:
        return f"{hours}h{gap}{minutes}m"
    return f"{minutes}m" if minutes > 0 else "<1m"


def reset_time(date: datetime) -> str:
    """'Fri 9:00 AM' or 'Fri 09:00', following the locale's clock style."""
    local = date.astimezone()
    if time.strftime("%p", local.timetuple()):
        return f"{local:%a} {local.hour % 12 or 12}:{local:%M} {local:%p}"
    return f"{local:%a %H:%M}"


def tokens(count: int) -> str:
    """'50,009': grouped, for the panel where there is room."""
    return f"{count:,}"


def compact_tokens(count: int) -> str:
    """'50K', '1.5M': for the context limit and the tray."""
    if count >= 1_000_000:
        millions = count / 1_000_000
        return f"{int(millions)}M" if millions == int(millions) else f"{millions:.1f}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)


def relative(date: datetime, now: datetime | None = None) -> str:
    seconds = int(((now or _now()) - date).total_seconds())
    if seconds < 5:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    return f"{seconds // 60}m ago"
