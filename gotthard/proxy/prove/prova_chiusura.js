// Prova del riconoscimento della CHIUSURA DEL TUNNEL.
//
// Il difetto che queste prove sorvegliano e' successo davvero: il 03.08.2026
// alle 22:16 il Gottardo e' rimasto chiuso per ore e l'app non se n'e'
// accorta. Non per il cursore, non per una risposta parziale: il messaggio
// arrivava e il filtro del corridoio lo scartava, perche' cercava il tunnel
// per nome e la fonte quella volta l'aveva scritto in un altro modo.
//
// I testi qui sotto sono presi dai feed veri, non inventati.

const fs = require("fs");
const path = require("path");

const tabelle = { Chiamate: [] };
class FakeObject {
  constructor(cls) { this.className = cls; this.attributes = {}; }
  set(k, v) { this.attributes[k] = v; }
  get(k) { return this.attributes[k]; }
  async save() { return this; }
}
class FakeQuery {
  constructor(cls) { this.className = cls; }
  equalTo() { return this; } greaterThanOrEqualTo() { return this; }
  lessThan() { return this; } descending() { return this; } ascending() { return this; }
  select() { return this; } limit() { return this; }
  async find() { return []; }
  async first() { return undefined; }
}
global.Parse = { Object: FakeObject, Query: FakeQuery, Cloud: { define() {}, job() {} } };
global.Parse.Object.saveAll = async () => {};
global.Parse.Object.destroyAll = async () => {};

const sorgente = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");
const richiedi = (p) => require(p.startsWith(".") ? path.join(__dirname, "..", p) : p);
const m = new Function("require", sorgente +
  "\n;return { estraiSituazioni, chiusuraDelTunnel, conEtichettaChiusura, senzaPrefissoDiStato, inVigore, conProgrammate, PUNTO_TUNNEL };")(richiedi);

const prove = [];
const ok = (nome, esito) => prove.push([nome, !!esito]);

// --- un documento come li manda la fonte, con i prefissi veri --------------
function documento(situazioni) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:dx223="http://datex2.eu/schema/2/2_0"><SOAP-ENV:Body><dx223:d2LogicalModel>` +
  situazioni.map((s) => `<dx223:situation xsi:type="dx223:Situation" id="${s.id}" version="1">` +
    `<dx223:situationRecord xsi:type="dx223:${s.tipo || "RoadOrCarriagewayOrLaneManagement"}" id="${s.id}.1.1" version="1">` +
    `<dx223:situationRecordVersionTime xsi:type="dx223:DateTime">${s.vt}</dx223:situationRecordVersionTime>` +
    `<dx223:validity xsi:type="dx223:Validity"><dx223:validityStatus>active</dx223:validityStatus>` +
    `<dx223:validityTimeSpecification xsi:type="dx223:OverallPeriod">` +
    (s.inizio ? `<dx223:overallStartTime xsi:type="dx223:DateTime">${s.inizio}</dx223:overallStartTime>` : "") +
    (s.periodo ? `<dx223:validPeriod xsi:type="dx223:Period">` +
      `<dx223:startOfPeriod xsi:type="dx223:DateTime">${s.periodo[0]}</dx223:startOfPeriod>` +
      (s.periodo[1] ? `<dx223:endOfPeriod xsi:type="dx223:DateTime">${s.periodo[1]}</dx223:endOfPeriod>` : "") +
      `</dx223:validPeriod>` : "") +
    `</dx223:validityTimeSpecification>` +
    (s.qualificatore ? `<dx223:validityExtension><elementEnumerationExtension>` +
      `<element>validityStatus</element><value>${s.qualificatore}</value>` +
      `</elementEnumerationExtension></dx223:validityExtension>` : "") +
    `</dx223:validity>` +
    `<dx223:generalPublicComment xsi:type="dx223:Comment"><dx223:comment><dx223:values>` +
    Object.entries(s.testi).map(([l, t]) =>
      `<dx223:value xsi:type="dx223:MultilingualStringValue" lang="${l}-CH">${t}</dx223:value>`).join("") +
    `</dx223:values></dx223:comment><dx223:commentType>description</dx223:commentType></dx223:generalPublicComment>` +
    (s.nota ? `<dx223:generalPublicComment xsi:type="dx223:Comment"><dx223:comment><dx223:values>` +
      `<dx223:value xsi:type="dx223:MultilingualStringValue" lang="de-CH">${s.nota}</dx223:value>` +
      `</dx223:values></dx223:comment><dx223:commentType>internalNote</dx223:commentType></dx223:generalPublicComment>` : "") +
    (s.punti || []).map((p) =>
      `<dx223:groupOfLocations><dx223:specificLocation>${p}</dx223:specificLocation></dx223:groupOfLocations>`).join("") +
    `</dx223:situationRecord></dx223:situation>`).join("") +
  `</dx223:d2LogicalModel></SOAP-ENV:Body></SOAP-ENV:Envelope>`;
}

// --- i messaggi veri ------------------------------------------------------

// Quello che ci e' sfuggito: nomina il tunnel SENZA "del".
const CHIUSURA_SENZA_DEL = {
  id: "situation.642392.1", vt: "2026-07-31T04:43:26Z", punti: ["11187"],
  inizio: "2026-08-04T00:00:00Z",
  testi: {
    it: "Approvato: A2 Chiasso &lt;-&gt; S. Gottardo Galleria Galleria San Gottardo Situazione: tunnel chiuso cantiere Durata: durante la notte probabile 10.08.2026 23:00 fino 28.08.2026 05:00",
    de: "Freigegeben: A2 Chiasso &lt;-&gt; Gotthard Tunnel Gotthard-Tunnel Sachlage: Tunnel gesperrt Baustelle",
  },
};
// La forma che gia' passava, col "del".
const CANTIERE_COL_DEL = {
  id: "situation.287191.1", vt: "2025-05-09T08:01:46Z", punti: ["11187"], tipo: "AbnormalTraffic",
  testi: { it: "Approvato: A2 Chiasso &lt;-&gt; S. Gottardo Galleria Galleria del S. Gottardo Situazione: problemi di traffico cantiere, lunghezza [km] 0.3" },
};
// Chiusura scritta coi due imbocchi invece che col nome del tunnel.
const CHIUSURA_FRA_I_PORTALI = {
  id: "situation.639408.1", vt: "2026-07-15T04:38:56Z", punti: ["10275", "10460"],
  testi: { it: "Approvato: A2 Chiasso &lt;-&gt; Luzern tra Svincolo autostradale Göschenen E Svincolo autostradale Airolo Situazione: tunnel chiuso Causa: trasporto eccezionale" },
};
// Un'altra galleria del corridoio: chiuderla NON e' chiudere il Gottardo.
const ALTRA_GALLERIA = {
  id: "situation.900001.1", vt: "2026-08-04T06:00:00Z", punti: ["27447"],
  testi: { it: "Approvato: A2 S. Gottardo -&gt; Luzern Galleria Galleria Naxberg Situazione: tunnel chiuso cantiere" },
};
// Fuori corridoio: stessa frase, tutt'altra strada.
const TUNNEL_ALTROVE = {
  id: "situation.900002.1", vt: "2026-08-04T06:00:00Z", punti: ["25954"],
  testi: { it: "Approvato: A8 Brienz &lt;-&gt; Sarnen Galleria Galleria Giswil Situazione: tunnel chiuso cantiere" },
};

(async () => {
  // --- il filtro del corridoio
  {
    const s = m.estraiSituazioni(documento([CHIUSURA_SENZA_DEL])).situazioni;
    ok("la chiusura scritta 'Galleria San Gottardo' entra nel corridoio",
      !!s["situation.642392.1"]);
    ok("  (col vecchio filtro sul solo nome sarebbe stata scartata)",
      !/galleria del/.test(CHIUSURA_SENZA_DEL.testi.it.toLowerCase()));
  }
  {
    const s = m.estraiSituazioni(documento([CANTIERE_COL_DEL])).situazioni;
    ok("la forma col 'del' continua a entrare", !!s["situation.287191.1"]);
  }
  {
    const s = m.estraiSituazioni(documento([TUNNEL_ALTROVE])).situazioni;
    ok("un tunnel chiuso sull'A8 resta fuori", !s["situation.900002.1"]);
  }
  {
    // Senza nessun nome noto nel testo: deve bastare il codice 11187.
    const soloCodice = Object.assign({}, CHIUSURA_SENZA_DEL, {
      id: "situation.900003.1",
      testi: { it: "Approvato: A2 in entrambe le direzioni Situazione: tunnel chiuso per problemi tecnici" },
    });
    const s = m.estraiSituazioni(documento([soloCodice])).situazioni;
    ok("il solo punto 11187 basta a dire che riguarda il Gottardo",
      !!s["situation.900003.1"]);
  }

  // --- riconoscimento della chiusura
  const situazione = (grezza) =>
    m.estraiSituazioni(documento([grezza])).situazioni[grezza.id];
  const chiusa = (grezza) => {
    const s = situazione(grezza);
    return s && m.chiusuraDelTunnel(s, (s.texts.it || "").toLowerCase());
  };

  ok("'tunnel chiuso' + punto del tunnel = chiusura", chiusa(CHIUSURA_SENZA_DEL) === true);
  ok("'tunnel chiuso' fra i due imbocchi = chiusura", chiusa(CHIUSURA_FRA_I_PORTALI) === true);
  ok("un cantiere nel tunnel NON e' una chiusura", chiusa(CANTIERE_COL_DEL) === false);
  ok("la Naxberg chiusa NON e' il Gottardo chiuso", chiusa(ALTRA_GALLERIA) === false);

  // --- l'etichetta
  {
    const s = situazione(CHIUSURA_SENZA_DEL);
    const testi = m.conEtichettaChiusura(s.texts);
    ok("l'italiano prende TUNNEL CHIUSO in testa", testi.it.startsWith("TUNNEL CHIUSO: "));
    ok("il tedesco prende TUNNEL GESCHLOSSEN", testi.de.startsWith("TUNNEL GESCHLOSSEN: "));
    ok("l'etichetta mangia il prefisso di stato della fonte",
      !/approvato|freigegeben/i.test(testi.it + testi.de));
    ok("  cioe' non si legge 'TUNNEL CHIUSO: Approvato: …'",
      testi.it.startsWith("TUNNEL CHIUSO: A2 Chiasso"));
    ok("il resto del messaggio non si tocca", testi.it.includes("tunnel chiuso cantiere"));
  }
  ok("il francese ha la sua etichetta",
    m.conEtichettaChiusura({ fr: "Libéré: A2 tunnel fermé" }).fr === "TUNNEL FERMÉ: A2 tunnel fermé");
  ok("l'inglese ha la sua etichetta",
    m.conEtichettaChiusura({ en: "Approved: A2 tunnel closed" }).en === "TUNNEL CLOSED: A2 tunnel closed");
  ok("una lingua che non conosciamo passa intatta",
    m.conEtichettaChiusura({ rm: "qualcosa" }).rm === "qualcosa");

  // --- il senso di marcia nell'etichetta -----------------------------------
  //
  // Una galleria non si chiude per forza nei due versi: su 17 chiusure
  // d'archivio una, situation.639533, e' a senso unico. Scriverci sopra
  // "TUNNEL CHIUSO" farebbe credere che sia chiusa del tutto.
  {
    const t = { it: "Approvato: A2 x", de: "Freigegeben: A2 x",
                fr: "Libéré: A2 x", en: "Approved: A2 x" };
    const sud = m.conEtichettaChiusura(t, "south");
    const nord = m.conEtichettaChiusura(t, "north");
    const due = m.conEtichettaChiusura(t, null);
    ok("chiusa verso sud, in italiano", sud.it === "TUNNEL CHIUSO VERSO SUD: A2 x");
    ok("  in tedesco", sud.de === "TUNNEL GESCHLOSSEN RICHTUNG SÜDEN: A2 x");
    ok("  in francese", sud.fr === "TUNNEL FERMÉ VERS LE SUD: A2 x");
    ok("  in inglese", sud.en === "TUNNEL CLOSED SOUTHBOUND: A2 x");
    ok("chiusa verso nord, in italiano", nord.it === "TUNNEL CHIUSO VERSO NORD: A2 x");
    ok("  in tedesco", nord.de === "TUNNEL GESCHLOSSEN RICHTUNG NORDEN: A2 x");
    ok("direzione non dichiarata: etichetta secca", due.it === "TUNNEL CHIUSO: A2 x");
    ok("  e 'both' si comporta uguale",
      m.conEtichettaChiusura(t, "both").it === "TUNNEL CHIUSO: A2 x");
  }

  // --- in vigore adesso, oppure programmata --------------------------------
  //
  // Il caso vero: `situation.642392.1`, cantiere notturno del 10-28 agosto,
  // dichiarato dalla fonte con overallStartTime al 05.08, un validPeriod dal
  // 10 al 28 e il qualificatore `duringTheNight`. Il 04.08 il tunnel era
  // aperto: scrivere TUNNEL CHIUSO sarebbe stato un falso allarme.
  const ADESSO = Date.parse("2026-08-04T16:00:00Z");
  const conValidita = (extra) => situazione(Object.assign(
    {}, CHIUSURA_SENZA_DEL, { id: "situation.900010.1" }, extra));

  ok("il cantiere notturno programmato NON e' in vigore adesso",
    m.inVigore(conValidita({
      inizio: "2026-08-05T13:00:00Z",
      periodo: ["2026-08-10T21:00:00Z", "2026-08-28T03:00:00Z"],
      qualificatore: "duringTheNight",
    }), ADESSO) === false);
  ok("  basta il qualificatore orario a fermare l'etichetta",
    m.inVigore(conValidita({ qualificatore: "duringTheNight" }), ADESSO) === false);
  ok("  e anche 'duringTheDayTime'",
    m.inVigore(conValidita({ qualificatore: "duringTheDayTime" }), ADESSO) === false);
  ok("una chiusura 'fino a nuovo avviso' e' in vigore",
    m.inVigore(conValidita({
      inizio: "2026-08-03T22:16:00Z", qualificatore: "untilFurtherNotice",
    }), ADESSO) === true);
  ok("  ed e' come era scritta quella del 03.08.2026",
    true);
  // La forma vera di una chiusura non programmata, presa da
  // situation.545066.1.1.1: il periodo ha l'inizio e NON ha la fine.
  ok("periodo aperto, senza fine: in vigore",
    m.inVigore(conValidita({
      inizio: "2026-08-03T22:16:00Z",
      periodo: ["2026-08-03T22:15:00Z", null],
      qualificatore: "untilFurtherNotice",
    }), ADESSO) === true);
  ok("  ed e' cosi' che la fonte scrive 'fino a nuovo avviso'", true);
  ok("periodo aperto ma che comincia domani: no",
    m.inVigore(conValidita({
      periodo: ["2026-08-05T22:15:00Z", null],
    }), ADESSO) === false);

  ok("un messaggio che comincia domani non e' in vigore",
    m.inVigore(conValidita({ inizio: "2026-08-05T13:00:00Z" }), ADESSO) === false);
  ok("dentro il periodo dichiarato: in vigore",
    m.inVigore(conValidita({
      inizio: "2026-08-01T00:00:00Z",
      periodo: ["2026-08-04T06:00:00Z", "2026-08-04T22:00:00Z"],
    }), ADESSO) === true);
  ok("fuori dal periodo dichiarato: no",
    m.inVigore(conValidita({
      inizio: "2026-08-01T00:00:00Z",
      periodo: ["2026-08-01T06:00:00Z", "2026-08-02T22:00:00Z"],
    }), ADESSO) === false);
  ok("senza date ne' qualificatori vale adesso (il caso normale)",
    m.inVigore({}, ADESSO) === true);
  ok("  e vale anche per il magazzino salvato prima del 04.08.2026",
    m.inVigore({ id: "x", texts: {} }, ADESSO) === true);

  // --- il prefisso di stato
  ok("'Approvato:' via", m.senzaPrefissoDiStato("Approvato: A2 x") === "A2 x");
  ok("'Revocato:' via", m.senzaPrefissoDiStato("Revocato: A2 x") === "A2 x");
  ok("un prefisso non nostro resta",
    m.senzaPrefissoDiStato("Situazione: A2 x") === "Situazione: A2 x");
  ok("i due punti interni non si toccano",
    m.senzaPrefissoDiStato("Approvato: A2 Causa: incidente") === "A2 Causa: incidente");
  ok("un testo senza due punti resta intero",
    m.senzaPrefissoDiStato("A2 tunnel chiuso") === "A2 tunnel chiuso");

  // --- l'etichetta si applica una volta sola, anche rileggendo lo stesso
  //     messaggio venti volte (la finestra larga lo fa di continuo)
  {
    const s = situazione(CHIUSURA_SENZA_DEL);
    let testi = s.texts;
    for (let i = 0; i < 5; i++) {
      const passo = m.conEtichettaChiusura(s.texts);   // sempre dal grezzo
      testi = passo;
    }
    ok("rileggere lo stesso messaggio non impila le etichette",
      (testi.it.match(/TUNNEL CHIUSO/g) || []).length === 1);
    ok("  e il magazzino tiene il testo GREZZO, senza etichetta",
      !/TUNNEL CHIUSO/.test(s.texts.it));
  }

  // --- la chiusura notturna ricorrente (07.09.2026) -------------------------
  //
  // Il 07.09.2026 alle 20:00 il tunnel e' stato chiuso per cantiere, ogni
  // notte fino al 25 settembre, e l'app ha detto "libera" tutta la sera. Il
  // messaggio c'era nel feed dal 17 agosto: non passava dall'incrementale
  // (versionTime fermo) e comunque `duringTheNight` lo faceva scartare.
  // I valori sono quelli veri di situation.645705.1.1.1.
  const notturno = {
    id: "situation.645705.1",
    versionTime: "2026-08-17T12:41:48Z",
    inizioValidita: "2026-08-17T12:38:00Z",
    periodi: [{ da: "2026-09-07T18:00:00Z", a: "2026-09-25T03:00:00Z" }],
    qualificatori: ["duringTheNight"],
    texts: { it: "Approvato: A2 Chiasso <-> S. Gottardo Galleria Galleria San Gottardo Situazione: tunnel chiuso cantiere" },
    punti: [m.PUNTO_TUNNEL],
    revocata: false,
  };
  const alle = (g, h, min) => Date.UTC(2026, 8, g, h, min || 0);

  ok("la chiusura notturna vale alle 18:00Z, cioe' le 20:00 in Svizzera",
     m.inVigore(notturno, alle(7, 18)) === true);
  ok("  mezz'ora prima ancora no", m.inVigore(notturno, alle(7, 17, 30)) === false);
  ok("  a mezzanotte passata si', la finestra scavalca il giorno",
     m.inVigore(notturno, alle(8, 1)) === true);
  ok("  alle 03:00Z, cioe' le 05:00, ha finito",
     m.inVigore(notturno, alle(8, 3)) === false);
  ok("  a mezzogiorno no: e' notturna, non continua",
     m.inVigore(notturno, alle(8, 10)) === false);
  ok("  e si ripete la settimana dopo", m.inVigore(notturno, alle(14, 22)) === true);
  ok("  finito l'inviluppo non vale piu'", m.inVigore(notturno, alle(26, 21)) === false);

  ok("severalTimes resta scartato: non da' nessuna finestra da cui dedurre",
     m.inVigore(Object.assign({}, notturno, { qualificatori: ["severalTimes"] }),
                alle(7, 19)) === false);
  ok("ricorrente senza periodo: la finestra non c'e', e non si inventa",
     m.inVigore(Object.assign({}, notturno, { periodi: [] }), alle(7, 19)) === false);
  ok("senza qualificatore lo stesso periodo e' continuo: vale a mezzogiorno",
     m.inVigore(Object.assign({}, notturno, { qualificatori: [] }),
                alle(8, 10)) === true);

  // --- i giorni della settimana dalla nota interna (ADEV-698, 19.09.2026) ---
  //
  // Il 18 e il 19.09.2026, venerdi' e sabato sera, l'app dava il tunnel
  // chiuso ed era aperto. Il record vero porta la nota interna «Mo-FR,
  // jeweils in den Nächten von 20:00 bis 05:00 Uhr», e il calendario
  // ufficiale dice «4 notti, da lunedì sera a venerdì mattina».
  // Settembre 2026: il 14 e il 21 sono lunedi', il 18 venerdi'. Ora estiva:
  // le 18:00Z sono le 20:00 in Svizzera.
  // La nota VERA, come sta nel magazzino (letta il 20.09.2026): il numero
  // della perturbazione sulla prima riga, i giorni sulla seconda.
  const NOTA_VERA = "ID116422\nMo-FR, jeweils in den Nächten von 20:00 bis 05:00 Uhr.";
  const conNota = (nota) => Object.assign({}, notturno, { notaInterna: nota });
  const feriale = conNota(NOTA_VERA);
  ok("Mo-Fr: lunedi' alle 20:00 chiuso", m.inVigore(feriale, alle(14, 18)) === true);
  ok("  lunedi' a mezzanotte e mezza (ancora lunedi' in UTC) chiuso",
     m.inVigore(feriale, alle(14, 22, 30)) === true);
  ok("  giovedi' alle 23:00 chiuso", m.inVigore(feriale, alle(17, 21)) === true);
  ok("  venerdi' alle 04:00, fine della notte di giovedi', chiuso",
     m.inVigore(feriale, alle(18, 2)) === true);
  ok("  venerdi' alle 21:56 APERTO (il caso del 18.09)",
     m.inVigore(feriale, alle(18, 19, 56)) === false);
  ok("  sabato alle 00:30, ancora la notte di venerdi', APERTO",
     m.inVigore(feriale, alle(18, 22, 30)) === false);
  ok("  sabato alle 20:05 APERTO (il caso del 19.09)",
     m.inVigore(feriale, alle(19, 18, 5)) === false);
  ok("  domenica alle 23:00 APERTO", m.inVigore(feriale, alle(20, 21)) === false);
  ok("  lunedi' 21 alle 20:00 di nuovo chiuso", m.inVigore(feriale, alle(21, 18)) === true);
  ok("  lunedi' 21 alle 19:30 non ancora", m.inVigore(feriale, alle(21, 17, 30)) === false);
  ok("  martedi' 22 alle 03:00 chiuso", m.inVigore(feriale, alle(22, 1)) === true);
  ok("  a mezzogiorno di mercoledi' no: la nota non allarga la fascia",
     m.inVigore(feriale, alle(16, 10)) === false);

  const daDomenica = conNota("So - Fr, jeweils nachts");
  ok("So - Fr: domenica sera chiuso", m.inVigore(daDomenica, alle(20, 21)) === true);
  ok("  venerdi' sera aperto", m.inVigore(daDomenica, alle(18, 21)) === false);
  const coppie = conNota("So/Mo Do/Fr");
  ok("So/Mo Do/Fr: la notte di domenica chiusa", m.inVigore(coppie, alle(20, 21)) === true);
  ok("  quella di giovedi' chiusa", m.inVigore(coppie, alle(17, 21)) === true);
  ok("  quella di lunedi' aperta", m.inVigore(coppie, alle(21, 21)) === false);

  // Tutto quello che non sappiamo leggere non restringe niente: sabato sera
  // resta chiuso, come prima di ADEV-698. Nel dubbio, chiuso.
  ok("nota assente: come prima, chiuso anche il sabato",
     m.inVigore(notturno, alle(19, 21)) === true);
  ok("  «Mo Do» non e' una forma che leggiamo: chiuso",
     m.inVigore(conNota("Mo Do"), alle(19, 21)) === true);
  ok("  «Mo-» nemmeno: chiuso", m.inVigore(conNota("Mo-"), alle(19, 21)) === true);
  ok("  una coppia che non e' una notte («Do/Sa»): chiuso",
     m.inVigore(conNota("Do/Sa"), alle(19, 21)) === true);
  ok("  una riga che non comincia coi giorni: chiuso",
     m.inVigore(conNota("Umleitung via Pass, Mo-Fr"), alle(19, 21)) === true);
  ok("  i giorni valgono da qualunque riga: «ID116422» davanti non disturba",
     m.inVigore(conNota("ID116422\nMo-FR, nachts"), alle(19, 21)) === false);
  ok("  e nemmeno due righe di premessa",
     m.inVigore(conNota("ID116422\nBaustelle\nSo/Mo Do/Fr"), alle(21, 21)) === false);
  ok("  «Montag» non e' «Mo»: chiuso",
     m.inVigore(conNota("Montag bis Freitag"), alle(19, 21)) === true);
  ok("la nota non tocca un periodo continuo: senza qualificatore vale a mezzogiorno",
     m.inVigore(Object.assign({}, feriale, { qualificatori: [] }), alle(19, 10)) === true);

  {
    const s = situazione(Object.assign({}, CHIUSURA_SENZA_DEL, {
      id: "situation.900020.1", nota: NOTA_VERA,
      periodo: ["2026-09-07T18:00:00Z", "2026-09-25T03:00:00Z"],
      qualificatore: "duringTheNight",
    }));
    ok("il parser tiene la nota interna a parte", s.notaInterna === NOTA_VERA);
    ok("  e la nota non finisce nel testo pubblico",
       !Object.values(s.texts).some((t) => t.includes("jeweils")));
    ok("  e dal documento vero il sabato sera e' aperto",
       m.inVigore(s, alle(19, 18, 5)) === false);
    ok("  e il lunedi' sera chiuso", m.inVigore(s, alle(21, 18, 5)) === true);
  }
  ok("il catalogo dei programmati il sabato sera non la mette nella vista",
     Object.keys(m.conProgrammate({}, [Object.assign({}, feriale, { programmata: true })],
                                  alle(19, 18, 5))).length === 0);

  // --- il catalogo dei programmati entra nella vista solo quando vale ------
  const programmata = Object.assign({}, notturno, { programmata: true });
  ok("dentro la finestra la programmata entra nella vista",
     Object.keys(m.conProgrammate({}, [programmata], alle(7, 21))).length === 1);
  ok("  fuori dalla finestra no: annunciata non vuol dire in corso",
     Object.keys(m.conProgrammate({}, [programmata], alle(8, 10))).length === 0);
  ok("  e se la stessa situazione e' gia' nel magazzino vince l'incrementale",
     m.conProgrammate({ "situation.645705.1": { id: "situation.645705.1", fresca: true } },
                      [programmata], alle(7, 21))["situation.645705.1"].fresca === true);

  let n = 0;
  console.log("=== chiusura del tunnel ===");
  for (const [nome, esito] of prove) { console.log(esito ? "  OK  " : "  NO  ", nome); if (esito) n++; }
  console.log(`\n${n}/${prove.length}`);
  process.exit(n === prove.length ? 0 : 1);
})();
