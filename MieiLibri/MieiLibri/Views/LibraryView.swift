import SwiftUI

/// Schermata principale: l'elenco dei libri letti.
/// Al primo avvio propone di collegare un account per la sincronizzazione.
struct LibraryView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.scenePhase) private var scenePhase
    @State private var showSearch = false
    @State private var showAccount = false
    @State private var filter = ""

    private var filteredBooks: [Book] {
        let trimmed = filter.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return library.books }
        return library.books.filter {
            $0.title.localizedCaseInsensitiveContains(trimmed) ||
            $0.authorsText.localizedCaseInsensitiveContains(trimmed)
        }
    }

    var body: some View {
        NavigationStack {
            if library.showsAccountGate {
                AccountView(isGate: true)
            } else {
                mainContent
            }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                library.scheduleSync(after: 0.2)
            }
        }
    }

    private var mainContent: some View {
        Group {
            if library.books.isEmpty {
                ContentUnavailableView {
                    Label("Nessun libro", systemImage: "books.vertical")
                } description: {
                    Text("Cerca un libro nel catalogo e aggiungilo alla tua libreria.")
                } actions: {
                    Button("Cerca un libro") { showSearch = true }
                        .buttonStyle(.borderedProminent)
                }
            } else {
                bookList
            }
        }
        .navigationTitle("I miei libri")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    showAccount = true
                } label: {
                    Image(systemName: library.isSignedIn ? "person.crop.circle.badge.checkmark" : "person.crop.circle")
                }
                .accessibilityLabel("Account e sincronizzazione")
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showSearch = true
                } label: {
                    Image(systemName: "plus")
                }
                .accessibilityLabel("Aggiungi un libro")
            }
        }
        .sheet(isPresented: $showSearch) {
            SearchView()
        }
        .sheet(isPresented: $showAccount) {
            NavigationStack {
                AccountView(isGate: false)
            }
        }
        .navigationDestination(for: String.self) { bookID in
            BookDetailView(bookID: bookID)
        }
    }

    private var bookList: some View {
        List {
            Section {
                ForEach(filteredBooks) { book in
                    NavigationLink(value: book.id) {
                        BookRowView(book: book)
                    }
                    .contextMenu {
                        Button("Rimuovi dalla libreria", role: .destructive) {
                            library.remove(book)
                        }
                    }
                }
                .onDelete(perform: delete)
            } footer: {
                VStack(alignment: .leading, spacing: 4) {
                    if filter.isEmpty {
                        Text(library.books.count == 1 ? "1 libro letto" : "\(library.books.count) libri letti")
                    }
                    if let status = library.syncStatusText {
                        Text(status)
                    }
                }
            }
        }
        .searchable(text: $filter, prompt: "Filtra la libreria")
    }

    private func delete(at offsets: IndexSet) {
        let toRemove = offsets.map { filteredBooks[$0] }
        for book in toRemove {
            library.remove(book)
        }
    }
}

/// Riga della libreria: copertina, titolo, autore, valutazione e data di lettura.
struct BookRowView: View {
    @EnvironmentObject private var library: Library
    let book: Book

    var body: some View {
        HStack(spacing: 12) {
            BookCoverView(image: library.localCover(for: book.id), url: book.coverURL, width: 46)
            VStack(alignment: .leading, spacing: 3) {
                Text(book.title)
                    .font(.headline)
                    .lineLimit(2)
                Text(book.authorsText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                HStack(spacing: 6) {
                    if book.rating > 0 {
                        HStack(spacing: 1) {
                            ForEach(1...book.rating, id: \.self) { _ in
                                Image(systemName: "star.fill")
                            }
                        }
                        .font(.caption2)
                        .foregroundStyle(.orange)
                    }
                    Text("Letto il \(book.dateRead.formatted(date: .abbreviated, time: .omitted))")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(.vertical, 4)
    }
}
