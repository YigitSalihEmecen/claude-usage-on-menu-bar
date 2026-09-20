# Claude Usage

[![Release](https://img.shields.io/github/v/release/YigitSalihEmecen/claude-usage-on-menu-bar?style=flat&color=D97757)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/YigitSalihEmecen/claude-usage-on-menu-bar/total?style=flat&color=D97757)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases)
[![macOS](https://img.shields.io/badge/macOS-14%2B-informational?style=flat)](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE)

See how much Claude usage you have left, right in your menu bar — no need to open
the app to check.

<img width="562" height="42" alt="image" src="https://github.com/user-attachments/assets/fcae62cd-9313-4f11-ad8a-431848a8f959" />

<img width="685" height="405" alt="image" src="https://github.com/user-attachments/assets/698b2884-950d-4389-8148-e8b48aa59267" />



- Your session usage and time until reset, always visible and updated every minute.
- Click for detail: weekly limits, per-model limits, and exact reset times.
- How full the context window is in your most recent Claude Code session.
- Sign in with your browser. Already use Claude Code? One click reuses that login.
- No Dock icon, no windows. Follows light and dark mode.

## Install

Download the DMG from the [**releases page**](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest),
open it, and drag **Claude Usage** to your Applications folder. One build works on
both Apple Silicon and Intel Macs.

**First launch:** macOS will say the developer cannot be verified, because the app
is not signed with a paid Apple Developer account. Open **System Settings → Privacy
& Security** and click **Open Anyway**. You only need to do this once.

Requires macOS 14 or later.

## Signing in

Click the menu bar item, then **Sign in with browser**. If that does not work, use
**Browser did not open?** to paste a code instead, or **Use my Claude Code login**
to reuse the login already on your Mac.

Your login is stored in your Mac's keychain and never leaves your computer.

The sign-in screen says *Claude Code*, because Anthropic does not offer a public
sign-in for third-party apps and the app reuses Claude Code's.

## Build it yourself

Needs macOS 14+ and Xcode or the Command Line Tools.

```sh
git clone https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar.git
cd claude-usage-on-menu-bar
Scripts/build.sh
open "build/Claude Usage.app"
```

`Scripts/test.sh` runs the tests and `Scripts/package.sh` builds the DMG.
See [CONTRIBUTING.md](CONTRIBUTING.md) for how the project is laid out.

## Notes

This is an unofficial app. It reads the same usage data Claude Code shows, from an
endpoint Anthropic has not documented, so the numbers may occasionally be wrong or
stop working if Anthropic changes it.

Not affiliated with or endorsed by Anthropic. [MIT licensed](LICENSE).
