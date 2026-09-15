# Claude Usage

[![Release](https://img.shields.io/github/v/release/YigitSalihEmecen/claude-usage-on-menu-bar?style=flat&color=D97757)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/YigitSalihEmecen/claude-usage-on-menu-bar/total?style=flat&color=D97757)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases)
[![macOS](https://img.shields.io/badge/macOS-14%2B-informational?style=flat)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/YigitSalihEmecen/claude-usage-on-menu-bar/ci.yml?branch=main&style=flat&label=tests)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE)

A native macOS menu bar app that shows how much of your Claude usage you have left,
and how long until it resets.

<!-- Add a screenshot once you have one (⇧⌘4 with the panel open, save to docs/panel.png):
<p align="center"><img src="docs/panel.png" width="320" alt="The Claude Usage panel"></p>
-->

## Features

- **Always visible** — a progress ring plus `42% · 2h14m` in the menu bar, refreshed every minute.
- **Click for detail** — session ring with the exact reset time, weekly and per-model
  windows, and extra-usage credits when your plan has them enabled.
- **Sign in with your browser** — OAuth with PKCE. Tokens live in your login keychain
  and refresh themselves. Already use Claude Code? One click adopts its existing login.
- **Stays out of the way** — no Dock icon, no windows. The panel is a rounded, vibrant
  menu bar panel, and the ring renders as a template glyph so it tints itself like any
  system icon in light and dark mode.
- **Universal** — one build runs natively on Apple Silicon and Intel.

## Install

Download the latest DMG from the [**releases page**](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest),
open it, and drag **Claude Usage** to your Applications folder.

### First launch

The app is signed ad-hoc rather than with a paid Apple Developer ID, so macOS
quarantines it after download and will say the developer cannot be verified. To
allow it:

1. Try to open the app once, and let macOS block it.
2. Open **System Settings → Privacy & Security**, scroll to the Security section,
   and click **Open Anyway** next to Claude Usage.

Or clear the quarantine flag from a terminal:

```sh
xattr -dr com.apple.quarantine "/Applications/Claude Usage.app"
```

You only need to do this once. If you would rather not trust a prebuilt binary,
[build it yourself](#build-from-source) — it takes about five seconds.

## Signing in

Click the menu bar item, then **Sign in with browser**. The app opens claude.ai and
catches the redirect on `localhost:54545`.

Two fallbacks if that does not work:

- **Browser did not open?** switches to a flow where claude.ai shows you a code to paste.
- **Use my Claude Code login** adopts the token the Claude Code CLI already stores on
  this Mac, skipping the browser entirely.

Because Anthropic issues no public OAuth client for claude.ai, the app authenticates
with Claude Code's client ID — so the consent screen says *Claude Code*.

## How usage is read

`GET https://api.anthropic.com/api/oauth/usage` — the same endpoint behind Claude
Code's `/usage`. It reports a utilization percentage and reset timestamp per window:
the 5-hour session, the rolling weekly cap, and any per-model weekly caps.

Two response shapes are in circulation and both are handled: a `limits[]` array and
the older flat `five_hour` / `seven_day` keys, with the array taking precedence. A
`claude-code/<version>` User-Agent is required — without it the endpoint rate-limits
aggressively.

> This is an unofficial client for an undocumented endpoint. Treat the numbers as
> indicative, and expect the shape to change without notice. The test suite covers both
> known shapes so a change surfaces as a test failure rather than a blank panel.
>
> Despite the name, the "weekly" window is widely observed to reset every 72 hours.
> The app shows whatever reset timestamp the API returns rather than assuming a period.

## Build from source

Requires macOS 14+ and a Swift 5.9+ toolchain (Xcode or Command Line Tools).

```sh
git clone https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar.git
cd claude-usage-on-menu-bar

Scripts/build.sh              # build/Claude Usage.app, host architecture
Scripts/build.sh --universal  # arm64 + x86_64
Scripts/test.sh               # run the test suite
Scripts/package.sh            # universal app wrapped in a DMG

open "build/Claude Usage.app"
```

`swift build --arch` needs full Xcode, so the universal build cross-compiles each
slice and merges them with `lipo`. That keeps Command Line Tools sufficient.

## Project layout

```
Sources/ClaudeUsage/
  App/      entry point, status item, borderless panel, menu bar ring drawing
  Auth/     PKCE flow, loopback redirect listener, keychain storage
  Model/    usage API client, payload decoding, observable store
  Views/    panel, meters, sign-in, settings
  Support/  preferences, palette, formatters
Scripts/    build.sh, package.sh, test.sh, make-icon.swift
Tests/      payload decoding and formatting
```

`UsageStore` is the single `@Observable` source of truth. The status item observes it
with `withObservationTracking`, and a one-second clock keeps countdowns live between
the one-minute network refreshes. All usage colors derive from one ramp in
`Support/Palette.swift`.

## Releasing

Tagging is all it takes — `.github/workflows/release.yml` builds the universal DMG and
publishes it:

```sh
# bump CFBundleShortVersionString in Resources/Info.plist, update CHANGELOG.md
git commit -am "Release v1.1.0"
git tag v1.1.0
git push origin main --tags
```

## License

[MIT](LICENSE). Not affiliated with, endorsed by, or supported by Anthropic.
