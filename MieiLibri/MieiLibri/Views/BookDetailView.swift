import SwiftUI

/// Dettaglio di un libro salvato: copertina, dati, data di lettura,
/// valutazione e note personali. Le modifiche si salvano da sole.
struct BookDetailView: View {
    @EnvironmentObject private var library: Library
    @Environment(\.dismiss) private var dismiss
    let bookID: String

    @State private var confirmDelete = false

    var body: some View {
        if let book = library.book(with: bookID) {
            detail(for: book)
        } else {
            EmptyView()
        }
    }

    private func detail(for book: Book) -> some View {
        let hasInfo = book.publisher != nil || book.publishedYear != nil
            || book.pageCount != nil || book.isbn != nil

        return List {
            Section {
                VStack(spacing: 12) {
                    BookCoverView(image: library.localCover(for: book.id), url: book.coverURL, width: 130)
                        .shadow(color: .black.opacity(0.2), radius: 8, y: 4)
                    Text(book.title)
                        .font(.title2.bold())
                        .multilineTextAlignment(.center)
                    Text(book.authorsText)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
            }

            Section("La mia lettura") {
                DatePicker(
                    "Letto il",
                    selection: binding(for: book, \.dateRead),
                    displayedComponents: .date
                )
                LabeledContent("Valutazione") {
                    StarRatingView(rating: binding(for: book, \.rating))
                }
            }

            Section("Note") {
                TextEditor(text: binding(for: book, \.notes))
                    .frame(minHeight: 120)
                    .overlay(alignment: .topLeading) {
                        if book.notes.isEmpty {
                            Text("Scrivi un pensiero sul libro…")
                                .foregroundStyle(.tertiary)
                                .padding(.top, 8)
                                .allowsHitTesting(false)
                        }
                    }
            }

            if hasInfo {
                Section("Informazioni") {
                    if let publisher = book.publisher {
                        LabeledContent("Editore", value: publisher)
                    }
                    if let year = book.publishedYear {
                        LabeledContent("Anno", value: year)
                    }
                    if let pages = book.pageCount {
                        LabeledContent("Pagine", value: "\(pages)")
                    }
                    if let isbn = book.isbn {
                        LabeledContent("ISBN", value: isbn)
                    }
                }
            }

            Section {
                Button("Rimuovi dalla libreria", role: .destructive) {
                    confirmDelete = true
                }
                .frame(maxWidth: .infinity)
            }
        }
        .navigationTitle("Dettagli")
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(
            "Vuoi rimuovere questo libro dalla libreria?",
            isPresented: $confirmDelete,
            titleVisibility: .visible
        ) {
            Button("Rimuovi", role: .destructive) {
                library.remove(book)
                dismiss()
            }
            Button("Annulla", role: .cancel) {}
        }
    }

    /// Binding che legge e scrive direttamente nella libreria,
    /// così ogni modifica viene salvata subito su disco.
    private func binding<Value>(for book: Book, _ keyPath: WritableKeyPath<Book, Value>) -> Binding<Value> {
        Binding(
            get: { (library.book(with: book.id) ?? book)[keyPath: keyPath] },
            set: { newValue in
                guard var updated = library.book(with: book.id) else { return }
                updated[keyPath: keyPath] = newValue
                library.update(updated)
            }
        )
    }
}

/// Selettore di valutazione da 1 a 5 stelle; toccando di nuovo
/// l'ultima stella la valutazione si azzera.
struct StarRatingView: View {
    @Binding var rating: Int

    var body: some View {
        HStack(spacing: 6) {
            ForEach(1...5, id: \.self) { star in
                Button {
                    rating = (rating == star) ? star - 1 : star
                } label: {
                    Image(systemName: star <= rating ? "star.fill" : "star")
                        .foregroundStyle(.orange)
                }
                .buttonStyle(.plain)
            }
        }
        .font(.title3)
        .accessibilityLabel("Valutazione")
        .accessibilityValue("\(rating) su 5")
    }
}
