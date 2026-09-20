# Contributing

## Building

Requires macOS 14+ and a Swift 5.9+ toolchain (Xcode or Command Line Tools).

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

## Layout

```
Sources/ClaudeUsage/
  App/      entry point, status item, borderless panel, menu bar ring drawing
  Auth/     PKCE flow, loopback redirect listener, keychain storage
  Model/    usage API client, payload decoding, observable store
  Views/    panel, meters, sign-in, settings
  Support/  preferences, palette, formatters
```

`UsageStore` is the single `@Observable` source of truth. The status item observes
it with `withObservationTracking`, and a one-second clock keeps countdowns live
between the one-minute network refreshes. All usage colors come from one ramp in
`Support/Palette.swift`.

Views that read frequently-changing store properties (`phase`, `tick`,
`lastUpdated`) are kept as small separate structs. Reading those from
`PanelRootView.body` would rebuild the whole panel — including the settings
controls — every time a fetch lands.

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
`~/.claude/projects/<slug>/<session-id>.jsonl`. `Model/ContextUsage.swift` takes the
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

## Releasing

Tagging is all it takes — `.github/workflows/release.yml` builds the universal DMG
and publishes it. The workflow checks that the tag matches the bundle version, and
runs from the workflow file **as of the tagged commit**, so land CI changes on `main`
before tagging.

```sh
# bump CFBundleShortVersionString in Resources/Info.plist, update CHANGELOG.md
git commit -am "Release v1.1.0"
git tag v1.1.0
git push origin main --tags
```
