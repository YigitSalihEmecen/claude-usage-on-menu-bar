"""Filesystem locations, following the XDG base directory specification."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = "claude-usage"


def _xdg(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable)
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_DIR


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache") / APP_DIR


def autostart_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "autostart"


def claude_code_dir() -> Path:
    """Claude Code's own config directory, honouring its override variable."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".claude"
