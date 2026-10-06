#!/bin/bash
# Builds "Claude Usage.app" into build/.
#
#   Scripts/build.sh                 release, host architecture
#   Scripts/build.sh --universal     arm64 + x86_64 merged with lipo
#   Scripts/build.sh --debug         debug configuration
set -euo pipefail

CONFIG=release
UNIVERSAL=0
for arg in "$@"; do
  case "$arg" in
    --universal) UNIVERSAL=1 ;;
    --debug) CONFIG=debug ;;
    --release) CONFIG=release ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/build/Claude Usage.app"
cd "$ROOT"

# swift build --arch needs full Xcode, so cross-compile per slice and lipo instead.
if [ "$UNIVERSAL" = 1 ]; then
  ARM="$(swift build -c "$CONFIG" --triple arm64-apple-macosx14.0 --show-bin-path)/ClaudeUsage"
  INTEL="$(swift build -c "$CONFIG" --triple x86_64-apple-macosx14.0 --show-bin-path)/ClaudeUsage"
  swift build -c "$CONFIG" --triple arm64-apple-macosx14.0 --product ClaudeUsage
  swift build -c "$CONFIG" --triple x86_64-apple-macosx14.0 --product ClaudeUsage
  mkdir -p "$ROOT/build"
  lipo -create -output "$ROOT/build/ClaudeUsage-universal" "$ARM" "$INTEL"
  BIN="$ROOT/build/ClaudeUsage-universal"
else
  swift build -c "$CONFIG" --product ClaudeUsage
  BIN="$(swift build -c "$CONFIG" --show-bin-path)/ClaudeUsage"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/ClaudeUsage"
cp "$ROOT/Resources/Info.plist" "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"

if [ ! -f "$ROOT/build/AppIcon.icns" ]; then
  swift "$ROOT/Scripts/make-icon.swift" "$ROOT/build/AppIcon.icns"
fi
cp "$ROOT/build/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

# Ad-hoc signature. Replace with a Developer ID identity to ship without
# Gatekeeper warnings: codesign --sign "Developer ID Application: ..." --options runtime
codesign --force --deep --sign - --options runtime "$APP" >/dev/null 2>&1 \
  || echo "note: ad-hoc signing failed; the app will still run locally"

echo "Built $APP ($(lipo -archs "$APP/Contents/MacOS/ClaudeUsage"))"
