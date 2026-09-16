// Authorization Code + PKCE sign-in against claude.ai, with a loopback redirect
// for the browser flow and a paste-the-code fallback.

import AppKit
import CryptoKit
import Foundation

enum AuthError: LocalizedError {
    case stateMismatch
    case noCode
    case timedOut
    case tokenExchangeFailed(String)

    var errorDescription: String? {
        switch self {
        case .stateMismatch: return "The sign-in response did not match this request."
        case .noCode: return "Claude did not return an authorization code."
        case .timedOut: return "Sign-in timed out. Please try again."
        case .tokenExchangeFailed(let detail): return "Could not complete sign-in. \(detail)"
        }
    }
}

struct OAuthService {
    static let clientID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    static let scopes = "user:profile user:inference"
    static let loopbackPort: UInt16 = 54545
    static let signInTimeout: Duration = .seconds(180)

    private static let authorizeURL = URL(string: "https://claude.ai/oauth/authorize")!
    private static let tokenURLs = [
        URL(string: "https://platform.claude.com/v1/oauth/token")!,
        URL(string: "https://console.anthropic.com/v1/oauth/token")!,
    ]

    static var loopbackRedirect: String { "http://localhost:\(loopbackPort)/callback" }
    static let manualRedirect = "https://platform.claude.com/oauth/code/callback"

    struct Session {
        let verifier: String
        let state: String
        let redirectURI: String
        let url: URL
    }

    // MARK: - Authorization

    static func makeSession(manual: Bool) -> Session {
        let verifier = randomURLSafeString()
        let state = randomURLSafeString()
        let redirectURI = manual ? manualRedirect : loopbackRedirect

        var components = URLComponents(url: authorizeURL, resolvingAgainstBaseURL: false)!
        components.queryItems = [
            .init(name: "code", value: "true"),
            .init(name: "client_id", value: clientID),
            .init(name: "response_type", value: "code"),
            .init(name: "redirect_uri", value: redirectURI),
            .init(name: "scope", value: scopes),
            .init(name: "code_challenge", value: challenge(for: verifier)),
            .init(name: "code_challenge_method", value: "S256"),
            .init(name: "state", value: state),
        ]

        return Session(verifier: verifier, state: state, redirectURI: redirectURI, url: components.url!)
    }

    /// Opens the browser and waits for the loopback redirect.
    static func signInWithBrowser() async throws -> Credentials {
        let session = makeSession(manual: false)
        let server = LoopbackServer(port: loopbackPort)

        let query = try await withThrowingTaskGroup(of: LoopbackServer.CallbackQuery.self) { group in
            group.addTask { try await server.waitForCallback() }
            group.addTask {
                try await Task.sleep(for: signInTimeout)
                throw AuthError.timedOut
            }
            NSWorkspace.shared.open(session.url)
            defer { group.cancelAll() }
            return try await group.next()!
        }.items

        guard let code = query["code"] else { throw AuthError.noCode }
        guard query["state"] == session.state else { throw AuthError.stateMismatch }

        return try await exchange(code: code, session: session)
    }

    /// Completes the paste-the-code fallback. Claude renders the value as `code#state`.
    static func signIn(pastedCode raw: String, session: Session) async throws -> Credentials {
        let parts = raw.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "#")
        guard let code = parts.first, !code.isEmpty else { throw AuthError.noCode }
        if let state = parts.dropFirst().first, state != session.state {
            throw AuthError.stateMismatch
        }
        return try await exchange(code: String(code), session: session)
    }

    // MARK: - Token endpoint

    static func refresh(_ credentials: Credentials) async throws -> Credentials {
        guard let refreshToken = credentials.refreshToken else {
            throw AuthError.tokenExchangeFailed("No refresh token stored.")
        }
        return try await post([
            "grant_type": "refresh_token",
            "refresh_token": refreshToken,
            "client_id": clientID,
        ], fallbackRefreshToken: refreshToken)
    }

    private static func exchange(code: String, session: Session) async throws -> Credentials {
        try await post([
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": session.redirectURI,
            "client_id": clientID,
            "code_verifier": session.verifier,
            "state": session.state,
        ], fallbackRefreshToken: nil)
    }

    private struct TokenResponse: Decodable {
        let access_token: String
        let refresh_token: String?
        let expires_in: Double?
        let scope: String?
    }

    private static func post(
        _ body: [String: String],
        fallbackRefreshToken: String?
    ) async throws -> Credentials {
        var lastError = "The server did not respond."

        for url in tokenURLs {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(UsageAPI.userAgent, forHTTPHeaderField: "User-Agent")
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)

            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                let status = (response as? HTTPURLResponse)?.statusCode ?? 0
                guard (200..<300).contains(status) else {
                    lastError = message(from: data, status: status)
                    continue
                }
                let token = try JSONDecoder().decode(TokenResponse.self, from: data)
                return Credentials(
                    accessToken: token.access_token,
                    refreshToken: token.refresh_token ?? fallbackRefreshToken,
                    expiresAt: token.expires_in.map { Date(timeIntervalSinceNow: $0) },
                    scopes: token.scope?.split(separator: " ").map(String.init)
                )
            } catch {
                lastError = error.localizedDescription
            }
        }

        throw AuthError.tokenExchangeFailed(lastError)
    }

    private static func message(from data: Data, status: Int) -> String {
        let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        let detail = (json?["error_description"] ?? json?["error"]) as? String
        return detail ?? "HTTP \(status)."
    }

    // MARK: - PKCE

    private static func randomURLSafeString() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).urlSafeBase64
    }

    private static func challenge(for verifier: String) -> String {
        Data(SHA256.hash(data: Data(verifier.utf8))).urlSafeBase64
    }
}

private extension Data {
    var urlSafeBase64: String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
