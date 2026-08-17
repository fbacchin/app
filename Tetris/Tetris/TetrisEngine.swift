import Foundation
import Observation

/// Dimensioni del campo: 10×20 visibili + 2 righe nascoste in alto per lo spawn.
enum Campo {
    static let cols = 10
    static let rows = 20
    static let hidden = 2
    static let total = 22
}

enum GamePhase {
    case ready, playing, clearing, paused, gameOver
}

enum GameEvent {
    case move, rotate, lock, hardDrop, hold, clear(Int), levelUp, gameOver
}

struct ActivePiece {
    var kind: Int
    var rot: Int
    var x: Int
    var y: Int
}

/// Motore di gioco con regole moderne: rotazione SRS con wall kick,
/// sacchetto da 7, ghost piece, tieni, lock delay con 15 rinnovi,
/// curva di velocità guideline e punteggio 100/300/500/800 × livello.
@Observable
final class TetrisEngine {

    // MARK: - Tempi (secondi)
    private let dasDelay = 0.170
    private let arrDelay = 0.040
    private let lockDelay = 0.500
    private let maxLockResets = 15
    private let clearDuration = 0.300
    private let softInterval = 0.045

    // MARK: - Forme: shapes[pezzo][rotazione] = 4 celle. Ordine: I J L O S T Z.
    static let shapes: [[[(x: Int, y: Int)]]] = buildShapes()

    private static func buildShapes() -> [[[(x: Int, y: Int)]]] {
        let base: [(n: Int, cells: [(Int, Int)])] = [
            (4, [(0, 1), (1, 1), (2, 1), (3, 1)]),   // I
            (3, [(0, 0), (0, 1), (1, 1), (2, 1)]),   // J
            (3, [(2, 0), (0, 1), (1, 1), (2, 1)]),   // L
            (2, [(0, 0), (1, 0), (0, 1), (1, 1)]),   // O
            (3, [(1, 0), (2, 0), (0, 1), (1, 1)]),   // S
            (3, [(1, 0), (0, 1), (1, 1), (2, 1)]),   // T
            (3, [(0, 0), (1, 0), (1, 1), (2, 1)])    // Z
        ]
        return base.map { piece in
            var states: [[(x: Int, y: Int)]] = [piece.cells.map { (x: $0.0, y: $0.1) }]
            for r in 1..<4 {
                let prev = states[r - 1]
                states.append(prev.map { (x: piece.n - 1 - $0.y, y: $0.x) })
            }
            return states
        }
    }

    // MARK: - Wall kick SRS (convenzione guideline, y verso l'alto: negata all'uso)
    private static let kicksJLSTZ: [String: [(Int, Int)]] = [
        "0>1": [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
        "1>0": [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
        "1>2": [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
        "2>1": [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
        "2>3": [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
        "3>2": [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
        "3>0": [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
        "0>3": [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)]
    ]
    private static let kicksI: [String: [(Int, Int)]] = [
        "0>1": [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
        "1>0": [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
        "1>2": [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
        "2>1": [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
        "2>3": [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
        "3>2": [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
        "3>0": [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
        "0>3": [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)]
    ]

    // MARK: - Stato osservato dalla vista
    private(set) var board: [[Int]] = TetrisEngine.emptyBoard()
    private(set) var current: ActivePiece?
    private(set) var holdKind: Int?
    private(set) var canHold = true
    private(set) var queue: [Int] = []
    private(set) var score = 0
    private(set) var lines = 0
    private(set) var level = 1
    private(set) var best = UserDefaults.standard.integer(forKey: "tetris_record")
    private(set) var phase: GamePhase = .ready
    private(set) var clearingRows: [Int] = []
    private(set) var clearFlash = 0.0
    private(set) var newRecord = false

    var onEvent: ((GameEvent) -> Void)?

    // MARK: - Stato interno
    private var dropAcc = 0.0
    private var softHeld = false
    private var dasDir = 0
    private var dasStart = 0.0
    private var dasLast = 0.0
    private var lockStart: Double?
    private var lockResets = 0
    private var lowestY = 0
    private var clearElapsed = 0.0
    private var pausedFrom = GamePhase.playing
    private var lastTick = 0.0
    private var timer: Timer?

    private static func emptyBoard() -> [[Int]] {
        Array(repeating: Array(repeating: 0, count: Campo.cols), count: Campo.total)
    }

    private var now: Double { ProcessInfo.processInfo.systemUptime }

    // MARK: - Ciclo di gioco
    func startLoop() {
        guard timer == nil else { return }
        lastTick = now
        let t = Timer(timeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
        t.tolerance = 0.002
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func stopLoop() {
        timer?.invalidate()
        timer = nil
    }

    private func tick() {
        let t = now
        let dt = min(0.1, t - lastTick)
        lastTick = t
        switch phase {
        case .playing:
            updatePlaying(dt: dt, now: t)
        case .clearing:
            clearElapsed += dt
            clearFlash = min(1.0, clearElapsed / clearDuration)
            if clearElapsed >= clearDuration { finishClear() }
        default:
            break
        }
    }

    private func updatePlaying(dt: Double, now t: Double) {
        // auto-ripetizione laterale (DAS/ARR)
        if dasDir != 0, t - dasStart >= dasDelay {
            var guardCount = 0
            while t - dasLast >= arrDelay, guardCount < Campo.cols {
                guardCount += 1
                if shift(dasDir) {
                    dasLast += arrDelay
                } else {
                    dasLast = t
                    break
                }
            }
        }
        // gravità (accelerata se la discesa morbida è tenuta premuta)
        let interval = softHeld ? min(gravityInterval, softInterval) : gravityInterval
        dropAcc += dt
        var guardCount = 0
        while dropAcc >= interval, guardCount < Campo.total {
            guardCount += 1
            dropAcc -= interval
            gravityStep()
            if phase != .playing { return }
        }
        if let started = lockStart, t - started >= lockDelay {
            lockPiece()
        }
    }

    /// Secondi per riga alla velocità del livello corrente (curva guideline).
    private var gravityInterval: Double {
        let l = Double(min(level, 20))
        return max(0.008, pow(0.8 - (l - 1) * 0.007, l - 1))
    }

    // MARK: - Geometria
    private func cells(of p: ActivePiece) -> [(x: Int, y: Int)] {
        TetrisEngine.shapes[p.kind][p.rot].map { (x: p.x + $0.x, y: p.y + $0.y) }
    }

    private func collides(_ p: ActivePiece) -> Bool {
        for c in cells(of: p) {
            if c.x < 0 || c.x >= Campo.cols || c.y >= Campo.total { return true }
            if c.y >= 0 && board[c.y][c.x] != 0 { return true }
        }
        return false
    }

    private var isGrounded: Bool {
        guard var p = current else { return false }
        p.y += 1
        return collides(p)
    }

    var currentKind: Int { current?.kind ?? 0 }

    var currentCells: [(x: Int, y: Int)] {
        guard let c = current, phase == .playing || phase == .paused else { return [] }
        return cells(of: c)
    }

    var ghostCells: [(x: Int, y: Int)] {
        guard var p = current, phase == .playing || phase == .paused else { return [] }
        var moved = false
        while true {
            var q = p
            q.y += 1
            if collides(q) { break }
            p = q
            moved = true
        }
        return moved ? cells(of: p) : []
    }

    var nextPreview: [Int] { Array(queue.prefix(3)) }

    // MARK: - Sacchetto da 7
    private func refill() {
        while queue.count < 7 {
            queue.append(contentsOf: [0, 1, 2, 3, 4, 5, 6].shuffled())
        }
    }

    @discardableResult
    private func spawn(_ kind: Int) -> Bool {
        let p = ActivePiece(kind: kind, rot: 0, x: kind == 3 ? 4 : 3, y: Campo.hidden - 1)
        current = p
        dropAcc = 0
        lockStart = nil
        lockResets = 0
        lowestY = p.y
        if collides(p) {
            endGame()
            return false
        }
        return true
    }

    private func spawnNext() {
        refill()
        let k = queue.removeFirst()
        spawn(k)
    }

    // MARK: - Comandi
    /// Un movimento riuscito mentre il pezzo è appoggiato rinnova il lock delay.
    private func afterSuccessfulMove() {
        if lockStart != nil, lockResets < maxLockResets {
            lockStart = now
            lockResets += 1
        }
        if !isGrounded { lockStart = nil }
    }

    @discardableResult
    func shift(_ dx: Int) -> Bool {
        guard phase == .playing, var p = current else { return false }
        p.x += dx
        guard !collides(p) else { return false }
        current = p
        afterSuccessfulMove()
        onEvent?(.move)
        return true
    }

    func rotate(_ dir: Int) {
        guard phase == .playing, let c = current, c.kind != 3 else { return }
        let from = c.rot
        let to = ((from + dir) % 4 + 4) % 4
        let table = c.kind == 0 ? TetrisEngine.kicksI : TetrisEngine.kicksJLSTZ
        guard let kicks = table["\(from)>\(to)"] else { return }
        for k in kicks {
            var p = c
            p.rot = to
            p.x += k.0
            p.y -= k.1
            if !collides(p) {
                current = p
                afterSuccessfulMove()
                onEvent?(.rotate)
                return
            }
        }
    }

    func pressMove(_ dir: Int) {
        dasDir = dir
        dasStart = now
        dasLast = dasStart + dasDelay - arrDelay
        shift(dir)
    }

    func releaseMove(_ dir: Int) {
        if dasDir == dir { dasDir = 0 }
    }

    func setSoftDrop(_ on: Bool) {
        softHeld = on
    }

    /// Discesa morbida di una riga, usata dal trascinamento verso il basso.
    @discardableResult
    func softStep() -> Bool {
        guard phase == .playing, var p = current else { return false }
        p.y += 1
        guard !collides(p) else { return false }
        current = p
        score += 1
        if p.y > lowestY { lowestY = p.y; lockResets = 0 }
        lockStart = nil
        return true
    }

    private func gravityStep() {
        guard var p = current else { return }
        p.y += 1
        if !collides(p) {
            current = p
            if softHeld { score += 1 }
            if p.y > lowestY { lowestY = p.y; lockResets = 0 }
            lockStart = nil
        } else if lockStart == nil {
            lockStart = now
        }
    }

    func hardDrop() {
        guard phase == .playing, var p = current else { return }
        var dist = 0
        while true {
            var q = p
            q.y += 1
            if collides(q) { break }
            p = q
            dist += 1
        }
        current = p
        score += 2 * dist
        onEvent?(.hardDrop)
        lockPiece()
    }

    func holdPiece() {
        guard phase == .playing, canHold, let c = current else { return }
        canHold = false
        onEvent?(.hold)
        if let h = holdKind {
            holdKind = c.kind
            spawn(h)
        } else {
            holdKind = c.kind
            spawnNext()
        }
    }

    // MARK: - Blocco e cancellazione righe
    private func lockPiece() {
        guard let c = current else { return }
        var allAbove = true
        for cell in cells(of: c) {
            if cell.y < 0 { endGame(); return }
            if cell.y >= Campo.hidden { allAbove = false }
            board[cell.y][cell.x] = c.kind + 1
        }
        if allAbove { endGame(); return }   // lock out: tutto sopra il pozzo
        canHold = true
        lockStart = nil
        let full = (0..<Campo.total).filter { y in board[y].allSatisfy { $0 != 0 } }
        if full.isEmpty {
            onEvent?(.lock)
            spawnNext()
        } else {
            phase = .clearing
            clearingRows = full
            clearElapsed = 0
            clearFlash = 0
            onEvent?(.clear(full.count))
        }
    }

    private func finishClear() {
        let removed = Set(clearingRows)
        var newBoard = board.enumerated().filter { !removed.contains($0.offset) }.map { $0.element }
        while newBoard.count < Campo.total {
            newBoard.insert(Array(repeating: 0, count: Campo.cols), at: 0)
        }
        board = newBoard
        let n = clearingRows.count
        let table = [0, 100, 300, 500, 800]
        score += table[min(n, 4)] * level
        lines += n
        let newLevel = lines / 10 + 1
        if newLevel > level {
            level = newLevel
            onEvent?(.levelUp)
        }
        clearingRows = []
        clearFlash = 0
        phase = .playing
        spawnNext()
    }

    // MARK: - Flusso di partita
    func newGame() {
        board = TetrisEngine.emptyBoard()
        queue = []
        holdKind = nil
        canHold = true
        score = 0
        lines = 0
        level = 1
        newRecord = false
        softHeld = false
        dasDir = 0
        clearingRows = []
        clearFlash = 0
        refill()
        phase = .playing
        spawnNext()
        startLoop()
    }

    private func endGame() {
        phase = .gameOver
        dasDir = 0
        softHeld = false
        newRecord = score > best && score > 0
        if newRecord {
            best = score
            UserDefaults.standard.set(best, forKey: "tetris_record")
        }
        onEvent?(.gameOver)
    }

    func togglePause() {
        switch phase {
        case .playing, .clearing:
            pausedFrom = phase
            phase = .paused
        case .paused:
            lastTick = now
            phase = pausedFrom
        default:
            break
        }
    }
}
