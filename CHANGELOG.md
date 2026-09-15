# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/tag/v1.0.0
