import SwiftUI

/// Il volto del Maestro, disegnato in vettoriale su una griglia 100×100.
struct YodaFaceView: View {
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
            func stroke(_ path: Path, _ color: Color, _ width: Double) {
                context.stroke(path, with: .color(color),
                               style: StrokeStyle(lineWidth: width * s, lineCap: .round))
            }

            let skin = Color(hex: 0x8CB862)
            let skinLight = Color(hex: 0x9EC774)
            let skinDark = Color(hex: 0x68923F)
            let lineColor = Color(hex: 0x4A6832)
            let eyeColor = Color(hex: 0x26221B)

            // Orecchio sinistro
            var leftEar = Path()
            leftEar.move(to: pt(30, 50))
            leftEar.addQuadCurve(to: pt(3, 40), control: pt(12, 38))
            leftEar.addQuadCurve(to: pt(32, 62), control: pt(16, 58))
            leftEar.closeSubpath()
            context.fill(leftEar, with: .color(skin))

            var leftInner = Path()
            leftInner.move(to: pt(28, 52))
            leftInner.addQuadCurve(to: pt(8, 42), control: pt(14, 42))
            leftInner.addQuadCurve(to: pt(30, 59), control: pt(18, 55))
            leftInner.closeSubpath()
            context.fill(leftInner, with: .color(skinDark.opacity(0.55)))

            // Orecchio destro (speculare)
            var rightEar = Path()
            rightEar.move(to: pt(70, 50))
            rightEar.addQuadCurve(to: pt(97, 40), control: pt(88, 38))
            rightEar.addQuadCurve(to: pt(68, 62), control: pt(84, 58))
            rightEar.closeSubpath()
            context.fill(rightEar, with: .color(skin))

            var rightInner = Path()
            rightInner.move(to: pt(72, 52))
            rightInner.addQuadCurve(to: pt(92, 42), control: pt(86, 42))
            rightInner.addQuadCurve(to: pt(70, 59), control: pt(82, 55))
            rightInner.closeSubpath()
            context.fill(rightInner, with: .color(skinDark.opacity(0.55)))

            // Testa
            let headRect = box(29, 33, 42, 44)
            context.fill(
                Path(ellipseIn: headRect),
                with: .linearGradient(
                    Gradient(colors: [skinLight, skin]),
                    startPoint: pt(50, 33),
                    endPoint: pt(50, 77)
                )
            )

            // Rughe della fronte
            var wrinkle1 = Path()
            wrinkle1.move(to: pt(38, 42))
            wrinkle1.addQuadCurve(to: pt(62, 42), control: pt(50, 39))
            stroke(wrinkle1, lineColor.opacity(0.35), 0.9)

            var wrinkle2 = Path()
            wrinkle2.move(to: pt(40, 46))
            wrinkle2.addQuadCurve(to: pt(60, 46), control: pt(50, 43.5))
            stroke(wrinkle2, lineColor.opacity(0.35), 0.9)

            // Arcate sopraccigliari
            var leftBrow = Path()
            leftBrow.move(to: pt(36, 51))
            leftBrow.addQuadCurve(to: pt(47, 50), control: pt(41, 47.5))
            stroke(leftBrow, skinDark, 1.2)

            var rightBrow = Path()
            rightBrow.move(to: pt(64, 51))
            rightBrow.addQuadCurve(to: pt(53, 50), control: pt(59, 47.5))
            stroke(rightBrow, skinDark, 1.2)

            // Occhi grandi e dolci
            context.fill(Path(ellipseIn: box(37, 52, 10, 11)), with: .color(eyeColor))
            context.fill(Path(ellipseIn: box(53, 52, 10, 11)), with: .color(eyeColor))
            context.fill(Path(ellipseIn: box(39.3, 54.2, 3.4, 3.4)), with: .color(.white.opacity(0.92)))
            context.fill(Path(ellipseIn: box(57.3, 54.2, 3.4, 3.4)), with: .color(.white.opacity(0.92)))
            context.fill(Path(ellipseIn: box(42.8, 59, 1.7, 1.7)), with: .color(.white.opacity(0.7)))
            context.fill(Path(ellipseIn: box(55.5, 59, 1.7, 1.7)), with: .color(.white.opacity(0.7)))

            // Narici
            context.fill(Path(ellipseIn: box(47.2, 63.2, 1.7, 1.2)), with: .color(skinDark))
            context.fill(Path(ellipseIn: box(51.1, 63.2, 1.7, 1.2)), with: .color(skinDark))

            // Sorriso sereno
            var smile = Path()
            smile.move(to: pt(42, 68))
            smile.addQuadCurve(to: pt(58, 68), control: pt(50, 73))
            stroke(smile, lineColor, 1.4)

            // Tunica
            var robe = Path()
            robe.move(to: pt(22, 100))
            robe.addLine(to: pt(23, 93))
            robe.addQuadCurve(to: pt(50, 76.5), control: pt(33, 81.5))
            robe.addQuadCurve(to: pt(77, 93), control: pt(67, 81.5))
            robe.addLine(to: pt(78, 100))
            robe.closeSubpath()
            context.fill(robe, with: .color(Color(hex: 0xBFB59E)))

            var trim = Path()
            trim.move(to: pt(23, 93))
            trim.addQuadCurve(to: pt(50, 76.5), control: pt(33, 81.5))
            trim.addQuadCurve(to: pt(77, 93), control: pt(67, 81.5))
            stroke(trim, Color(hex: 0x7C7460), 1.1)
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
