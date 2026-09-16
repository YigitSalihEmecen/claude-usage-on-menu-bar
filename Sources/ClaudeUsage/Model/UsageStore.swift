// Single source of truth for the menu bar and panel: owns credentials,
// the refresh timer, and the latest snapshot.

import Foundation
import Observation

@MainActor
@Observable
final class UsageStore {
    enum Phase: Equatable {
        case signedOut
        case loading
        case ready(UsageSnapshot)
        case failed(String)
    }

    private(set) var phase: Phase = .signedOut
    private(set) var isSigningIn = false
    private(set) var signInError: String?
    private(set) var lastUpdated: Date?
    /// Advances every second so reset countdowns stay live without refetching.
    private(set) var tick = Date.now

    let preferences = Preferences()

    private var credentials: Credentials?
    private var refreshTask: Task<Void, Never>?
    private var inFlight: Task<Void, Never>?
    private var clock: Timer?

    var snapshot: UsageSnapshot? {
        if case .ready(let snapshot) = phase { return snapshot }
        return nil
    }

    var isSignedIn: Bool { credentials != nil }

    /// True when a Claude Code CLI login exists that we can adopt.
    var importAvailable: Bool {
        FileManager.default.fileExists(atPath: URL.homeDirectory.appending(path: ".claude").path)
    }

    init() {
        credentials = CredentialStore.load()
        if credentials != nil { phase = .loading }
        startClock()
    }

    // MARK: - Lifecycle

    func start() {
        guard credentials != nil else { return }
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.refresh()
                try? await Task.sleep(for: .seconds(self.preferences.refreshInterval))
            }
        }
    }

    /// Called when the refresh interval changes.
    func restartTimer() {
        guard refreshTask != nil else { return }
        start()
    }

    func stop() {
        refreshTask?.cancel()
        refreshTask = nil
    }

    private func startClock() {
        clock = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick = .now }
        }
    }

    // MARK: - Data

    /// Called when the panel opens; avoids hammering a rate-limited endpoint.
    func refreshIfStale(maxAge: TimeInterval = 15) {
        guard isSignedIn else { return }
        if let lastUpdated, lastUpdated.timeIntervalSinceNow > -maxAge { return }
        Task { await refresh() }
    }

    func refresh() async {
        if let inFlight { return await inFlight.value }
        let task = Task { await performRefresh() }
        inFlight = task
        await task.value
        inFlight = nil
    }

    private func performRefresh() async {
        guard let credentials else {
            phase = .signedOut
            return
        }
        if snapshot == nil { phase = .loading }

        do {
            let token = try await validToken(credentials)
            phase = .ready(try await UsageAPI.fetch(accessToken: token))
            lastUpdated = .now
        } catch UsageError.unauthorized {
            await handleUnauthorized()
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func validToken(_ credentials: Credentials) async throws -> String {
        guard credentials.isExpired, credentials.refreshToken != nil else { return credentials.accessToken }
        let refreshed = try await OAuthService.refresh(credentials)
        adopt(refreshed)
        return refreshed.accessToken
    }

    private func handleUnauthorized() async {
        if let credentials, credentials.refreshToken != nil {
            if let refreshed = try? await OAuthService.refresh(credentials) {
                adopt(refreshed)
                if let snapshot = try? await UsageAPI.fetch(accessToken: refreshed.accessToken) {
                    phase = .ready(snapshot)
                    lastUpdated = .now
                    return
                }
            }
        }
        signOut()
        phase = .signedOut
    }

    // MARK: - Auth

    func signInWithBrowser() async {
        await signIn { try await OAuthService.signInWithBrowser() }
    }

    func completeManualSignIn(code: String, session: OAuthService.Session) async {
        await signIn { try await OAuthService.signIn(pastedCode: code, session: session) }
    }

    private func signIn(_ authorize: () async throws -> Credentials) async {
        isSigningIn = true
        signInError = nil
        defer { isSigningIn = false }
        do {
            adopt(try await authorize())
            await refresh()
            start()
        } catch is CancellationError {
        } catch {
            signInError = error.localizedDescription
        }
    }

    @discardableResult
    func importClaudeCodeLogin() -> Bool {
        guard let imported = CredentialStore.importFromClaudeCode() else {
            signInError = "No Claude Code login found on this Mac."
            return false
        }
        signInError = nil
        adopt(imported)
        Task {
            await refresh()
            start()
        }
        return true
    }

    func signOut() {
        stop()
        credentials = nil
        signInError = nil
        CredentialStore.clear()
        lastUpdated = nil
        phase = .signedOut
    }

    private func adopt(_ credentials: Credentials) {
        self.credentials = credentials
        CredentialStore.save(credentials)
    }
}
