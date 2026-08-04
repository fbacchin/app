/**
 * IL RIPASSO — la rilettura a finestra larga.
 *
 * ============================================================ perche' esiste
 *
 * Perche' UNA RISPOSTA SOLA NON BASTA. Misurato il 04.08.2026: due richieste
 * identiche, stessa chiave, stessa finestra di sei ore, a un minuto di
 * distanza, hanno reso 13 situazioni e 24. La seconda conteneva le quattro
 * del Gottardo che l'app aspettava da tre ore; la prima nessuna.
 *
 * Non e' un difetto dell'estrattore — dato lo stesso documento le riconosce
 * tutte e quattro, provato — e non e' il ritardo con cui la fonte pubblica,
 * che il cursore sul versionTime gia' assorbe (vedi prossimoCursore in
 * main.js). E' che la singola risposta e' parziale, e l'unica difesa e'
 * chiedere piu' volte la stessa finestra.
 *
 * Rileggere non costa niente: R3 sostituisce per id e solo in avanti, quindi
 * un messaggio gia' visto viene riconosciuto e scartato, e una revoca gia'
 * registrata resta registrata. Perdere un messaggio invece costa una mezza
 * giornata di schede sbagliate — successo il 04.08.2026, dalle 08:16 alle
 * 12:01, con l'app che dava 1 km mentre ce n'erano 4 a nord e 3 a sud.
 *
 * =========================================================== perche' e' qui
 *
 * Le sue regole stanno in un file suo, anche se il ripasso gira dentro il
 * giro dei 4 minuti, perche' e' una cosa diversa: il giro insegue il
 * presente, il ripasso rimedia al passato. Tenerle separate vuol dire poter
 * cambiare il ritmo o la profondita' del secondo — o spegnerlo, mettendo
 * PERIODO a Infinity — senza mettere le mani nel primo, che e' quello da cui
 * dipendono le schede.
 *
 * ============================================================= come si usa
 *
 * Il ripasso NON ha una sua schedulazione: gira **dentro il lavoro
 * `aggiorna`**, che parte ogni 4 minuti. A ogni giro `sincronizza` chiede a
 * questo file se e' ora (`tocca`), e in caso allarga la finestra: uno su
 * cinque, quindi, e' un ripasso.
 *
 * Cosi' perche' su Back4App si puo' schedulare un lavoro solo. Le regole
 * restano pero' qui, in un file loro: cambiare il ritmo o la profondita' non
 * vuol dire mettere le mani nel giro da cui dipendono le schede.
 *
 * Resta anche il lavoro `ripassa`, per i lanci a mano: accetta il parametro
 * `ore` (default 6, tetto 24) e serve quando si vuole una rilettura profonda
 * subito, senza aspettare il turno.
 *
 * ============================================== i due numeri, e cosa fanno
 *
 *   PERIODO   ogni quanto tocca. Governa il ripescaggio delle REVOCHE, che
 *             la piattaforma tiene disponibili 60 minuti e poi butta (R4).
 *             Venti minuti danno a ogni revoca tre occasioni dentro la sua
 *             ora di vita. Un ripasso raro, per quanto profondo, non ne
 *             salverebbe nessuna: provato il 04.08.2026 su
 *             situation.643096, la cui revoca aveva cinque ore e non
 *             esisteva piu' in nessuna finestra.
 *
 *   FINESTRA  quanto indietro chiede. Governa il ripescaggio delle
 *             SITUAZIONI perse, che invece restano pubblicate finche' sono
 *             vive, quindi si possono ripescare anche ore dopo.
 *
 * Costo misurato: una finestra di sei ore pesa fra i 20 e i 300 KB, contro i
 * ~10 KB di un giro normale. A un ripasso ogni venti minuti e' irrilevante, e
 * il numero di chiamate alla fonte non cambia di una — e' lo stesso giro.
 *
 * Fa esattamente quello che fa il giro normale — magazzino, tabelle,
 * schermata pronta — solo con la finestra allargata. Se la fonte non
 * risponde, esce senza salvare e senza spostare il cursore, come sempre.
 */
const PERIODO_MS = 20 * 60 * 1000;
const FINESTRA_MS = 6 * 3600 * 1000;
const ORE_PREDEFINITE = 6;
const ORE_MASSIME = 24;   // oltre, si chiede l'archivio invece del recente

/**
 * E' ora di ripassare? `ultimoRipasso` e' quello che risulta nello stato
 * salvato; una data illeggibile o assente vale come "mai", quindi si ripassa
 * subito — al primo avvio, e dopo qualunque pasticcio sullo stato.
 */
function tocca(ultimoRipasso, adesso) {
  const t = Date.parse(ultimoRipasso || "");
  return isNaN(t) || adesso - t >= PERIODO_MS;
}

/** Registra il lavoro per i lanci a mano. Chiamato in fondo a main.js. */
function registraLavoro(giroCompleto) {
  Parse.Cloud.job("ripassa", async (request) => {
    const chieste = Number((request.params && request.params.ore) || ORE_PREDEFINITE);
    const ore = Math.min(
      Math.max(Number.isFinite(chieste) && chieste > 0 ? chieste : ORE_PREDEFINITE, 1),
      ORE_MASSIME);

    request.message("ripasso a mano: chiedo le ultime " + ore + " ore");
    const payload = await giroCompleto(null, {
      finestraMinima: ore * 3600 * 1000,
      etichettaModo: "ripasso",
    });
    request.message("ripasso finito: record " + payload.recordsSeen +
      ", eventi " + payload.events.length +
      ", storico " + (payload.history || []).length);
  });
}

module.exports = { PERIODO_MS, FINESTRA_MS, tocca, registraLavoro };
