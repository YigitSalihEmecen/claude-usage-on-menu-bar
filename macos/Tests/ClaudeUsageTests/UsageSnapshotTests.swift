// Covers both payload shapes Anthropic's usage endpoint returns.

import Foundation
import Testing
@testable import ClaudeUsage

private func decode(_ json: String) throws -> UsageSnapshot {
    UsageSnapshot(payload: try JSONDecoder().decode(UsagePayload.self, from: Data(json.utf8)))
}

@Suite("Usage payload decoding")
struct UsageSnapshotTests {
    @Test func legacyFlatPayload() throws {
        let snapshot = try decode("""
        {
          "five_hour": { "utilization": 42, "resets_at": "2026-09-15T23:00:00Z" },
          "seven_day": { "utilization": 37.5, "resets_at": "2026-09-19T09:00:00Z" },
          "seven_day_opus": { "utilization": 12, "resets_at": "2026-09-19T09:00:00Z" },
          "seven_day_sonnet": null,
          "extra_usage": { "is_enabled": true, "monthly_limit": 50, "used_credits": 4.25, "utilization": 8.5 }
        }
        """)

        #expect(snapshot.session?.percent == 42)
        #expect(abs((snapshot.session?.fraction ?? 0) - 0.42) < 0.0001)
        #expect(snapshot.weekly?.percent == 38)
        #expect(snapshot.scoped.map(\.title) == ["Weekly · Opus"])
        #expect(snapshot.extra?.isEnabled == true)
        #expect(snapshot.extra?.usedCredits == 4.25)
        #expect(snapshot.session?.resetsAt != nil)
    }

    @Test func limitsArrayTakesPrecedence() throws {
        let snapshot = try decode("""
        {
          "five_hour": { "utilization": 99, "resets_at": "2026-09-15T23:00:00Z" },
          "limits": [
            { "kind": "session", "group": "session", "percent": 9, "is_active": false },
            { "kind": "weekly_all", "group": "weekly", "percent": 55, "is_active": true,
              "resets_at": "2026-09-19T09:00:00Z" },
            { "kind": "weekly_scoped", "group": "weekly", "percent": 100, "is_active": true,
              "resets_at": "2026-09-19T09:00:00Z", "scope": { "model": { "display_name": "Fable" } } }
          ]
        }
        """)

        #expect(snapshot.session?.percent == 9)
        #expect(snapshot.session?.isActive == false)
        #expect(snapshot.weekly?.percent == 55)
        #expect(snapshot.scoped.map(\.title) == ["Weekly · Fable"])
        #expect(snapshot.windows.map(\.kind.sortRank) == [0, 1, 2])
    }

    @Test func unknownKindFallsBackToGroup() throws {
        let snapshot = try decode("""
        { "limits": [ { "group": "session", "percent": 20 }, { "group": "mystery", "percent": 90 } ] }
        """)

        #expect(snapshot.windows.count == 1)
        #expect(snapshot.session?.percent == 20)
    }

    @Test func fractionIsClampedAndEmptyPayloadIsSafe() throws {
        let snapshot = try decode("""
        { "five_hour": { "utilization": 160 }, "seven_day": { "utilization": -5 } }
        """)

        #expect(snapshot.session?.fraction == 1)
        #expect(snapshot.weekly?.fraction == 0)
        #expect(snapshot.session?.resetsAt == nil)
        #expect(try decode("{}").windows.isEmpty)
    }

    @Test("Timestamps parse with and without fractional seconds",
          arguments: ["2026-09-15T23:00:00Z", "2026-09-15T23:00:00.123Z"])
    func timestampVariants(stamp: String) throws {
        let snapshot = try decode(#"{ "five_hour": { "utilization": 10, "resets_at": "\#(stamp)" } }"#)
        #expect(snapshot.session?.resetsAt != nil)
    }
}

@Suite("Formatting")
struct FormatTests {
    private let now = Date(timeIntervalSince1970: 1_757_980_000)

    @Test(arguments: [
        (8040.0, false, "2h 14m"),
        (8040.0, true, "2h14m"),
        (2880.0, false, "48m"),
        (30.0, false, "<1m"),
        (-10.0, false, "now"),
        (187_200.0, false, "2d 4h"),
    ])
    func countdown(seconds: Double, compact: Bool, expected: String) {
        #expect(Format.countdown(to: now.addingTimeInterval(seconds), from: now, compact: compact) == expected)
    }

    @Test func relative() {
        #expect(Format.relative(now.addingTimeInterval(-2), from: now) == "just now")
        #expect(Format.relative(now.addingTimeInterval(-42), from: now) == "42s ago")
        #expect(Format.relative(now.addingTimeInterval(-300), from: now) == "5m ago")
    }
}
