"""Normalized view of Anthropic's rate-limit windows.

Decodes either the legacy flat payload (``five_hour`` / ``seven_day`` / ...) or the
newer ``limits[]`` array, which takes precedence when present.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SESSION = "session"
WEEKLY = "weekly"
WEEKLY_SCOPED = "weeklyScoped"

_SORT_RANK = {SESSION: 0, WEEKLY: 1, WEEKLY_SCOPED: 2}


def round_half_up(value: float) -> int:
    """Rounds .5 away from zero, unlike ``round`` which rounds to even."""
    return int(math.floor(value + 0.5))


@dataclass(frozen=True)
class UsageWindow:
    id: str
    kind: str
    title: str
    #: Fraction in 0...1.
    fraction: float
    resets_at: datetime | None
    is_active: bool = True

    @property
    def percent(self) -> int:
        return round_half_up(self.fraction * 100)


@dataclass(frozen=True)
class ExtraUsage:
    is_enabled: bool
    monthly_limit: float | None
    used_credits: float | None
    fraction: float | None


@dataclass(frozen=True)
class UsageSnapshot:
    windows: list[UsageWindow] = field(default_factory=list)
    extra: ExtraUsage | None = None

    @property
    def session(self) -> UsageWindow | None:
        return next((w for w in self.windows if w.kind == SESSION), None)

    @property
    def weekly(self) -> UsageWindow | None:
        return next((w for w in self.windows if w.kind == WEEKLY), None)

    @property
    def scoped(self) -> list[UsageWindow]:
        return [w for w in self.windows if w.kind == WEEKLY_SCOPED]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> UsageSnapshot:
        windows: list[UsageWindow] = []

        limits = payload.get("limits")
        if isinstance(limits, list) and limits:
            scoped_index = 0
            for limit in limits:
                if not isinstance(limit, dict):
                    continue
                kind = _resolve_kind(limit)
                if kind is None:
                    continue
                model = (limit.get("scope") or {}).get("model") or {}
                name = model.get("display_name")
                if kind == SESSION:
                    window_id = "session"
                elif kind == WEEKLY:
                    window_id = "weekly"
                else:
                    scoped_index += 1
                    window_id = "weekly-" + (name.lower() if name else f"scoped-{scoped_index}")
                percent = limit.get("percent")
                if percent is None:
                    percent = limit.get("utilization")
                windows.append(
                    UsageWindow(
                        id=window_id,
                        kind=kind,
                        title=_label(kind, name),
                        fraction=_clamp(percent),
                        resets_at=parse_timestamp(limit.get("resets_at")),
                        is_active=limit.get("is_active", True) is not False,
                    )
                )

        if not windows:
            legacy = [
                ("session", SESSION, None, payload.get("five_hour")),
                ("weekly", WEEKLY, None, payload.get("seven_day")),
                ("weekly-opus", WEEKLY_SCOPED, "Opus", payload.get("seven_day_opus")),
                ("weekly-sonnet", WEEKLY_SCOPED, "Sonnet", payload.get("seven_day_sonnet")),
            ]
            for window_id, kind, name, window in legacy:
                if not isinstance(window, dict):
                    continue
                windows.append(
                    UsageWindow(
                        id=window_id,
                        kind=kind,
                        title=_label(kind, name),
                        fraction=_clamp(window.get("utilization")),
                        resets_at=parse_timestamp(window.get("resets_at")),
                    )
                )

        windows.sort(key=lambda w: (_SORT_RANK[w.kind], w.title))

        extra = None
        raw_extra = payload.get("extra_usage")
        if isinstance(raw_extra, dict):
            utilization = raw_extra.get("utilization")
            extra = ExtraUsage(
                is_enabled=bool(raw_extra.get("is_enabled", False)),
                monthly_limit=raw_extra.get("monthly_limit"),
                used_credits=raw_extra.get("used_credits"),
                fraction=_clamp(utilization) if utilization is not None else None,
            )

        return cls(windows=windows, extra=extra)


def _resolve_kind(limit: dict[str, Any]) -> str | None:
    kind = limit.get("kind")
    if kind == "session":
        return SESSION
    if kind == "weekly_all":
        return WEEKLY
    if kind == "weekly_scoped":
        return WEEKLY_SCOPED
    group = limit.get("group")
    if group == "session":
        return SESSION
    if group == "weekly":
        return WEEKLY
    return None


def _label(kind: str, model_name: str | None) -> str:
    if kind == SESSION:
        return "Session"
    if kind == WEEKLY:
        return "Weekly"
    return f"Weekly · {model_name}" if model_name else "Weekly · model"


def _clamp(percent: Any) -> float:
    if not isinstance(percent, (int, float)) or isinstance(percent, bool):
        return 0.0
    return min(max(percent / 100, 0.0), 1.0)


_FRACTION = re.compile(r"(\.\d+)")


def parse_timestamp(value: Any) -> datetime | None:
    """Parses an ISO 8601 timestamp, with or without fractional seconds."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    # fromisoformat accepts exactly 3 or 6 fractional digits before 3.11.
    text = _FRACTION.sub(lambda m: (m.group(1) + "000000")[:7], text, count=1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
