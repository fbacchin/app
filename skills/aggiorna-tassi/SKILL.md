---
name: aggiorna-tassi
description: >
  Aggiorna automaticamente tutti i file CSV dei tassi di interesse nella cartella Libor
  con i dati più recenti da global-rates.com, e ne pubblica la versione per le app nella
  repo GitHub fbacchin/app. Usa questa skill ogni volta che l'utente scrive
  "aggiorna i tassi", "update rates", "aggiorna i file CSV", "aggiorna libor",
  "puoi aggiornare i tassi" o qualsiasi variante simile — anche in inglese o misto.
  La skill gestisce 7 file (ESTER, EURIBOR, LIBOR GBP, LIBOR USD SOFR, LIBOR USD,
  SARON CHF, TONAR JPY) con due formati diversi, scarica i dati via browser Chrome,
  aggiunge solo le date mancanti senza toccare i dati esistenti, poi pubblica le
  stesse date nuove sui CSV su GitHub Pages.
---

# Aggiornamento Tassi di Interesse

## Scopo

Due passi, in quest'ordine:

1. **Aggiornare la cartella Libor su Google Drive** con i dati più recenti da
   global-rates.com. È la fonte di verità: il sito mostra sempre gli ultimi ~5
   giorni lavorativi, aggiungere solo le date non ancora presenti.
2. **Pubblicare su GitHub** le stesse date nuove, sui CSV che le app leggono.
   Ci pensa uno script: aggiunge solo le date mancanti, non rigenera i file.

## Limiti di accesso

Questa skill deve toccare **soltanto** due percorsi:

- la cartella **Libor** su Google Drive (il workspace, fonte dei dati);
- il clone della repo **`fbacchin/app`**, e al suo interno solo `Euribor/`.

Nessun altro file o repo, né sul Mac né su GitHub. Se un percorso non è
raggiungibile, **fermarsi e dirlo** invece di cercare alternative.

---

## Passo 1 — Aggiornare i file su Google Drive

### File e fonti

| File | URL da aprire in Chrome | Tasso |
|------|------------------------|-------|
| `ESTER.csv` | https://www.global-rates.com/en/interest-rates/ester/ | ESTER ON |
| `EURIBOR.csv` | https://www.global-rates.com/en/interest-rates/euribor/ | Euribor 1w, 1m, 3m, 6m, 12m |
| `LIBOR GBP.csv` | https://www.global-rates.com/en/interest-rates/sonia/ | SONIA ON |
| `LIBOR USD SOFR.csv` | https://www.global-rates.com/en/interest-rates/sofr/ | SOFR ON |
| `LIBOR USD.csv` | https://www.global-rates.com/en/interest-rates/cme-term-sofr/ | CME Term SOFR 1M, 3M, 6M, 12M |
| `SARON CHF.csv` | https://www.global-rates.com/en/interest-rates/saron/ | SARON ON |
| `TONAR JPY.csv` | https://www.global-rates.com/en/interest-rates/tonar/ | TONAR ON |

La cartella Libor è il workspace selezionato (la copia locale del Drive:
`~/Library/CloudStorage/GoogleDrive-*/Il mio Drive/*/Libor`).

**Su Drive i nomi mantengono gli spazi e i formati restano quelli storici**: non
rinominare né riformattare nulla qui. La conversione avviene solo al passo 2.

### Formato A — `ESTER.csv` e `EURIBOR.csv` (date come colonne)

La prima riga contiene le date in `dd/mm/yyyy`, le righe successive il nome del
tenore e i valori:

```
,01/01/2026,02/01/2026,...
ON,2.45670,2.46000,...
```

Per EURIBOR i tenori sono: `1w`, `1m`, `3m`, `6m`, `12m`

Come aggiornare:
- leggere l'ultima data presente (ultima colonna della riga 1);
- aggiungere le date mancanti **in fondo** a ogni riga (append a destra);
- formato data `dd/mm/yyyy`, valore decimale senza `%` (es. `2.45670`).

### Formato B — tutti gli altri file (date come righe)

Header fisso (9 colonne):

```
"Date","Week day","ON","1W","1M","2M","3M","6M","12M"
```

Colonne popolate per ciascun file:

| File | ON | 1W | 1M | 2M | 3M | 6M | 12M |
|------|----|----|----|----|----|----|-----|
| `LIBOR GBP.csv` | ✓ SONIA | — | — | — | — | — | — |
| `LIBOR USD SOFR.csv` | ✓ SOFR | — | — | — | — | — | — |
| `LIBOR USD.csv` | — | — | ✓ CME 1M | — | ✓ CME 3M | ✓ CME 6M | ✓ CME 12M |
| `SARON CHF.csv` | ✓ SARON | — | — | — | — | — | — |
| `TONAR JPY.csv` | ✓ TONAR | — | — | — | — | — | — |

Regole:
- i campi non usati restano `""` (stringa vuota quotata);
- date più recenti **in cima**, ordine decrescente: riordinare dopo ogni inserimento;
- data `dd.mm.yyyy` con il punto (es. `06.04.2026`);
- valore decimale senza `%` e **con il punto come separatore** (es. `3.66000`);
  mai la virgola, che manderebbe in errore chi legge il file;
- `Week day`: nome inglese completo e coerente con la data (es. `Monday`).

### Procedura

Per ogni file:

1. leggere il file e identificare l'ultima data presente;
2. aprire la pagina con Claude in Chrome (il sito non è accessibile via WebFetch);
3. leggere solo le date più recenti di quella già presente;
4. aggiungere i nuovi dati nel formato corretto del file;
5. per il Formato B, riordinare per data decrescente e verificare che ogni riga
   abbia esattamente 9 campi.

Scrivere i file con Python via Bash, per evitare errori di formattazione.

---

## Passo 2 — Pubblicare su GitHub

Le app (Euribor X, Libor) non leggono da Drive: leggono i CSV pubblicati su
GitHub Pages da `fbacchin/app`, in `Euribor/`. Lì tutti e sette i file sono nel
Formato B, con i nomi senza spazi.

**Non convertire i file a mano.** Lo fa uno script, che prende dai file su
Drive **solo le date non ancora pubblicate**, le converte e le inserisce. Le
righe già presenti su GitHub non vengono mai riscritte: lo storico lì è già
bonificato e non va rigenerato dal Drive, che contiene ancora giorni della
settimana incoerenti e valori con la virgola.

```bash
cd /Users/fabrizio/Xcode/=NewApps/app
git pull --quiet
python3 Euribor/sync-from-drive.py
```

Se non ci sono date nuove non tocca niente e lo dice. Con `--check` mostra cosa
aggiungerebbe senza scrivere.

> `--rebuild` rigenera l'intero storico da Drive: **non usarlo di routine**.
> Serve solo se hai corretto un valore storico su Drive. Riscrive tutto e
> nel farlo elimina le righe con date duplicate: controlla il git diff.

Poi, **solo se ha segnalato dei file aggiornati**:

```bash
cd /Users/fabrizio/Xcode/=NewApps/app
git add Euribor
git commit -m "Aggiorna i tassi al $(date +%d.%m.%Y)"
git push origin main
```

Corrispondenza dei nomi (la gestisce lo script, è qui solo come riferimento):

| Su Drive | Su GitHub |
|---|---|
| `ESTER.csv` (Formato A) | `ESTER.csv` (Formato B) |
| `EURIBOR.csv` (Formato A) | `EURIBOR.csv` (Formato B) |
| `LIBOR GBP.csv` | `LIBOR-GBP.csv` |
| `LIBOR USD SOFR.csv` | `LIBOR-USD-SOFR.csv` |
| `LIBOR USD.csv` | `LIBOR-USD.csv` |
| `SARON CHF.csv` | `SARON-CHF.csv` |
| `TONAR JPY.csv` | `TONAR-JPY.csv` |

Dopo il push, GitHub Pages impiega circa un minuto a pubblicare. Verifica
facoltativa:

```bash
curl -s https://fbacchin.github.io/app/Euribor/EURIBOR.csv | head -2
```

---

## Note importanti

- **Non modificare mai i dati già presenti nei file.**
- **Non modificare a mano i file dentro `Euribor/`**: le date nuove le aggiunge
  lo script. Per correggere un valore storico, correggerlo su Drive e poi usare
  `--rebuild`, perché la modalità normale guarda solo le date mancanti.
- **CME Term SOFR (`LIBOR USD.csv`)**: il sito mostra solo gli ultimi 5 giorni.
  Se una data non appare, saltarla — non è disponibile.
- **SONIA e altri overnight escono con un giorno di ritardo**: è normale che
  l'ultima data non coincida tra i file.
- **SARON**: i valori negativi sono corretti, non sono errori.
- **Giorni festivi**: se il sito non mostra un giorno, saltarlo.
- **Verifica finale**: stampare un riepilogo con, per ogni file, l'ultima data
  inserita, e dire se il push su GitHub è andato a buon fine o no. Se il push
  fallisce, dirlo esplicitamente: i dati su Drive sono aggiornati ma le app
  continuerebbero a vedere quelli vecchi.
