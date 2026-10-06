// Settings shown inside the panel.

import AppKit
import SwiftUI

struct SettingsPane: View {
    let store: UsageStore
    @Bindable var preferences: Preferences

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            section {
                LabeledRow("Menu bar") {
                    Picker("", selection: $preferences.display) {
                        ForEach(MenuBarDisplay.allCases) { option in
                            Text(option.label).tag(option)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 138)
                }

                LabeledRow("Refresh") {
                    Picker("", selection: $preferences.refreshInterval) {
                        ForEach(Preferences.refreshOptions, id: \.self) { seconds in
                            Text(seconds < 60 ? "\(seconds) sec" : "\(seconds / 60) min").tag(seconds)
                        }
                    }
                    .labelsHidden()
                    .frame(width: 138)
                    .onChange(of: preferences.refreshInterval) { store.restartTimer() }
                }

                LabeledRow("Warn above") {
                    HStack(spacing: 7) {
                        Slider(value: $preferences.warnThreshold, in: 0.5...0.95, step: 0.05)
                        Text("\(Int(preferences.warnThreshold * 100))%")
                            .font(.system(size: 11))
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                            .frame(width: 32, alignment: .trailing)
                    }
                    .frame(width: 138)
                }

                LabeledRow("Context in menu bar") {
                    Toggle("", isOn: $preferences.showContextInMenuBar)
                        .toggleStyle(.switch)
                        .controlSize(.mini)
                        .labelsHidden()
                        .frame(width: 138, alignment: .leading)
                }

                LabeledRow("Start at login") {
                    Toggle("", isOn: $preferences.launchAtLogin)
                        .toggleStyle(.switch)
                        .controlSize(.mini)
                        .labelsHidden()
                        .frame(width: 138, alignment: .leading)
                }
            }

            Divider().opacity(0.6)

            section {
                HStack {
                    Text(store.isSignedIn ? "Signed in" : "Not signed in")
                        .font(.system(size: 12, weight: .medium))
                    Spacer()
                    if store.isSignedIn {
                        Button("Sign out") { store.signOut() }
                            .controlSize(.small)
                    }
                }
            }

            Divider().opacity(0.6)

            HStack {
                Text("Claude Usage \(Bundle.main.shortVersion)")
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
                    .buttonStyle(.link)
                    .font(.system(size: 10))
            }
            .font(.system(size: 10))
            .foregroundStyle(.tertiary)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
        }
    }

    private func section<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            content()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 13)
    }
}

private struct LabeledRow<Content: View>: View {
    let title: String
    let content: Content

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        HStack(spacing: 10) {
            Text(title)
                .font(.system(size: 12))
                .frame(width: 92, alignment: .leading)
            content
            Spacer(minLength: 0)
        }
    }
}

extension Bundle {
    var shortVersion: String {
        object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
    }
}
