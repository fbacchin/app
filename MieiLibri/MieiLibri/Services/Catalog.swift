import Foundation

/// Perché una ricerca nel catalogo non è riuscita.
/// Distinguere i casi è importante: "manca la rete" e "il catalogo ha
/// rifiutato la richiesta" richiedono reazioni diverse da parte di chi legge.
enum CatalogError: LocalizedError {
    case offline
    case rateLimited
    case server(Int)
    case malformed

    var errorDescription: String? {
        switch self {
        case .offline:
            return "Nessuna connessione a internet."
        case .rateLimited:
            return "Il catalogo ha esaurito le richieste disponibili per ora."
        case .server(let codice):
            return "Il catalogo non risponde (errore \(codice))."
        case .malformed:
            return "Il catalogo ha risposto in modo inatteso."
        }
    }

    var suggerimento: String {
        switch self {
        case .offline:
            return "Controlla la connessione e riprova."
        case .rateLimited:
            return "Riprova fra qualche minuto, oppure imposta una chiave Google Books personale."
        case .server, .malformed:
            return "Riprova fra poco."
        }
    }

    /// Traduce gli errori di URLSession nei casi qui sopra.
    static func from(_ error: Error) -> CatalogError {
        if let catalogo = error as? CatalogError { return catalogo }
        guard let url = error as? URLError else { return .malformed }
        switch url.code {
        case .notConnectedToInternet, .networkConnectionLost, .cannotFindHost,
             .cannotConnectToHost, .dataNotAllowed, .timedOut, .internationalRoamingOff:
            return .offline
        default:
            return .malformed
        }
    }
}

/// I criteri con cui cercare nel catalogo.
struct CatalogQuery: Equatable {
    /// Dove cercare il testo digitato. Cercare ovunque include anche la
    /// descrizione e il testo integrale, e produce spesso risultati inattesi:
    /// per questo si può restringere a titolo o autore.
    enum Ambito: String, CaseIterable, Identifiable {
        case tutto, titolo, autore

        var id: String { rawValue }

        var etichetta: String {
            switch self {
            case .tutto: return "Tutto"
            case .titolo: return "Titolo"
            case .autore: return "Autore"
            }
        }
    }

    var testo: String = ""
    var ambito: Ambito = .tutto
    /// Anno di pubblicazione, vuoto quando non si filtra.
    var anno: String = ""

    var testoRipulito: String {
        testo.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var annoRipulito: String {
        let a = anno.trimmingCharacters(in: .whitespaces)
        return (a.count == 4 && a.allSatisfy(\.isNumber)) ? a : ""
    }

    var isEmpty: Bool { testoRipulito.isEmpty }

    /// Vero quando il testo è un codice ISBN: in quel caso l'ambito non conta.
    var sembraISBN: Bool {
        let compatta = testoRipulito
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: " ", with: "")
        return (compatta.count == 10 || compatta.count == 13) && compatta.allSatisfy(\.isNumber)
    }

    var isbnCompatto: String {
        testoRipulito
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: " ", with: "")
    }
}

/// Coordina i cataloghi disponibili: Google Books ha il repertorio migliore in
/// italiano, ma senza chiave la sua quota è condivisa fra molti utenti e può
/// esaurirsi. In quel caso si ripiega su Open Library, che non ha quote.
enum Catalog {
    static func search(_ criteri: CatalogQuery) async throws -> [RemoteBook] {
        let risultati: [RemoteBook]
        do {
            risultati = try await GoogleBooksAPI.search(criteri)
        } catch {
            let motivo = CatalogError.from(error)
            // Senza rete non ha senso interrogare un secondo catalogo.
            guard motivo != .offline else { throw motivo }
            guard let ripiego = try? await OpenLibraryAPI.search(criteri), !ripiego.isEmpty else {
                throw motivo
            }
            return rimuoviDoppioni(filtraPerAnno(ripiego, criteri: criteri))
        }
        return rimuoviDoppioni(filtraPerAnno(risultati, criteri: criteri))
    }

    /// Il filtro per anno si applica qui, non nella richiesta: Google Books non
    /// offre un parametro per la data di pubblicazione, quindi filtrare al
    /// ritorno è l'unico modo di comportarsi allo stesso modo con entrambi i
    /// cataloghi.
    private static func filtraPerAnno(_ libri: [RemoteBook], criteri: CatalogQuery) -> [RemoteBook] {
        let anno = criteri.annoRipulito
        guard !anno.isEmpty else { return libri }
        return libri.filter { $0.publishedYear == anno }
    }

    /// I cataloghi elencano una voce per ogni edizione, così la stessa opera
    /// compare più volte. Qui se ne tiene una sola, preferendo quella con la
    /// copertina: senza immagine la riga sarebbe poco utile.
    private static func rimuoviDoppioni(_ libri: [RemoteBook]) -> [RemoteBook] {
        var posizioni: [String: Int] = [:]
        var risultato: [RemoteBook] = []
        for libro in libri {
            let chiave = chiaveConfronto(libro)
            if let indice = posizioni[chiave] {
                if risultato[indice].coverURL == nil, libro.coverURL != nil {
                    risultato[indice] = libro
                }
            } else {
                posizioni[chiave] = risultato.count
                risultato.append(libro)
            }
        }
        return risultato
    }

    /// Titolo e primo autore, senza accenti, maiuscole e punteggiatura: basta
    /// a riconoscere la stessa opera fra edizioni diverse.
    private static func chiaveConfronto(_ libro: RemoteBook) -> String {
        func normalizza(_ testo: String) -> String {
            testo.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: nil)
                .filter { $0.isLetter || $0.isNumber || $0.isWhitespace }
                .split(separator: " ")
                .joined(separator: " ")
        }
        return normalizza(libro.title) + "|" + normalizza(libro.authors.first ?? "")
    }
}

extension CatalogError: Equatable {
    static func == (a: CatalogError, b: CatalogError) -> Bool {
        switch (a, b) {
        case (.offline, .offline), (.rateLimited, .rateLimited), (.malformed, .malformed):
            return true
        case (.server(let x), .server(let y)):
            return x == y
        default:
            return false
        }
    }
}

/// Lingua in cui cercare i libri. Senza vincolo lo stesso titolo compare
/// molte volte, una per ogni edizione tradotta.
enum LinguaLibri: String, CaseIterable, Identifiable {
    case tutte = ""
    case italiano = "it"
    case inglese = "en"
    case francese = "fr"
    case tedesco = "de"
    case spagnolo = "es"

    var id: String { rawValue }

    var etichetta: String {
        switch self {
        case .tutte: return "Tutte le lingue"
        case .italiano: return "Italiano"
        case .inglese: return "Inglese"
        case .francese: return "Francese"
        case .tedesco: return "Tedesco"
        case .spagnolo: return "Spagnolo"
        }
    }

    /// Google Books usa i codici a due lettere; Open Library quelli a tre
    /// del catalogo MARC, che non si ricavano troncando i primi.
    var codiceOpenLibrary: String? {
        switch self {
        case .tutte: return nil
        case .italiano: return "ita"
        case .inglese: return "eng"
        case .francese: return "fre"
        case .tedesco: return "ger"
        case .spagnolo: return "spa"
        }
    }
}

/// Preferenze di ricerca, condivise fra interfaccia e cataloghi.
enum Preferenze {
    private static let chiaveLingua = "linguaLibri"

    static var lingua: LinguaLibri {
        LinguaLibri(rawValue: UserDefaults.standard.string(forKey: chiaveLingua) ?? "") ?? .tutte
    }
}

/// Chiavi facoltative per i cataloghi.
enum CatalogConfig {
    /// Chiave Google Books personale. Lasciata vuota, l'app usa la quota
    /// condivisa e anonima, che può risultare esaurita in certi momenti.
    /// Con una chiave propria la quota è tutta tua.
    static let googleAPIKey = ""
}
