import Foundation

/// Errore restituito dal server o dallo stato dell'account.
enum SupabaseError: LocalizedError {
    case notSignedIn
    case notConfigured
    case api(Int, String)

    var errorDescription: String? {
        switch self {
        case .notSignedIn:
            return "Nessun account collegato."
        case .notConfigured:
            return "Il server di sincronizzazione non è ancora configurato."
        case .api(_, let message):
            return message
        }
    }

    var statusCode: Int? {
        if case .api(let code, _) = self { return code }
        return nil
    }
}

/// Sessione dell'utente (token di accesso e di rinnovo).
struct Session: Codable {
    var accessToken: String
    var refreshToken: String
    var userID: String
    var email: String
    var expiresAt: Date
}

/// Riga della tabella `books` su Supabase.
struct BookRecord: Codable {
    var id: String
    var userId: String
    var title: String
    var authors: [String]
    var publisher: String?
    var publishedYear: String?
    var isbn: String?
    var pageCount: Int?
    var coverUrl: String?
    var summary: String?
    var dateRead: Date
    var rating: Int
    var notes: String
    var updatedAt: Date

    init(book: Book, userID: String) {
        id = book.id
        userId = userID
        title = book.title
        authors = book.authors
        publisher = book.publisher
        publishedYear = book.publishedYear
        isbn = book.isbn
        pageCount = book.pageCount
        coverUrl = book.coverURL?.absoluteString
        summary = book.summary
        dateRead = book.dateRead
        rating = book.rating
        notes = book.notes
        updatedAt = book.updatedAt ?? Date()
    }

    func toBook() -> Book {
        Book(
            id: id,
            title: title,
            authors: authors,
            publisher: publisher,
            publishedYear: publishedYear,
            isbn: isbn,
            pageCount: pageCount,
            coverURL: coverUrl.flatMap { URL(string: $0) },
            summary: summary,
            dateRead: dateRead,
            rating: rating,
            notes: notes,
            updatedAt: updatedAt
        )
    }
}

/// Client minimale per Supabase (autenticazione GoTrue + REST PostgREST),
/// basato solo su URLSession: nessuna dipendenza esterna.
enum SupabaseClient {

    // MARK: - Autenticazione

    static func signIn(email: String, password: String) async throws -> Session {
        let data = try await postAuth(path: "token?grant_type=password", body: ["email": email, "password": password])
        let payload = try decoder.decode(AuthPayload.self, from: data)
        guard let session = session(from: payload, fallbackEmail: email) else {
            throw SupabaseError.api(0, "Risposta di accesso non valida.")
        }
        return session
    }

    /// Restituisce la sessione, oppure nil se serve prima confermare l'email.
    static func signUp(email: String, password: String) async throws -> Session? {
        let data = try await postAuth(path: "signup", body: ["email": email, "password": password])
        let payload = try decoder.decode(AuthPayload.self, from: data)
        return session(from: payload, fallbackEmail: email)
    }

    /// Ricostruisce la sessione a partire dai token ricevuti dal collegamento
    /// contenuto nell'email di conferma.
    static func session(accessToken: String, refreshToken: String, expiresIn: Double) async throws -> Session {
        let profilo = try await user(accessToken: accessToken)
        return Session(
            accessToken: accessToken,
            refreshToken: refreshToken,
            userID: profilo.id,
            email: profilo.email,
            expiresAt: Date().addingTimeInterval(expiresIn)
        )
    }

    /// Chiede al server a chi appartiene un token di accesso.
    private static func user(accessToken: String) async throws -> (id: String, email: String) {
        guard !SupabaseConfig.isPlaceholder else { throw SupabaseError.notConfigured }
        guard let url = URL(string: SupabaseConfig.url.absoluteString + "/auth/v1/user") else {
            throw SupabaseError.api(0, "Indirizzo del server non valido.")
        }
        var request = URLRequest(url: url)
        request.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        try ensureOK(data: data, response: response)
        let profilo = try decoder.decode(UserPayload.self, from: data)
        return (profilo.id, profilo.email ?? "")
    }

    private struct UserPayload: Decodable {
        let id: String
        let email: String?
    }

    static func refresh(_ old: Session) async throws -> Session {
        let data = try await postAuth(path: "token?grant_type=refresh_token", body: ["refresh_token": old.refreshToken])
        let payload = try decoder.decode(AuthPayload.self, from: data)
        guard let session = session(from: payload, fallbackEmail: old.email) else {
            throw SupabaseError.api(0, "Impossibile rinnovare la sessione.")
        }
        return session
    }

    // MARK: - Libri

    static func fetchBooks(session: Session) async throws -> [BookRecord] {
        let data = try await rest(method: "GET", path: "books?select=*&order=date_read.desc", session: session)
        return try decoder.decode([BookRecord].self, from: data)
    }

    static func upsertBooks(_ records: [BookRecord], session: Session) async throws {
        guard !records.isEmpty else { return }
        let body = try encoder.encode(records)
        _ = try await rest(
            method: "POST",
            path: "books?on_conflict=user_id,id",
            session: session,
            body: body,
            prefer: "resolution=merge-duplicates,return=minimal"
        )
    }

    static func deleteBook(id: String, session: Session) async throws {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? id
        _ = try await rest(method: "DELETE", path: "books?id=eq.\(encoded)", session: session)
    }

    // MARK: - Richieste HTTP

    private static func postAuth(path: String, body: [String: String]) async throws -> Data {
        guard !SupabaseConfig.isPlaceholder else { throw SupabaseError.notConfigured }
        guard let url = URL(string: SupabaseConfig.url.absoluteString + "/auth/v1/" + path) else {
            throw SupabaseError.api(0, "Indirizzo del server non valido.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        try ensureOK(data: data, response: response)
        return data
    }

    private static func rest(
        method: String,
        path: String,
        session: Session,
        body: Data? = nil,
        prefer: String? = nil
    ) async throws -> Data {
        guard !SupabaseConfig.isPlaceholder else { throw SupabaseError.notConfigured }
        guard let url = URL(string: SupabaseConfig.url.absoluteString + "/rest/v1/" + path) else {
            throw SupabaseError.api(0, "Indirizzo del server non valido.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let prefer {
            request.setValue(prefer, forHTTPHeaderField: "Prefer")
        }
        request.httpBody = body
        let (data, response) = try await URLSession.shared.data(for: request)
        try ensureOK(data: data, response: response)
        return data
    }

    private static func ensureOK(data: Data, response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else {
            throw SupabaseError.api(0, "Risposta del server non valida.")
        }
        guard (200...299).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(ErrorPayload.self, from: data))?.friendlyMessage
            throw SupabaseError.api(http.statusCode, message ?? "Errore del server (\(http.statusCode)).")
        }
    }

    // MARK: - Decodifica

    /// I nomi seguono le proprietà in camelCase: il decoder condiviso
    /// converte già le chiavi snake_case della risposta (access_token…).
    private struct AuthPayload: Decodable {
        struct User: Decodable {
            let id: String
            let email: String?
        }

        let accessToken: String?
        let refreshToken: String?
        let expiresIn: Double?
        let user: User?
    }

    private struct ErrorPayload: Decodable {
        let msg: String?
        let message: String?
        let errorDescription: String?

        enum CodingKeys: String, CodingKey {
            case msg
            case message
            case errorDescription = "error_description"
        }

        var friendlyMessage: String? {
            guard let raw = msg ?? message ?? errorDescription else { return nil }
            switch raw {
            case "Invalid login credentials":
                return "Email o password non corretti."
            case "User already registered":
                return "Utente già registrato: prova ad accedere."
            case "Email not confirmed":
                return "Email non ancora confermata: apri il collegamento ricevuto per posta."
            default:
                return raw
            }
        }
    }

    private static func session(from payload: AuthPayload, fallbackEmail: String) -> Session? {
        guard let access = payload.accessToken,
              let refresh = payload.refreshToken,
              let user = payload.user else { return nil }
        return Session(
            accessToken: access,
            refreshToken: refresh,
            userID: user.id,
            email: user.email ?? fallbackEmail,
            expiresAt: Date().addingTimeInterval(payload.expiresIn ?? 3600)
        )
    }

    // MARK: - Date in formato Postgres

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .custom { date, enc in
            var container = enc.singleValueContainer()
            try container.encode(isoWithFraction.string(from: date))
        }
        return encoder
    }()

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { dec in
            let container = try dec.singleValueContainer()
            let string = try container.decode(String.self)
            guard let date = parseDate(string) else {
                throw DecodingError.dataCorruptedError(in: container, debugDescription: "Data non riconosciuta: \(string)")
            }
            return date
        }
        return decoder
    }()

    private static let isoWithFraction: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let isoPlain: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    private static let postgresFormatters: [DateFormatter] = [
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX",
        "yyyy-MM-dd'T'HH:mm:ssXXXXX",
    ].map { format in
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = format
        return formatter
    }

    static func parseDate(_ string: String) -> Date? {
        if let date = isoWithFraction.date(from: string) { return date }
        if let date = isoPlain.date(from: string) { return date }
        for formatter in postgresFormatters {
            if let date = formatter.date(from: string) { return date }
        }
        return nil
    }
}
