"""Application entry point: wires the store, the tray, and the panel together."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__

log = logging.getLogger("claude_usage")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="claude-usage", description="Claude usage limits in your system tray."
    )
    parser.add_argument("--version", action="version", version=f"claude-usage {__version__}")
    parser.add_argument(
        "--background",
        action="store_true",
        help="start in the tray without opening the panel (used by Start at login)",
    )
    parser.add_argument("--verbose", action="store_true", help="log debugging information to stderr")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        from .ui.application import ClaudeUsageApplication
    except (ImportError, ValueError) as error:
        print(
            f"claude-usage: missing GTK or tray libraries ({error}).\n"
            "On Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0 "
            "gir1.2-ayatanaappindicator3-0.1 gir1.2-secret-1",
            file=sys.stderr,
        )
        return 1

    return ClaudeUsageApplication(background=args.background).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
