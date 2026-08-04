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
 * Sta in un file suo, e non dentro il giro dei 4 minuti, perche' e' una cosa
 * diversa: il giro pianificato insegue il presente, il ripasso rimedia al
 * passato. Tenerli separati vuol dire poter cambiare il ritmo del secondo —
 * o spegnerlo — senza toccare il primo, che e' quello da cui dipendono le
 * schede.
 *
 * ============================================================= come si usa
 *
 * E' un lavoro pianificato a se': `ripassa`, da schedulare nel cruscotto di
 * Back4App con il ritmo che si decide. Accetta un parametro:
 *
 *     ore    quanto indietro chiedere (default 6, tetto 24 come il resto)
 *
 * I due numeri fanno due mestieri diversi:
 *   - ogni quanto gira  = per quanto tempo un messaggio perso resta perso;
 *   - quante ore chiede = da quanto lungo un fermo si riesce a rientrare.
 *
 * Costo: una finestra di sei ore pesa ~300 KB contro i ~10 KB di un giro
 * normale, ed e' una chiamata sola in piu' ogni volta che gira.
 *
 * Fa esattamente quello che fa il giro pianificato — magazzino, tabelle,
 * schermata pronta — solo con la finestra allargata. Se la fonte non
 * risponde, esce senza salvare e senza spostare il cursore, come sempre.
 */
module.exports = function (giroCompleto) {
  const ORE_PREDEFINITE = 6;
  const ORE_MASSIME = 24;   // oltre, si chiede l'archivio invece del recente

  Parse.Cloud.job("ripassa", async (request) => {
    const chieste = Number((request.params && request.params.ore) || ORE_PREDEFINITE);
    const ore = Math.min(
      Math.max(Number.isFinite(chieste) && chieste > 0 ? chieste : ORE_PREDEFINITE, 1),
      ORE_MASSIME);

    request.message("ripasso: chiedo le ultime " + ore + " ore");
    const payload = await giroCompleto(null, {
      finestraMinima: ore * 3600 * 1000,
      etichettaModo: "ripasso",
    });
    request.message("ripasso finito: record " + payload.recordsSeen +
      ", eventi " + payload.events.length +
      ", storico " + (payload.history || []).length);
  });
};
