import SwiftUI

/// La libreria personale: elenco dei libri letti, salvato come JSON
/// nella cartella Documenti con le copertine scaricate in locale, e
/// sincronizzato con Supabase quando è collegato un account.
///
/// Modello "offline-first": ogni modifica viene applicata e salvata
/// subito sul dispositivo; l'allineamento col server avviene in
/// background e riprende da solo dopo un errore di rete.
@MainActor
final class Library: ObservableObject {
    @Published private(set) var books: [Book] = []
    @Published private(set) var sessionEmail: String?
    @Published private(set) var isSyncing = false
    @Published private(set) var syncStatusText: String?
    @Published var localOnly: Bool {
        didSet { UserDefaults.standard.set(localOnly, forKey: "localOnly") }
    }

    var isSignedIn: Bool { session != nil }

    /// True quando la sincronizzazione è disponibile: senza le coordinate
    /// del server l'app resta una normale libreria locale.
    var syncAvailable: Bool { !SupabaseConfig.isPlaceholder }

    /// Mostra la schermata di benvenuto solo se c'è davvero una scelta da fare.
    var showsAccountGate: Bool { syncAvailable && !isSignedIn && !localOnly }

    private var session: Session?
    private var dirtyIDs: Set<String> = []
    private var pendingDeletions: Set<String> = []
    private var pendingAnotherSync = false
    private var syncDebounceTask: Task<Void, Never>?

    private let libraryFileURL: URL
    private let coversDirectoryURL: URL
    private let coverCache = NSCache<NSString, PlatformImage>()

    init() {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        libraryFileURL = documents.appendingPathComponent("library.json")
        coversDirectoryURL = documents.appendingPathComponent("Covers", isDirectory: true)
        localOnly = UserDefaults.standard.bool(forKey: "localOnly")
        try? FileManager.default.createDirectory(at: coversDirectoryURL, withIntermediateDirectories: true)
        load()
        loadSession()
        scheduleSync(after: 0.5)
    }

    func book(with id: String) -> Book? {
        books.first { $0.id == id }
    }

    func contains(_ id: String) -> Bool {
        books.contains { $0.id == id }
    }

    // MARK: - Modifiche alla libreria

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
            notes: "",
            updatedAt: Date()
        )
        books.append(book)
        pendingDeletions.remove(book.id)
        dirtyIDs.insert(book.id)
        sortBooks()
        save()
        scheduleSync()
        await downloadCoverIfNeeded(for: book)
    }

    func update(_ book: Book) {
        guard let index = books.firstIndex(where: { $0.id == book.id }) else { return }
        var updated = book
        updated.updatedAt = Date()
        books[index] = updated
        dirtyIDs.insert(book.id)
        sortBooks()
        save()
        scheduleSync(after: 1.5)
    }

    func remove(_ book: Book) {
        books.removeAll { $0.id == book.id }
        dirtyIDs.remove(book.id)
        if isSignedIn {
            pendingDeletions.insert(book.id)
        }
        try? FileManager.default.removeItem(at: coverFileURL(for: book.id))
        coverCache.removeObject(forKey: book.id as NSString)
        save()
        scheduleSync()
    }

    // MARK: - Account

    func signIn(email: String, password: String) async throws {
        let session = try await SupabaseClient.signIn(email: email, password: password)
        storeSession(session)
        localOnly = false
        await initialMergeSync()
    }

    /// Restituisce true se l'utente deve prima confermare l'email.
    func signUp(email: String, password: String) async throws -> Bool {
        if let session = try await SupabaseClient.signUp(email: email, password: password) {
            storeSession(session)
            localOnly = false
            await initialMergeSync()
            return false
        }
        return true
    }

    func signOut() {
        storeSession(nil)
        dirtyIDs = []
        pendingDeletions = []
        localOnly = true
        syncStatusText = "Account scollegato: i dati restano su questo dispositivo."
        save()
    }

    private func loadSession() {
        guard let data = Keychain.load(key: "session"),
              let stored = try? JSONDecoder().decode(Session.self, from: data) else { return }
        session = stored
        sessionEmail = stored.email
    }

    private func storeSession(_ newSession: Session?) {
        session = newSession
        sessionEmail = newSession?.email
        if let newSession, let data = try? JSONEncoder().encode(newSession) {
            Keychain.save(data, key: "session")
        } else {
            Keychain.delete(key: "session")
        }
    }

    private func validSession() async throws -> Session {
        guard var current = session else { throw SupabaseError.notSignedIn }
        if current.expiresAt.timeIntervalSinceNow < 60 {
            current = try await SupabaseClient.refresh(current)
            storeSession(current)
        }
        return current
    }

    // MARK: - Sincronizzazione

    /// Avvia una sincronizzazione a breve, riunendo le richieste ravvicinate.
    func scheduleSync(after seconds: Double = 0.8) {
        guard isSignedIn else { return }
        syncDebounceTask?.cancel()
        syncDebounceTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(seconds))
            guard !Task.isCancelled else { return }
            await self?.syncNow()
        }
    }

    func syncNow() async {
        // Se un'altra sincronizzazione è già in corso ci si limita a
        // segnalarne una successiva: sarà il ciclo già avviato a occuparsene.
        // Rientrare qui girerebbe a vuoto senza mai cedere il thread.
        guard !isSyncing else {
            pendingAnotherSync = true
            return
        }
        repeat {
            pendingAnotherSync = false
            await performSync()
        } while pendingAnotherSync
    }

    private func performSync() async {
        guard session != nil, !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }
        do {
            let current = try await validSession()

            // Si lavora su una fotografia degli elenchi: le modifiche fatte
            // durante le chiamate di rete restano in coda per il giro dopo.
            let deletions = pendingDeletions
            for id in deletions {
                try await SupabaseClient.deleteBook(id: id, session: current)
            }
            if !deletions.isEmpty {
                pendingDeletions.subtract(deletions)
                save()
            }

            let dirtySnapshot = dirtyIDs
            let dirty = books.filter { dirtySnapshot.contains($0.id) }
            if !dirty.isEmpty {
                try await SupabaseClient.upsertBooks(dirty.map { BookRecord(book: $0, userID: current.userID) }, session: current)
                dirtyIDs.subtract(dirtySnapshot)
                save()
            }

            let remote = try await SupabaseClient.fetchBooks(session: current).map { $0.toBook() }
            var merged = remote
            let stillDirty = books.filter { dirtyIDs.contains($0.id) }
            for book in stillDirty {
                merged.removeAll { $0.id == book.id }
                merged.append(book)
            }
            merged.removeAll { pendingDeletions.contains($0.id) }
            books = merged
            sortBooks()
            save()
            setSyncedNow()
            await downloadMissingCovers()
        } catch {
            if (error as? SupabaseError)?.statusCode == 401,
               let expired = session,
               let refreshed = try? await SupabaseClient.refresh(expired) {
                storeSession(refreshed)
                pendingAnotherSync = true
            } else {
                syncStatusText = friendlyError(error)
            }
        }
    }

    /// Prima sincronizzazione dopo l'accesso: i dati del server hanno la
    /// precedenza, i libri presenti solo in locale vengono caricati.
    private func initialMergeSync() async {
        guard let current = session else { return }
        isSyncing = true
        do {
            let remote = try await SupabaseClient.fetchBooks(session: current).map { $0.toBook() }
            let remoteIDs = Set(remote.map { $0.id })
            let onlyLocal = books.filter { !remoteIDs.contains($0.id) }
            dirtyIDs.formUnion(onlyLocal.map { $0.id })
            books = remote + onlyLocal
            sortBooks()
            save()
            let dirtySnapshot = dirtyIDs
            if !dirtySnapshot.isEmpty {
                let dirty = books.filter { dirtySnapshot.contains($0.id) }
                try await SupabaseClient.upsertBooks(dirty.map { BookRecord(book: $0, userID: current.userID) }, session: current)
                dirtyIDs.subtract(dirtySnapshot)
                save()
            }
            setSyncedNow()
            isSyncing = false
            await downloadMissingCovers()
        } catch {
            syncStatusText = friendlyError(error)
            isSyncing = false
        }
        if pendingAnotherSync {
            pendingAnotherSync = false
            await syncNow()
        }
    }

    private func setSyncedNow() {
        syncStatusText = "Sincronizzato alle \(Date().formatted(date: .omitted, time: .shortened))"
    }

    private func friendlyError(_ error: Error) -> String {
        if let supabaseError = error as? SupabaseError {
            return supabaseError.errorDescription ?? "Errore di sincronizzazione."
        }
        if error is URLError {
            return "Server non raggiungibile: le modifiche restano salvate sul dispositivo."
        }
        return "Errore di sincronizzazione."
    }

    // MARK: - Copertine

    func localCover(for id: String) -> PlatformImage? {
        if let cached = coverCache.object(forKey: id as NSString) { return cached }
        guard let data = try? Data(contentsOf: coverFileURL(for: id)),
              let image = PlatformImage(data: data) else { return nil }
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
              PlatformImage(data: data) != nil else { return }
        try? data.write(to: fileURL, options: .atomic)
        objectWillChange.send()
    }

    private func downloadMissingCovers() async {
        for book in books {
            await downloadCoverIfNeeded(for: book)
        }
    }

    // MARK: - Persistenza locale

    private struct LibraryData: Codable {
        var books: [Book]
        var dirtyIDs: [String]
        var pendingDeletions: [String]
    }

    private func load() {
        guard let data = try? Data(contentsOf: libraryFileURL) else { return }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        if let container = try? decoder.decode(LibraryData.self, from: data) {
            books = container.books
            dirtyIDs = Set(container.dirtyIDs)
            pendingDeletions = Set(container.pendingDeletions)
        } else if let oldBooks = try? decoder.decode([Book].self, from: data) {
            // Formato della prima versione dell'app: solo l'elenco dei libri.
            books = oldBooks
        }
        sortBooks()
    }

    private func sortBooks() {
        books.sort { $0.dateRead > $1.dateRead }
    }

    private func save() {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let container = LibraryData(
            books: books,
            dirtyIDs: Array(dirtyIDs),
            pendingDeletions: Array(pendingDeletions)
        )
        guard let data = try? encoder.encode(container) else { return }
        try? data.write(to: libraryFileURL, options: .atomic)
    }
}
