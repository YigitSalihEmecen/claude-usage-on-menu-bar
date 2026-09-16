# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-16

### Fixed

- The sign-in redirect listener bound to every network interface, leaving the
  callback port reachable from the local network while sign-in was open. It now
  binds to `127.0.0.1` only.
- Overlapping usage refreshes could each spend the same rotating refresh token,
  and the losing request signed the user out. Refreshes are now coalesced.
- Settings controls flickered when a usage fetch completed, because reading the
  fetch state in the panel body rebuilt the whole panel.
- A sign-in callback split across TCP segments could be parsed incompletely.
- The pasted-code sign-in path did not verify the returned state value.
- Tokens are now stored as accessible only while the Mac is unlocked, rather than
  after first unlock.

## [1.0.0] - 2026-09-15

First release.

### Added

- Menu bar item showing session usage and time until reset, refreshed every minute.
  The progress ring renders as a template glyph so it tints like any system icon, and
  takes on color only past the warn threshold.
- Panel with the session ring and exact reset time, weekly and per-model weekly
  windows, and extra-usage credits when enabled.
- Browser sign-in via OAuth with PKCE and a loopback redirect on `localhost:54545`,
  with a paste-the-code fallback and one-click adoption of an existing Claude Code login.
- Token storage in the login keychain with automatic refresh on expiry and on 401.
- Settings for menu bar format, refresh interval, warn threshold, and start at login.
- Support for both known shapes of the usage endpoint response: the `limits[]` array
  and the older flat `five_hour` / `seven_day` keys.
- Universal binary for Apple Silicon and Intel.

[1.0.1]: https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/tag/v1.0.1
[1.0.0]: https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/tag/v1.0.0
