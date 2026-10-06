// Reusable usage indicators: the large session ring and the compact window bars.

import SwiftUI

struct UsageRing: View {
    let fraction: Double
    let color: Color
    var lineWidth: CGFloat = 9
    var size: CGFloat = 96

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.primary.opacity(0.09), lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: max(fraction, 0.001))
                .stroke(color.gradient, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.smooth(duration: 0.5), value: fraction)

            VStack(spacing: -1) {
                Text("\(Int((fraction * 100).rounded()))")
                    .font(.system(size: 28, weight: .medium, design: .rounded))
                    .monospacedDigit()
                Text("percent")
                    .font(.system(size: 9, weight: .medium))
                    .textCase(.uppercase)
                    .kerning(0.5)
                    .foregroundStyle(.tertiary)
            }
        }
        .frame(width: size, height: size)
    }
}

struct UsageBar: View {
    let fraction: Double
    let color: Color

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.primary.opacity(0.09))
                Capsule()
                    .fill(color.gradient)
                    .frame(width: max(geometry.size.width * fraction, fraction > 0 ? 5 : 0))
                    .animation(.smooth(duration: 0.5), value: fraction)
            }
        }
        .frame(height: 6)
    }
}

/// Context window of the most recent Claude Code session. Unlike the usage
/// windows this is read from disk, so it carries the project it came from.
struct ContextRow: View {
    let context: ContextUsage
    let warnThreshold: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text("Context")
                    .font(.system(size: 12, weight: .medium))
                Spacer(minLength: 8)
                Text("\(Format.tokens(context.tokens)) / \(Format.compactTokens(context.limit))")
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                Text("\(context.percent)%")
                    .font(.system(size: 12, weight: .medium))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            UsageBar(
                fraction: context.fraction,
                color: context.fraction.usageColor(warnThreshold: warnThreshold)
            )
            Text(context.project)
                .font(.system(size: 10))
                .foregroundStyle(.tertiary)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }
}

struct WindowRow: View {
    let window: UsageWindow
    let now: Date
    let warnThreshold: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(window.title)
                    .font(.system(size: 12, weight: .medium))
                Spacer(minLength: 8)
                Text("\(window.percent)%")
                    .font(.system(size: 12, weight: .medium))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            UsageBar(fraction: window.fraction, color: window.fraction.usageColor(warnThreshold: warnThreshold))
            if let resetsAt = window.resetsAt {
                Text("Resets in \(Format.countdown(to: resetsAt, from: now)) · \(Format.resetTime(resetsAt))")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
            }
        }
    }
}
