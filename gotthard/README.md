# Gottardo Live — Collector

Campiona ogni ~5 minuti lo stato delle code al tunnel del San Gottardo
dall'API ufficiale di opentransportdata.swiss (DATEX II, dati USTRA/VMZ-CH),
mantiene lo storico per il grafico dell'app iOS **Gottardo Live** e invia le
notifiche push automatiche quando si forma una coda.

## Componenti

- `collect.py` — interroga l'API Traffic Situations, estrae code/attese ai
  portali (filtro corridoio, direzioni, anti-zombie), aggiorna i file dati e
  decide le notifiche
- `.github/workflows/gotthard-collect.yml` (alla radice del repo) — il
  workflow che lo esegue in loop
- `privacy-gotthard.html` / `support-gotthard.html` — pagine pubbliche per
  l'App Store (via GitHub Pages)

## Cosa produce (in `data/`)

| File | Contenuto | Chi lo usa |
|---|---|---|
| `history.json` | Finestra mobile di 48h di campioni (attesa in minuti per direzione) | Il grafico 6/12/24h dell'app — **unica fonte**, i campioni locali sono stati aboliti (01.08.2026) |
| `latest.json` | Ultimo stato completo + eventi in tutte le lingue del feed | Fallback dell'app quando la chiamata diretta fallisce, e **seme** della tenuta anti-lampeggio all'avvio a freddo |
| `alerts.json` | Archivio degli avvisi ufficiali per `id`, con `firstSeen`/`lastSeen`/`revokedAt` — finestra 48h dall'ultimo avvistamento | Lista avvisi dell'app (ripiego quando il feed tace) e storico che la fonte non conserva |
| `push-state.json` | Fase corrente per direzione (clear/queued/heavy) e timestamp ultimo invio | Il collector stesso, per non ri-notificare |

Gli URL letti dall'app sono cablati in `APIConfig.swift`
(`raw.githubusercontent.com/fbacchin/app/main/gotthard/data/…`).

## Tenuta anti-lampeggio (01.08.2026)

Il feed **non tiene pubblicati** i messaggi per tutta la loro durata: li
revoca e li riemette a impulsi, e a volte svuota il corridoio per interi
minuti. Preso alla lettera, il risultato è una coda che sparisce e riappare.

La scoperta che ha risolto il problema: **la fonte annuncia la fine** con un
messaggio prefissato `Revocato:` / `Aufgehoben:` / `Révoqué:` — e il codice lo
scartava con un `continue`. Lo zero non nasceva mai da un'informazione:
nasceva dall'**assenza**, indistinguibile da un buco del feed.

`hold_through_gaps()` applica quindi queste regole al campione:

| Situazione | Esito |
|---|---|
| Coda letta dal feed | osservazione diretta, si registra |
| Coda assente, **revoca** vista | zero subito: la fonte ha dichiarato la fine |
| Coda assente, nessuna revoca, entro `HOLD_WINDOW` (60 min) | si **mantiene** l'ultimo valore, campione marcato `southHeld`/`northHeld` |
| Coda assente oltre i 60 minuti | zero |

Dettagli che contano:

- la finestra decorre dall'ultima osservazione **diretta**: i valori mantenuti
  non riarmano il timer, ed è a questo che servono i marcatori `Held`
  (correggendo i dati a mano **non vanno aggiunti**)
- serve una coda vista in **due campioni consecutivi** prima di mantenere:
  altrimenti un'eco — il messaggio riemesso una volta sola a coda già chiusa —
  diventerebbe un plateau di un'ora
- `HOLD_WINDOW` è 60 minuti perché il 1° agosto un silenzio reale è durato 59;
  è separato da `CLEAR_CONFIRM` (20 min), che governa solo la notifica di fine
- `update_alerts()` fa lo stesso lavoro per gli avvisi: un avviso che sparisce
  per un giro non viene perso, `revokedAt` registra la chiusura dichiarata, e
  se il messaggio viene ripubblicato la revoca decade

⚠️ Una protezione contro il lampeggio va applicata a **tutti** i consumatori
del dato. A luglio era stata messa solo sulle notifiche e il problema è
riemerso su storico, schede e lista avvisi.

## Notifiche push automatiche

Inviate via Back4App (REST con Master Key, canale `global`) quando l'attesa
di una direzione attraversa le soglie:

- **≥ 20 min** → 🚦 coda formata
- **≥ 60 min** → ⚠️ escalation "coda pesante" (una sola volta per episodio)
- **< 10 min per almeno 20 min** → ✅ coda finita

Cooldown di 45 minuti per direzione; l'isteresi tra le soglie (20/10) evita
il ping-pong ai bordi. La fine coda è **confermata nel tempo**
(`CLEAR_CONFIRM`, 20 min): all'area di dosaggio di Airolo il messaggio viene
revocato e riemesso a impulsi, e un singolo buco nel feed non va scambiato
per "traffico scorrevole" (altrimenti parte un falso "coda finita" mentre la
coda è ancora presente). Quando il messaggio ufficiale riporta solo i km senza
tempo d'attesa, l'attesa è stimata a ~10 min/km (dosaggio del Gottardo).

## Workflow GitHub Actions

I cron di GitHub sono "best effort" e quelli frequenti vengono ritardati
anche di ore: il `*/10` originale campionava ogni 1-3,5h. La strategia
attuale:

- cron `*/30` che avvia **run lunghi ~3 ore** (34 campioni × 5 minuti),
  con gruppo di concorrenza che incatena i run in coda
- a ogni campione: `git fetch` + `reset --hard origin/main`, poi commit e
  push dei tre file dati (**mai `pull --rebase`**: un merge conflittuale
  aveva committato marcatori `<<<<<<<` dentro `history.json` corrompendolo)
- l'ultimo statement del loop è un `if/then`, non `[ ] && sleep`
  (altrimenti l'ultima iterazione esce con codice 1 e GitHub manda mail di
  failure spurie)
- secrets e env sono fissati all'avvio del job: se cambi i Secrets, cancella
  il run in corso e rilancialo
- **anche il YAML del workflow è congelato all'avvio**: `collect.py` si
  aggiorna a ogni giro grazie al `fetch`+`reset`, la definizione del job no.
  Una modifica al workflow (per esempio aggiungere un file al `git add`)
  entra in vigore **solo al run successivo**
- **il gruppo di concorrenza tiene in coda un solo run**: quando ne arriva uno
  nuovo, quello che era in attesa viene annullato. Aspettare non fa avanzare
  la fila, la rimpiazza — se serve che una modifica al workflow entri subito,
  l'unica via è cancellare il run in corso
- il `git add` elenca i file **esplicitamente**: un file dati nuovo va
  aggiunto lì, altrimenti viene creato a ogni giro e perso al `reset`
  successivo senza mai arrivare su GitHub (successo con `latest.json` a
  luglio e con `alerts.json` il 1° agosto)

**Secrets richiesti** (Settings → Secrets and variables → Actions):
`OTD_API_KEY` (chiave opentransportdata.swiss), `B4A_APP_ID` e
`B4A_MASTER_KEY` (Back4App — la Master Key vive **solo** qui, mai nell'app
iOS).

## Insidie del feed (già gestite in `collect.py`)

- Il parsing di km/minuti/direzioni è affidabile **solo sul testo italiano**;
  `latest.json` conserva comunque i testi in tutte le lingue per la UI
- Record "zombie" mai chiusi → finestra di freschezza di **6 ore** (quella
  iniziale di 45 min scartava i messaggi di code stabili, il cui
  `versionTime` resta fermo a lungo, producendo falsi zeri nel grafico)
- La risposta è **sempre gzip**, anche senza `Accept-Encoding`
- Quota API condivisa: **5 chiamate/min per tutti i device + collector**
  (piano `astra_situations_plan`, quota totale 260 000). Il campione ogni 5
  minuti pesa 0,2 chiamate/min. Attenzione: la pagina pubblica *Limits and
  costs* indica 50/min per la famiglia FEDRO TDP, ma vale il piano associato
  alla credenziale — verificare su *my apps → Credential*
- Nei giorni di punta il server risponde **503** a raffiche: `fetch_feed()`
  riprova 2× a 25 s sugli errori 5xx, perché ogni giro perso è un buco di
  10-20 minuti nello storico
- Una risposta **200 valida può non contenere alcun messaggio**: il 1° agosto
  alle 11:38 il record più recente del corridoio aveva 79 ore mentre un minuto
  prima c'erano code da 7 km. Non è un errore da intercettare — è il caso che
  la tenuta anti-lampeggio esiste per gestire

## Test locale

```bash
OTD_API_KEY=... python3 collect.py                 # solo dati, niente push
OTD_API_KEY=... B4A_APP_ID=... B4A_MASTER_KEY=... python3 collect.py
```

Scrive in `data/` accanto allo script.

---

Questo repo è l'**unica copia** del collector: le modifiche a `collect.py`,
al workflow e a questo README si fanno direttamente qui (via API GitHub o
interfaccia web). Non esiste più una copia locale nel progetto Xcode.
