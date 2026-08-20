import Foundation

/// Client minimale per la ricerca nel catalogo di Google Books.
/// L'endpoint pubblico non richiede alcuna chiave API.
enum GoogleBooksAPI {
    static func search(_ criteri: CatalogQuery) async throws -> [RemoteBook] {
        var components = URLComponents(string: "https://www.googleapis.com/books/v1/volumes")!
        // Filtrando per anno si scarta parte dei risultati a valle, quindi
        // conviene chiederne di piu' (40 e' il massimo ammesso).
        let quanti = criteri.annoRipulito.isEmpty ? "30" : "40"
        var parametri = [
            URLQueryItem(name: "q", value: interrogazione(per: criteri)),
            URLQueryItem(name: "maxResults", value: quanti),
            URLQueryItem(name: "printType", value: "books"),
        ]
        // Senza vincolo di lingua lo stesso titolo torna una volta per ogni
        // edizione tradotta.
        let lingua = Preferenze.lingua
        if lingua != .tutte {
            parametri.append(URLQueryItem(name: "langRestrict", value: lingua.rawValue))
        }
        if !CatalogConfig.googleAPIKey.isEmpty {
            parametri.append(URLQueryItem(name: "key", value: CatalogConfig.googleAPIKey))
        }
        components.queryItems = parametri
        guard let url = components.url else { throw CatalogError.malformed }

        var richiesta = URLRequest(url: url)
        // Permette di restringere la chiave API a questa sola app dalla console
        // Google: senza questa intestazione la restrizione rifiuterebbe tutto.
        if !CatalogConfig.googleAPIKey.isEmpty,
           let identificativo = Bundle.main.bundleIdentifier {
            richiesta.setValue(identificativo, forHTTPHeaderField: "X-Ios-Bundle-Identifier")
        }

        let (data, response) = try await URLSession.shared.data(for: richiesta)
        guard let httpResponse = response as? HTTPURLResponse else { throw CatalogError.malformed }
        switch httpResponse.statusCode {
        case 200:
            break
        case 429:
            // Quota esaurita: senza chiave e' condivisa fra tutti gli utenti
            // che escono dallo stesso indirizzo IP.
            throw CatalogError.rateLimited
        case 403:
            // Google usa 403 sia per la quota sia per chiavi non valide.
            let corpo = String(data: data, encoding: .utf8) ?? ""
            throw corpo.lowercased().contains("quota") ? CatalogError.rateLimited
                                                       : CatalogError.server(403)
        case let codice:
            throw CatalogError.server(codice)
        }

        guard let payload = try? JSONDecoder().decode(SearchResponse.self, from: data) else {
            throw CatalogError.malformed
        }
        var seenIDs = Set<String>()
        return (payload.items ?? []).compactMap { volume in
            guard let title = volume.volumeInfo.title, seenIDs.insert(volume.id).inserted else { return nil }
            let info = volume.volumeInfo
            return RemoteBook(
                id: volume.id,
                title: title,
                authors: info.authors ?? [],
                publisher: info.publisher,
                publishedYear: year(from: info.publishedDate),
                isbn: isbn(from: info.industryIdentifiers),
                pageCount: info.pageCount,
                coverURL: secureURL(from: info.imageLinks?.thumbnail ?? info.imageLinks?.smallThumbnail),
                summary: testoSemplice(info.description)
            )
        }
    }

    /// Traduce i criteri negli operatori di Google Books. Senza operatore la
    /// ricerca copre anche descrizione e testo integrale, da cui i risultati
    /// inattesi; "intitle" e "inauthor" la restringono al campo voluto.
    private static func interrogazione(per criteri: CatalogQuery) -> String {
        if criteri.sembraISBN {
            return "isbn:\(criteri.isbnCompatto)"
        }
        let testo = criteri.testoRipulito
        switch criteri.ambito {
        case .tutto:
            return testo
        case .titolo:
            return "intitle:\"\(testo)\""
        case .autore:
            return "inauthor:\"\(testo)\""
        }
    }

    private static func year(from publishedDate: String?) -> String? {
        guard let publishedDate, publishedDate.count >= 4 else { return nil }
        let prefix = String(publishedDate.prefix(4))
        return prefix.allSatisfy(\.isNumber) ? prefix : nil
    }

    private static func isbn(from identifiers: [IndustryIdentifier]?) -> String? {
        guard let identifiers else { return nil }
        if let isbn13 = identifiers.first(where: { $0.type == "ISBN_13" })?.identifier {
            return isbn13
        }
        return identifiers.first(where: { $0.type == "ISBN_10" })?.identifier
    }

    /// Le descrizioni di Google contengono spesso marcatori HTML, che a schermo
    /// comparirebbero come tali: qui si riducono a testo semplice.
    private static func testoSemplice(_ html: String?) -> String? {
        guard let html, !html.isEmpty else { return nil }
        var testo = html.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        for (entita, carattere) in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                                    ("&quot;", "\""), ("&#39;", "'"), ("&nbsp;", " ")] {
            testo = testo.replacingOccurrences(of: entita, with: carattere)
        }
        testo = testo
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return testo.isEmpty ? nil : testo
    }

    /// Google Books restituisce spesso URL http://, ma App Transport Security richiede https.
    private static func secureURL(from string: String?) -> URL? {
        guard var string = string else { return nil }
        if string.hasPrefix("http://") {
            string = "https://" + string.dropFirst("http://".count)
        }
        return URL(string: string)
    }
}

// MARK: - Struttura della risposta di Google Books

private struct SearchResponse: Decodable {
    let items: [Volume]?
}

private struct Volume: Decodable {
    let id: String
    let volumeInfo: VolumeInfo
}

private struct VolumeInfo: Decodable {
    let title: String?
    let authors: [String]?
    let publisher: String?
    let publishedDate: String?
    let pageCount: Int?
    let description: String?
    let industryIdentifiers: [IndustryIdentifier]?
    let imageLinks: ImageLinks?
}

private struct IndustryIdentifier: Decodable {
    let type: String?
    let identifier: String?
}

private struct ImageLinks: Decodable {
    let smallThumbnail: String?
    let thumbnail: String?
}
