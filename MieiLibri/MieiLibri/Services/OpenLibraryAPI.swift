import Foundation

/// Catalogo di riserva, usato quando Google Books non è disponibile.
/// Open Library è gratuito e senza quote per singolo indirizzo IP.
enum OpenLibraryAPI {
    static func search(_ criteri: CatalogQuery) async throws -> [RemoteBook] {
        var components = URLComponents(string: "https://openlibrary.org/search.json")!
        let quanti = criteri.annoRipulito.isEmpty ? "30" : "40"
        components.queryItems = [
            URLQueryItem(name: "q", value: interrogazione(per: criteri)),
            URLQueryItem(name: "limit", value: quanti),
            URLQueryItem(
                name: "fields",
                value: "key,title,author_name,first_publish_year,isbn,cover_i,number_of_pages_median,publisher"
            ),
        ]
        guard let url = components.url else { throw CatalogError.malformed }

        let (data, response) = try await URLSession.shared.data(from: url)
        guard let http = response as? HTTPURLResponse else { throw CatalogError.malformed }
        guard http.statusCode == 200 else { throw CatalogError.server(http.statusCode) }

        guard let payload = try? JSONDecoder().decode(SearchResponse.self, from: data) else {
            throw CatalogError.malformed
        }

        var visti = Set<String>()
        return (payload.docs ?? []).compactMap { doc in
            guard let titolo = doc.title, let chiave = doc.key else { return nil }
            let id = identificativo(from: chiave)
            guard visti.insert(id).inserted else { return nil }
            return RemoteBook(
                id: id,
                title: titolo,
                authors: doc.author_name ?? [],
                publisher: doc.publisher?.first,
                publishedYear: doc.first_publish_year.map(String.init),
                isbn: doc.isbn?.first,
                pageCount: doc.number_of_pages_median,
                coverURL: doc.cover_i.flatMap {
                    URL(string: "https://covers.openlibrary.org/b/id/\($0)-M.jpg")
                }
            )
        }
    }

    /// Le chiavi di Open Library sono del tipo "/works/OL123W". L'id finisce nel
    /// nome del file di copertina salvato su disco, quindi le barre vanno tolte;
    /// il prefisso evita ogni sovrapposizione con gli id di Google Books.
    private static func identificativo(from chiave: String) -> String {
        let ripulita = chiave
            .split(separator: "/")
            .joined(separator: "-")
        return "ol-" + ripulita
    }

    /// Traduce i criteri nella sintassi di Open Library. A differenza di Google,
    /// qui l'anno si può indicare nella richiesta stessa, il che restringe i
    /// risultati alla fonte.
    private static func interrogazione(per criteri: CatalogQuery) -> String {
        var parti: [String] = []

        if criteri.sembraISBN {
            parti.append("isbn:\(criteri.isbnCompatto)")
        } else {
            let testo = criteri.testoRipulito
            switch criteri.ambito {
            case .tutto:  parti.append(testo)
            case .titolo: parti.append("title:\"\(testo)\"")
            case .autore: parti.append("author:\"\(testo)\"")
            }
        }

        let anno = criteri.annoRipulito
        if !anno.isEmpty {
            parti.append("first_publish_year:\(anno)")
        }
        return parti.joined(separator: " AND ")
    }
}

// MARK: - Struttura della risposta di Open Library

private struct SearchResponse: Decodable {
    let docs: [Doc]?
}

private struct Doc: Decodable {
    let key: String?
    let title: String?
    let author_name: [String]?
    let publisher: [String]?
    let first_publish_year: Int?
    let isbn: [String]?
    let cover_i: Int?
    let number_of_pages_median: Int?
}
