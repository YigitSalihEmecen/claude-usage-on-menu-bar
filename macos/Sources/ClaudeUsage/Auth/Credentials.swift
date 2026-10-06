// OAuth token storage. Persists to the keychain and can adopt an existing
// Claude Code CLI login so the user does not have to authenticate twice.

import Foundation

struct Credentials: Codable, Equatable {
    var accessToken: String
    var refreshToken: String?
    /// Absolute expiry; nil when the server did not say.
    var expiresAt: Date?
    var scopes: [String]?

    var isExpired: Bool {
        guard let expiresAt else { return false }
        return expiresAt.timeIntervalSinceNow < 60
    }
}

enum CredentialStore {
    private static let service = "com.claudeusage.menubar"
    private static let account = "oauth"

    static func load() -> Credentials? {
        guard let data = Keychain.read(service: service, account: account) else { return nil }
        return try? JSONDecoder().decode(Credentials.self, from: data)
    }

    static func save(_ credentials: Credentials) {
        guard let data = try? JSONEncoder().encode(credentials) else { return }
        Keychain.write(data, service: service, account: account)
    }

    static func clear() {
        Keychain.delete(service: service, account: account)
    }

    /// Reads `~/.claude/.credentials.json` or the CLI's keychain item.
    static func importFromClaudeCode() -> Credentials? {
        struct CLIFile: Decodable {
            struct OAuth: Decodable {
                let accessToken: String
                let refreshToken: String?
                let expiresAt: Double?
                let scopes: [String]?
            }
            let claudeAiOauth: OAuth
        }

        let file = URL.homeDirectory.appending(path: ".claude/.credentials.json")
        let sources = [Keychain.read(service: "Claude Code-credentials"), try? Data(contentsOf: file)]

        for case let data? in sources {
            guard let decoded = try? JSONDecoder().decode(CLIFile.self, from: data) else { continue }
            let oauth = decoded.claudeAiOauth
            return Credentials(
                accessToken: oauth.accessToken,
                refreshToken: oauth.refreshToken,
                expiresAt: oauth.expiresAt.map { Date(timeIntervalSince1970: $0 / 1000) },
                scopes: oauth.scopes
            )
        }
        return nil
    }
}
