import SwiftUI

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isTyping = false
    @Published private(set) var usesAppleIntelligence = false

    private let brain = YodaBrain()
    private var started = false
    // Conserva YodaAIEngine come Any per restare compatibili con iOS < 26.
    private var aiStorage: Any?

    init() {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *), YodaAI.isAvailable {
            let engine = YodaAIEngine()
            engine.prewarm()
            aiStorage = engine
            usesAppleIntelligence = true
        }
        #endif
    }

    /// Avvia la conversazione: benvenuto e la domanda rituale del Maestro.
    func startConversation() {
        guard !started else { return }
        started = true
        Task {
            isTyping = true
            try? await Task.sleep(for: .seconds(1.3))
            isTyping = false
            append(Message(role: .yoda, text: "Benvenuta, \(YodaConfig.appellativo). Il saggio Yoda ti ascolta."))
            isTyping = true
            try? await Task.sleep(for: .seconds(1.5))
            isTyping = false
            append(Message(role: .yoda, text: "Su cosa avere risposta tu vuoi?"))
        }
    }

    func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        append(Message(role: .user, text: trimmed))
        Task {
            try? await Task.sleep(for: .seconds(0.4))
            isTyping = true
            let reply = await generateReply(for: trimmed)
            isTyping = false
            append(Message(role: .yoda, text: reply))
        }
    }

    /// Apple Intelligence quando disponibile; altrimenti il motore offline,
    /// che resta anche la rete di sicurezza se il modello dovesse fallire.
    private func generateReply(for text: String) async -> String {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *), let engine = aiStorage as? YodaAIEngine {
            if let answer = try? await engine.reply(to: text), !answer.isEmpty {
                return answer
            }
        }
        #endif
        try? await Task.sleep(for: .seconds(Double.random(in: 0.9...1.7)))
        return brain.reply(to: text)
    }

    private func append(_ message: Message) {
        withAnimation(.spring(duration: 0.35)) {
            messages.append(message)
        }
    }
}
