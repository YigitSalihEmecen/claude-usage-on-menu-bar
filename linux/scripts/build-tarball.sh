#!/bin/bash
# Builds dist/claude-usage-linux-<version>.tar.gz: a source archive for distributions
# without a .deb. Unpack it and run `sudo make install`.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERSION="$(make -s version)"
NAME="claude-usage-linux-${VERSION}"
EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"
STAGE="build/tarball/${NAME}"

rm -rf build/tarball
mkdir -p "$STAGE" dist
cp -R claude_usage packaging scripts Makefile pyproject.toml README.md "$STAGE/"
cp ../LICENSE "$STAGE/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +

tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="@${EPOCH}" \
  -C build/tarball -cf - "$NAME" | gzip -9n > "dist/${NAME}.tar.gz"

echo "Built dist/${NAME}.tar.gz"
sha256sum "dist/${NAME}.tar.gz"
