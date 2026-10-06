// A borderless vibrant panel anchored just under the status item. NSPopover's
// arrow and offset do not match system menu bar extras, so we place our own.

import AppKit
import SwiftUI

/// Borderless panels refuse key status by default, which would break text fields.
private final class Panel: NSPanel {
    override var canBecomeKey: Bool { true }
}

@MainActor
final class PanelController {
    private static let cornerRadius: CGFloat = 12
    private static let menuBarGap: CGFloat = 5
    private static let screenMargin: CGFloat = 8

    private let panel: Panel
    private let effectView = NSVisualEffectView()
    private var globalClickMonitor: Any?
    private var keyMonitor: Any?
    private var contentSize: CGSize = .zero

    private weak var anchor: NSStatusBarButton?

    var isVisible: Bool { panel.isVisible }

    init(store: UsageStore) {
        panel = Panel(
            contentRect: NSRect(x: 0, y: 0, width: PanelRootView.width, height: 1),
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        panel.isFloatingPanel = true
        panel.level = .popUpMenu
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.isMovable = false
        panel.hidesOnDeactivate = false
        panel.animationBehavior = .none
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]

        effectView.material = .menu
        effectView.blendingMode = .behindWindow
        effectView.state = .active
        effectView.wantsLayer = true
        effectView.layer?.cornerRadius = Self.cornerRadius
        effectView.layer?.cornerCurve = .continuous
        effectView.layer?.masksToBounds = true

        let hosting = NSHostingView(
            rootView: PanelRootView(store: store) { [weak self] size in
                self?.contentDidResize(to: size)
            }
        )
        hosting.translatesAutoresizingMaskIntoConstraints = false
        effectView.addSubview(hosting)
        NSLayoutConstraint.activate([
            hosting.leadingAnchor.constraint(equalTo: effectView.leadingAnchor),
            hosting.trailingAnchor.constraint(equalTo: effectView.trailingAnchor),
            hosting.topAnchor.constraint(equalTo: effectView.topAnchor),
            hosting.bottomAnchor.constraint(equalTo: effectView.bottomAnchor),
        ])

        panel.contentView = effectView
    }

    // MARK: - Presentation

    func toggle(from button: NSStatusBarButton) {
        isVisible ? close() : show(from: button)
    }

    func show(from button: NSStatusBarButton) {
        anchor = button
        button.highlight(true)
        reposition()

        panel.alphaValue = 0
        panel.orderFrontRegardless()
        panel.makeKey()
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.12
            panel.animator().alphaValue = 1
        }

        startMonitors()
    }

    func close() {
        stopMonitors()
        anchor?.highlight(false)
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.09
            panel.animator().alphaValue = 0
        } completionHandler: { [panel] in
            panel.orderOut(nil)
        }
    }

    // MARK: - Geometry

    /// SwiftUI reports its natural size; the panel grows from a fixed top edge.
    private func contentDidResize(to size: CGSize) {
        guard size.height > 0, size != contentSize else { return }
        contentSize = size
        reposition()
    }

    private func reposition() {
        guard let anchor,
              let anchorWindow = anchor.window,
              let screen = anchorWindow.screen ?? NSScreen.main
        else { return }

        let size = contentSize.height > 0
            ? contentSize
            : CGSize(width: PanelRootView.width, height: panel.frame.height)
        let visible = screen.visibleFrame
        let anchorFrame = anchorWindow.frame

        let x = min(
            max(anchorFrame.midX - size.width / 2, visible.minX + Self.screenMargin),
            visible.maxX - size.width - Self.screenMargin
        )
        let y = anchorFrame.minY - size.height - Self.menuBarGap

        panel.setFrame(
            NSRect(x: x.rounded(), y: y.rounded(), width: size.width, height: size.height),
            display: true
        )
    }

    // MARK: - Dismissal

    /// Global monitors only see other applications' events, so clicks inside our
    /// own panel and its pop-up menus never reach here.
    private func startMonitors() {
        stopMonitors()
        globalClickMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown]
        ) { [weak self] _ in
            Task { @MainActor in self?.close() }
        }
        keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard event.keyCode == 53 else { return event }
            Task { @MainActor in self?.close() }
            return nil
        }
    }

    private func stopMonitors() {
        [globalClickMonitor, keyMonitor].compactMap { $0 }.forEach(NSEvent.removeMonitor)
        globalClickMonitor = nil
        keyMonitor = nil
    }
}
