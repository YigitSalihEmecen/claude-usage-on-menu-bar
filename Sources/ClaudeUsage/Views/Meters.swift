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
