import SwiftUI

/// Il volto del Maestro in stile cartoon, disegnato su una griglia 100×100.
/// Stessa geometria dell'icona dell'app: cupola larga, palpebre pesanti,
/// naso largo, ciuffi bianchi e tunica a strati.
struct YodaFaceView: View {

    private typealias Seg = ((Double, Double), (Double, Double), (Double, Double))

    var body: some View {
        Canvas { context, size in
            let s = min(size.width, size.height) / 100
            let ox = (size.width - 100 * s) / 2
            let oy = (size.height - 100 * s) / 2

            func pt(_ x: Double, _ y: Double) -> CGPoint {
                CGPoint(x: ox + x * s, y: oy + y * s)
            }
            func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> CGRect {
                CGRect(x: ox + x * s, y: oy + y * s, width: w * s, height: h * s)
            }
            func quadPath(_ segs: [Seg], closed: Bool = false) -> Path {
                var path = Path()
                path.move(to: pt(segs[0].0.0, segs[0].0.1))
                for seg in segs {
                    path.addQuadCurve(to: pt(seg.2.0, seg.2.1), control: pt(seg.1.0, seg.1.1))
                }
                if closed { path.closeSubpath() }
                return path
            }
            func fill(_ path: Path, _ color: Color) {
                context.fill(path, with: .color(color))
            }
            func stroke(_ path: Path, _ color: Color, _ width: Double) {
                context.stroke(path, with: .color(color),
                               style: StrokeStyle(lineWidth: width * s, lineCap: .round))
            }
            func circle(_ x: Double, _ y: Double, _ r: Double, _ color: Color) {
                fill(Path(ellipseIn: box(x - r, y - r, r * 2, r * 2)), color)
            }

            let skin = Color(hex: 0x8E9E64)
            let skinLight = Color(hex: 0xA6B47A)
            let skinDeep = Color(hex: 0x7E8E56)
            let skinDark = Color(hex: 0x647340)
            let outline = Color(hex: 0x546238)
            let wrinkle = Color(hex: 0x7A8955)
            let lid = Color(hex: 0x86955D)
            let eyeWhite = Color(hex: 0xF3F0E2)
            let iris = Color(hex: 0x82663A)
            let pupil = Color(hex: 0x201C16)
            let hair = Color(hex: 0xECEBE2)
            let robe = Color(hex: 0xCBC1A8)
            let trim = Color(hex: 0xA2967C)
            let tunic = Color(hex: 0x584232)

            // Capelli: ciuffi nell'incavo tra cupola e orecchio, e sotto l'orecchio
            for (hx, hy, hr) in [(31.0, 40.5, 3.0), (27.5, 40.0, 2.4), (33.5, 38.5, 2.2),
                                 (30.0, 61.0, 2.6), (26.5, 58.5, 2.0)] {
                circle(hx, hy, hr, hair)
                circle(100 - hx, hy, hr, hair)
            }

            // Orecchie lunghe, leggermente abbassate
            let leftEar = quadPath([((32, 44), (12, 33), (2, 34)),
                                    ((2, 34), (13, 55), (33, 60))], closed: true)
            fill(leftEar, skin)
            stroke(leftEar, outline, 0.6)
            let rightEar = quadPath([((68, 44), (88, 33), (98, 34)),
                                     ((98, 34), (87, 55), (67, 60))], closed: true)
            fill(rightEar, skin)
            stroke(rightEar, outline, 0.6)
            fill(quadPath([((30, 47), (14, 37), (7, 37)),
                           ((7, 37), (15, 52), (31, 57))], closed: true), skinDark)
            fill(quadPath([((70, 47), (86, 37), (93, 37)),
                           ((93, 37), (85, 52), (69, 57))], closed: true), skinDark)

            // Testa: cupola larga, mento stretto
            let head = quadPath([((50, 78), (38, 77), (33, 66)),
                                 ((33, 66), (27.5, 57), (30, 46)),
                                 ((30, 46), (31, 33), (43, 31)),
                                 ((43, 31), (50, 28.5), (57, 31)),
                                 ((57, 31), (69, 33), (70, 46)),
                                 ((70, 46), (72.5, 57), (67, 66)),
                                 ((67, 66), (62, 77), (50, 78))], closed: true)
            context.fill(head, with: .linearGradient(
                Gradient(stops: [.init(color: skinLight, location: 0),
                                 .init(color: skin, location: 0.45),
                                 .init(color: skinDeep, location: 1)]),
                startPoint: pt(50, 28.5),
                endPoint: pt(50, 78)))
            stroke(head, outline, 0.6)

            // Rughe della fronte
            stroke(quadPath([((44, 34.5), (50, 33), (56, 34.5))]), wrinkle, 0.8)
            stroke(quadPath([((39, 38.5), (50, 35.8), (61, 38.5))]), wrinkle, 0.9)
            stroke(quadPath([((37.5, 43), (50, 40.2), (62.5, 43))]), wrinkle, 0.9)

            // Occhi nocciola con palpebra pesante
            func eye(mirror: Bool) {
                func m(_ x: Double) -> Double { mirror ? 100 - x : x }

                let almond = quadPath([((m(37), 54), (m(41.5), 50.7), (m(46), 54)),
                                       ((m(46), 54), (m(41.5), 58.5), (m(37), 54))],
                                      closed: true)
                fill(almond, eyeWhite)
                let ix = m(41.5) + 0.7
                circle(ix, 54.5, 2.7, iris)
                circle(ix, 54.5, 1.35, pupil)
                circle(ix - 0.9, 53.4, 0.75, .white.opacity(0.92))
                circle(ix + 0.9, 55.6, 0.4, .white.opacity(0.7))
                let lidShape = quadPath([((m(37), 54), (m(41.5), 50.7), (m(46), 54)),
                                         ((m(46), 54), (m(41.5), 52.6), (m(37), 54))],
                                        closed: true)
                fill(lidShape, lid)
                stroke(quadPath([((m(37), 54), (m(41.5), 52.6), (m(46), 54))]), outline, 0.7)
                stroke(almond, outline, 0.55)
                stroke(quadPath([((m(37.5), 52.2), (m(41.5), 49.9), (m(45.5), 52.2))]), wrinkle, 0.6)
                stroke(quadPath([((m(36), 49.2), (m(41), 46.4), (m(47.2), 48.4))]), skinDark, 1.3)
                var feet = Path()
                feet.move(to: pt(m(35.8), 54.2))
                feet.addLine(to: pt(m(33.4), 53.2))
                feet.move(to: pt(m(35.9), 55.6))
                feet.addLine(to: pt(m(33.6), 56.4))
                stroke(feet, wrinkle, 0.6)
            }
            eye(mirror: false)
            eye(mirror: true)

            // Naso largo
            let nose = quadPath([((45.8, 62.8), (47, 58.5), (50, 58.2)),
                                 ((50, 58.2), (53, 58.5), (54.2, 62.8)),
                                 ((54.2, 62.8), (50, 65), (45.8, 62.8))], closed: true)
            fill(nose, Color(hex: 0x86965C))
            stroke(quadPath([((45.8, 62.8), (50, 65), (54.2, 62.8))]), outline, 0.7)
            fill(Path(ellipseIn: box(47.0, 62.0, 1.7, 1.1)), skinDark)
            fill(Path(ellipseIn: box(51.3, 62.0, 1.7, 1.1)), skinDark)

            // Pieghe naso-labiali, sorriso, labbro e fossetta
            stroke(quadPath([((44.5, 63), (42.8, 65.5), (42.5, 68.5))]), wrinkle, 0.7)
            stroke(quadPath([((55.5, 63), (57.2, 65.5), (57.5, 68.5))]), wrinkle, 0.7)
            stroke(quadPath([((43, 70.2), (50, 73.8), (57, 70.2))]), outline, 1.2)
            stroke(quadPath([((46.5, 74.8), (50, 76.1), (53.5, 74.8))]), wrinkle, 0.7)

            // Tunica a strati con sottotunica a V
            var robePath = Path()
            robePath.move(to: pt(16, 100))
            robePath.addLine(to: pt(17, 93))
            robePath.addQuadCurve(to: pt(50, 77.5), control: pt(30, 83))
            robePath.addQuadCurve(to: pt(83, 93), control: pt(70, 83))
            robePath.addLine(to: pt(84, 100))
            robePath.closeSubpath()
            fill(robePath, robe)
            stroke(quadPath([((17, 93), (30, 83), (50, 77.5)),
                             ((50, 77.5), (70, 83), (83, 93))]), trim, 1.3)
            var vNeck = Path()
            vNeck.move(to: pt(45, 78.6))
            vNeck.addLine(to: pt(55, 78.6))
            vNeck.addLine(to: pt(50, 87.5))
            vNeck.closeSubpath()
            fill(vNeck, tunic)
            stroke(quadPath([((26, 89.5), (30, 87), (35, 85.5))]), trim, 0.9)
            stroke(quadPath([((74, 89.5), (70, 87), (65, 85.5))]), trim, 0.9)
        }
    }
}

/// Distintivo circolare con il volto del Maestro e un alone verde.
struct YodaAvatarView: View {
    var size: CGFloat = 40

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [Color(hex: 0x1E3B18), Color(hex: 0x0B1424)],
                        center: .center,
                        startRadius: 0,
                        endRadius: size * 0.62
                    )
                )
            YodaFaceView()
                .padding(size * 0.07)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(
            Circle().strokeBorder(Color.saberGreen.opacity(0.7), lineWidth: max(1, size * 0.022))
        )
        .shadow(color: Color.saberGreen.opacity(0.45), radius: size * 0.12)
    }
}
