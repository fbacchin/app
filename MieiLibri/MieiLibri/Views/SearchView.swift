import SwiftUI

/// Ricerca nel catalogo, con copertine nei risultati.
/// Si può scegliere se cercare ovunque, solo nel titolo o solo nell'autore,
/// e restringere i risultati a un anno di pubblicazione.
struct SearchView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.dismiss) private var dismiss

    @AppStorage("linguaLibri") private var lingua: LinguaLibri = .tutte
    @State private var criteri = CatalogQuery()
    @State private var results: [RemoteBook] = []
    @State private var isLoading = false
    @State private var errore: CatalogError?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                filtroAnno
                Divider()
                List(results) { book in
                    SearchResultRow(book: book)
                }
                .listStyle(.plain)
                .dismissKeyboardOnScroll()
                .overlay { overlayContent }
            }
            .navigationTitle("Cerca libri")
            .inlineNavigationTitle()
            #if os(iOS)
            .searchable(
                text: $criteri.testo,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: promptRicerca
            )
            #else
            .searchable(text: $criteri.testo, prompt: promptRicerca)
            #endif
            .searchScopes($criteri.ambito) {
                ForEach(CatalogQuery.Ambito.allCases) { ambito in
                    Text(ambito.etichetta).tag(ambito)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Chiudi") { dismiss() }
                }
            }
            .task(id: ChiaveRicerca(criteri: criteri, lingua: lingua)) {
                await search()
            }
        }
        #if os(macOS)
        .frame(minWidth: 560, minHeight: 620)
        #endif
    }

    private var promptRicerca: String {
        switch criteri.ambito {
        case .tutto: return "Titolo, autore o ISBN"
        case .titolo: return "Titolo del libro"
        case .autore: return "Nome dell'autore"
        }
    }

    // MARK: - Filtro per anno

    private var filtroAnno: some View {
        HStack(spacing: 8) {
            Image(systemName: "calendar")
                .foregroundStyle(.secondary)
            Text("Anno")
                .foregroundStyle(.secondary)
            TextField("qualsiasi", text: $criteri.anno)
                .numericFieldStyle()
                .frame(width: 90)
                .textFieldStyle(.roundedBorder)
                .onChange(of: criteri.anno) { _, nuovo in
                    // Solo quattro cifre: qualunque altra cosa non e' un anno.
                    let cifre = String(nuovo.filter(\.isNumber).prefix(4))
                    if cifre != nuovo { criteri.anno = cifre }
                }
            if !criteri.anno.isEmpty {
                Button {
                    criteri.anno = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Togli il filtro sull'anno")
            }
            Spacer()
            if criteri.sembraISBN {
                Text("ricerca per ISBN")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            } else if lingua != .tutte {
                Text(lingua.etichetta.lowercased())
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .font(.subheadline)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    // MARK: - Stati della schermata

    @ViewBuilder
    private var overlayContent: some View {
        if isLoading && results.isEmpty {
            ProgressView("Ricerca in corso…")
        } else if let errore {
            ContentUnavailableView(
                errore.errorDescription ?? "Ricerca non riuscita",
                systemImage: errore == .offline ? "wifi.exclamationmark" : "books.vertical.circle",
                description: Text(errore.suggerimento)
            )
        } else if criteri.isEmpty {
            ContentUnavailableView(
                "Cerca nel catalogo",
                systemImage: "magnifyingglass",
                description: Text(descrizioneIniziale)
            )
        } else if results.isEmpty && !criteri.annoRipulito.isEmpty {
            // Distinzione utile: il libro potrebbe esistere, ma non in
            // quell'anno fra i risultati trovati.
            ContentUnavailableView(
                "Nessun risultato del \(criteri.annoRipulito)",
                systemImage: "calendar.badge.exclamationmark",
                description: Text("Prova a togliere il filtro sull'anno: l'edizione trovata potrebbe avere una data diversa.")
            )
        } else if results.isEmpty {
            ContentUnavailableView.search(text: criteri.testoRipulito)
        }
    }

    private var descrizioneIniziale: String {
        switch criteri.ambito {
        case .tutto:
            return "Cerca per titolo, autore o ISBN.\nPuoi restringere la ricerca con le linguette qui sopra."
        case .titolo:
            return "Digita il titolo del libro."
        case .autore:
            return "Digita il nome dell'autore."
        }
    }

    // MARK: - Ricerca

    private func search() async {
        guard !criteri.isEmpty else {
            results = []
            isLoading = false
            errore = nil
            return
        }
        // Piccola pausa per non interrogare il catalogo a ogni carattere digitato.
        try? await Task.sleep(for: .milliseconds(350))
        guard !Task.isCancelled else { return }
        isLoading = true
        errore = nil
        do {
            let trovati = try await Catalog.search(criteri)
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

/// Criteri e lingua insieme: basta che uno dei due cambi perché la ricerca
/// venga rifatta.
private struct ChiaveRicerca: Equatable {
    let criteri: CatalogQuery
    let lingua: LinguaLibri
}

/// Riga di un risultato: copertina, dati del libro e pulsante di aggiunta.
private struct SearchResultRow: View {
    @EnvironmentObject private var library: Library
    let book: RemoteBook

    @State private var mostraCopertina = false

    private var isSaved: Bool { library.contains(book.id) }

    var body: some View {
        HStack(spacing: 12) {
            BookCoverView(image: nil, url: book.coverURL, width: 46)
                .onTapGesture { mostraCopertina = true }
                .accessibilityAddTraits(.isButton)
                .accessibilityHint("Tocca per ingrandire la copertina")
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
        .schermoIntero(isPresented: $mostraCopertina) {
            CoverZoomView(image: nil, url: book.coverURL, titolo: book.title)
        }
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
