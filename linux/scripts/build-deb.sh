#!/bin/bash
# Builds dist/claude-usage_<version>_all.deb. The package is pure Python, so one
# architecture-independent .deb serves amd64, arm64 and the rest.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 022

VERSION="$(make -s version)"
PACKAGE="claude-usage_${VERSION}_all"
STAGE="build/deb/${PACKAGE}"
DEB="dist/${PACKAGE}.deb"
EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"

rm -rf build/deb
mkdir -p "$STAGE/DEBIAN" dist

make -s install PREFIX=/usr DESTDIR="$STAGE" SOURCE_DATE_EPOCH="$EPOCH"

# Debian policy: man pages are compressed, and every package ships its copyright.
gzip -9n "$STAGE/usr/share/man/man1/claude-usage.1"
DOC="$STAGE/usr/share/doc/claude-usage"
install -Dm 644 packaging/debian/copyright "$DOC/copyright"
if [ -f ../CHANGELOG.md ]; then
  gzip -9n -c ../CHANGELOG.md > "$DOC/changelog.gz"
  chmod 644 "$DOC/changelog.gz"
fi

SIZE="$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)"
sed -e "s|@VERSION@|${VERSION}|" -e "s|@SIZE@|${SIZE}|" packaging/debian/control.in > "$STAGE/DEBIAN/control"
install -m 755 packaging/debian/postinst packaging/debian/prerm "$STAGE/DEBIAN/"

find "$STAGE" -exec touch -h -d "@${EPOCH}" {} +
rm -f "$DEB"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null

echo "Built $DEB"
sha256sum "$DEB"
