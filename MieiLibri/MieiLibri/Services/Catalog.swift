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

/// Coordina i cataloghi disponibili: Google Books ha il repertorio migliore in
/// italiano, ma senza chiave la sua quota è condivisa fra molti utenti e può
/// esaurirsi. In quel caso si ripiega su Open Library, che non ha quote.
enum Catalog {
    static func search(_ query: String) async throws -> [RemoteBook] {
        do {
            return try await GoogleBooksAPI.search(query)
        } catch {
            let motivo = CatalogError.from(error)
            // Senza rete non ha senso interrogare un secondo catalogo.
            guard motivo != .offline else { throw motivo }
            if let ripiego = try? await OpenLibraryAPI.search(query), !ripiego.isEmpty {
                return ripiego
            }
            throw motivo
        }
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

/// Chiavi facoltative per i cataloghi.
enum CatalogConfig {
    /// Chiave Google Books personale. Lasciata vuota, l'app usa la quota
    /// condivisa e anonima, che può risultare esaurita in certi momenti.
    /// Con una chiave propria la quota è tutta tua.
    static let googleAPIKey = ""
}
