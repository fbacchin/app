# Valichi Live — l'app universale dei valichi europei

Il modello di **Gottardo Live** esteso a tutta Europa: un'app che mostra i
tempi d'attesa in tempo reale ai valichi di frontiera e agli assi alpini
dove il traffico si incolonna davvero (l'esempio che ha fatto nascere
l'idea: Croazia ↔ Montenegro a Karasovići in un sabato d'agosto), con i
valichi raggruppati in **zone acquistabili via in-app purchase**.

Il principio è lo stesso del Gottardo: le autorità pubblicano i dati, un
collector li campiona e li ripubblica come open data in questo repo, l'app
iOS legge i file da `raw.githubusercontent.com`. Differenza importante:
qui il device **non chiama mai le fonti** — solo i file aggregati. Un solo
punto da mantenere quando una fonte cambia faccia, zero quote API bruciate
dai client.

**Nome di lavoro**: "Valichi Live" (alternative valutabili: "Frontiere
Live", "EuroValichi"). Cartella `valichi/`, product ID con prefisso
`valichi.`.

## Componenti

- `catalog.json` — **il cuore del prodotto**: valichi, zone, pacchetti,
  nomi con cui le fonti chiamano i valichi (`matchNames`), coordinate
  (indicative, da rifinire in app), direzioni con etichette
- `collect.py` — collector multi-fonte; `python3 collect.py --prova` lo
  collauda offline sulle fixture in `prove/`
- `prove/` — pagine finte nel formato atteso dalle fonti, per il collaudo
  del parser senza rete
- `.github/workflows/valichi-collect.yml` (alla radice del repo) — il
  workflow che lo esegue in loop
- `privacy-valichi.html` / `support-valichi.html` — pagine pubbliche per
  l'App Store (via GitHub Pages), quadrilingue come quelle del Gottardo

## Cosa produce (in `data/`)

| File | Contenuto | Chi lo usa |
|---|---|---|
| `latest.json` | Ultimo stato per valico e direzione + salute delle fonti | La schermata principale dell'app |
| `history.json` | Finestra mobile di 48h, campioni compatti `{"time", "w": {"<valico>.<direzione>": minuti}}` | I grafici 6/12/24h |
| `push-state.json` | Fase notifiche per `<valico>.<direzione>` | Il collector stesso, per non ri-notificare |
| `sources-log.jsonl` | Salute fonti a ogni giro + finestre di testo estratte quando cambiano (14 giorni) | Nessuna app: è il materiale per **tarare i parser** sulle pagine vere |

Convenzione dei valori: `wait` in minuti; **0 solo se la fonte dichiara
"nessuna attesa"**; `null` = ignoto. Ai confini l'assenza di un numero è
ignoranza, non scorrevolezza — uno zero inventato è il difetto peggiore
che questo progetto possa produrre (lezione del Gottardo).

## Le fonti

| Fonte | Copre | Stato | Note |
|---|---|---|---|
| `gotthard` (file interno) | Gottardo | ✅ attiva | riusa `gotthard/data/latest.json` già raccolto dal collector gemello: zero rete, zero quota doppia |
| `hak` (hak.hr) | HR ↔ ME / BA / RS | ✅ attiva | tabella del MUP in fondo a `/info/stanje-na-cestama`, letta a celle. ⚠️ elenca **solo i valichi con una coda da dichiarare**: chi non è in tabella è ignoto, non libero. Vicoli ciechi da non riprovare: `/info/granicni-prijelazi/` è 404 e `m.hak.hr/stanje.asp?id=2` — che pure si intitola "Granični prijelazi" — è la pagina AVVISI, prosa senza un solo numero |
| `police_hu` (police.hu Határinfó) | HU ↔ RS / UA | ⚠️ parziale | HU–UA (Záhony, Beregsurány) ha i blocchi di attesa; **HU–RS no**: Röszke compare solo nei paragrafi di spiegazione e Tompa non compare affatto, quindi restano ignoti. HU–RO esclusa: Romania in Schengen dal 1.1.2025. Serve una seconda fonte per il confine serbo |
| `granica_pl` (granica.gov.pl) | PL ↔ UA | ✅ attiva | servizio **SOAP** ufficiale, operazione `getCzasyWszystko`. ⚠️ tre cose da sapere: l'endpoint e il WSDL rispondono solo **senza `www.`** (con `www.` è 500); le durate sono **ore**, anche decimali (`0.5`); il servizio pubblica solo le uscite dalla Polonia (`czas_osobowe_wjazd` è `-` a ogni ora e a ogni valico), quindi UA → PL resta ignoto |
| `otd_ch` | San Bernardino | 🔜 | stesso feed DATEX II del Gottardo, stessa chiave `OTD_API_KEY`: si estende il filtro del corridoio (attenzione alla quota condivisa) |
| `asfinag` | Brennero, Tauri | 🔜 | open data Asfinag da integrare |
| `promet_si` | Caravanche | 🔜 | B2B promet.si (DARS), registrazione gratuita |
| `tmb` / `sftrf` | Monte Bianco, Fréjus | 🔜 | le società dei trafori pubblicano attese e chiusure |
| `mvr_bg` | Kapitan Andreevo–Kapıkule | 🔜 | polizia di frontiera bulgara |

**Il collaudo sulle pagine vere** (il parser nasce su fixture: la sandbox
di sviluppo non raggiunge le fonti). Primo giro il 09.08.2026, esiti in
`data/sources-log.jsonl`:

- tutte e quattro le fonti raggiungibili e nomi riconosciuti (HAK 3/6,
  police.hu 3/4, granica 4/4), ma **zero attese lette** al primo colpo:
  m.hak.hr era la pagina avvisi, su police.hu vinceva il titolo di
  cronaca, la tabella di granica è a colonne. Da qui le due regole "miglior
  URL" e "miglior occorrenza" e la finestra di log a 400 caratteri;
- **secondo giro, stesso giorno**: le finestre a 400 caratteri hanno
  mostrato che il problema non era la taratura ma la fonte. Le regole
  "miglior URL" e "miglior occorrenza" non potevano salvare HAK, perché
  dei due URL uno era 404 e l'altro non conteneva numeri. Da qui i due
  parser strutturali (tabella per HAK, blocchi per police.hu) e il
  passaggio da 0 a 8 attese note su 15 valichi;
- il registro resta lo strumento: a ogni modifica di formato le finestre
  mostrano il testo vero su cui adeguare i parser. Poi si rifà la cattura
  in `prove/` — che ora sono **pagine reali**, non imitazioni — e si
  riallineano i valori attesi di `--prova`, che protegge da regressioni.

## Come legge le pagine (e perché così)

Le fonti di frontiera sono pagine HTML **senza contratto**: nessun feed
garantito, markup libero di cambiare. Da qui la scelta iniziale di non
interpretare la struttura ma il **testo**. Il collaudo del 09.08.2026 ha
mostrato il limite della regola: quando la pagina è una vera tabella a
colonne, dal testo appiattito le direzioni **non sono ricostruibili**, e
la lettura fuzzy le attribuisce tutte all'uscita. Oggi quindi convivono
due strategie, e si sceglie la struttura quando c'è:

- **HAK** — parser di tabella (`estrai_hak`): si leggono le celle di
  `table.gptable`, l'intestazione dice quali colonne sono Ulaz/Izlaz e
  quali auto/camion. Il tooltip (`L: 0 km`, timestamp) si butta prima di
  cercare i minuti: uno `0 km` letto come attesa sarebbe uno zero falso.
- **police.hu** — parser di blocchi (`estrai_police_hu`): per ogni valico
  si legge solo lo spezzone che segue il marcatore di direzione, chiuso
  alla voce successiva del blocco.
- **granica.gov.pl** — non è più una pagina: si interroga il servizio SOAP
  (`fonte_granica_pl`), una chiamata per valico, e i valori arrivano già
  separati per direzione e categoria.

**Sul SOAP polacco, una cautela che vale la pena scrivere.** Il servizio
indicizza per ora locale polacca e risponde **anche per ore che non sono
ancora accadute**: interrogato il 09.08 dava un valore per il 10.08 alle
12, e la risposta non contiene alcun marcatore di freschezza — rimanda
indietro la data e l'ora che gli hai chiesto, non quelle del rilevamento.
Per questo si chiede sempre e solo l'ora in corso (`ora_polacca`), e la
coppia data/ora che il servizio rimanda finisce nel registro delle
finestre: se un giorno i valori si rivelassero trascinati, la verifica è
già lì. Lo zero, invece, qui è affidabile come in nessun'altra fonte: il
servizio scrive `0` quando non si aspetta e `-` (o il campo vuoto) quando
non sa, e le due cose non si confondono.

Il funzionamento a finestre, che oggi non serve a nessuna fonte attiva ma
resta la rete di sicurezza per quelle future:

1. la pagina viene spianata (tag via, minuscole, senza accenti, spazi
   compressi) — "Karasovići", "KARASOVIĆI" e "karasovici" diventano la
   stessa stringa;
2. si cerca ogni valico per `matchNames`; la finestra di testo che segue
   (max 320 caratteri) si chiude alla prima comparsa del nome di un
   *altro* valico, altrimenti su una pagina-elenco i numeri del valico
   successivo vincerebbero per la regola del massimo;
3. nella finestra si leggono direzioni e durate in hr/hu/pl/en/it:
   `izlaz`/`ulaz`, `kilépő`/`belépő`, `wyjazd`/`wjazd`, "1 h 30 min",
   "2 sata", "1 godz. 15 min", e le frasi di zero esplicito ("nema
   zadržavanja", "nincs várakozás", "brak kolejki");
4. due impaginazioni, entrambe gestite: **per categoria** ("auto: uscita
   X, entrata Y. camion: uscita Z" — il marcatore di direzione che segue
   una voce camion appartiene ai camion e si salta) e **per direzione**
   ("uscita — auto X, camion Z; entrata — auto Y" — nel segmento di
   direzione si legge dal marcatore auto alla prima altra categoria).
   Sono le forme osservate su HAK, police.hu e granica prima che le tre
   fonti passassero a parser propri. Si mostrano le attese delle **auto**:
   l'app parla ai viaggiatori, e i camion — spesso ore in più — non devono
   vincere per la regola del massimo;
5. una finestra con un'attesa ma senza marcatori di direzione va
   sull'**uscita**: è il dato che le pagine danno per primo e quello che
   serve a chi parte. Scelta da verificare sul registro delle finestre;
6. durate oltre le 24 ore per le auto si scartano come letture sbagliate
   (l'etichetta `[h]` del Gottardo insegna: meglio ignoto che assurdo).

Una fonte che fallisce **non ferma le altre**: la salute per fonte finisce
in `latest.json` e l'app può dire "fonte momentaneamente non disponibile".

## Tenuta anti-buco

Le pagine di stato non hanno revoche esplicite come il feed svizzero: qui
il buco tipico è il **fetch fallito** (sito sotto carico nei giorni di
esodo) o il valico sparito per un giro. Regola: si riporta l'ultimo stato
osservato, marcato `held` e con l'`updated` **originale** (i valori tenuti
non riarmano il timer — identico al Gottardo), per al massimo
`HOLD_WINDOW` = 90 minuti. Oltre, le attese tornano `null`: ignote, mai 0.

## Notifiche push

Canali Back4App **per valico**: `valico-<id con - al posto dei punti>`
(es. `valico-hr-me-karasovici`); l'app iscrive il device ai canali dei
valichi seguiti. Fasi e conferme come al Gottardo, soglie da frontiera:
coda formata ≥ 30 min, pesante ≥ 120, fine < 15 confermata per 20 minuti,
cooldown 60 per direzione. Secrets **separati** da Gottardo Live
(`B4A_VALICHI_APP_ID`, `B4A_VALICHI_MASTER_KEY`, app Back4App dedicata):
pubblico diverso, e la Master Key vive solo nei Secrets di Actions. Senza
secrets il collector raccoglie e basta.

## Workflow

Stessa strategia del Gottardo (cron best-effort ⇒ run lunghi ~3 ore
incatenati dal gruppo di concorrenza, sync con `fetch`+`reset`, mai
`pull --rebase`, `git add` con i file **elencati esplicitamente**).
Cadenza 10 minuti, non 5: le fonti si aggiornano più lentamente e sono
siti pubblici da non martellare. Vale anche qui: il YAML è congelato
all'avvio del run, `collect.py` si aggiorna a ogni giro.

**Attivazione**: gli scheduled workflow girano solo dal branch di default
— il collector parte quando questo progetto arriva su `main` (o con
`workflow_dispatch` manuale).

## Acquisti in-app: il disegno

Modello **freemium a pacchetti una tantum** (niente abbonamenti — coerente
con lo stile delle altre app, e le attese ai valichi sono un bisogno
stagionale: l'abbonamento churn-a subito dopo le ferie):

| Product ID | Sblocca | Prezzo indicativo |
|---|---|---|
| — (gratis) | Gottardo completo + elenco di tutte le zone con lucchetto | — |
| `valichi.zona.alpi` | tutti i valichi della zona Alpi | Tier 3,99 € |
| `valichi.zona.balcani` | Balcani e Adriatico | Tier 3,99 € |
| `valichi.zona.est` | Europa dell'Est | Tier 3,99 € |
| `valichi.europa` | tutto, **incluse le zone future** | Tier 9,99 € |

Decisioni prese e loro perché:

- **il Gottardo è gratis e completo**: è la demo che dimostra il valore
  ("questo, ma per il TUO valico"), riusa dati già raccolti e porta in
  dote gli utenti di Gottardo Live;
- **qualsiasi acquisto rimuove la pubblicità** (banner AdMob solo nella
  versione gratuita, stesso flusso di consenso UMP/ATT del Gottardo);
- i pacchetti sono **non-consumable** con Family Sharing abilitato;
  "Tutta Europa" include le zone aggiunte dopo — promessa esplicita nelle
  pagine di supporto, prezzabile perché le zone nuove costano solo lavoro
  di adapter;
- i valichi `coming_soon` compaiono nel catalogo ma non contano nel
  pitch di vendita del pacchetto: si vende ciò che è **attivo oggi**
  (le pagine di supporto lo dicono chiaro);
- in App Store Connect: 4 prodotti non-consumable, screenshot per la
  review con il paywall visibile, e le solite pagine
  `support-valichi.html` / `privacy-valichi.html` via GitHub Pages.

`catalog.json` è pensato per essere **impacchettato nell'app** (bundle) e
riletto da remoto: l'app usa la copia remota se più recente, così un
valico nuovo o un matchName corretto arrivano senza release. I product ID
lì dentro sono la mappa zona→prodotto che il paywall legge.

## L'app iOS (progetto locale, fuori repo)

Come per Gottardo Live, il progetto Xcode **non vive in questo repo**:
sta sul Mac, in `Xcode/=NewApps/ValichiLive` (consegnato come zip il
09.08.2026). **iPhone + iPad**, iOS 17+, SwiftUI, formato progetto
Xcode 16 (cartelle sincronizzate — i file nuovi entrano nel target da
soli). Il repo resta la casa di collector, dati e pagine; l'app è solo un
client dei file pubblicati qui.

Già implementato nello scaffold:

- lista zone → scheda valico (direzioni con attesa colorata, marcatore
  `held` "fonte muta", grafico 12/24/48h con Swift Charts da
  `history.json`, salute della fonte);
- `DataStore`: catalogo dal bundle all'avvio, poi catalogo+dati remoti
  (il remoto vince: valichi nuovi senza release);
- `StoreManager` (StoreKit 2): prodotti letti dal catalogo, paywall per
  zona con pacchetto "Tutta Europa", ripristino, Family Sharing, listener
  `Transaction.updates`;
- `Products.storekit` (nel progetto) per provare gli acquisti senza App
  Store Connect: in Xcode, Scheme → Run → Options → StoreKit
  Configuration.

Per farlo girare: aprire il progetto, impostare il **Development Team**
e (se serve) il bundle ID — ora `com.bacchin.valichi`, segnaposto. Dentro
il progetto c'è una copia di `catalog.json` come fallback offline del
primo avvio: quando si tocca `valichi/catalog.json` qui nel repo va
ricopiata nel progetto (la versione remota comunque vince quando c'è
rete).

Restano da fare:

1. push: registrazione ai canali `valico-…` dei valichi seguiti
   (Back4App SDK o REST, come già fatto per `global` sul Gottardo);
2. AdMob nella versione gratuita con flusso di consenso UMP/ATT (riusare
   quello di Gottardo Live) — lo scaffold non ha pubblicità;
3. mappa d'Europa con i valichi colorati per attesa (le coordinate del
   catalogo sono indicative: rifinirle);
4. localizzazione en/it/de/fr (le stringhe dello scaffold sono in
   italiano) e icona; `icon.png` va aggiunta anche alle due pagine HTML;
5. i 4 prodotti non-consumable in App Store Connect con gli stessi ID del
   catalogo.

## Test locale

```bash
python3 valichi/collect.py --prova    # parser sulle fixture, niente rete
python3 valichi/collect.py            # giro vero (dalla sandbox riesce solo
                                      # la fonte gotthard: le altre sono
                                      # bloccate dal proxy, e latest.json
                                      # lo dichiara in "sources")
```

---

Come per il Gottardo: questo repo è l'unica copia del collector — le
modifiche a `collect.py`, `catalog.json`, al workflow e a questo README
si fanno qui.
