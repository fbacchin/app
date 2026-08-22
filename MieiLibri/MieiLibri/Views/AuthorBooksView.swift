import SwiftUI

/// Un autore nell'elenco della libreria.
/// L'uguaglianza guarda solo il nome: il conteggio cambia aggiungendo libri
/// e non deve invalidare una destinazione di navigazione già aperta.
struct Autore: Hashable, Identifiable {
    let nome: String
    let conteggio: Int

    var id: String { nome }

    static func == (sinistra: Autore, destra: Autore) -> Bool {
        sinistra.nome == destra.nome
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(nome)
    }
}

/// I libri letti di un autore, dal più recente di pubblicazione al più vecchio.
struct AuthorBooksView: View {
    @EnvironmentObject private var library: Library
    let autore: String

    private var libri: [Book] {
        library.books
            .filter { libro in
                libro.authors.isEmpty
                    ? autore == Book.autoreIgnoto
                    : libro.authors.contains(autore)
            }
            .sorted(by: Book.perAnnoDecrescente)
    }

    var body: some View {
        List {
            Section {
                ForEach(libri) { libro in
                    NavigationLink(value: libro.id) {
                        BookRowView(book: libro, mostraAutore: false)
                    }
                    .contextMenu {
                        Button("Rimuovi dalla libreria", role: .destructive) {
                            library.remove(libro)
                        }
                    }
                }
                .onDelete(perform: elimina)
            } footer: {
                Text(libri.count == 1 ? "1 libro letto" : "\(libri.count) libri letti")
            }
        }
        .listStyle(.plain)
        .navigationTitle(autore)
        .inlineNavigationTitle()
    }

    private func elimina(at offsets: IndexSet) {
        for libro in offsets.map({ libri[$0] }) {
            library.remove(libro)
        }
    }
}
