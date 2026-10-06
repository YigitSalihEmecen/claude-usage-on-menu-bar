"""User-visible settings, persisted as JSON under ``~/.config/claude-usage``."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

DISPLAY_OPTIONS = {
    "percentAndTime": "Usage and reset",
    "percent": "Usage only",
    "time": "Reset only",
    "iconOnly": "Icon only",
}
REFRESH_OPTIONS = [30, 60, 120, 300]
WARN_RANGE = (0.5, 0.95)

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Claude Usage
Comment=Claude usage limits in your system tray
Exec=claude-usage --background
Icon=io.github.YigitSalihEmecen.ClaudeUsage
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""


class Preferences:
    """Observable settings. Assigning a property saves it and notifies observers."""

    def __init__(self, path: Path | None = None, autostart_file: Path | None = None):
        self._path = path
        self._autostart_file = autostart_file
        self._observers: list[Callable[[str], None]] = []

        self._display = "percentAndTime"
        self._refresh_interval = 60
        self._warn_threshold = 0.8
        self._show_context_in_tray = False

        self._load()

    # MARK: - Properties

    @property
    def display(self) -> str:
        return self._display

    @display.setter
    def display(self, value: str) -> None:
        if value in DISPLAY_OPTIONS:
            self._set("display", value)

    @property
    def refresh_interval(self) -> int:
        return self._refresh_interval

    @refresh_interval.setter
    def refresh_interval(self, value: int) -> None:
        if value in REFRESH_OPTIONS:
            self._set("refresh_interval", value)

    @property
    def warn_threshold(self) -> float:
        return self._warn_threshold

    @warn_threshold.setter
    def warn_threshold(self, value: float) -> None:
        low, high = WARN_RANGE
        self._set("warn_threshold", round(min(max(value, low), high), 2))

    @property
    def show_context_in_tray(self) -> bool:
        return self._show_context_in_tray

    @show_context_in_tray.setter
    def show_context_in_tray(self, value: bool) -> None:
        self._set("show_context_in_tray", bool(value))

    @property
    def launch_at_login(self) -> bool:
        return self.autostart_file.is_file()

    @launch_at_login.setter
    def launch_at_login(self, enabled: bool) -> None:
        file = self.autostart_file
        try:
            if enabled:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(DESKTOP_ENTRY)
            else:
                file.unlink(missing_ok=True)
        except OSError as error:
            log.warning("could not update autostart entry: %s", error)
        self._notify("launch_at_login")

    # MARK: - Derived

    @property
    def shows_percent(self) -> bool:
        return self._display in ("percentAndTime", "percent")

    @property
    def shows_time(self) -> bool:
        return self._display in ("percentAndTime", "time")

    @property
    def path(self) -> Path:
        return self._path or paths.config_dir() / "settings.json"

    @property
    def autostart_file(self) -> Path:
        return self._autostart_file or paths.autostart_dir() / "claude-usage.desktop"

    # MARK: - Observation

    def subscribe(self, observer: Callable[[str], None]) -> None:
        self._observers.append(observer)

    def _notify(self, name: str) -> None:
        for observer in list(self._observers):
            observer(name)

    # MARK: - Persistence

    def _set(self, name: str, value: object) -> None:
        if getattr(self, f"_{name}") == value:
            return
        setattr(self, f"_{name}", value)
        self._save()
        self._notify(name)

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return

        if data.get("display") in DISPLAY_OPTIONS:
            self._display = data["display"]
        if data.get("refresh_interval") in REFRESH_OPTIONS:
            self._refresh_interval = data["refresh_interval"]
        warn = data.get("warn_threshold")
        if isinstance(warn, (int, float)) and not isinstance(warn, bool):
            self._warn_threshold = round(min(max(warn, WARN_RANGE[0]), WARN_RANGE[1]), 2)
        if isinstance(data.get("show_context_in_tray"), bool):
            self._show_context_in_tray = data["show_context_in_tray"]

    def _save(self) -> None:
        data = {
            "display": self._display,
            "refresh_interval": self._refresh_interval,
            "warn_threshold": self._warn_threshold,
            "show_context_in_tray": self._show_context_in_tray,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2) + "\n")
            os.replace(temporary, self.path)
        except OSError as error:
            log.warning("could not save settings: %s", error)
