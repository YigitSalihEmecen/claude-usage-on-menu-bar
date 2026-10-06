// Compact duration and timestamp formatting for the menu bar and panel.

import SwiftUI

enum Format {
    /// "2h 14m", "48m", "<1m" — tuned to stay short in the menu bar.
    static func countdown(to date: Date, from now: Date = .now, compact: Bool = false) -> String {
        let remaining = Int(date.timeIntervalSince(now))
        guard remaining > 0 else { return "now" }

        let hours = remaining / 3600
        let minutes = (remaining % 3600) / 60
        let gap = compact ? "" : " "

        if hours >= 24 {
            let days = hours / 24
            return "\(days)d\(gap)\(hours % 24)h"
        }
        if hours > 0 { return "\(hours)h\(gap)\(minutes)m" }
        return minutes > 0 ? "\(minutes)m" : "<1m"
    }

    static func resetTime(_ date: Date) -> String {
        date.formatted(
            .dateTime
                .weekday(.abbreviated)
                .hour(.defaultDigits(amPM: .abbreviated))
                .minute()
        )
    }

    /// "50,009" — grouped, for the panel where there is room.
    static func tokens(_ count: Int) -> String {
        count.formatted(.number.grouping(.automatic))
    }

    /// "50K", "1.0M" — for the context limit and the menu bar.
    static func compactTokens(_ count: Int) -> String {
        if count >= 1_000_000 {
            let millions = Double(count) / 1_000_000
            return millions == millions.rounded()
                ? "\(Int(millions))M"
                : String(format: "%.1fM", millions)
        }
        if count >= 1_000 { return "\(count / 1_000)K" }
        return "\(count)"
    }

    static func relative(_ date: Date, from now: Date = .now) -> String {
        let seconds = Int(now.timeIntervalSince(date))
        if seconds < 5 { return "just now" }
        if seconds < 60 { return "\(seconds)s ago" }
        return "\(seconds / 60)m ago"
    }
}

extension Double {
    /// Colour ramp shared by the ring, bars and menu bar tint.
    func usageHue(warnThreshold: Double) -> Palette.Hue {
        if self >= 0.95 { return Palette.ember }
        if self >= warnThreshold { return Palette.amber }
        return Palette.clay
    }

    func usageColor(warnThreshold: Double) -> Color {
        usageHue(warnThreshold: warnThreshold).color
    }
}
