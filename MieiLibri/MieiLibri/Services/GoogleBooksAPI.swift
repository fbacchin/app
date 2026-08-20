import Foundation

/// Client minimale per la ricerca nel catalogo di Google Books.
/// L'endpoint pubblico non richiede alcuna chiave API.
enum GoogleBooksAPI {
    static func search(_ query: String) async throws -> [RemoteBook] {
        var components = URLComponents(string: "https://www.googleapis.com/books/v1/volumes")!
        var parametri = [
            URLQueryItem(name: "q", value: normalizedQuery(from: query)),
            URLQueryItem(name: "maxResults", value: "30"),
            URLQueryItem(name: "printType", value: "books"),
        ]
        if !CatalogConfig.googleAPIKey.isEmpty {
            parametri.append(URLQueryItem(name: "key", value: CatalogConfig.googleAPIKey))
        }
        components.queryItems = parametri
        guard let url = components.url else { throw CatalogError.malformed }

        let (data, response) = try await URLSession.shared.data(from: url)
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
                coverURL: secureURL(from: info.imageLinks?.thumbnail ?? info.imageLinks?.smallThumbnail)
            )
        }
    }

    /// Una query di sole cifre (10 o 13) viene trattata come ricerca per ISBN.
    private static func normalizedQuery(from query: String) -> String {
        let compact = query
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: " ", with: "")
        if compact.count == 10 || compact.count == 13, compact.allSatisfy(\.isNumber) {
            return "isbn:\(compact)"
        }
        return query
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
