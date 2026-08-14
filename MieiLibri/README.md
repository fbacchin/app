# I miei libri (MieiLibri)

App **iPhone, iPad e Mac** per registrare i libri letti, con le copertine e la
sincronizzazione dei dati tra tutti i dispositivi.

Un solo progetto Xcode e un solo codice sorgente: la stessa app si compila come
app iOS nativa e come app Mac nativa (non Catalyst).

## Funzionalità

- **Ricerca nel catalogo**: cerca per titolo, autore o ISBN nel catalogo di
  [Google Books](https://developers.google.com/books) (API pubblica e gratuita,
  nessuna chiave richiesta). I risultati mostrano la copertina di ogni libro.
- **Libreria personale**: un tocco su ＋ aggiunge il libro all'elenco dei letti.
  La copertina viene scaricata e salvata sul dispositivo, così resta visibile
  anche senza connessione.
- **Dettagli di lettura**: data di lettura, valutazione da 1 a 5 stelle e note
  personali. Le modifiche si salvano automaticamente.
- **Sincronizzazione iPhone ↔ Mac**: con un account gratuito i libri, i voti e
  le note si allineano da soli tra i dispositivi.
- **Filtro**: la libreria si filtra per titolo o autore. Per eliminare un libro
  scorri la riga verso sinistra (iPhone) o usa il menu contestuale (Mac).

## Requisiti

- Xcode 16 o successivo
- iOS 17.0 o successivo / macOS 14.0 (Sonoma) o successivo

## Come eseguirla

1. Apri `MieiLibri.xcodeproj` con Xcode.
2. Nella barra in alto scegli la destinazione:
   - **iPhone** (o un simulatore) per la versione iOS;
   - **My Mac** per la versione Mac.
3. Premi **Run** (⌘R).

Per installarla su un dispositivo fisico imposta il tuo team in
*Signing & Capabilities* del target `MieiLibri`.

## Sincronizzazione tra Mac e iPhone

Senza configurazione l'app funziona subito, ma tiene i dati solo sul singolo
dispositivo. Per condividerli serve un progetto **Supabase** gratuito: fa da
server per i dati (database Postgres) e gestisce gli account.

### 1. Crea il progetto

Su [supabase.com](https://supabase.com) crea un account e un nuovo progetto
(piano *Free*). Scegli una regione vicina, per esempio *Frankfurt (eu-central-1)*.

### 2. Crea la tabella

Nella dashboard apri **SQL Editor**, incolla tutto il contenuto del file
[`supabase/schema.sql`](supabase/schema.sql) e premi *Run*. Crea la tabella
`books` con le regole di sicurezza: ogni utente può leggere e scrivere
**soltanto i propri libri**.

### 3. Collega l'app

In **Project Settings → API** copia il *Project URL* e la *publishable key*
(chiamata anche *anon key*), poi dalla cartella `MieiLibri` esegui:

```bash
./supabase/configura.sh https://TUOPROGETTO.supabase.co sb_publishable_LATUACHIAVE
```

Lo script scrive i due valori in `MieiLibri/Services/SupabaseConfig.swift`
(in alternativa puoi modificarlo a mano). Ricompila e il gioco è fatto.

> La chiave *publishable* è pensata per essere distribuita insieme all'app: da
> sola non dà accesso ai dati, perché è il server a filtrare le righe per
> utente tramite le policy di Row Level Security.

### 4. Usala

Al primo avvio l'app chiede di **registrarti** con email e password. Riceverai
un'email di conferma: apri il collegamento e poi premi *Accedi*. Ripeti
l'accesso con le **stesse credenziali** sull'altro dispositivo e i libri
compariranno da soli.

Se preferisci non usare alcun account, tocca *Usa solo su questo dispositivo*:
potrai attivare la sincronizzazione più avanti dal simbolo della persona.

### Come funziona la sincronizzazione

L'app è **offline-first**: ogni modifica viene applicata e salvata subito in
locale, poi inviata al server in background. Se la rete manca, le modifiche
restano in coda e partono al primo momento utile o alla riapertura dell'app.
In caso di modifiche allo stesso libro da due dispositivi diversi vince
l'ultima inviata.

## Dati e privacy

- Senza account: nulla lascia il dispositivo, a parte le ricerche su Google Books.
- Con account: i dati dei libri stanno nel **tuo** progetto Supabase, di cui sei
  l'unico proprietario. Le copertine restano comunque salvate sui dispositivi.
- La sessione dell'account è custodita nel portachiavi di sistema.

## Struttura del codice

```
MieiLibri/
├── MieiLibriApp.swift          # Punto di ingresso
├── Models/
│   ├── Book.swift              # Libro salvato in libreria
│   └── RemoteBook.swift        # Risultato di ricerca dal catalogo
├── Services/
│   ├── GoogleBooksAPI.swift    # Ricerca nel catalogo
│   ├── Library.swift           # Dati locali, copertine e sincronizzazione
│   ├── SupabaseClient.swift    # Account e API del server (solo URLSession)
│   └── SupabaseConfig.swift    # Indirizzo e chiave del progetto
├── Support/
│   ├── Platform.swift          # Piccole differenze tra iOS e macOS
│   └── Keychain.swift          # Sessione nel portachiavi
└── Views/
    ├── LibraryView.swift       # Elenco dei libri letti
    ├── SearchView.swift        # Ricerca nel catalogo
    ├── BookDetailView.swift    # Dettaglio con data, stelle e note
    ├── AccountView.swift       # Accesso, registrazione e stato sincronia
    └── BookCoverView.swift     # Copertina (locale → remota → segnaposto)

supabase/
├── schema.sql                  # Tabella books + Row Level Security
└── configura.sh                # Scrive URL e chiave in SupabaseConfig.swift
```

Nessuna dipendenza esterna: solo SwiftUI e URLSession.
