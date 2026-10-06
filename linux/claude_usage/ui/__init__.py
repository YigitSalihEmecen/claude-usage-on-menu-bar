"""GTK 3 user interface: the tray indicator, the panel, and its pages.

The GObject Introspection versions are pinned here, so they are set before any
submodule imports ``gi.repository``.
"""

import contextlib

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
with contextlib.suppress(ValueError):  # no tray library: the app falls back to a panel-only mode
    gi.require_version("AyatanaAppIndicator3", "0.1")
