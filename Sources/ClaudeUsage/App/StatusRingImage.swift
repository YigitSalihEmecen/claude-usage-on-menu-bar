// Draws the small progress ring used as the status item icon. Rendered as a
// template image at normal usage so macOS tints it like any system glyph.

import AppKit

enum StatusRingImage {
    static func make(fraction: Double?, tint: NSColor?) -> NSImage {
        let diameter: CGFloat = 15
        let lineWidth: CGFloat = 2
        let size = NSSize(width: diameter, height: diameter)

        let image = NSImage(size: size, flipped: false) { _ in
            let inset = lineWidth / 2
            let rect = NSRect(origin: .zero, size: size).insetBy(dx: inset, dy: inset)
            let center = NSPoint(x: rect.midX, y: rect.midY)
            let radius = rect.width / 2

            let track = NSBezierPath()
            track.appendArc(withCenter: center, radius: radius, startAngle: 0, endAngle: 360)
            track.lineWidth = lineWidth
            (tint ?? .black).withAlphaComponent(0.3).setStroke()
            track.stroke()

            guard let fraction, fraction > 0 else {
                Self.drawDot(center: center, color: tint ?? .black)
                return true
            }

            let progress = NSBezierPath()
            progress.appendArc(
                withCenter: center,
                radius: radius,
                startAngle: 90,
                endAngle: 90 - 360 * min(fraction, 1),
                clockwise: true
            )
            progress.lineWidth = lineWidth
            progress.lineCapStyle = .round
            (tint ?? .black).setStroke()
            progress.stroke()
            return true
        }

        image.isTemplate = tint == nil
        return image
    }

    private static func drawDot(center: NSPoint, color: NSColor) {
        let dot = NSBezierPath(
            ovalIn: NSRect(x: center.x - 1.5, y: center.y - 1.5, width: 3, height: 3)
        )
        color.withAlphaComponent(0.55).setFill()
        dot.fill()
    }
}
