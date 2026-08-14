# Installazione over-the-air via GitHub Pages

Distribuzione Ad Hoc senza TestFlight: l'`.ipa` e il manifest stanno su GitHub
Pages, e l'iPhone li installa con il protocollo `itms-services://`.

**Base URL di questo repository:** `https://fbacchin.github.io/app/volcano/ota/`

---

## Prima di iniziare: due prerequisiti che bloccano tutto

### Serve un Apple Developer Program a pagamento

L'export Ad Hoc **non è possibile con un Apple ID gratuito**. Un account free
può solo installare via cavo da Xcode, con un profilo che scade dopo 7 giorni e
senza alcuna possibilità di installazione over-the-air.

La scelta del team Apple Developer è ancora aperta
(`../docs/06-decisioni.md` D-C7): finché non è fatta, questa procedura non può
partire.

### Il dispositivo va registrato prima dell'export

Ad Hoc e Development includono nel profilo l'elenco degli **UDID autorizzati**.
Un iPhone non registrato riceve il pop-up di installazione, accetta, e poi
fallisce senza dire perché — è il modo più frustrante in cui questa procedura
può rompersi.

1. Collega l'iPhone al Mac, apri Xcode → **Window → Devices and Simulators**
2. Copia l'**Identifier** (l'UDID)
3. Registralo su [developer.apple.com](https://developer.apple.com/account/resources/devices/list)
4. **Rigenera il provisioning profile** dopo aver aggiunto il dispositivo:
   un profilo generato prima non contiene il nuovo UDID

Il limite è di 100 dispositivi per tipo per anno di membership, e si azzera
solo al rinnovo.

---

## 1. Export da Xcode

1. **Product → Archive**
2. Nell'Organizer, **Distribute App**
3. Metodo: **Debugging** (Development) oppure **Release Testing** (Ad Hoc)

   ⚠️ **Il metodo deve accordarsi con `aps-environment`**, che oggi vale
   `development` (vedi `../ios/project.yml`). Quindi:

   | Metodo | `aps-environment` richiesto |
   |---|---|
   | Debugging (Development) | `development` ← **configurazione attuale** |
   | Release Testing (Ad Hoc) | `production` |

   Scegliere Ad Hoc senza prima portare l'entitlement a `production` fa
   fallire la firma con un errore sul profilo che non menziona la causa vera.
   Per installare sul proprio iPhone **Debugging va benissimo**: Ad Hoc serve
   quando i dispositivi non sono i tuoi.
4. Spunta **Include manifest for over-the-air installation**
5. Xcode chiede tre URL. Sono questi:

   | Campo | Valore |
   |---|---|
   | App URL | `https://fbacchin.github.io/app/volcano/ota/Volcano.ipa` |
   | Display Image URL | `https://fbacchin.github.io/app/volcano/ota/icon-57.png` |
   | Full Size Image URL | `https://fbacchin.github.io/app/volcano/ota/icon-512.png` |

   Le due icone sono già in questa cartella e già pubblicate.

**Oppure, meglio: salta il punto 5.** Esporta senza manifest e generalo con lo
script, che legge bundle identifier e versione **dall'`.ipa` stesso**:

```bash
./make-manifest.sh Volcano.ipa
```

Quei tre URL digitati a mano sono il punto in cui questa procedura fallisce più
spesso, e un refuso non produce nessun errore leggibile: iOS mostra soltanto
"Impossibile installare". Lo script costruisce gli URL da un'unica base e
verifica il plist con `plutil -lint` prima di scriverlo.

---

## 2. Pubblicazione

Copia `Volcano.ipa` e `manifest.plist` in `volcano/ota/`, poi:

```bash
git add volcano/ota/
git commit -m "Volcano: build OTA <versione>"
git push
```

### Il branch conta

GitHub Pages serve **un branch solo**, quasi certamente `main`. I file su un
branch di sviluppo non sono raggiungibili dagli URL sopra, e il risultato è un
404 che dal telefono sembra un problema dell'iPhone.

Verifica in **Settings → Pages** quale branch è configurato, e pubblica lì.

### Verifica prima di prendere in mano il telefono

```bash
curl -I https://fbacchin.github.io/app/volcano/ota/manifest.plist
curl -I https://fbacchin.github.io/app/volcano/ota/Volcano.ipa
```

Entrambe devono rispondere `200`. La pubblicazione di Pages richiede da pochi
secondi a un paio di minuti dopo il push.

---

## 3. Installazione sull'iPhone

Apri **con Safari**:

```
https://fbacchin.github.io/app/volcano/ota/
```

e tocca **Installa Volcano**.

### Perché una pagina e non il link diretto

Digitare `itms-services://?action=download-manifest&url=...` nella barra
indirizzi di Safari **non funziona in modo affidabile** su iOS recenti: Safari
spesso non riconosce lo schema quando viene scritto a mano, e non dà nessun
riscontro.

Il protocollo va invece attivato da un `<a href="itms-services://…">` toccato
dentro una pagina. È esattamente ciò che fa `index.html`, ed è il motivo per
cui quel file esiste invece di essere un dettaglio estetico.

### Alla prima apertura

L'app installata non parte subito: iOS chiede di autorizzare lo sviluppatore in
**Impostazioni → Generali → VPN e gestione dispositivo**. È normale per una
build che non viene dall'App Store.

---

## File grandi: quando l'`.ipa` non sta nel repository

Git rifiuta i file oltre i **100 MB**, e GitHub Pages ha un limite indicativo
di 1 GB per sito. Un `.ipa` di questa app dovrebbe restare sotto i 100 MB, ma
ogni build committata resta **per sempre nella storia del repository**, anche
dopo essere stata cancellata: dopo una decina di build il clone diventa
pesante per tutti.

**Alternativa consigliata: l'`.ipa` come asset di una GitHub Release**, e solo
il manifest su Pages. Gli asset di release arrivano a 2 GB, non entrano nella
storia di git, e hanno URL HTTPS stabili:

```
https://github.com/fbacchin/app/releases/download/volcano-v1.0/Volcano.ipa
```

**Stato reale, verificato il 14 agosto 2026.** Questa cartella è l'unica parte
del progetto rimasta su GitHub: sta in `fbacchin/app`, branch `main`, percorso
`volcano/ota/`. La branch `claude/volcano-monitoring-app-8but8p` che conteneva
`docs/`, `backend/` e `ios/` è stata cancellata, e quel codice vive ora solo in
`~/Xcode/Volcano` sul Mac.

Pages è attivo e serve la pagina:

```
https://fbacchin.github.io/app/volcano/ota/
```

Manca solo l'`.ipa`: il repository **non ha ancora nessuna release**, quindi
l'URL qui sopra è la destinazione da creare, non un link funzionante.

⚠️ **Attenzione a come si usa lo script in questo caso.** `make-manifest.sh`
usa **una sola base URL** per tutti e tre gli asset: passargli l'URL della
release sposterebbe lì anche `icon-57.png` e `icon-512.png`, che su una release
non esistono. Le due strade corrette sono: modificare a mano il solo campo
`software-package` nel manifest generato, oppure caricare anche le due icone
come asset della release.

**Per questa app, però, la release probabilmente non serve.** L'`.ipa` di
Volcano dovrebbe stare ampiamente sotto i 100 MB: metterlo direttamente in
`volcano/ota/` fa funzionare una sola base URL senza nessuna complicazione.
La release conviene solo quando le build si accumulano e la storia di git
inizia a pesare.

Questo funziona però solo con un repository **pubblico**: gli asset di release
di un repository privato richiedono autenticazione, e l'iPhone non ce l'ha.

---

## Scadenze

- Un profilo **Ad Hoc** vale un anno. Alla scadenza l'app smette di aprirsi:
  serve una nuova build, non basta reinstallare la stessa.
- Il **certificato di distribuzione** scade indipendentemente dal profilo.
- Se l'app un giorno smette di partire senza motivo apparente, la prima cosa da
  controllare è la data di scadenza del profilo.

---

## Cosa aspettarsi da questa build oggi

Poco, ed è bene saperlo prima di installarla.

Il backend non ha **nessuna fonte attiva**: gli host istituzionali sono
bloccati dalla policy di rete e nessuna licenza è stata verificata, quindi il
gate in `config.js` tiene tutte le fonti fuori dalla produzione. L'app si
collegherà a un backend vuoto e mostrerà i suoi stati vuoti — che è comunque
utile per verificare navigazione, layout, Dynamic Type, VoiceOver e traduzioni.

Il codice iOS invece ora **compila e passa i 51 test** (verificato il 14 agosto
2026 con Xcode 26.5), quindi da quel lato non ci sono ostacoli all'archivio.
Attenzione solo a non usare `swift build` per verificarlo: non funziona su
questo progetto, i comandi giusti sono in `../ios/README.md`.
