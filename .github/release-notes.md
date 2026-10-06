## What's new

@CHANGES@

## Downloads

| Platform | File |
| --- | --- |
| macOS 14 or later, Apple Silicon and Intel | `ClaudeUsage-@VERSION@-universal.dmg` |
| Ubuntu, Debian and derivatives | `claude-usage_@VERSION@_all.deb` |
| Other Linux distributions | `claude-usage-linux-@VERSION@.tar.gz` |

### macOS

Open the DMG and drag **Claude Usage** to your Applications folder. This build is signed
ad-hoc rather than with a paid Apple Developer ID, so macOS quarantines it after download.
Try to open it once, let macOS block it, then go to **System Settings → Privacy &
Security** and click **Open Anyway**. Alternatively:

```sh
xattr -dr com.apple.quarantine "/Applications/Claude Usage.app"
```

### Ubuntu and Debian

```sh
sudo apt install ./claude-usage_@VERSION@_all.deb
```

Then start **Claude Usage** from your application menu. The same package runs on amd64 and
arm64, and needs Ubuntu 22.04 / Debian 12 or later. GNOME needs the AppIndicator extension
for the tray icon; Ubuntu ships it. See the
[Linux guide](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/blob/@TAG@/linux/README.md)
for other distributions.

### Checksums

```
@CHECKSUMS@
```

See the [README](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar#readme) for how
signing in and usage reading work, and the full
[changelog](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/blob/@TAG@/CHANGELOG.md).
