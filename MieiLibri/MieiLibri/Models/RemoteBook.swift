import Foundation

/// Un libro trovato nel catalogo remoto (Google Books), non ancora salvato.
struct RemoteBook: Identifiable, Equatable {
    let id: String
    let title: String
    let authors: [String]
    let publisher: String?
    let publishedYear: String?
    let isbn: String?
    let pageCount: Int?
    let coverURL: URL?
    let summary: String?
}
