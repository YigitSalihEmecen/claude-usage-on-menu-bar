"""Application-wide CSS."""

from gi.repository import Gdk, Gtk

CSS = b"""
.panel-title { font-weight: 600; }
.section-title { font-weight: 600; font-size: 0.92em; }
.big-number { font-size: 1.55em; font-weight: 500; }
.ring-number { font-size: 2.1em; font-weight: 500; }
.ring-caption { font-size: 0.65em; font-weight: 600; letter-spacing: 1px; opacity: 0.5; }
.dim { opacity: 0.65; }
.caption { font-size: 0.8em; opacity: 0.55; }
.warning-text { color: #E3962E; }

progressbar trough { min-height: 6px; border-radius: 3px; }
progressbar progress { min-height: 6px; border-radius: 3px; background-image: none; }
progressbar.clay progress { background-color: #D97757; }
progressbar.amber progress { background-color: #E3962E; }
progressbar.ember progress { background-color: #D2453D; }

button.clay { background-image: none; background-color: #D97757; border-color: #C26548;
              color: #FFFFFF; text-shadow: none; }
button.clay:hover { background-color: #E08565; }
button.clay:disabled { opacity: 0.6; }
"""


def install() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
