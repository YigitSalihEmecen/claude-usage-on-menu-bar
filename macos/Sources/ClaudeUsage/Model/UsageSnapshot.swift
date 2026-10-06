// Normalized view of Anthropic's rate-limit windows, decoded from either the
// legacy flat payload (five_hour / seven_day / ...) or the newer limits[] array.

import Foundation

enum WindowKind: String {
    case session
    case weekly
    case weeklyScoped

    var sortRank: Int {
        switch self {
        case .session: return 0
        case .weekly: return 1
        case .weeklyScoped: return 2
        }
    }
}

struct UsageWindow: Identifiable, Equatable {
    let id: String
    let kind: WindowKind
    let title: String
    /// Fraction in 0...1.
    let fraction: Double
    let resetsAt: Date?
    let isActive: Bool

    var percent: Int { Int((fraction * 100).rounded()) }
}

struct ExtraUsage: Equatable {
    let isEnabled: Bool
    let monthlyLimit: Double?
    let usedCredits: Double?
    let fraction: Double?
}

struct UsageSnapshot: Equatable {
    var windows: [UsageWindow]
    var extra: ExtraUsage?

    var session: UsageWindow? { windows.first { $0.kind == .session } }
    var weekly: UsageWindow? { windows.first { $0.kind == .weekly } }
    var scoped: [UsageWindow] { windows.filter { $0.kind == .weeklyScoped } }
}

// MARK: - Decoding

extension UsageSnapshot {
    init(payload: UsagePayload) {
        var windows: [UsageWindow] = []

        if let limits = payload.limits, !limits.isEmpty {
            var scopedIndex = 0
            for limit in limits {
                guard let kind = limit.resolvedKind else { continue }
                let name = limit.scope?.model?.display_name
                let id: String
                switch kind {
                case .session: id = "session"
                case .weekly: id = "weekly"
                case .weeklyScoped:
                    scopedIndex += 1
                    id = "weekly-" + (name?.lowercased() ?? "scoped-\(scopedIndex)")
                }
                windows.append(
                    UsageWindow(
                        id: id,
                        kind: kind,
                        title: kind.label(modelName: name),
                        fraction: UsageSnapshot.clamp(limit.effectivePercent),
                        resetsAt: UsageSnapshot.date(from: limit.resets_at),
                        isActive: limit.is_active ?? true
                    )
                )
            }
        }

        if windows.isEmpty {
            let legacy: [(String, WindowKind, String?, UsagePayload.Window?)] = [
                ("session", .session, nil, payload.five_hour),
                ("weekly", .weekly, nil, payload.seven_day),
                ("weekly-opus", .weeklyScoped, "Opus", payload.seven_day_opus),
                ("weekly-sonnet", .weeklyScoped, "Sonnet", payload.seven_day_sonnet),
            ]
            for (id, kind, name, window) in legacy {
                guard let window else { continue }
                windows.append(
                    UsageWindow(
                        id: id,
                        kind: kind,
                        title: kind.label(modelName: name),
                        fraction: UsageSnapshot.clamp(window.utilization),
                        resetsAt: UsageSnapshot.date(from: window.resets_at),
                        isActive: true
                    )
                )
            }
        }

        windows.sort { lhs, rhs in
            lhs.kind.sortRank == rhs.kind.sortRank
                ? lhs.title < rhs.title
                : lhs.kind.sortRank < rhs.kind.sortRank
        }

        self.windows = windows
        self.extra = payload.extra_usage.map {
            ExtraUsage(
                isEnabled: $0.is_enabled ?? false,
                monthlyLimit: $0.monthly_limit,
                usedCredits: $0.used_credits,
                fraction: $0.utilization.map(UsageSnapshot.clamp)
            )
        }
    }

    private static func clamp(_ percent: Double?) -> Double {
        min(max((percent ?? 0) / 100, 0), 1)
    }

    private static func date(from string: String?) -> Date? {
        guard let string, !string.isEmpty else { return nil }
        for formatter in ISO8601DateFormatter.candidates {
            if let date = formatter.date(from: string) { return date }
        }
        return nil
    }
}

private extension WindowKind {
    func label(modelName: String?) -> String {
        switch self {
        case .session: return "Session"
        case .weekly: return "Weekly"
        case .weeklyScoped: return modelName.map { "Weekly · \($0)" } ?? "Weekly · model"
        }
    }
}

struct UsagePayload: Decodable {
    struct Window: Decodable {
        let utilization: Double?
        let resets_at: String?
    }

    struct Limit: Decodable {
        struct Scope: Decodable {
            struct Model: Decodable { let display_name: String? }
            let model: Model?
        }
        let kind: String?
        let group: String?
        let percent: Double?
        let utilization: Double?
        let is_active: Bool?
        let resets_at: String?
        let scope: Scope?

        var resolvedKind: WindowKind? {
            switch kind {
            case "session": return .session
            case "weekly_all": return .weekly
            case "weekly_scoped": return .weeklyScoped
            default: return group == "session" ? .session : group == "weekly" ? .weekly : nil
            }
        }
    }

    struct Extra: Decodable {
        let is_enabled: Bool?
        let monthly_limit: Double?
        let used_credits: Double?
        let utilization: Double?
    }

    let five_hour: Window?
    let seven_day: Window?
    let seven_day_opus: Window?
    let seven_day_sonnet: Window?
    let limits: [Limit]?
    let extra_usage: Extra?
}

extension UsagePayload.Limit {
    var effectivePercent: Double? { percent ?? utilization }
}

extension ISO8601DateFormatter {
    static let candidates: [ISO8601DateFormatter] = {
        let options: [Options] = [
            [.withInternetDateTime],
            [.withInternetDateTime, .withFractionalSeconds],
        ]
        return options.map {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = $0
            return formatter
        }
    }()
}
