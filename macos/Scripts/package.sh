#!/bin/bash
# Builds a universal app and wraps it in a distributable DMG.
# Output: build/ClaudeUsage-<version>-universal.dmg
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" Resources/Info.plist)"
APP="$ROOT/build/Claude Usage.app"
STAGE="$ROOT/build/dmg"
DMG="$ROOT/build/ClaudeUsage-${VERSION}-universal.dmg"

Scripts/build.sh --universal

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

hdiutil create \
  -volname "Claude Usage $VERSION" \
  -srcfolder "$STAGE" \
  -fs HFS+ \
  -format UDZO \
  -imagekey zlib-level=9 \
  -quiet \
  "$DMG"

rm -rf "$STAGE"
codesign --force --sign - "$DMG" >/dev/null 2>&1 || true

echo "Packaged $DMG"
shasum -a 256 "$DMG"
