import AppKit
import Foundation

let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
guard let bitmap = NSBitmapImageRep(data: data) else { fatalError("Screenshot unreadable") }
var violetPixels = 0
for y in stride(from: 0, to: bitmap.pixelsHigh, by: 4) {
    for x in stride(from: 0, to: bitmap.pixelsWide, by: 4) {
        if let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB),
           color.blueComponent > 0.55, color.redComponent < 0.4, color.greenComponent < 0.5 {
            violetPixels += 1
        }
    }
}
guard violetPixels > 500 else { fatalError("EDGE interface did not render; inspect the runtime logs") }
print("EDGE interface rendered: \(violetPixels) sampled violet pixels")
