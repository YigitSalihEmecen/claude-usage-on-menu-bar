// Sign-in surface: browser OAuth, with a paste-the-code fallback.

import AppKit
import SwiftUI

struct SignInView: View {
    let store: UsageStore

    @State private var manualSession: OAuthService.Session?
    @State private var pastedCode = ""

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 10) {
                Image(systemName: "gauge.with.needle")
                    .font(.system(size: 26, weight: .light))
                    .foregroundStyle(.secondary)

                Text("Connect your Claude account")
                    .font(.system(size: 13, weight: .semibold))

                Text("Sign in to see how much of your session and weekly limits you have used.")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.horizontal, 24)
            .padding(.top, 22)
            .padding(.bottom, 16)

            VStack(spacing: 8) {
                Button {
                    Task { await store.signInWithBrowser() }
                } label: {
                    HStack(spacing: 5) {
                        if store.isSigningIn {
                            ProgressView().controlSize(.small)
                        }
                        Text(store.isSigningIn ? "Waiting for browser…" : "Sign in with browser")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Palette.clay.color)
                .controlSize(.large)
                .disabled(store.isSigningIn)

                if store.importAvailable {
                    Button("Use my Claude Code login") {
                        store.importClaudeCodeLogin()
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.horizontal, 14)

            if let error = store.signInError {
                Text(error)
                    .font(.system(size: 10))
                    .foregroundStyle(Palette.amber.color)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
            }

            manualFallback
                .padding(.horizontal, 14)
                .padding(.top, 12)
                .padding(.bottom, 16)
        }
    }

    @ViewBuilder
    private var manualFallback: some View {
        if let session = manualSession {
            VStack(alignment: .leading, spacing: 7) {
                Text("Paste the code Claude showed you.")
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)

                HStack(spacing: 6) {
                    TextField("Authorization code", text: $pastedCode)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 11, design: .monospaced))
                        .onSubmit { submit(session) }

                    Button("Done") { submit(session) }
                        .controlSize(.small)
                        .disabled(pastedCode.isEmpty || store.isSigningIn)
                }
            }
            .transition(.opacity)
        } else {
            Button("Browser did not open?") {
                let session = OAuthService.makeSession(manual: true)
                manualSession = session
                NSWorkspace.shared.open(session.url)
                // The panel does not activate the app, but the code field needs focus.
                NSApp.activate(ignoringOtherApps: true)
            }
            .buttonStyle(.link)
            .font(.system(size: 10))
            .frame(maxWidth: .infinity)
        }
    }

    private func submit(_ session: OAuthService.Session) {
        let code = pastedCode
        pastedCode = ""
        Task { await store.completeManualSignIn(code: code, session: session) }
    }
}
