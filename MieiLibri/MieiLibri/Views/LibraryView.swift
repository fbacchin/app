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
        VStack(spacing: 0) {
            intestazione
            if !library.books.isEmpty {
                campoFiltro
            }
            contenuto
        }
        // La barra di navigazione di sistema riserva al titolo grande una
        // fascia fissa, che lascia molto spazio vuoto in cima. Qui il titolo
        // se lo disegna la schermata, con lo stesso carattere ma subito sotto
        // la barra di stato.
        #if os(iOS)
        .toolbar(.hidden, for: .navigationBar)
        #endif
        .navigationTitle("I miei libri")
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

    // MARK: - Intestazione

    private var intestazione: some View {
        HStack(spacing: 18) {
            Text("I miei libri")
                .font(.largeTitle.bold())
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            Spacer(minLength: 8)
            Button {
                showAccount = true
            } label: {
                Image(systemName: library.isSignedIn
                      ? "person.crop.circle.badge.checkmark"
                      : "person.crop.circle")
                    .font(.title2)
            }
            .accessibilityLabel("Account e sincronizzazione")
            Button {
                showSearch = true
            } label: {
                Image(systemName: "plus")
                    .font(.title2)
            }
            .accessibilityLabel("Aggiungi un libro")
        }
        .padding(.horizontal, 20)
        .padding(.top, 2)
        .padding(.bottom, 10)
    }

    private var campoFiltro: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
            TextField("Filtra la libreria", text: $filter)
                .textFieldStyle(.plain)
                .autocorrectionDisabled()
            if !filter.isEmpty {
                Button {
                    filter = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Cancella il filtro")
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }

    // MARK: - Contenuto

    @ViewBuilder
    private var contenuto: some View {
        if library.books.isEmpty {
            ContentUnavailableView {
                Label("Nessun libro", systemImage: "books.vertical")
            } description: {
                Text("Cerca un libro nel catalogo e aggiungilo alla tua libreria.")
            } actions: {
                Button("Cerca un libro") { showSearch = true }
                    .buttonStyle(.borderedProminent)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            bookList
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
                    Text(AppInfo.descrizione)
                }
            }
        }
        .listStyle(.plain)
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
