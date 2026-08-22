import SwiftUI

/// Schermata principale: gli autori letti. Scegliendone uno si vedono i suoi
/// libri, dal più recente di pubblicazione al più vecchio.
struct LibraryView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.scenePhase) private var scenePhase
    @State private var showSearch = false
    @State private var showAccount = false
    @State private var filter = ""

    /// I libri di un autore, ordinati per anno di uscita decrescente.
    private func libri(di nome: String) -> [Book] {
        library.books
            .filter { $0.authors.isEmpty ? nome == Book.autoreIgnoto : $0.authors.contains(nome) }
            .sorted(by: Book.perAnnoDecrescente)
    }

    /// Gli autori in ordine alfabetico: qui si sceglie, quindi conta trovarli
    /// in fretta più che vederli per data.
    private var autori: [Autore] {
        var conteggi: [String: Int] = [:]
        for libro in library.books {
            for nome in (libro.authors.isEmpty ? [Book.autoreIgnoto] : libro.authors) {
                conteggi[nome, default: 0] += 1
            }
        }
        let cercato = filter.trimmingCharacters(in: .whitespaces)
        return conteggi.keys
            .filter { nome in
                guard !cercato.isEmpty else { return true }
                // Il filtro trova sia il nome dell'autore sia il titolo di un
                // suo libro: cercando un titolo si arriva comunque all'autore.
                return nome.localizedCaseInsensitiveContains(cercato)
                    || libri(di: nome).contains { $0.title.localizedCaseInsensitiveContains(cercato) }
            }
            .sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
            .map { Autore(nome: $0, conteggio: conteggi[$0] ?? 0) }
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
        .navigationDestination(for: Autore.self) { autore in
            AuthorBooksView(autore: autore.nome)
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
            TextField("Filtra per autore o titolo", text: $filter)
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
        } else if autori.isEmpty {
            ContentUnavailableView.search(text: filter)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            elencoAutori
        }
    }

    private var elencoAutori: some View {
        List {
            Section {
                ForEach(autori) { autore in
                    NavigationLink(value: autore) {
                        AuthorRowView(autore: autore, ultimo: libri(di: autore.nome).first)
                    }
                }
            } footer: {
                VStack(alignment: .leading, spacing: 4) {
                    if filter.isEmpty {
                        Text(riepilogo)
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

    private var riepilogo: String {
        let libri = library.books.count
        let quantiAutori = autori.count
        let parteLibri = libri == 1 ? "1 libro letto" : "\(libri) libri letti"
        let parteAutori = quantiAutori == 1 ? "1 autore" : "\(quantiAutori) autori"
        return "\(parteLibri), \(parteAutori)"
    }
}

/// Riga di un autore: la copertina del suo libro più recente, il nome e
/// quanti se ne sono letti.
struct AuthorRowView: View {
    @EnvironmentObject private var library: Library
    let autore: Autore
    let ultimo: Book?

    var body: some View {
        HStack(spacing: 12) {
            BookCoverView(
                image: ultimo.flatMap { library.localCover(for: $0.id) },
                url: ultimo?.coverURL,
                width: 40
            )
            VStack(alignment: .leading, spacing: 3) {
                Text(autore.nome)
                    .font(.headline)
                    .lineLimit(2)
                Text(autore.conteggio == 1 ? "1 libro" : "\(autore.conteggio) libri")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

/// Riga di un libro: copertina, titolo, autore, valutazione e data di lettura.
struct BookRowView: View {
    @EnvironmentObject private var library: Library
    let book: Book
    /// Dentro la schermata di un autore il nome sarebbe ripetuto a ogni riga.
    var mostraAutore = true

    var body: some View {
        HStack(spacing: 12) {
            BookCoverView(image: library.localCover(for: book.id), url: book.coverURL, width: 46)
            VStack(alignment: .leading, spacing: 3) {
                Text(book.title)
                    .font(.headline)
                    .lineLimit(2)
                if mostraAutore {
                    Text(book.authorsText)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                HStack(spacing: 6) {
                    if let anno = book.publishedYear {
                        Text(anno)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
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
                if let riassunto = book.summary, !riassunto.isEmpty {
                    TestoGiustificato(testo: riassunto, stile: .piccolo, righeMassime: 2)
                        .padding(.top, 1)
                }
            }
        }
        .padding(.vertical, 4)
    }
}
