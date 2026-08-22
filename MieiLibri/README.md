# I miei libri (MieiLibri)

App **iPhone, iPad e Mac** per registrare i libri letti, con le copertine e la
sincronizzazione dei dati tra tutti i dispositivi.

Un solo progetto Xcode e un solo codice sorgente: la stessa app si compila come
app iOS nativa e come app Mac nativa (non Catalyst).

## Funzionalità

- **Ricerca nel catalogo**: cerca in [Google Books](https://developers.google.com/books)
  scegliendo l'ambito — **Tutto**, **Titolo** o **Autore** — con le linguette
  sotto il campo di ricerca. Restringere a titolo o autore evita i risultati
  strani che si ottengono cercando anche nel testo integrale. Un codice ISBN
  viene riconosciuto da solo. Si può inoltre filtrare per **anno** di
  pubblicazione e scegliere la **lingua** dei libri (Account ▸ Ricerca), così
  lo stesso titolo non si ripete in ogni traduzione. Le edizioni doppie della
  stessa opera vengono unite, tenendo quella con la copertina.
- **Copertine ingrandibili**: toccando una copertina si apre a schermo intero,
  con pizzico per allargare e doppio tocco per alternare.
- **Libreria per autore**: la schermata principale elenca gli autori letti;
  scegliendone uno si vedono i suoi libri, ordinati **dal più recente di
  pubblicazione al più vecchio** (quelli senza anno in fondo). Un tocco su ＋
  aggiunge un libro. La copertina viene scaricata e salvata sul dispositivo,
  così resta visibile anche senza connessione.
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

## Installare sull'iPhone

### Il modo più rapido: da Xcode

Se hai il Mac a portata di mano è questione di un minuto e non serve nient'altro:
collega l'iPhone via cavo, selezionalo nella barra in alto di Xcode e premi ⌘R.
Con un account sviluppatore la firma è automatica. Alla prima installazione
l'iPhone chiede di autorizzare lo sviluppatore: *Impostazioni ▸ Generali ▸ VPN e
gestione dispositivo*.

### Senza Mac: la build automatica su GitHub

Il workflow [`.github/workflows/mieilibri.yml`](../.github/workflows/mieilibri.yml)
compila e firma l'app su un runner macOS di GitHub Actions (gratuito, perché il
repository è pubblico) e pubblica il risultato in `MieiLibri/download/` con una
pagina da cui installare direttamente.

**Una volta sola**, crea una chiave API di App Store Connect e quattro segreti.

1. Su [App Store Connect](https://appstoreconnect.apple.com) vai in *Users and
   Access ▸ Integrations ▸ App Store Connect API ▸ Team Keys*, premi **+**, dai
   un nome alla chiave e assegnale il ruolo **App Manager** (con *Developer* non
   può creare i certificati). Scarica il file `.p8`: **si scarica una volta
   sola**, conservalo.
2. Dalla stessa pagina annota **Key ID** e **Issuer ID**.
3. Il **Team ID** (10 caratteri) è su
   [developer.apple.com](https://developer.apple.com/account) sotto *Membership*.
4. Su GitHub, in *Settings ▸ Secrets and variables ▸ Actions*, aggiungi:

   | Segreto | Contenuto |
   |---|---|
   | `ASC_KEY_ID` | il Key ID (es. `ABCD123456`) |
   | `ASC_ISSUER_ID` | l'Issuer ID (un UUID) |
   | `ASC_KEY_P8` | il contenuto del file `.p8` |
   | `APPLE_TEAM_ID` | il Team ID |

Il file `.p8` è un normale file di testo: aprilo con un qualsiasi editor e
copia **tutto**, dalla riga `-----BEGIN PRIVATE KEY-----` a
`-----END PRIVATE KEY-----` incluse, poi incollalo nel campo del segreto. I
segreti di GitHub accettano valori su più righe, quindi non serve convertire
nulla. Se preferisci, il workflow accetta anche la chiave codificata in
base64: riconosce da solo quale delle due forme hai usato.

**Ogni volta che vuoi una build**: apri la scheda *Actions*, scegli il workflow
*MieiLibri*, premi *Run workflow*, spunta **firma** e lascia il metodo
predefinito `debugging`. Al termine apri con **Safari sull'iPhone**:

```
https://fbacchin.github.io/app/MieiLibri/download/
```

e tocca *Installa sull'iPhone*. Il tuo telefono è già registrato fra i
dispositivi di sviluppo, quindi il profilo lo include automaticamente.

### Perché `debugging` e non ad-hoc

`release-testing` (ad-hoc) e `app-store-connect` (TestFlight) richiedono un
certificato di **distribuzione**, e per crearlo via cloud Apple pretende che la
chiave API abbia ruolo **Admin**: con *App Manager* l'esportazione fallisce con
`Cloud signing permission error`. La firma di **sviluppo** invece funziona con
App Manager e basta e avanza, perché l'iPhone è già registrato. Se un giorno ti
serve TestFlight, alza il ruolo della chiave ad Admin.

### La cartella deve stare su `main`

GitHub Pages serve dalla radice di `main`. Il workflow pubblica sul branch da
cui viene lanciato, quindi se lo esegui da un branch di sviluppo ricordati di
riportare `MieiLibri/download/` su `main`, altrimenti il collegamento risponde
404. È lo stesso schema già usato da `volcano/ota/`.

> ⚠️ L'IPA finisce in una cartella pubblica del repository. L'app si installa
> comunque solo sui dispositivi registrati, ma il profilo incluso contiene il
> Team ID e gli UDID dei tuoi dispositivi. Se preferisci non esporli, usa
> TestFlight (che però richiede il ruolo Admin, vedi sopra).

## Se la ricerca dà errore

La ricerca usa **Google Books**, che senza chiave attribuisce le richieste a una
quota *condivisa fra tutti gli utenti che escono dallo stesso indirizzo IP*. Sui
dati mobili l'indirizzo è quello dell'operatore, condiviso con molte persone:
capita quindi di trovare la quota già esaurita e di ricevere un rifiuto
(`HTTP 429`) pur avendo la connessione perfettamente funzionante.

L'app se ne accorge e **ripiega automaticamente su [Open Library](https://openlibrary.org)**,
che non ha quote per indirizzo IP. Il suo repertorio italiano è più povero, ma la
ricerca continua a funzionare. I messaggi distinguono i casi: *nessuna
connessione* è un problema di rete, *il catalogo ha esaurito le richieste* no.

### Una chiave Google personale

Con una chiave la quota diventa tua e il problema sparisce. Si crea gratis:

1. Apri la [console Google Cloud](https://console.cloud.google.com/) e crea un
   progetto (o usane uno che hai già).
2. Vai su [Books API](https://console.cloud.google.com/apis/library/books.googleapis.com)
   e premi **Abilita**.
3. *API e servizi ▸ Credenziali ▸ Crea credenziali ▸ Chiave API*. Copia la
   chiave: inizia per `AIza…`.
4. Premi **Modifica chiave API** e limitala:
   - *Restrizioni API* → **Limita chiave** → solo **Books API**;
   - *Restrizioni applicazione* → **App iOS** → aggiungi
     `com.bacchin.MieiLibri` (l'app invia già l'intestazione che serve).

**Dove metterla.** Questo repository è pubblico, quindi la chiave **non va
messa nel codice e committata**. Due modi corretti:

- **Build automatica** (consigliato): aggiungi su GitHub il segreto
  `GOOGLE_BOOKS_KEY` in *Settings ▸ Secrets and variables ▸ Actions*. Il
  workflow la inserisce al momento della compilazione e non la scrive mai nel
  repository.
- **Solo in locale**: dalla cartella `MieiLibri` esegui
  ```bash
  ./configura-catalogo.sh AIzaSy...
  ```
  che scrive la chiave in `MieiLibri/Services/Catalog.swift`. Ricordati di non
  fare il commit di quella modifica.

## Sincronizzazione tra Mac e iPhone

**Il server è già configurato e pronto all'uso.** I dati stanno su un progetto
[Supabase](https://supabase.com) (database Postgres + gestione account) del
piano gratuito:

| | |
|---|---|
| Progetto | `fbacchin's Project` (`qtgbfbmldmxjsvrtehha`) |
| Regione | Irlanda (`eu-west-1`) |
| Tabella | `public.books`, con Row Level Security attiva |

Le coordinate sono già scritte in `MieiLibri/Services/SupabaseConfig.swift`:
basta compilare l'app.

### Come usarla

Al primo avvio l'app chiede di **registrarti** con email e password. Riceverai
un'email di conferma: apri il collegamento e poi premi *Accedi*. Ripeti
l'accesso con le **stesse credenziali** sull'altro dispositivo e i libri
compariranno da soli.

Se preferisci non usare alcun account, tocca *Usa solo su questo dispositivo*:
potrai attivare la sincronizzazione più avanti dal simbolo della persona.

### Sulla chiave nel codice

La chiave *publishable* presente in `SupabaseConfig.swift` è pensata per essere
distribuita insieme alle app: da sola non dà accesso ai dati, perché è il
server a filtrare le righe per utente. L'isolamento è stato verificato sul
database con due utenti di prova:

- un utente rilegge i propri libri; ✅
- non vede quelli di un altro utente; ✅
- non può cancellarli; ✅
- senza login non si vede nulla. ✅

> ⚠️ **Questo repository è pubblico**, quindi la chiave è visibile a chiunque.
> Non è un problema per i tuoi dati — l'isolamento qui sopra vale comunque — ma
> conviene disattivare le registrazioni libere dalla dashboard Supabase
> (*Authentication → Sign In / Providers → Allow new users to sign up*) subito
> dopo aver registrato i tuoi dispositivi: altrimenti un estraneo può creare
> account e consumare la quota del piano gratuito.

### Ricreare il server altrove

Se un giorno vuoi spostare i dati su un altro progetto Supabase: crea il
progetto, incolla [`supabase/schema.sql`](supabase/schema.sql) nel *SQL
Editor*, poi aggiorna le coordinate con

```bash
./supabase/configura.sh https://TUOPROGETTO.supabase.co sb_publishable_LATUACHIAVE
```

### Se la sincronizzazione smette di funzionare

Sul piano gratuito Supabase **mette in pausa i progetti inutilizzati** dopo
circa una settimana (era già successo a questo). In quel caso l'app continua a
funzionare normalmente in locale e mostra un avviso di server non
raggiungibile: per riattivarlo entra su [supabase.com](https://supabase.com),
apri il progetto e premi *Restore project*. Ci vogliono un paio di minuti e
nessun dato viene perso. Usando l'app con regolarità la pausa non scatta.

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
