#!/bin/bash
# Runs the test suite. swift-testing ships with Command Line Tools but is not on
# the default search path, so point the compiler and linker at it explicitly.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

FRAMEWORKS="$(xcode-select -p)/Library/Developer/Frameworks"
INTEROP="$(xcode-select -p)/Library/Developer/usr/lib"

if [ -d "$FRAMEWORKS/Testing.framework" ]; then
  exec swift test \
    -Xswiftc -F -Xswiftc "$FRAMEWORKS" \
    -Xlinker -F -Xlinker "$FRAMEWORKS" \
    -Xlinker -rpath -Xlinker "$FRAMEWORKS" \
    -Xlinker -rpath -Xlinker "$INTEROP" "$@"
fi

exec swift test "$@"
