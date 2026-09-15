// Client for Anthropic's OAuth usage endpoint.

import Foundation

enum UsageError: LocalizedError {
    case unauthorized
    case rateLimited
    case http(Int)

    var errorDescription: String? {
        switch self {
        case .unauthorized: return "Your session expired. Please sign in again."
        case .rateLimited: return "Anthropic is rate-limiting usage checks. Retrying shortly."
        case .http(let code): return "Usage request failed (HTTP \(code))."
        }
    }
}

struct UsageAPI {
    /// Anthropic rate-limits this endpoint aggressively without a claude-code User-Agent.
    static let userAgent = "claude-code/2.0.0"

    private static let endpoint = URL(string: "https://api.anthropic.com/api/oauth/usage")!

    static func fetch(accessToken: String) async throws -> UsageSnapshot {
        var request = URLRequest(url: endpoint)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("oauth-2025-04-20", forHTTPHeaderField: "anthropic-beta")
        request.setValue(userAgent, forHTTPHeaderField: "User-Agent")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await URLSession.shared.data(for: request)

        switch (response as? HTTPURLResponse)?.statusCode ?? 0 {
        case 200..<300: break
        case 401, 403: throw UsageError.unauthorized
        case 429: throw UsageError.rateLimited
        case let code: throw UsageError.http(code)
        }

        return UsageSnapshot(payload: try JSONDecoder().decode(UsagePayload.self, from: data))
    }
}
