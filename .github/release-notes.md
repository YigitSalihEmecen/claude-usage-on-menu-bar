Download the DMG below, open it, and drag **Claude Usage** to your Applications folder.
One universal build runs natively on both Apple Silicon and Intel Macs.

### First launch

This build is signed ad-hoc rather than with a paid Apple Developer ID, so macOS
quarantines it after download. Try to open it once, let macOS block it, then go to
**System Settings → Privacy & Security** and click **Open Anyway**. Alternatively:

```sh
xattr -dr com.apple.quarantine "/Applications/Claude Usage.app"
```

### Requirements

macOS 14 Sonoma or later, and a Claude account.

See the [changelog](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar/blob/@TAG@/CHANGELOG.md)
for what is in this version, and the [README](https://github.com/YigitSalihEmecen/claude-usage-on-menu-bar#readme)
for how signing in and usage reading work.
