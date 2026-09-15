// Owns the NSStatusItem and its panel, and keeps the title in sync with the store.

import AppKit
import Observation
import SwiftUI

@MainActor
final class StatusItemController {
    private let store: UsageStore
    private let statusItem: NSStatusItem
    private let panel: PanelController
    private var drawnIcon: (fraction: Double?, tint: NSColor?)?

    init(store: UsageStore) {
        self.store = store
        self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        self.panel = PanelController(store: store)

        statusItem.button?.target = self
        statusItem.button?.action = #selector(togglePanel)
        statusItem.button?.imagePosition = .imageLeading

        observeStore()
    }

    // MARK: - Panel

    @objc private func togglePanel() {
        guard let button = statusItem.button else { return }
        panel.toggle(from: button)
        if panel.isVisible { store.refreshIfStale() }
    }

    // MARK: - Title

    /// Re-registers after every render so `withObservationTracking` keeps firing.
    private func observeStore() {
        withObservationTracking {
            render()
        } onChange: { [weak self] in
            Task { @MainActor in self?.observeStore() }
        }
    }

    private func render() {
        guard let button = statusItem.button else { return }

        let session = store.snapshot?.session
        let fraction = session?.fraction
        let warn = store.preferences.warnThreshold
        let tint: NSColor? = switch fraction ?? 0 {
        case 0.95...: Palette.ember.nsColor
        case warn...: Palette.amber.nsColor
        default: nil
        }

        if drawnIcon?.fraction != fraction || drawnIcon?.tint != tint {
            button.image = StatusRingImage.make(fraction: fraction, tint: tint)
            drawnIcon = (fraction, tint)
        }

        guard store.isSignedIn else {
            button.attributedTitle = attributed("Sign in")
            button.toolTip = "Claude Usage — not signed in"
            return
        }

        let display = store.preferences.display
        var parts: [String] = []
        if display.showsPercent, let session { parts.append("\(session.percent)%") }
        if display.showsTime, let resetsAt = session?.resetsAt {
            parts.append(Format.countdown(to: resetsAt, from: store.tick, compact: true))
        }

        button.attributedTitle = attributed(parts.joined(separator: " · "), tint: tint)
        button.toolTip = tooltip()
    }

    private func attributed(_ string: String, tint: NSColor? = nil) -> NSAttributedString {
        guard !string.isEmpty else { return NSAttributedString() }
        return NSAttributedString(
            string: " " + string,
            attributes: [
                .font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .regular),
                .foregroundColor: tint ?? NSColor.labelColor,
            ]
        )
    }

    private func tooltip() -> String {
        guard let snapshot = store.snapshot else { return "Claude Usage" }
        var lines = snapshot.windows.map { window -> String in
            let reset = window.resetsAt.map { " · resets in \(Format.countdown(to: $0, from: store.tick))" } ?? ""
            return "\(window.title): \(window.percent)%\(reset)"
        }
        if lines.isEmpty { lines = ["No active usage windows"] }
        return lines.joined(separator: "\n")
    }
}
