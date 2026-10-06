# Claude Usage for Linux

The Linux version of Claude Usage: your Claude session and weekly limits, one glance away
in the system tray. See the [main README](../README.md) for what the app does and for the
macOS version.

It is a small GTK 3 application written in Python. It has no dependencies beyond what a
desktop already ships: PyGObject, GTK 3, libayatana-appindicator and libsecret.

## Install

### Ubuntu, Debian and derivatives

Download `claude-usage_<version>_all.deb` from the
[releases page](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/releases/latest)
and install it. `apt` pulls in the dependencies for you:

```sh
sudo apt install ./claude-usage_*_all.deb
```

The package is architecture-independent, so the same file works on amd64 and arm64. It
needs Python 3.10 or newer, which means Ubuntu 22.04 or later and Debian 12 or later.

Start **Claude Usage** from your application menu, or run `claude-usage`.

### Other distributions

Download `claude-usage-linux-<version>.tar.gz` from the releases page, unpack it, and
install with `make`:

```sh
tar xf claude-usage-linux-*.tar.gz
cd claude-usage-linux-*
sudo make install                 # into /usr/local
# or, without root:
make install PREFIX=~/.local
```

Install the runtime dependencies first: PyGObject, GTK 3, libayatana-appindicator and
libsecret, each with its GObject typelib. On Fedora these are typically
`python3-gobject gtk3 libayatana-appindicator-gtk3 libsecret`, and on Arch
`python-gobject gtk3 libayatana-appindicator libsecret`. Those distributions are not yet
tested, so reports are welcome. Remove the app again with `make uninstall` (use the same
`PREFIX`).

## Supported desktops

Where the tray icon appears depends on your desktop:

| Desktop | Tray |
| --- | --- |
| Ubuntu (GNOME) | Works out of the box; Ubuntu ships the AppIndicator extension. |
| GNOME on other distributions | Install the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/) and enable it. |
| KDE Plasma, XFCE, Cinnamon, MATE, Budgie | Should work, as these support the StatusNotifier tray protocol; not yet tested. |

Without a tray the app still runs: starting it from the application menu opens the
panel, and closing the panel quits the app.

The app was developed and tested on Ubuntu 22.04 with GNOME on X11. The tray label next to
the icon (for example `42% · 2h13m`) is shown by GNOME and KDE; some other panels show
only the icon.

## Using it

The tray shows a progress ring for your current session, plus the percentage used and the
time until it resets. Open the tray menu for a summary of every limit, then
**Open Claude Usage** for the full panel: weekly limits, per-model limits, extra usage,
and the context window of the Claude Code session you worked in most recently.

Running `claude-usage` again while it is already running brings the panel forward.

### Signing in

Open the panel and choose **Sign in with browser**. If the browser does not open, use
**Browser did not open?** to paste a code instead, or **Use my Claude Code login** to
reuse the login Claude Code keeps in `~/.claude/.credentials.json`.

Your tokens are stored in your desktop keyring (GNOME Keyring, KWallet, or any Secret
Service). If there is no keyring they go in `~/.config/claude-usage/credentials.json`,
readable only by you. They are sent only to Anthropic.

The consent screen says *Claude Code*, because Anthropic offers no public sign-in for
third-party apps and this app reuses Claude Code's.

### Settings

Open the gear in the panel. You can change what the tray label shows, how often usage is
refreshed, the percentage above which the ring turns amber, whether context usage is
shown in the tray, and whether the app starts when you log in. Settings are stored in
`~/.config/claude-usage/settings.json`.

## Troubleshooting

**There is no tray icon.** On GNOME, make sure the AppIndicator extension is installed and
enabled (`gnome-extensions list --enabled` should include `appindicator`). Log out and in
after enabling it.

**Sign-in says port 54545 is in use.** The browser sign-in listens briefly on
`127.0.0.1:54545`. Close whatever is using it, or use **Browser did not open?** to sign in with a pasted code instead.

**The usage numbers are wrong or missing.** The app reads the same undocumented endpoint
Claude Code's `/usage` uses, so Anthropic can change it without notice. Run
`claude-usage --verbose` from a terminal to see what it logs, and please
[open an issue](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/issues).

**Claude Code asks me to log in again after I used "Use my Claude Code login".** Anthropic
rotates refresh tokens, so when this app refreshes the copy it imported, the copy Claude
Code holds can go stale. If that bothers you, sign in with the browser instead, which gives
this app its own login.

## Building from source

You need `make` and Python 3.10+, plus the runtime dependencies above.

```sh
make run         # run from the checkout
make test        # run the tests
make deb         # build dist/claude-usage_<version>_all.deb
make dist        # build dist/claude-usage-linux-<version>.tar.gz
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the layout and how to develop without a
Claude account.
