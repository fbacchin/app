import SwiftUI

/// Ricerca nel catalogo di Google Books, con copertine nei risultati.
struct SearchView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.dismiss) private var dismiss

    @State private var query = ""
    @State private var results: [RemoteBook] = []
    @State private var isLoading = false
    @State private var errore: CatalogError?

    var body: some View {
        NavigationStack {
            List(results) { book in
                SearchResultRow(book: book)
            }
            .listStyle(.plain)
            .dismissKeyboardOnScroll()
            .overlay { overlayContent }
            .navigationTitle("Cerca libri")
            .inlineNavigationTitle()
            #if os(iOS)
            .searchable(
                text: $query,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: "Titolo, autore o ISBN"
            )
            #else
            .searchable(text: $query, prompt: "Titolo, autore o ISBN")
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Chiudi") { dismiss() }
                }
            }
            .task(id: query) {
                await search()
            }
        }
        #if os(macOS)
        .frame(minWidth: 540, minHeight: 600)
        #endif
    }

    @ViewBuilder
    private var overlayContent: some View {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if isLoading && results.isEmpty {
            ProgressView("Ricerca in corso…")
        } else if let errore {
            ContentUnavailableView(
                errore.errorDescription ?? "Ricerca non riuscita",
                systemImage: errore == .offline ? "wifi.exclamationmark" : "books.vertical.circle",
                description: Text(errore.suggerimento)
            )
        } else if trimmed.isEmpty {
            ContentUnavailableView(
                "Cerca nel catalogo",
                systemImage: "magnifyingglass",
                description: Text("Cerca per titolo, autore o ISBN.\nI risultati arrivano da Google Libri.")
            )
        } else if results.isEmpty {
            ContentUnavailableView.search(text: trimmed)
        }
    }

    private func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            results = []
            isLoading = false
            errore = nil
            return
        }
        // Piccola pausa per non interrogare l'API a ogni carattere digitato.
        try? await Task.sleep(for: .milliseconds(350))
        guard !Task.isCancelled else { return }
        isLoading = true
        errore = nil
        do {
            let trovati = try await Catalog.search(trimmed)
            guard !Task.isCancelled else { return }
            results = trovati
        } catch {
            if Task.isCancelled || (error as? URLError)?.code == .cancelled { return }
            results = []
            errore = CatalogError.from(error)
        }
        isLoading = false
    }
}

/// Riga di un risultato: copertina, dati del libro e pulsante di aggiunta.
private struct SearchResultRow: View {
    @EnvironmentObject private var library: Library
    let book: RemoteBook

    private var isSaved: Bool { library.contains(book.id) }

    var body: some View {
        HStack(spacing: 12) {
            BookCoverView(image: nil, url: book.coverURL, width: 46)
            VStack(alignment: .leading, spacing: 3) {
                Text(book.title)
                    .font(.headline)
                    .lineLimit(2)
                if !book.authors.isEmpty {
                    Text(book.authors.joined(separator: ", "))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                if let details = detailsText {
                    Text(details)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            Button {
                add()
            } label: {
                Image(systemName: isSaved ? "checkmark.circle.fill" : "plus.circle.fill")
                    .font(.title2)
                    .foregroundStyle(isSaved ? Color.green : Color.accentColor)
            }
            .buttonStyle(.borderless)
            .disabled(isSaved)
            .accessibilityLabel(isSaved ? "Già in libreria" : "Aggiungi alla libreria")
        }
        .padding(.vertical, 4)
    }

    private var detailsText: String? {
        let parts = [book.publishedYear, book.publisher].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private func add() {
        guard !isSaved else { return }
        playSuccessHaptic()
        Task {
            await library.add(book)
        }
    }
}
