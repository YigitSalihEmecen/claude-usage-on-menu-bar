#!/usr/bin/env python3
"""Assembles GitHub release notes for a version.

    scripts/release-notes.py <tag> <checksums-file>

Fills .github/release-notes.md with the version's section of CHANGELOG.md and the
SHA-256 checksums of the release files, and prints the result.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def changelog_section(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text()
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M)
    if not match:
        raise SystemExit(f"CHANGELOG.md has no entry for {version}")
    return match.group(1).strip()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    tag, checksums_file = sys.argv[1], Path(sys.argv[2])
    version = tag.removeprefix("v")

    notes = (ROOT / ".github" / "release-notes.md").read_text()
    for placeholder, value in {
        "@CHANGES@": changelog_section(version),
        "@CHECKSUMS@": checksums_file.read_text().strip(),
        "@VERSION@": version,
        "@TAG@": tag,
    }.items():
        notes = notes.replace(placeholder, value)
    print(notes)


if __name__ == "__main__":
    main()
