import SwiftUI
import UIKit

/// La libreria personale: elenco dei libri letti, salvato come JSON
/// nella cartella Documenti, con le copertine scaricate in locale
/// così da restare visibili anche senza connessione.
@MainActor
final class Library: ObservableObject {
    @Published private(set) var books: [Book] = []

    private let libraryFileURL: URL
    private let coversDirectoryURL: URL
    private let coverCache = NSCache<NSString, UIImage>()

    init() {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        libraryFileURL = documents.appendingPathComponent("library.json")
        coversDirectoryURL = documents.appendingPathComponent("Covers", isDirectory: true)
        try? FileManager.default.createDirectory(at: coversDirectoryURL, withIntermediateDirectories: true)
        load()
    }

    func book(with id: String) -> Book? {
        books.first { $0.id == id }
    }

    func contains(_ id: String) -> Bool {
        books.contains { $0.id == id }
    }

    func add(_ remote: RemoteBook) async {
        guard !contains(remote.id) else { return }
        let book = Book(
            id: remote.id,
            title: remote.title,
            authors: remote.authors,
            publisher: remote.publisher,
            publishedYear: remote.publishedYear,
            isbn: remote.isbn,
            pageCount: remote.pageCount,
            coverURL: remote.coverURL,
            dateRead: .now,
            rating: 0,
            notes: ""
        )
        books.append(book)
        sortAndSave()
        await downloadCoverIfNeeded(for: book)
    }

    func update(_ book: Book) {
        guard let index = books.firstIndex(where: { $0.id == book.id }) else { return }
        books[index] = book
        sortAndSave()
    }

    func remove(_ book: Book) {
        books.removeAll { $0.id == book.id }
        try? FileManager.default.removeItem(at: coverFileURL(for: book.id))
        coverCache.removeObject(forKey: book.id as NSString)
        save()
    }

    // MARK: - Copertine

    func localCover(for id: String) -> UIImage? {
        if let cached = coverCache.object(forKey: id as NSString) { return cached }
        guard let data = try? Data(contentsOf: coverFileURL(for: id)),
              let image = UIImage(data: data) else { return nil }
        coverCache.setObject(image, forKey: id as NSString)
        return image
    }

    private func coverFileURL(for id: String) -> URL {
        coversDirectoryURL.appendingPathComponent("\(id).jpg")
    }

    private func downloadCoverIfNeeded(for book: Book) async {
        let fileURL = coverFileURL(for: book.id)
        guard !FileManager.default.fileExists(atPath: fileURL.path),
              let coverURL = book.coverURL else { return }
        guard let (data, response) = try? await URLSession.shared.data(from: coverURL),
              (response as? HTTPURLResponse)?.statusCode == 200,
              UIImage(data: data) != nil else { return }
        try? data.write(to: fileURL, options: .atomic)
        objectWillChange.send()
    }

    // MARK: - Persistenza

    private func load() {
        guard let data = try? Data(contentsOf: libraryFileURL) else { return }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        books = (try? decoder.decode([Book].self, from: data)) ?? []
        sortBooks()
    }

    private func sortAndSave() {
        sortBooks()
        save()
    }

    private func sortBooks() {
        books.sort { $0.dateRead > $1.dateRead }
    }

    private func save() {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(books) else { return }
        try? data.write(to: libraryFileURL, options: .atomic)
    }
}
