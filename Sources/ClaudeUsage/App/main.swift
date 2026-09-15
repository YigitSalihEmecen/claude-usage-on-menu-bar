// Entry point. Runs as an accessory app: menu bar only, no Dock icon or main window.

import AppKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let store = UsageStore()
    private var statusItem: StatusItemController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = StatusItemController(store: store)
        store.start()
    }
}

@MainActor
private enum Launcher {
    /// Static storage keeps the delegate alive; NSApplication holds it weakly.
    static let delegate = AppDelegate()

    static func run() -> Never {
        let app = NSApplication.shared
        app.delegate = delegate
        app.run()
        exit(0)
    }
}

MainActor.assumeIsolated { Launcher.run() }
