import Foundation

/// Analizza la domanda e compone una risposta nello stile del Maestro.
/// Motore completamente offline: nessuna connessione serve alla Forza.
final class YodaBrain {

    private var bags: [String: [String]] = [:]
    private var lastCategory: String?
    private var exchanges = 0

    // Ordine di priorità: le voci più specifiche prima, "lavoro" come rete generale.
    private static let keywordMap: [(category: String, keywords: [String])] = [
        ("capo", ["capo", "boss", "direttor", "manager", "responsabil", "titolare"]),
        ("colleghi", ["colleg", "team", "squadra", "gruppo"]),
        ("colloquio", ["colloqui", "intervista", "candidatur", "curriculum", "assunzion"]),
        ("riunione", ["riunion", "meeting", "presentazion", "parlare in pubblico"]),
        ("carriera", ["promozion", "carriera", "aumento", "stipendio", "avanzament", "ruolo"]),
        ("progetto", ["progett", "scadenz", "deadline", "consegna", "compit", "task", "obiettiv", "esame", "studiare"]),
        ("stress", ["stress", "stanc", "esaurit", "burnout", "pression", "riposo", "vacanz", "dormire", "sonno"]),
        ("paura", ["paura", "timore", "temo", "ansia", "ansios", "preoccup", "dubbio", "dubbi", "insicur", "spavent", "non ce la faccio"]),
        ("errore", ["sbagli", "errore", "errori", "fallit", "falliment", "colpa", "licenzia"]),
        ("decisione", ["decid", "decision", "scelta", "sceglier", "dimission", "offerta", "cambiare"]),
        ("soldi", ["soldi", "denaro", "guadagn", "risparmi", "pagament", "bolletta"]),
        ("motivazione", ["procrastin", "rimand", "pigr", "voglia", "motivazion", "concentr", "iniziare", "distra"]),
        ("successo", ["vincere", "vincero", "successo", "riuscir", "farcela", "sogno", "sogni"]),
        ("amore", ["amore", "fidanzat", "ragazzo", "relazion", "matrimonio"]),
        ("futuro", ["futuro", "domani", "destino", "andra", "succedera"]),
        ("lavoro", ["lavor", "ufficio", "azienda", "profession", "turno", "contratto", "cliente", "clienti", "smart working"]),
    ]

    // MARK: - Risposta

    func reply(to raw: String) -> String {
        defer { exchanges += 1 }
        let input = normalize(raw)
        guard input.count > 1 else { return draw("incomprensione") }

        if let special = specialReply(for: input) { return special }
        if let short = shortReply(for: input) { return short }

        let category = detectCategory(in: input)

        if isOracleQuestion(input) {
            var parts = [draw(oraclePool())]
            if let category, chance(0.65) { parts.append(draw(category)) }
            lastCategory = category
            return parts.joined(separator: " ")
        }

        lastCategory = category
        return composed(from: category ?? "generico")
    }

    // MARK: - Casi speciali

    private func specialReply(for input: String) -> String? {
        if input.contains("come stai") || input.contains("come va") { return draw("come_stai") }
        if input.contains("grazie") { return draw("grazie") }
        if input.contains("ti amo") || input.contains("ti voglio bene") { return draw("affetto") }
        if input.contains("chi sei") || input.contains("come ti chiami") || input == "yoda" { return draw("chi_sono") }
        if input.contains("lato oscuro") { return draw("lato_oscuro") }
        if input.contains("guerre stellari") || input.contains("star wars") || input.contains("skywalker") || input.contains("luke") { return draw("saga") }
        if input.contains("novecento") || input.contains("900") || input.contains("quanti anni") { return draw("eta") }
        if input.contains("caffe") { return draw("caffe") }
        let saluti = ["ciao", "salve", "buongiorno", "buonasera", "buonanotte", "ehi", "hey"]
        if wordCount(input) <= 3, saluti.contains(where: { input.contains($0) }) {
            return draw("saluto")
        }
        return nil
    }

    private func shortReply(for input: String) -> String? {
        guard exchanges > 0, wordCount(input) <= 3 else { return nil }
        let affermazioni = ["si", "certo", "esatto", "vero", "ok", "va bene", "hai ragione", "giusto"]
        let negazioni = ["no", "non credo", "non penso", "macche", "mai"]
        let incertezze = ["non lo so", "non so", "boh", "forse", "chissa", "mah", "dipende"]
        if incertezze.contains(input) { return draw("continua_boh") }
        if affermazioni.contains(input) { return draw("continua_si") }
        if negazioni.contains(input) { return draw("continua_no") }
        return nil
    }

    // MARK: - Analisi

    private func detectCategory(in input: String) -> String? {
        var best: (category: String, score: Int)?
        for entry in Self.keywordMap {
            let score = entry.keywords.reduce(0) { $0 + (input.contains($1) ? 1 : 0) }
            if score > 0, score > (best?.score ?? 0) {
                best = (entry.category, score)
            }
        }
        return best?.category
    }

    private func isOracleQuestion(_ input: String) -> Bool {
        let starters = [
            "devo ", "dovrei ", "posso ", "potrei ", "e giusto ", "e meglio ",
            "mi conviene ", "conviene ", "faccio bene ", "ce la faro",
            "ce la posso fare", "riusciro", "andra bene", "otterro", "avro ",
            "vincero", "sara ",
        ]
        return starters.contains { input.hasPrefix($0) }
    }

    private func oraclePool() -> String {
        let roll = Double.random(in: 0..<1)
        if roll < 0.45 { return "oracolo_si" }
        if roll < 0.75 { return "oracolo_forse" }
        return "oracolo_no"
    }

    // MARK: - Composizione

    private func composed(from category: String) -> String {
        var parts: [String] = []
        if chance(0.3) { parts.append(draw("aperture")) }
        let core = draw(category)
        parts.append(core)
        if !core.hasSuffix("?") {
            if chance(0.22) {
                parts.append(draw("chiusure"))
            } else if chance(0.28) {
                parts.append(draw("domande"))
            }
        }
        return parts.joined(separator: " ")
    }

    /// Estrae una frase dal sacchetto: nessuna ripetizione finché il pool non si esaurisce.
    private func draw(_ key: String) -> String {
        if bags[key, default: []].isEmpty {
            bags[key] = (YodaPhrases.pools[key] ?? ["Mmm, misterioso questo è."]).shuffled()
        }
        return bags[key]!.removeLast()
    }

    private func chance(_ probability: Double) -> Bool {
        Double.random(in: 0..<1) < probability
    }

    private func wordCount(_ text: String) -> Int {
        text.split(separator: " ").count
    }

    /// Minuscole, senza accenti né punteggiatura: così "Perché?" e "perche" si equivalgono.
    private func normalize(_ raw: String) -> String {
        let folded = raw.folding(options: [.diacriticInsensitive, .caseInsensitive],
                                 locale: Locale(identifier: "it_IT"))
        let characters = folded.map { ch -> Character in
            (ch.isLetter || ch.isNumber || ch == " ") ? ch : " "
        }
        return String(characters)
            .split(separator: " ")
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespaces)
    }
}
