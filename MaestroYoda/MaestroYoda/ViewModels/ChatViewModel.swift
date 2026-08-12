import SwiftUI

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isTyping = false

    private let brain = YodaBrain()
    private var started = false

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
        let reply = brain.reply(to: trimmed)
        Task {
            try? await Task.sleep(for: .seconds(0.5))
            isTyping = true
            try? await Task.sleep(for: .seconds(Double.random(in: 1.1...2.0)))
            isTyping = false
            append(Message(role: .yoda, text: reply))
        }
    }

    private func append(_ message: Message) {
        withAnimation(.spring(duration: 0.35)) {
            messages.append(message)
        }
    }
}
