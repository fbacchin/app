# Proxy Gottardo — Cloud Code

Il server che sta fra la fonte DATEX di opentransportdata.swiss e l'app
**Gottardo Live**. Gira come Cloud Code su Back4App (app `Gotthard`).

L'app non tocca più la fonte: chiede a questo proxy lo schermo già pronto —
le due schede, la lista avvisi, la serie del grafico. Le ragioni, coi numeri
misurati, stanno nel commento in testa a `main.js`; in breve: la chiamata
diretta scaricava 21,6 MB di XML da analizzare sul telefono a ogni giro, la
chiave API viaggiava dentro il binario, e la quota di 5 chiamate al minuto è
condivisa fra tutti i client.

## I file

| file | cosa fa |
|---|---|
| `main.js` | tutto: trasporto, magazzino, schermo pronto, tabelle, la funzione `gotthard`, le correzioni a mano e il lavoro `aggiorna` (ogni 4 minuti) |
| `ripasso.js` | le regole della rilettura a finestra larga: ogni quanto tocca e quanto indietro chiedere. Gira **dentro** `aggiorna` — su Back4App si schedula un lavoro solo — e resta il lavoro `ripassa` per i lanci a mano |
| `prove/` | 268 prove, da lanciare prima di ogni distribuzione |

## Le chiavi

Nessuna delle due sta nel sorgente, e non devono tornarci. Si impostano nelle
**Server Settings** dell'app su Back4App, in Environment Variables.

| variabile | a cosa serve | senza |
|---|---|---|
| `OTD_KEY` | leggere la fonte DATEX | il giro fallisce subito, senza chiamare la fonte |
| `GH_TOKEN` | leggere e correggere `history.json` sul repo (`Contents: read and write` su `fbacchin/app`) | il quadro GitHub di Gottardo Dati dice che la variabile manca |

In tutti e due i casi la guardia c'è apposta: senza, si prenderebbe un 401 o un
404 e si andrebbe a cercare una chiave scaduta o un permesso sbagliato invece
di una variabile assente. Fino al 04.08.2026 la chiave della fonte era un
segnaposto sostituito da un passo di build, che produceva un secondo file —
quello vero, con la chiave dentro — impossibile da versionare.

## Le correzioni a mano (app Gottardo Dati)

Tre funzioni, tutte con lo stesso codice di conferma (`CODICE_MANUALE`), tutte
per la stessa ragione: le tabelle hanno le scritture chiuse alla master key e i
segreti stanno sul server, quindi il client può fare solo queste cose, su
questi campi.

| funzione | cosa cambia |
|---|---|
| `revoca` | mette o toglie la revoca su un avviso, e lo toglie dal magazzino |
| `correggiStorico` | corregge o cancella un campione della tabella `Storico` |
| `storicoGitHub` | legge `history.json` dal repo, e ne corregge o cancella un campione con un commit |

Due dettagli che sembrano eccessivi e non lo sono:

- dopo ogni correzione si butta la risposta già pronta (`builtAt`), altrimenti
  per un minuto l'app continua a servire il numero vecchio e sembra che la
  scrittura non sia andata;
- `history.json` si riscrive con `comeIlCollector()` e non con
  `JSON.stringify`. Il collector usa `json.dumps(indent=1)`, e Python scrive i
  float tondi come `2.0` dove JavaScript scriverebbe `2`: riserializzare col
  JSON di serie cambierebbe ogni riga di chilometri del file — cinquecento
  righe di diff per correggere un campione, e i chilometri diventati interi per
  sempre. Se un giorno il collector cambiasse forma al file, la scrittura si
  ferma con un messaggio esplicito invece di riformattare tutto.

## Distribuire

Si carica `main.js` e `ripasso.js` così come sono, nessuna trasformazione.
Dalla dashboard di Back4App (Cloud Code → Files), oppure via API.

**Prima di distribuire, lanciare le prove.** Vogliono solo `node` e `python3`:

```bash
cd gotthard/proxy
for f in prove/*.js; do node "$f" | tail -1; done
```

Attese: `108/108`, `51/51`, `45/45`, `37/37`, `27/27`. Il collector ha le sue,
accanto a lui: `python3 ../prova_collector.py` → `21/21`.

## Cosa sorvegliano le prove

Non sono prove di forma: ognuna sta lì per un guasto successo davvero, e il
commento in testa dice quale.

- **`prova_trasporto.js`** — errori e ritentativi. La domanda che ogni prova
  pone è sempre la stessa: dopo questo errore, il cursore di lettura è rimasto
  dov'era? Più le regole del cursore e della finestra.
- **`prova_direzione.js`** — direzione e portale letti dai campi che la fonte
  dichiara (`alertCDirectionCoded`, `specificLocation`) invece che dedotti dal
  testo. Girano sul feed vero d'archivio, `feed.campione.xml.gz`, 1037
  situazioni.
- **`prova_chiusura.js`** — chiusura del tunnel: riconoscerla, distinguerla da
  un cantiere programmato, etichettarla nelle quattro lingue e col senso di
  marcia.
- **`prova_tabelle.js`** — le tabelle leggibili (`Attuale`, `Avvisi`,
  `Storico`) e lo schermo pronto.
- **`prova_correzioni.js`** — le correzioni a mano dei due storici. La prova
  che conta è l'ultima: `history.json` vero, riscritto senza toccarlo, deve
  tornare identico byte per byte — se non lo è, un giorno un commit di
  correzione riformatterebbe l'intero file.

## Tre cose sulla fonte che è costato caro imparare

Sono nei commenti del codice, ma vale la pena averle qui perché spiegano
scelte che altrimenti sembrano eccessive.

1. **Un messaggio diventa leggibile parecchi minuti dopo l'orario che porta
   scritto.** Misurato il 04.08.2026: alle 10:45 il record più recente
   disponibile portava le 10:09, alle 10:57 portava le 10:41. Per questo il
   cursore avanza sul `versionTime` ricevuto e non sull'orologio: chiedendo
   "cosa è cambiato negli ultimi 5 minuti" la risposta vuota è corretta, ed è
   la domanda a essere sbagliata.

2. **Una risposta sola non basta mai.** Due richieste identiche, stessa
   chiave, stessa finestra di sei ore, a un minuto di distanza: 13 situazioni
   e 24. La seconda conteneva le quattro del Gottardo che l'app aspettava da
   tre ore. È il motivo del ripasso.

3. **L'assenza non è un caso.** Una coda vive finché la fonte non la revoca.
   Le revoche arrivano davvero — il 04.08 alle 20:35 ne è stata documentata
   una da capo a fondo, ricevuta 17 minuti dopo — e costruire sull'assenza
   significa far sparire code vive al primo buco nel feed.

4. **Una revoca vive 60 minuti, poi non esiste più.** È R4: la piattaforma
   tiene disponibile un messaggio revocato per un'ora (è la stessa costante
   `MEMORIA_REVOCHE_MS`). Passata quella, nessuna finestra per quanto larga la
   riporta indietro — provato il 04.08 alle 20:49 su `situation.643096`, la
   cui revoca era di quasi cinque ore prima: un ripasso di sei ore ha risposto
   con cinque record e nessuno era quello.

   Da qui una distinzione che vale per il ripasso, e che è facile sbagliare:

   | | serve a ripescare | quel che conta |
   |---|---|---|
   | profondità della finestra | **situazioni** perse, che restano pubblicate finché sono vive | ore |
   | frequenza del ripasso | **revoche** perse, che scadono dopo un'ora | meno di un'ora |

   Perdere una revoca costa caro: l'unica rete rimasta è la potatura a 13 ore,
   e nel frattempo l'app mostra una coda che non c'è. Il 03.08 ne sono state
   perse tre di fila e una ha lasciato in vita una coda fantasma di 2 km per
   quasi undici ore.

## Dove sta il resto

- il collector che campiona lo storico: `gotthard/collect.py`, accanto;
- i dati pubblicati: `gotthard/data/`;
- le pagine di supporto e privacy dell'app: `gotthard/*.html`.
