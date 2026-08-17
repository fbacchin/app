import SwiftUI
import UIKit

/// Palette "notte indaco, cromo ambra": tema unico e voluto, da schermo di gioco.
enum Theme {
    static let notte = Color(red: 0.063, green: 0.063, blue: 0.141)      // #101024
    static let notteAlta = Color(red: 0.102, green: 0.102, blue: 0.227)  // #1a1a3a
    static let pozzo = Color(red: 0.043, green: 0.043, blue: 0.098)      // #0b0b19
    static let pannello = Color(red: 0.086, green: 0.086, blue: 0.188)   // #161630
    static let telaio = Color(red: 0.149, green: 0.149, blue: 0.290)     // #26264a
    static let telaioChiaro = Color(red: 0.204, green: 0.204, blue: 0.416)
    static let avorio = Color(red: 0.918, green: 0.906, blue: 0.859)     // #eae7db
    static let nebbia = Color(red: 0.561, green: 0.561, blue: 0.682)     // #8f8fae
    static let ambra = Color(red: 1.0, green: 0.706, blue: 0.329)        // #ffb454

    /// Colori dei pezzi, ordine I J L O S T Z.
    static let pieces: [Color] = [
        Color(red: 0.275, green: 0.784, blue: 0.878),  // I
        Color(red: 0.306, green: 0.420, blue: 0.878),  // J
        Color(red: 0.910, green: 0.573, blue: 0.235),  // L
        Color(red: 0.910, green: 0.776, blue: 0.235),  // O
        Color(red: 0.345, green: 0.784, blue: 0.431),  // S
        Color(red: 0.659, green: 0.408, blue: 0.878),  // T
        Color(red: 0.878, green: 0.345, blue: 0.408)   // Z
    ]
}

struct TetrisView: View {
    @State private var engine = TetrisEngine()
    @State private var drag: DragTracker?
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            background
            VStack(spacing: 10) {
                header
                hud
                stage
                controls
                Text("Trascina per muovere · tocca per ruotare · scorri giù per calare")
                    .font(.system(size: 10, weight: .regular, design: .monospaced))
                    .foregroundStyle(Theme.nebbia)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .frame(maxWidth: 560)
        }
        .persistentSystemOverlays(.hidden)
        .defersSystemGestures(on: .bottom)
        .focusable()
        .focusEffectDisabled()
        .onKeyPress(phases: [.down, .up]) { press in
            handleKey(press)
        }
        .onAppear {
            setupFeedback()
            engine.startLoop()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase != .active, engine.phase == .playing || engine.phase == .clearing {
                engine.togglePause()
            }
        }
    }

    private var background: some View {
        ZStack {
            Theme.notte
            RadialGradient(colors: [Theme.notteAlta, Theme.notte],
                           center: .top, startRadius: 0, endRadius: 520)
        }
        .ignoresSafeArea()
    }

    // MARK: - Intestazione
    private var header: some View {
        HStack {
            LogoView()
            Spacer()
            Button(action: pauseAction) {
                Image(systemName: engine.phase == .paused ? "play.fill" : "pause.fill")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Theme.nebbia)
                    .frame(width: 40, height: 40)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Theme.pannello))
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.telaio, lineWidth: 1))
            }
            .buttonStyle(PressableStyle())
            .accessibilityLabel("Pausa")
        }
    }

    // MARK: - Quadro punteggi
    private var hud: some View {
        HStack(spacing: 8) {
            statTile("Punti", value: engine.score, accent: true)
            statTile("Record", value: engine.best)
            statTile("Livello", value: engine.level)
            statTile("Linee", value: engine.lines)
        }
    }

    private func statTile(_ label: String, value: Int, accent: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(label.uppercased())
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .kerning(1.2)
                .foregroundStyle(Theme.nebbia)
            Text("\(value)")
                .font(.system(size: 19, weight: .bold, design: .monospaced))
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.5)
                .foregroundStyle(accent ? Theme.ambra : Theme.avorio)
                .shadow(color: accent ? Theme.ambra.opacity(0.35) : .clear, radius: 7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.pannello.opacity(0.8)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.telaio, lineWidth: 1))
    }

    // MARK: - Palco: tieni · pozzo · prossimi
    private var stage: some View {
        GeometryReader { geo in
            let sideW: CGFloat = 60
            let gap: CGFloat = 10
            let availW = geo.size.width - 2 * (sideW + gap)
            let cell = max(10, floor(min(availW / CGFloat(Campo.cols), geo.size.height / CGFloat(Campo.rows))))
            let wellW = cell * CGFloat(Campo.cols)
            let wellH = cell * CGFloat(Campo.rows)
            HStack(alignment: .top, spacing: gap) {
                miniPanel("Tieni") {
                    MiniPieceCanvas(kind: engine.holdKind, alpha: engine.canHold ? 1 : 0.38)
                }
                .frame(width: sideW)
                boardArea(cell: cell)
                    .frame(width: wellW, height: wellH)
                miniPanel("Prossimi") {
                    VStack(spacing: 2) {
                        MiniPieceCanvas(kind: preview(0), alpha: 1)
                        MiniPieceCanvas(kind: preview(1), alpha: 1)
                        MiniPieceCanvas(kind: preview(2), alpha: 1)
                    }
                }
                .frame(width: sideW)
            }
            .frame(width: geo.size.width, height: geo.size.height, alignment: .top)
        }
    }

    private func preview(_ i: Int) -> Int? {
        let q = engine.nextPreview
        return i < q.count ? q[i] : nil
    }

    private func miniPanel<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 6) {
            Text(title.uppercased())
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .kerning(1)
                .foregroundStyle(Theme.nebbia)
            content()
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.pannello.opacity(0.8)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.telaio, lineWidth: 1))
    }

    private func boardArea(cell: CGFloat) -> some View {
        let snap = BoardSnapshot(
            board: engine.board,
            activeKind: engine.currentKind,
            active: engine.currentCells,
            ghost: engine.ghostCells,
            clearing: engine.clearingRows,
            flash: engine.clearFlash
        )
        return ZStack {
            BoardView(snap: snap, cell: cell)
                .gesture(dragGesture(cell: cell))
            boardOverlay
        }
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.telaioChiaro, lineWidth: 1))
        .shadow(color: .black.opacity(0.5), radius: 22, y: 14)
    }

    // MARK: - Velo (pronto / pausa / fine partita)
    @ViewBuilder
    private var boardOverlay: some View {
        if engine.phase == .ready || engine.phase == .paused || engine.phase == .gameOver {
            VStack(spacing: 12) {
                Text(overlayTitle)
                    .font(.system(size: 21, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.avorio)
                Text(overlayMessage)
                    .font(.system(size: 13, weight: .regular, design: .default))
                    .foregroundStyle(Theme.nebbia)
                    .multilineTextAlignment(.center)
                    .lineSpacing(3)
                Button(action: startAction) {
                    Text(overlayButtonLabel)
                        .font(.system(size: 15, weight: .bold, design: .monospaced))
                        .kerning(1.2)
                        .foregroundStyle(Color(red: 0.14, green: 0.08, blue: 0.01))
                        .padding(.horizontal, 26)
                        .padding(.vertical, 12)
                        .background(
                            Capsule().fill(
                                LinearGradient(colors: [Color(red: 1.0, green: 0.77, blue: 0.46),
                                                        Color(red: 0.94, green: 0.63, blue: 0.24)],
                                               startPoint: .top, endPoint: .bottom)
                            )
                        )
                        .shadow(color: Theme.ambra.opacity(0.35), radius: 14, y: 5)
                }
                .buttonStyle(PressableStyle())
                .padding(.top, 4)
            }
            .padding(18)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.pozzo.opacity(0.86))
        }
    }

    private var overlayTitle: String {
        switch engine.phase {
        case .ready: return "Pronto?"
        case .paused: return "In pausa"
        case .gameOver: return "Fine partita"
        default: return ""
        }
    }

    private var overlayMessage: String {
        switch engine.phase {
        case .ready:
            return "Trascina sul pozzo per muovere,\ntocca per ruotare,\nscorri in giù per calare."
        case .paused:
            return "Il pozzo ti aspetta."
        case .gameOver:
            let prefix = engine.newRecord ? "Nuovo record! " : ""
            return "\(prefix)Hai totalizzato \(engine.score) punti\ncon \(engine.lines) linee."
        default:
            return ""
        }
    }

    private var overlayButtonLabel: String {
        switch engine.phase {
        case .paused: return "RIPRENDI"
        case .gameOver: return "GIOCA ANCORA"
        default: return "GIOCA"
        }
    }

    // MARK: - Pulsantiera
    private var controls: some View {
        HStack(alignment: .center) {
            HStack(spacing: 10) {
                HoldButton(symbol: "arrowtriangle.left.fill", size: 58,
                           onPress: { engine.pressMove(-1) },
                           onRelease: { engine.releaseMove(-1) })
                HoldButton(symbol: "arrowtriangle.down.fill", size: 58,
                           onPress: { engine.setSoftDrop(true) },
                           onRelease: { engine.setSoftDrop(false) })
                HoldButton(symbol: "arrowtriangle.right.fill", size: 58,
                           onPress: { engine.pressMove(1) },
                           onRelease: { engine.releaseMove(1) })
            }
            Spacer()
            VStack(spacing: 8) {
                HStack(spacing: 8) {
                    TapButton(symbol: "arrow.counterclockwise", size: 48, accent: true,
                              action: { engine.rotate(-1) })
                    TapButton(symbol: "arrow.clockwise", size: 48, accent: true,
                              action: { engine.rotate(1) })
                }
                HStack(spacing: 8) {
                    TapButton(symbol: "arrow.left.arrow.right", size: 48, accent: true,
                              action: { engine.holdPiece() })
                    TapButton(symbol: "arrow.down.to.line", size: 48, accent: true,
                              action: { engine.hardDrop() })
                }
            }
        }
    }

    // MARK: - Gesti sul pozzo
    private func dragGesture(cell: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 0)
            .onChanged { v in
                guard engine.phase == .playing else { return }
                if drag == nil {
                    drag = DragTracker(startLoc: v.location, lastLoc: v.location,
                                       startTime: Date(), moved: false)
                }
                guard var t = drag else { return }
                let step = cell * 0.72
                var dx = v.location.x - t.lastLoc.x
                var dy = v.location.y - t.lastLoc.y
                while dx >= step {
                    if engine.shift(1) { t.lastLoc.x += step; dx -= step; t.moved = true }
                    else { t.lastLoc.x = v.location.x; dx = 0 }
                }
                while dx <= -step {
                    if engine.shift(-1) { t.lastLoc.x -= step; dx += step; t.moved = true }
                    else { t.lastLoc.x = v.location.x; dx = 0 }
                }
                while dy >= step {
                    if engine.softStep() { t.lastLoc.y += step; dy -= step; t.moved = true }
                    else { t.lastLoc.y = v.location.y; dy = 0 }
                }
                if abs(v.location.x - t.startLoc.x) > 12 || abs(v.location.y - t.startLoc.y) > 12 {
                    t.moved = true
                }
                drag = t
            }
            .onEnded { v in
                let t = drag
                drag = nil
                guard engine.phase == .playing, let tracker = t else { return }
                let dt = Date().timeIntervalSince(tracker.startTime)
                let dx = v.location.x - tracker.startLoc.x
                let dy = v.location.y - tracker.startLoc.y
                if !tracker.moved && dt < 0.26 {
                    engine.rotate(1)
                } else if dy > 64 && dt < 0.26 && dy > 1.4 * abs(dx) {
                    engine.hardDrop()
                }
            }
    }

    // MARK: - Tastiera (iPad / Mac)
    private func handleKey(_ press: KeyPress) -> KeyPress.Result {
        let down = press.phase == .down
        switch press.key {
        case .leftArrow:
            if down { engine.pressMove(-1) } else { engine.releaseMove(-1) }
            return .handled
        case .rightArrow:
            if down { engine.pressMove(1) } else { engine.releaseMove(1) }
            return .handled
        case .downArrow:
            engine.setSoftDrop(down)
            return .handled
        case .upArrow:
            if down { engine.rotate(1) }
            return .handled
        case .space:
            if down { spaceAction() }
            return .handled
        case .escape:
            if down { pauseAction() }
            return .handled
        case .return:
            if down { startAction() }
            return .handled
        case KeyEquivalent("x"):
            if down { engine.rotate(1) }
            return .handled
        case KeyEquivalent("z"):
            if down { engine.rotate(-1) }
            return .handled
        case KeyEquivalent("c"):
            if down { engine.holdPiece() }
            return .handled
        case KeyEquivalent("p"):
            if down { pauseAction() }
            return .handled
        default:
            return .ignored
        }
    }

    // MARK: - Azioni
    private func startAction() {
        switch engine.phase {
        case .ready, .gameOver: engine.newGame()
        case .paused: engine.togglePause()
        default: break
        }
    }

    private func pauseAction() {
        switch engine.phase {
        case .playing, .clearing, .paused: engine.togglePause()
        default: break
        }
    }

    private func spaceAction() {
        if engine.phase == .playing { engine.hardDrop() } else { startAction() }
    }

    private func setupFeedback() {
        engine.onEvent = { event in
            switch event {
            case .lock:
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            case .hardDrop:
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            case .clear:
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            case .levelUp:
                UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
            case .gameOver:
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            default:
                break
            }
        }
    }
}

// MARK: - Istantanea del campo per il disegno
struct BoardSnapshot {
    var board: [[Int]]
    var activeKind: Int
    var active: [(x: Int, y: Int)]
    var ghost: [(x: Int, y: Int)]
    var clearing: [Int]
    var flash: Double
}

struct DragTracker {
    var startLoc: CGPoint
    var lastLoc: CGPoint
    var startTime: Date
    var moved: Bool
}

// MARK: - Pozzo
struct BoardView: View {
    let snap: BoardSnapshot
    let cell: CGFloat

    var body: some View {
        Canvas { ctx, size in
            // griglia sottile
            var grid = Path()
            for x in 1..<Campo.cols {
                grid.move(to: CGPoint(x: CGFloat(x) * cell, y: 0))
                grid.addLine(to: CGPoint(x: CGFloat(x) * cell, y: size.height))
            }
            for y in 1..<Campo.rows {
                grid.move(to: CGPoint(x: 0, y: CGFloat(y) * cell))
                grid.addLine(to: CGPoint(x: size.width, y: CGFloat(y) * cell))
            }
            ctx.stroke(grid, with: .color(Theme.avorio.opacity(0.045)), lineWidth: 1)

            // blocchi fissati
            for y in Campo.hidden..<Campo.total {
                for x in 0..<Campo.cols where snap.board[y][x] != 0 {
                    drawBlock(ctx, x: x, y: y - Campo.hidden, kind: snap.board[y][x] - 1, ghost: false)
                }
            }
            // ghost e pezzo attivo
            for c in snap.ghost where c.y >= Campo.hidden {
                drawBlock(ctx, x: c.x, y: c.y - Campo.hidden, kind: snap.activeKind, ghost: true)
            }
            for c in snap.active where c.y >= Campo.hidden {
                drawBlock(ctx, x: c.x, y: c.y - Campo.hidden, kind: snap.activeKind, ghost: false)
            }
            // lampo di cancellazione
            if !snap.clearing.isEmpty {
                let a = 0.2 + 0.75 * abs(sin(snap.flash * .pi * 3))
                for y in snap.clearing where y >= Campo.hidden {
                    let r = CGRect(x: 0, y: CGFloat(y - Campo.hidden) * cell,
                                   width: size.width, height: cell)
                    ctx.fill(Path(r), with: .color(Theme.avorio.opacity(a)))
                }
            }
        }
        .background(Theme.pozzo)
    }

    private func drawBlock(_ ctx: GraphicsContext, x: Int, y: Int, kind: Int, ghost: Bool) {
        let m = max(1, cell * 0.045)
        let rect = CGRect(x: CGFloat(x) * cell + m, y: CGFloat(y) * cell + m,
                          width: cell - 2 * m, height: cell - 2 * m)
        let path = Path(roundedRect: rect, cornerRadius: cell * 0.18)
        let color = Theme.pieces[kind]
        if ghost {
            ctx.fill(path, with: .color(color.opacity(0.11)))
            ctx.stroke(path, with: .color(color.opacity(0.6)), lineWidth: max(1.5, cell * 0.07))
        } else {
            ctx.fill(path, with: .color(color))
            let smalto = Gradient(stops: [
                .init(color: .white.opacity(0.32), location: 0),
                .init(color: .white.opacity(0.04), location: 0.42),
                .init(color: .clear, location: 0.68),
                .init(color: .black.opacity(0.28), location: 1)
            ])
            ctx.fill(path, with: .linearGradient(smalto,
                                                 startPoint: CGPoint(x: rect.midX, y: rect.minY),
                                                 endPoint: CGPoint(x: rect.midX, y: rect.maxY)))
            ctx.stroke(path, with: .color(.black.opacity(0.35)), lineWidth: 1)
        }
    }
}

// MARK: - Anteprima pezzo (tieni / prossimi)
struct MiniPieceCanvas: View {
    let kind: Int?
    let alpha: Double

    var body: some View {
        Canvas { ctx, size in
            guard let kind else { return }
            let unit: CGFloat = 10
            let cells = TetrisEngine.shapes[kind][0]
            let xs = cells.map { $0.x }
            let ys = cells.map { $0.y }
            guard let minX = xs.min(), let maxX = xs.max(),
                  let minY = ys.min(), let maxY = ys.max() else { return }
            let w = CGFloat(maxX - minX + 1) * unit
            let h = CGFloat(maxY - minY + 1) * unit
            let ox = (size.width - w) / 2
            let oy = (size.height - h) / 2
            for c in cells {
                let r = CGRect(x: ox + CGFloat(c.x - minX) * unit + unit * 0.06,
                               y: oy + CGFloat(c.y - minY) * unit + unit * 0.06,
                               width: unit * 0.88, height: unit * 0.88)
                ctx.fill(Path(roundedRect: r, cornerRadius: unit * 0.2),
                         with: .color(Theme.pieces[kind].opacity(alpha)))
                ctx.fill(Path(CGRect(x: r.minX + unit * 0.1, y: r.minY + unit * 0.08,
                                     width: r.width - unit * 0.2, height: unit * 0.14)),
                         with: .color(.white.opacity(0.25 * alpha)))
            }
        }
        .frame(width: 48, height: 40)
    }
}

// MARK: - Wordmark costruito con le tessere del gioco
struct LogoView: View {
    private static let glyphs: [Character: [String]] = [
        "T": ["111", "010", "010", "010", "010"],
        "E": ["111", "100", "110", "100", "111"],
        "R": ["110", "101", "110", "101", "101"],
        "I": ["111", "010", "010", "010", "111"],
        "S": ["011", "100", "010", "001", "110"]
    ]

    var body: some View {
        Canvas { ctx, _ in
            let word = Array("TETRIS")
            let pal = [5, 0, 3, 6, 4, 1]
            let u: CGFloat = 6
            for (i, ch) in word.enumerated() {
                guard let rows = LogoView.glyphs[ch] else { continue }
                let ox = CGFloat(i) * 4 * u
                for (y, row) in rows.enumerated() {
                    for (x, bit) in row.enumerated() where bit == "1" {
                        let rect = CGRect(x: ox + CGFloat(x) * u + 0.4, y: CGFloat(y) * u + 0.4,
                                          width: u - 0.8, height: u - 0.8)
                        ctx.fill(Path(roundedRect: rect, cornerRadius: 1.6),
                                 with: .color(Theme.pieces[pal[i]]))
                        ctx.fill(Path(CGRect(x: rect.minX + 0.7, y: rect.minY + 0.6,
                                             width: rect.width - 1.4, height: 1.3)),
                                 with: .color(.white.opacity(0.28)))
                    }
                }
            }
        }
        .frame(width: 138, height: 30)
        .accessibilityLabel("Tetris")
    }
}

// MARK: - Pulsanti
struct HoldButton: View {
    let symbol: String
    let size: CGFloat
    let onPress: () -> Void
    let onRelease: () -> Void
    @State private var pressed = false

    var body: some View {
        Keycap(symbol: symbol, size: size, accent: false, pressed: pressed)
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if !pressed {
                            pressed = true
                            onPress()
                        }
                    }
                    .onEnded { _ in
                        pressed = false
                        onRelease()
                    }
            )
    }
}

struct TapButton: View {
    let symbol: String
    let size: CGFloat
    var accent = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Keycap(symbol: symbol, size: size, accent: accent, pressed: false)
        }
        .buttonStyle(PressableStyle())
    }
}

struct Keycap: View {
    let symbol: String
    let size: CGFloat
    let accent: Bool
    let pressed: Bool

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: size * 0.34, weight: .bold))
            .foregroundStyle(accent ? Theme.ambra : Theme.avorio)
            .frame(width: size, height: size)
            .background(
                Circle().fill(
                    LinearGradient(colors: [Color(red: 0.133, green: 0.133, blue: 0.267),
                                            Color(red: 0.082, green: 0.082, blue: 0.188)],
                                   startPoint: .top, endPoint: .bottom)
                )
            )
            .overlay(Circle().stroke(Theme.telaioChiaro, lineWidth: 1))
            .shadow(color: .black.opacity(0.4), radius: 7, y: 4)
            .scaleEffect(pressed ? 0.92 : 1)
            .opacity(pressed ? 0.9 : 1)
    }
}

struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.92 : 1)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}

#Preview {
    TetrisView()
}
