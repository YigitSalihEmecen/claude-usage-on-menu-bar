// The panel shown when the menu bar item is clicked.
// Reports its natural size so PanelController can size the window to fit.

import SwiftUI

struct PanelRootView: View {
    static let width: CGFloat = 292

    let store: UsageStore
    let onResize: (CGSize) -> Void

    @State private var showingSettings = false

    var body: some View {
        VStack(spacing: 0) {
            header

            Divider().opacity(0.6)

            Group {
                if showingSettings {
                    SettingsPane(store: store, preferences: store.preferences)
                } else {
                    content
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(width: Self.width)
        .background(
            GeometryReader { proxy in
                Color.clear.onChange(of: proxy.size, initial: true) { _, size in
                    onResize(size)
                }
            }
        )
        .animation(.smooth(duration: 0.22), value: showingSettings)
    }

    // MARK: - Header

    private var header: some View {
        HStack(spacing: 8) {
            if showingSettings {
                Button {
                    showingSettings = false
                } label: {
                    Label("Back", systemImage: "chevron.left")
                        .labelStyle(.iconOnly)
                        .font(.system(size: 12, weight: .semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            }

            Text(showingSettings ? "Settings" : "Claude Usage")
                .font(.system(size: 13, weight: .semibold))

            Spacer()

            if !showingSettings, store.isSignedIn {
                IconButton(systemImage: "arrow.clockwise", help: "Refresh now") {
                    Task { await store.refresh() }
                }
                .rotationEffect(.degrees(store.phase == .loading ? 360 : 0))
                .animation(.linear(duration: 0.6), value: store.phase == .loading)
            }

            IconButton(
                systemImage: showingSettings ? "xmark" : "gearshape",
                help: showingSettings ? "Close settings" : "Settings"
            ) {
                showingSettings.toggle()
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
    }

    // MARK: - Body states

    @ViewBuilder
    private var content: some View {
        switch store.phase {
        case .signedOut:
            SignInView(store: store)
        case .loading:
            placeholder {
                ProgressView().controlSize(.small)
                Text("Reading your usage…")
            }
        case .failed(let message):
            placeholder {
                Image(systemName: "exclamationmark.triangle")
                    .font(.system(size: 20))
                    .foregroundStyle(Palette.amber.color)
                Text(message)
                    .multilineTextAlignment(.center)
                Button("Try again") { Task { await store.refresh() } }
                    .controlSize(.small)
                    .padding(.top, 2)
            }
        case .ready(let snapshot):
            snapshotView(snapshot)
        }
    }

    private func snapshotView(_ snapshot: UsageSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            sessionSection(snapshot.session)

            let others = snapshot.windows.filter { $0.kind != .session }
            if !others.isEmpty {
                Divider().opacity(0.6)
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(others) { window in
                        WindowRow(
                            window: window,
                            now: store.tick,
                            warnThreshold: store.preferences.warnThreshold
                        )
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 14)
            }

            if let extra = snapshot.extra, extra.isEnabled {
                Divider().opacity(0.6)
                extraUsageSection(extra)
            }

            Divider().opacity(0.6)
            footer
        }
    }

    @ViewBuilder
    private func sessionSection(_ session: UsageWindow?) -> some View {
        HStack(spacing: 16) {
            let fraction = session?.fraction ?? 0
            UsageRing(
                fraction: fraction,
                color: fraction.usageColor(warnThreshold: store.preferences.warnThreshold)
            )

            VStack(alignment: .leading, spacing: 3) {
                Text("Session")
                    .font(.system(size: 13, weight: .semibold))

                if let resetsAt = session?.resetsAt {
                    Text(Format.countdown(to: resetsAt, from: store.tick))
                        .font(.system(size: 19, weight: .medium, design: .rounded))
                        .monospacedDigit()
                    Text("until reset")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    Text(Format.resetTime(resetsAt))
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                        .padding(.top, 3)
                } else {
                    Text("No active window")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    Text("Your 5-hour limit starts on your next message.")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 16)
    }

    private func extraUsageSection(_ extra: ExtraUsage) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Extra usage")
                    .font(.system(size: 12, weight: .medium))
                Spacer()
                if let used = extra.usedCredits, let limit = extra.monthlyLimit {
                    Text("$\(used, specifier: "%.2f") of $\(limit, specifier: "%.0f")")
                        .font(.system(size: 11))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
            }
            if let fraction = extra.fraction {
                UsageBar(fraction: fraction, color: fraction.usageColor(warnThreshold: store.preferences.warnThreshold))
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var footer: some View {
        HStack(spacing: 4) {
            if let lastUpdated = store.lastUpdated {
                Text("Updated \(Format.relative(lastUpdated, from: store.tick))")
            }
            Spacer()
            Link("Manage plan", destination: URL(string: "https://claude.ai/settings/usage")!)
                .foregroundStyle(.secondary)
        }
        .font(.system(size: 10))
        .foregroundStyle(.tertiary)
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
    }

    private func placeholder<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 9) {
            content()
        }
        .font(.system(size: 11))
        .foregroundStyle(.secondary)
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 22)
        .padding(.vertical, 32)
    }
}

struct IconButton: View {
    let systemImage: String
    let help: String
    let action: () -> Void

    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 11, weight: .semibold))
                .frame(width: 22, height: 22)
                .background(
                    Circle().fill(Color.primary.opacity(hovering ? 0.09 : 0))
                )
        }
        .buttonStyle(.plain)
        .foregroundStyle(.secondary)
        .onHover { hovering = $0 }
        .help(help)
    }
}
