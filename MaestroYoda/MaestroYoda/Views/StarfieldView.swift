import SwiftUI

/// Campo stellare animato: stelle che brillano e una stella cadente periodica.
struct StarfieldView: View {
    private struct Star {
        let x: Double
        let y: Double
        let radius: Double
        let baseOpacity: Double
        let twinkleSpeed: Double
        let phase: Double
    }

    private static let stars: [Star] = {
        var generator = SeededGenerator(seed: 42)
        return (0..<140).map { _ in
            Star(
                x: Double.random(in: 0...1, using: &generator),
                y: Double.random(in: 0...1, using: &generator),
                radius: Double.random(in: 0.6...1.9, using: &generator),
                baseOpacity: Double.random(in: 0.3...1.0, using: &generator),
                twinkleSpeed: Double.random(in: 0.6...2.4, using: &generator),
                phase: Double.random(in: 0...(2 * Double.pi), using: &generator)
            )
        }
    }()

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let t = timeline.date.timeIntervalSinceReferenceDate

                for star in Self.stars {
                    let twinkle = 0.65 + 0.35 * sin(t * star.twinkleSpeed + star.phase)
                    let rect = CGRect(
                        x: star.x * size.width - star.radius,
                        y: star.y * size.height - star.radius,
                        width: star.radius * 2,
                        height: star.radius * 2
                    )
                    context.fill(
                        Path(ellipseIn: rect),
                        with: .color(.white.opacity(star.baseOpacity * twinkle))
                    )
                }

                // Una stella cadente ogni ~9 secondi, su tre traiettorie diverse.
                let cycle = t.truncatingRemainder(dividingBy: 9)
                if cycle < 1.0 {
                    let progress = cycle
                    let lane = (t / 9).rounded(.down).truncatingRemainder(dividingBy: 3)
                    let startX = size.width * (0.12 + 0.22 * lane)
                    let startY = size.height * (0.1 + 0.16 * lane)
                    let dx = size.width * 0.55 * progress
                    let head = CGPoint(x: startX + dx, y: startY + dx * 0.35)
                    let tail = CGPoint(x: head.x - 70, y: head.y - 24.5)
                    var streak = Path()
                    streak.move(to: tail)
                    streak.addLine(to: head)
                    let fade = sin(progress * Double.pi)
                    context.stroke(
                        streak,
                        with: .linearGradient(
                            Gradient(colors: [.clear, .white.opacity(0.8 * fade)]),
                            startPoint: tail,
                            endPoint: head
                        ),
                        lineWidth: 1.6
                    )
                }
            }
        }
        .allowsHitTesting(false)
    }
}

/// Generatore deterministico: il cielo resta identico a ogni avvio.
struct SeededGenerator: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed &+ 0x9E3779B97F4A7C15
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}
