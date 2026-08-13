# I miei libri (MieiLibri)

App iOS semplice e leggera per registrare i libri letti, con le copertine.

## Funzionalità

- **Ricerca nel catalogo**: cerca per titolo, autore o ISBN nel catalogo di
  [Google Books](https://developers.google.com/books) (API pubblica e gratuita,
  nessuna chiave richiesta). I risultati mostrano la copertina di ogni libro.
- **Libreria personale**: un tocco su ＋ aggiunge il libro all'elenco dei letti.
  La copertina viene scaricata e salvata sul dispositivo, così resta visibile
  anche senza connessione.
- **Dettagli di lettura**: per ogni libro puoi impostare la data di lettura,
  una valutazione da 1 a 5 stelle e note personali. Le modifiche si salvano
  automaticamente.
- **Filtro**: la libreria si filtra per titolo o autore; per eliminare un libro
  basta scorrere la riga verso sinistra.

## Requisiti

- Xcode 16 o successivo
- iOS 17.0 o successivo

## Come eseguirla

1. Apri `MieiLibri.xcodeproj` con Xcode.
2. Scegli un simulatore (o il tuo iPhone) e premi **Run** (⌘R).
3. Per installarla su un dispositivo fisico, imposta il tuo team in
   *Signing & Capabilities* del target `MieiLibri`.

## Dati e privacy

Nessun account e nessun server proprio: la libreria è un file JSON
(`library.json`) nella cartella Documenti dell'app e le copertine sono
salvate nella sottocartella `Covers/`. L'unica connessione di rete è verso
le API di Google Books per la ricerca e il download delle copertine.

## Struttura del codice

```
MieiLibri/
├── MieiLibriApp.swift        # Punto di ingresso
├── Models/
│   ├── Book.swift            # Libro salvato in libreria
│   └── RemoteBook.swift      # Risultato di ricerca dal catalogo
├── Services/
│   ├── GoogleBooksAPI.swift  # Client per la ricerca su Google Books
│   └── Library.swift         # Persistenza JSON + copertine locali
└── Views/
    ├── LibraryView.swift     # Elenco dei libri letti
    ├── SearchView.swift      # Ricerca nel catalogo
    ├── BookDetailView.swift  # Dettaglio con data, stelle e note
    └── BookCoverView.swift   # Copertina (locale → remota → segnaposto)
```
