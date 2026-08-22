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
    var summary: String?
    var dateRead: Date
    var rating: Int
    var notes: String
    var updatedAt: Date? = nil

    /// Etichetta usata per i libri privi di autore, così da poterli comunque
    /// raggruppare invece di lasciarli fuori dall'elenco.
    static let autoreIgnoto = "Autore sconosciuto"

    var authorsText: String {
        authors.isEmpty ? Book.autoreIgnoto : authors.joined(separator: ", ")
    }

    /// Anno di pubblicazione come numero, per poter ordinare.
    var annoNumerico: Int? {
        publishedYear.flatMap(Int.init)
    }

    /// Dal più recente di pubblicazione al più vecchio. I libri senza anno
    /// finiscono in fondo, ordinati per titolo: metterli in cima o mescolati
    /// darebbe l'impressione di un elenco disordinato.
    static func perAnnoDecrescente(_ sinistra: Book, _ destra: Book) -> Bool {
        switch (sinistra.annoNumerico, destra.annoNumerico) {
        case let (primo?, secondo?):
            return primo == secondo
                ? sinistra.title.localizedCaseInsensitiveCompare(destra.title) == .orderedAscending
                : primo > secondo
        case (_?, nil):
            return true
        case (nil, _?):
            return false
        case (nil, nil):
            return sinistra.title.localizedCaseInsensitiveCompare(destra.title) == .orderedAscending
        }
    }
}
