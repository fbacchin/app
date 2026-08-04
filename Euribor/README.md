# Euribor X — Dati

Serie storiche pubbliche dei principali tassi di riferimento, in CSV.
Alimentano l'app iOS **Euribor X** (e **Euribor X Light**) e sostituiscono i
file precedentemente ospitati su Google Drive.

## File e URL

Serviti da GitHub Pages, quindi scaricabili direttamente:

| File | Tasso | Colonne valorizzate |
|---|---|---|
| [`ESTER.csv`](https://fbacchin.github.io/app/Euribor/ESTER.csv) | €STR — Euro Short-Term Rate (BCE) | ON |
| [`EURIBOR.csv`](https://fbacchin.github.io/app/Euribor/EURIBOR.csv) | Euribor (EMMI) | 1W, 1M, 3M, 6M, 12M |
| [`LIBOR-USD-SOFR.csv`](https://fbacchin.github.io/app/Euribor/LIBOR-USD-SOFR.csv) | SOFR / USD | ON, 1M, 3M, 6M, 12M |
| [`LIBOR-USD.csv`](https://fbacchin.github.io/app/Euribor/LIBOR-USD.csv) | LIBOR USD (storico) | varie |
| [`LIBOR-GBP.csv`](https://fbacchin.github.io/app/Euribor/LIBOR-GBP.csv) | LIBOR GBP / SONIA | ON, 3M |
| [`SARON-CHF.csv`](https://fbacchin.github.io/app/Euribor/SARON-CHF.csv) | SARON (CHF) | ON |
| [`TONAR-JPY.csv`](https://fbacchin.github.io/app/Euribor/TONAR-JPY.csv) | TONAR (JPY) | ON |

Schema dell'URL:

```
https://fbacchin.github.io/app/Euribor/<NOME FILE>
```

L'app usa solo `EURIBOR.csv` ed `ESTER.csv`. I nomi non contengono spazi, così
gli URL non hanno bisogno di percent-encoding: attenzione che sul Drive
sorgente gli stessi file si chiamano ancora `LIBOR USD SOFR.csv` eccetera.

## Formato

Tutti i file condividono lo stesso schema:

```csv
"Date","Week day","ON","1W","1M","2M","3M","6M","12M"
"14.07.2026","Tuesday","","2.153","2.220","","2.452","2.654","2.825"
```

- **Date** — `GG.MM.AAAA`.
- **Week day** — giorno della settimana in inglese, ricalcolato dalla data.
- **ON … 12M** — il tasso per quel tenor, in percentuale, con il punto come
  separatore decimale. Stringa vuota se il tasso non esiste o non è stato
  pubblicato quel giorno.
- Ogni campo è racchiuso tra virgolette; una riga per data,
  **dalla più recente alla più vecchia**.
- I fixing escono solo nei giorni lavorativi, e non tutti gli indici escono lo
  stesso giorno: l'€STR viene pubblicato il giorno lavorativo successivo,
  quindi può essere indietro di una data rispetto all'Euribor.

## Aggiornamento

La skill `aggiorna-tassi` scarica i dati da global-rates.com, aggiorna i CSV
nella cartella Libor su Drive, e pubblica qui le sole date mancanti con
`pubblica-github-api.py` (che sta nella cartella Libor e scrive via API, senza
bisogno di un clone). L'automazione via GitHub Action è tracciata in ADEV-197
(il collector di `gotthard/` in questa stessa repo è il modello di riferimento).

### Correggere un valore storico già pubblicato

**Il flusso normale non lo fa, e non lo dice.** Sia `pubblica-github-api.py`
sia `sync-from-drive.py` aggiungono soltanto le date *mancanti* e non
riscrivono mai una riga già presente. È voluto: lo storico qui è stato
bonificato (vedi sotto), mentre su Drive restano giorni della settimana
incoerenti e valori con la virgola, quindi rigenerare da Drive rovinerebbe il
lavoro fatto.

Conseguenza da conoscere: se correggi un valore su Drive e lanci
l'aggiornamento, **non succede niente** — quella data c'è già, quindi viene
saltata. Nessun errore, nessun avviso, e il valore sbagliato resta pubblicato.

L'unico strumento che riscrive è `sync-from-drive.py --rebuild`, che rigenera
l'intero storico da Drive. Vuole il clone locale di questa repo:

```bash
cd <clone di fbacchin/app>
git sparse-checkout list                     # se Euribor/ è escluso, rimettilo
python3 Euribor/sync-from-drive.py --check   # cosa farebbe, senza scrivere
python3 Euribor/sync-from-drive.py --rebuild
git diff -- Euribor                          # GUARDALO PRIMA DI COMMITTARE
```

`--rebuild` riscrive tutto ed elimina le righe con date duplicate: il `git
diff` è l'unica rete. Serve per riparare, mai per l'uso quotidiano.

Questa nota esiste perché fino al 04.08.2026 la cosa era scritta nella skill,
e togliendo da lì la via del clone è rimasta senza casa: lo strumento c'era
ancora, la conoscenza di quando serve no.

## Note sulla qualità dei dati

Bonifiche già applicate ai file ereditati dallo storico:

- **Virgole decimali** → punto: 14 valori del 16–17.11.2023 in
  `LIBOR-USD-SOFR.csv`, `LIBOR-USD.csv` e `LIBOR-GBP.csv` usavano la virgola
  (`5,44701`), che rompe i parser numerici.
- **Giorni della settimana** ricalcolati dalla data su tutti i file: nei file
  LIBOR la colonna `Week day` era spesso incoerente (lunghe sequenze marcate
  `Fri`) e mescolava forme estese e abbreviate.

Restano note:

- Il campo `Week day` è ridondante (deducibile da `Date`): non farci
  affidamento.
- Alcune **date compaiono due volte** (1 in `LIBOR-GBP.csv`, `LIBOR-USD.csv` e
  `LIBOR-USD-SOFR.csv`, 2 in `SARON-CHF.csv`). Chi legge dovrebbe tenere la
  prima occorrenza o deduplicare.

## Licenza / uso

Dati di pubblico dominio pubblicati da BCE, EMMI e dalle rispettive
amministrazioni degli indici, raccolti qui per comodità. Nessuna garanzia di
accuratezza o continuità: non usare per scopi di regolamento o contrattuali.
