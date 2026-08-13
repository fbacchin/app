import Foundation

/// Un libro salvato nella libreria personale.
struct Book: Identifiable, Codable, Equatable {
    let id: String
    var title: String
    var authors: [String]
    var publisher: String?
    var publishedYear: String?
    var isbn: String?
    var pageCount: Int?
    var coverURL: URL?
    var dateRead: Date
    var rating: Int
    var notes: String

    var authorsText: String {
        authors.isEmpty ? "Autore sconosciuto" : authors.joined(separator: ", ")
    }
}
