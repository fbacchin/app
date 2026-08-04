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
| `main.js` | tutto: trasporto, magazzino, schermo pronto, tabelle, la funzione `gotthard` e il lavoro `aggiorna` (ogni 4 minuti) |
| `ripasso.js` | il lavoro `ripassa`, rilettura a finestra larga, con la sua schedulazione |
| `prove/` | 211 prove, da lanciare prima di ogni distribuzione |

## La chiave

`main.js` legge la chiave della fonte dalla **variabile d'ambiente `OTD_KEY`**,
impostata nelle Server Settings dell'app su Back4App. Nel sorgente non c'è, e
non deve tornarci: fino al 04.08.2026 c'era un segnaposto sostituito da un
passo di build, che produceva un secondo file — quello vero, con la chiave
dentro — impossibile da versionare.

Se la variabile manca, il giro fallisce subito con un messaggio esplicito e
senza chiamare la fonte: senza quella guardia si prenderebbe un 401 e si
andrebbe a cercare una chiave scaduta invece di una variabile assente.

## Distribuire

Si carica `main.js` e `ripasso.js` così come sono, nessuna trasformazione.
Dalla dashboard di Back4App (Cloud Code → Files), oppure via API.

**Prima di distribuire, lanciare le prove.** Vogliono solo `node` e `python3`:

```bash
cd gotthard/proxy
for f in prove/*.js; do node "$f" | tail -1; done
```

Attese: `102/102`, `45/45`, `37/37`, `27/27`. Il collector ha le sue, accanto
a lui: `python3 ../prova_collector.py` → `21/21`.

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

## Dove sta il resto

- il collector che campiona lo storico: `gotthard/collect.py`, accanto;
- i dati pubblicati: `gotthard/data/`;
- le pagine di supporto e privacy dell'app: `gotthard/*.html`.
