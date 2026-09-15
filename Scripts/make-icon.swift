// Renders AppIcon.icns: a usage ring on a rounded, warm-neutral tile.

import AppKit

let sizes = [16, 32, 64, 128, 256, 512, 1024]
let output = URL(fileURLWithPath: CommandLine.arguments[1])
let iconset = output.deletingLastPathComponent().appending(path: "AppIcon.iconset")
try? FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)

func render(_ side: Int) -> Data {
    let size = CGFloat(side)
    let image = NSImage(size: NSSize(width: size, height: size), flipped: false) { rect in
        let tile = rect.insetBy(dx: size * 0.06, dy: size * 0.06)
        let plate = NSBezierPath(roundedRect: tile, xRadius: size * 0.22, yRadius: size * 0.22)
        NSGradient(
            starting: NSColor(srgbRed: 0xD9 / 255, green: 0x77 / 255, blue: 0x57 / 255, alpha: 1),
            ending: NSColor(srgbRed: 0xB4 / 255, green: 0x53 / 255, blue: 0x38 / 255, alpha: 1)
        )?.draw(in: plate, angle: -90)

        let line = size * 0.085
        let radius = size * 0.26
        let center = NSPoint(x: rect.midX, y: rect.midY)

        let track = NSBezierPath()
        track.appendArc(withCenter: center, radius: radius, startAngle: 0, endAngle: 360)
        track.lineWidth = line
        NSColor.white.withAlphaComponent(0.28).setStroke()
        track.stroke()

        let progress = NSBezierPath()
        progress.appendArc(withCenter: center, radius: radius, startAngle: 90, endAngle: -126, clockwise: true)
        progress.lineWidth = line
        progress.lineCapStyle = .round
        NSColor.white.setStroke()
        progress.stroke()
        return true
    }

    guard let tiff = image.tiffRepresentation,
          let data = NSBitmapImageRep(data: tiff)?.representation(using: .png, properties: [:])
    else { fatalError("render failed") }
    return data
}

for side in sizes {
    let data = render(side)
    let base = side > 512 ? "icon_512x512@2x" : "icon_\(side)x\(side)"
    try data.write(to: iconset.appending(path: "\(base).png"))
    if side <= 512 {
        try render(side * 2).write(to: iconset.appending(path: "icon_\(side)x\(side)@2x.png"))
    }
}

let iconutil = Process()
iconutil.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
iconutil.arguments = ["-c", "icns", iconset.path, "-o", output.path]
try iconutil.run()
iconutil.waitUntilExit()
try? FileManager.default.removeItem(at: iconset)
