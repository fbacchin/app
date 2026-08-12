import SwiftUI

/// Sfondo interstellare: gradiente profondo, nebulose e campo stellare animato.
struct SpaceBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: 0x03010E), Color(hex: 0x0A0724), Color(hex: 0x160E38)],
                startPoint: .top,
                endPoint: .bottom
            )
            NebulaView()
            StarfieldView()
        }
        .ignoresSafeArea()
    }
}

private struct NebulaView: View {
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            ZStack {
                Circle()
                    .fill(Color(hex: 0x5B2A86).opacity(0.35))
                    .frame(width: w * 0.9)
                    .blur(radius: 80)
                    .position(x: w * 0.12, y: h * 0.18)
                Circle()
                    .fill(Color(hex: 0x1F6F6B).opacity(0.28))
                    .frame(width: w * 0.8)
                    .blur(radius: 90)
                    .position(x: w * 0.92, y: h * 0.5)
                Circle()
                    .fill(Color(hex: 0x30306E).opacity(0.4))
                    .frame(width: w * 0.9)
                    .blur(radius: 70)
                    .position(x: w * 0.5, y: h * 1.02)
            }
        }
        .allowsHitTesting(false)
    }
}
