// Claude's warm palette. Single source for the panel meters and the menu bar tint.

import AppKit
import SwiftUI

enum Palette {
    struct Hue {
        let red, green, blue: Int

        var color: Color { Color(.sRGB, red: scale(red), green: scale(green), blue: scale(blue)) }
        var nsColor: NSColor { NSColor(srgbRed: scale(red), green: scale(green), blue: scale(blue), alpha: 1) }

        private func scale(_ channel: Int) -> Double { Double(channel) / 255 }
    }

    /// Claude clay — the resting accent for usage meters.
    static let clay = Hue(red: 0xD9, green: 0x77, blue: 0x57)
    /// Amber — past the warn threshold.
    static let amber = Hue(red: 0xE3, green: 0x96, blue: 0x2E)
    /// Warm red — nearly exhausted. Kept in the same family as clay.
    static let ember = Hue(red: 0xD2, green: 0x45, blue: 0x3D)
}
