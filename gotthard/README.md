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
| `history.json` | Finestra mobile di 48h di campioni (attesa in minuti per direzione) | Il grafico 6/12/24h dell'app, mergiato con lo storico locale |
| `latest.json` | Ultimo stato completo + eventi in tutte le lingue del feed | Fallback dell'app quando la chiamata diretta fallisce (quota/errori) |
| `push-state.json` | Fase corrente per direzione (clear/queued/heavy) e timestamp ultimo invio | Il collector stesso, per non ri-notificare |

Gli URL letti dall'app sono cablati in `APIConfig.swift`
(`raw.githubusercontent.com/fbacchin/app/main/gotthard/data/…`).

## Notifiche push automatiche

Inviate via Back4App (REST con Master Key, canale `global`) quando l'attesa
di una direzione attraversa le soglie:

- **≥ 20 min** → 🚦 coda formata
- **≥ 60 min** → ⚠️ escalation "coda pesante" (una sola volta per episodio)
- **< 10 min** → ✅ coda finita

Cooldown di 45 minuti per direzione; l'isteresi tra le soglie (20/10) evita
il ping-pong ai bordi. Quando il messaggio ufficiale riporta solo i km senza
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
- Quota API condivisa (5 chiamate/min per tutti i device + collector): il
  campione ogni 5 minuti pesa una sola chiamata

## Test locale

```bash
OTD_API_KEY=... python3 collect.py                 # solo dati, niente push
OTD_API_KEY=... B4A_APP_ID=... B4A_MASTER_KEY=... python3 collect.py
```

Scrive in `data/` accanto allo script.

---

La copia di riferimento del sorgente vive nel progetto Xcode
(`Gotthard/Collector/`): le modifiche si fanno lì e si ricopiano qui.
