# Contributing

The repository holds two native apps that share one design and one release:

- [`macos/`](macos): Swift, SwiftUI and AppKit, for macOS 14+.
- [`linux/`](linux): Python and GTK 3, for Ubuntu, Debian and other desktops with a
  system tray.

Both read the same usage endpoint and the same Claude Code transcripts, so a change to
how usage is decoded, or to how context is computed, belongs in both. Keep the test cases
mirrored: the Linux tests are ports of the Swift ones, so a payload shape pinned in one
should be pinned in the other.

## Building

### macOS

Requires macOS 14+ and a Swift 5.9+ toolchain (Xcode or Command Line Tools). Run these
from `macos/`.

```sh
Scripts/build.sh              # build/Claude Usage.app, host architecture
Scripts/build.sh --universal  # arm64 + x86_64
Scripts/test.sh               # run the tests
Scripts/package.sh            # universal app wrapped in a DMG
```

`swift build --arch` needs full Xcode, so the universal build cross-compiles each
slice and merges them with `lipo`, keeping Command Line Tools sufficient.
`Scripts/test.sh` points the compiler at swift-testing, which ships with the
toolchain but is not on the default search path.

### Linux

Requires Python 3.10+, `make`, and the libraries the package depends on. On Debian and
Ubuntu:

```sh
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 gir1.2-secret-1 xvfb dbus
```

Run these from `linux/`.

```sh
make run      # run from the checkout
make test     # run the tests
make lint     # ruff check and format check (pip install ruff)
make deb      # dist/claude-usage_<version>_all.deb
make dist     # dist/claude-usage-linux-<version>.tar.gz
```

The tests cover the core without a display, and the GTK widgets with one. Run the whole
suite headless the way CI does:

```sh
xvfb-run -a dbus-run-session -- make test
```

Without `xvfb-run` the widget tests skip themselves.

#### Developing without a Claude account

`linux/scripts/fake-usage-server.py` serves a fake usage payload. Point the app at it, with
a throwaway config so your real settings and login stay untouched:

```sh
linux/scripts/fake-usage-server.py &
CLAUDE_USAGE_API_URL=http://127.0.0.1:8765/api/oauth/usage \
XDG_CONFIG_HOME=/tmp/cu/config CLAUDE_CONFIG_DIR=/tmp/cu/claude \
  make -C linux run
```

Put a fake `{"claudeAiOauth": {"accessToken": "x"}}` in `/tmp/cu/claude/.credentials.json`
to use **Use my Claude Code login**, and a transcript under `/tmp/cu/claude/projects/` to
see the context row.

## Layout

```
macos/
  Sources/ClaudeUsage/
    App/      entry point, status item, borderless panel, menu bar ring drawing
    Auth/     PKCE flow, loopback redirect listener, keychain storage
    Model/    usage API client, payload decoding, observable store
    Views/    panel, meters, sign-in, settings
    Support/  preferences, palette, formatters
  Tests/  Scripts/  Resources/
linux/
  claude_usage/
    snapshot.py context.py api.py   payload decoding, transcript reading, usage client
    oauth.py loopback.py credentials.py   PKCE flow, redirect listener, keyring storage
    store.py preferences.py         observable store, settings
    ui/       tray indicator, panel window, pages, widgets
  tests/  packaging/  scripts/  Makefile
scripts/    release tooling shared by both platforms
```

On macOS, `UsageStore` is the single `@Observable` source of truth. The status item
observes it with `withObservationTracking`, and a one-second clock keeps countdowns live
between the one-minute network refreshes. All usage colors come from one ramp in
`Support/Palette.swift`.

Views that read frequently-changing store properties (`phase`, `tick`,
`lastUpdated`) are kept as small separate structs. Reading those from
`PanelRootView.body` would rebuild the whole panel — including the settings
controls — every time a fetch lands.

On Linux, `store.UsageStore` plays the same role. Network and disk work runs on worker
threads and every state change is applied on the GLib main loop through a `post`
callable, so observers (the tray and the panel) always run on the UI thread. The tests
pass synchronous `post` and `spawn` callables to stay deterministic. Everything outside
`ui/` is toolkit-free and importable without GTK. The panel reuses its widgets between
refreshes and only rebuilds when the set of limits changes, which is the GTK equivalent of
the macOS note above.

Two GTK 3 details are worth knowing. `show_all()` skips widgets marked `no_show_all`, so
conditionally visible widgets are toggled with `set_visible`. A `Gtk.Stack` ignores a
request to show a child that is not yet visible, so the panel realises its pages before
the first render.

Tray hosts show a menu and a text label, not arbitrary widgets, so the Linux tray carries a
text summary and opens the panel window for the rich view. The ring icon is drawn as SVG
files in `~/.cache/claude-usage/icons`, one per percentage and colour, because hosts load
icons by name.

## How usage is read

`GET https://api.anthropic.com/api/oauth/usage`, the endpoint behind Claude Code's
`/usage`. It returns a utilization percentage and reset timestamp per window: the
5-hour session, the rolling weekly cap, and any per-model weekly caps.

Two response shapes are in circulation and both are handled: a `limits[]` array and
the older flat `five_hour` / `seven_day` keys, with the array taking precedence. A
`claude-code/<version>` User-Agent is required, or the endpoint rate-limits
aggressively.

The endpoint is undocumented and may change without notice. `Tests/` covers both
known shapes so a change surfaces as a test failure rather than a blank panel.

Despite the name, the "weekly" window is widely observed to reset every 72 hours.
The app shows whatever reset timestamp the API returns rather than assuming a period.

## How context is read

Claude Code appends one JSON object per line to
`~/.claude/projects/<slug>/<session-id>.jsonl`. `Model/ContextUsage.swift` (macOS) and
`context.py` (Linux) take the
most recently modified transcript across every project, so the reading follows
whichever session you touched last, and reads the `usage` block off the last
assistant line. Context used is `input + cache_creation + cache_read + output` —
cached tokens still occupy the window. Sidechain lines are subagent turns and are
skipped, since they do not consume the session's own context.

Transcripts reach tens of megabytes, so the file is never read whole: the reader
tails the last 256KB and scans backwards, retrying at 4MB when a run of large tool
results fills the first window. The context limit comes from the model recorded on
the turn (200K for Haiku, 1M otherwise), not from a constant.

This is local and read-only; it adds no network calls. The transcript format is
undocumented, so decoding ignores unknown fields and `Tests/` pins the shape.

## Authentication

Authorization Code + PKCE against claude.ai, using Claude Code's client ID because
Anthropic issues no public OAuth client. The redirect lands on a one-shot
`NWListener` bound to `127.0.0.1:54545`; `requiredLocalEndpoint` must carry the port,
since also passing `on:` makes listener creation fail. There is a paste-the-code
fallback, and an importer for an existing Claude Code login.

Tokens live in the login keychain (`kSecAttrAccessibleWhenUnlocked`) and refresh on
expiry and on 401. Refresh calls are coalesced: the tokens rotate, so two concurrent
refreshes would spend the same refresh token and sign the user out.

The Linux app runs the same flow with the standard library: `http.server` bound to
`127.0.0.1:54545` for the redirect, which answers only `/callback` so a browser's stray
`/favicon.ico` request cannot end the wait. Tokens go to the desktop keyring through
libsecret, and to a `0600` file under `~/.config/claude-usage` when no keyring exists.

## Releasing

One tag publishes one release containing the downloads for every platform. Pushing a
`v*` tag runs `.github/workflows/release.yml`, which:

1. checks that the tag matches the macOS bundle version, the Linux package version and a
   `CHANGELOG.md` entry;
2. builds and tests the macOS DMG (on a macOS runner) and the Linux `.deb` and tarball
   (on Ubuntu) in parallel;
3. only if both succeed, creates the GitHub release with all files, a `SHA256SUMS` file,
   and notes assembled from `CHANGELOG.md` by `scripts/release-notes.py`.

The workflow runs from the workflow file **as of the tagged commit**, so land CI changes
on `main` before tagging.

```sh
# 1. Bump the version in both places and add a CHANGELOG.md entry
#      macos/Resources/Info.plist   CFBundleShortVersionString (and CFBundleVersion)
#      linux/claude_usage/__init__.py   __version__
#      linux/packaging/*.metainfo.xml   a new <release> entry
git commit -am "Release v1.2.0"
git tag v1.2.0
git push origin main --tags
```

The two apps share a version number even when only one changed, so a release page always
offers a matching download for each platform.
