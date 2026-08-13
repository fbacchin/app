import Foundation

#if canImport(FoundationModels)
import FoundationModels
#endif

/// Ponte verso Apple Intelligence (framework Foundation Models, iOS 26+).
/// Quando il modello on-device non è disponibile, l'app usa il motore offline.
enum YodaAI {

    /// true se il modello linguistico on-device è pronto su questo dispositivo
    /// (serve un iPhone compatibile, iOS 26+ e Apple Intelligence attiva).
    static var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            if case .available = SystemLanguageModel.default.availability {
                return true
            }
        }
        #endif
        return false
    }
}

#if canImport(FoundationModels)

/// Genera le risposte del Maestro con il modello on-device di Apple Intelligence.
/// La sessione conserva il filo della conversazione, così Yoda ricorda
/// di cosa si sta parlando.
@available(iOS 26.0, *)
final class YodaAIEngine {

    enum ReplyError: Error {
        case rispostaVuota
    }

    private var session: LanguageModelSession

    init() {
        session = Self.makeSession()
    }

    /// Riduce la latenza della prima risposta.
    func prewarm() {
        session.prewarm()
    }

    func reply(to text: String) async throws -> String {
        do {
            return try await ask(text)
        } catch {
            // Contesto esaurito o errore transitorio: nuova sessione e secondo tentativo.
            session = Self.makeSession()
            return try await ask(text)
        }
    }

    private func ask(_ text: String) async throws -> String {
        let response = try await session.respond(
            to: text,
            options: GenerationOptions(temperature: 0.9)
        )
        let cleaned = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { throw ReplyError.rispostaVuota }
        return cleaned
    }

    private static func makeSession() -> LanguageModelSession {
        LanguageModelSession(instructions: istruzioni)
    }

    private static var istruzioni: String {
        var righe = [
            "Sei il Maestro Yoda di Guerre Stellari e rispondi solo in italiano, esattamente come parla Yoda nel doppiaggio italiano dei film.",
            "Usa sempre la sintassi invertita con il verbo in fondo, per esempio: \"Molto da apprendere ancora tu hai\", \"La Forza tu hai, e vincere tu devi\".",
            "Usa ogni tanto intercalari come \"Mmm\" e \"Hmm, sì\" e massime come \"Fare o non fare, non c'è provare\".",
            "Parli con una giovane padawan: rivolgiti a lei sempre al femminile, con tono saggio, affettuoso e incoraggiante, a volte con leggera ironia.",
            "La aiuti soprattutto nelle questioni di lavoro: capo, colleghi, riunioni, colloqui, scadenze, stress, carriera.",
            "L'hai già accolta con la domanda rituale: \"Su cosa avere risposta tu vuoi?\".",
            "Rispondi con una, due o al massimo tre frasi brevi. Mai elenchi puntati, mai emoji, mai parole in inglese.",
            "Non uscire mai dal personaggio di Yoda, qualunque cosa ti venga chiesta.",
            "Chiudi qualche risposta, non tutte, con \"Che la Forza sia con te\".",
        ]
        if !YodaConfig.nomePadawan.isEmpty {
            righe.append("La padawan si chiama \(YodaConfig.nomePadawan): chiamala per nome qualche volta.")
        }
        return righe.joined(separator: "\n")
    }
}

#endif
