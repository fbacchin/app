// Prova della gestione errori e della politica di ritentativi.
//
// Il trasporto non si puo' collaudare sul feed vero: la fonte non risponde
// 429 su richiesta, e aspettare che sbagli per vedere se reagiamo bene e'
// il contrario di un collaudo. Qui la rete e' finta e sa sbagliare in tutti
// i modi previsti dalla specifica, uno alla volta.
//
// La domanda che ogni prova pone e' sempre la stessa: dopo questo errore,
// il cursore di lettura e' rimasto dov'era?

const fs = require("fs");
const path = require("path");

const tabelle = { Chiamate: [] };
class FakeObject {
  constructor(cls) { this.className = cls; this.attributes = {}; }
  set(k, v) { this.attributes[k] = v; }
  get(k) { return this.attributes[k]; }
  async save() { tabelle[this.className].push(this); return this; }
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

// --- rete finta -------------------------------------------------------
// `copione` e' la lista di risposte, una per tentativo. Ogni chiamata
// registra gli header ricevuti, cosi' si puo' controllare che il cursore
// non cambi fra un tentativo e l'altro.
let copione = [];
let chiamate = [];
global.fetch = async (url, opzioni) => {
  chiamate.push({
    ifModifiedSince: opzioni.headers["If-Modified-Since"] || null,
    soapAction: opzioni.headers["SOAPAction"] || null,
  });
  const r = copione[Math.min(chiamate.length - 1, copione.length - 1)];
  if (r.rete) {
    const e = new Error(r.rete === "timeout" ? "aborted" : r.rete);
    e.name = r.rete === "timeout" ? "AbortError" : "TypeError";
    throw e;
  }
  const corpo = Buffer.from(r.corpo || "", "utf8");
  return {
    status: r.status,
    ok: r.status >= 200 && r.status < 300,
    async arrayBuffer() { return corpo; },
  };
};

// La chiave arriva dall'ambiente (Back4App la mette nelle Server Settings).
// Qui ne basta una finta: la rete e' finta a sua volta, e queste prove
// guardano il trasporto — ritentativi, cursore, fault — non l'autenticazione.
process.env.OTD_KEY = "chiave-finta-per-le-prove";

const sorgente = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");
// `require` come lo vede il Cloud Code: i percorsi relativi partono da
// cloud/, non da qui, altrimenti il require di ripasso.js non si risolve.
const richiedi = (p) => require(p.startsWith(".") ? require("path").join(__dirname, "..", p) : p);
const m = new Function("require", sorgente +
  "\n;return { fetchFeed, CLASSE, classificaHttp, leggiFault, estraiSituazioni, piuVecchio, stradaDi, sullaAutostrada, prossimoCursore, inizioFinestra };")(richiedi);

// --- risposte tipo ----------------------------------------------------
// PREFISSO VERO, preso dalla risposta reale del 03.08.2026: "SOAP-ENV:".
// Il trattino non e' un dettaglio: \w non lo comprende, e una prova scritta
// col comodo "soap:" lascia passare un controllo che in produzione rifiuta
// ogni risposta buona. E' successo davvero, alle 00:53.
const BUSTA_OK = `<?xml version="1.0" encoding="UTF-8"?>\n<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:dx223="http://datex2.eu/schema/2/2_0"><SOAP-ENV:Body><dx223:d2LogicalModel></dx223:d2LogicalModel></SOAP-ENV:Body></SOAP-ENV:Envelope>`;
const BUSTA_ALTRO_PREFISSO = `<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body/></soap:Envelope>`;
const fault = (codice, stringa) => `<?xml version="1.0" encoding="UTF-8"?>\n<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body><SOAP-ENV:Fault><faultcode>${codice}</faultcode><faultstring>${stringa}</faultstring></SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>`;

const prove = [];
const ok = (nome, esito) => prove.push([nome, !!esito]);

const CURSORE = new Date("2026-08-03T00:00:00Z");

async function giro(script) {
  copione = script; chiamate = []; tabelle.Chiamate = [];
  try {
    const { xml, diario } = await m.fetchFeed(CURSORE);
    return { ok: true, xml, diario, chiamate };
  } catch (e) {
    return { ok: false, classe: e.classe, messaggio: e.message, diario: e.diario, chiamate };
  }
}

(async () => {
  // --- classificazione pura
  ok("400 = configurazione", m.classificaHttp(400) === m.CLASSE.CONFIGURAZIONE);
  ok("401 = configurazione", m.classificaHttp(401) === m.CLASSE.CONFIGURAZIONE);
  ok("403 = configurazione", m.classificaHttp(403) === m.CLASSE.CONFIGURAZIONE);
  ok("404 = endpoint", m.classificaHttp(404) === m.CLASSE.ENDPOINT);
  ok("405 = endpoint", m.classificaHttp(405) === m.CLASSE.ENDPOINT);
  ok("429 = throttling", m.classificaHttp(429) === m.CLASSE.THROTTLING);
  for (const s of [500, 502, 503, 504]) ok(`${s} = server`, m.classificaHttp(s) === m.CLASSE.SERVER);
  ok("200 = ok", m.classificaHttp(200) === m.CLASSE.OK);

  // --- fault SOAP, le cinque categorie della specifica
  ok("fault header mancante → fermo",
    m.leggiFault(fault("soap:Client", "Missing required header SOAPAction")).classe === m.CLASSE.FAULT_FERMO);
  ok("fault autorizzazione → fermo",
    m.leggiFault(fault("soap:Client", "Unauthorized: invalid subscription key")).classe === m.CLASSE.FAULT_FERMO);
  ok("fault richiesta malformata → fermo",
    m.leggiFault(fault("soap:Client", "Malformed request body")).classe === m.CLASSE.FAULT_FERMO);
  ok("fault temporaneo → ritentabile",
    m.leggiFault(fault("soap:Server", "Service temporarily unavailable")).classe === m.CLASSE.FAULT_TRANSITORIO);
  ok("fault sconosciuto → ritentabile",
    m.leggiFault(fault("soap:Server", "qualcosa di mai visto")).classe === m.CLASSE.FAULT_TRANSITORIO);
  ok("una risposta buona non e' un fault", m.leggiFault(BUSTA_OK) === null);
  ok("la parola 'fault' dentro un avviso non e' un fault",
    m.leggiFault(BUSTA_OK.replace("<d2LogicalModel>", "<d2LogicalModel>" + "x".repeat(9000) + "Fault ")) === null);

  // --- il prefisso col trattino: il difetto del 03.08.2026
  {
    const r = await giro([{ status: 200, corpo: BUSTA_OK }]);
    ok("una busta SOAP-ENV: (prefisso col TRATTINO) e' accettata", r.ok && r.chiamate.length === 1);
  }
  {
    const r = await giro([{ status: 200, corpo: BUSTA_ALTRO_PREFISSO }]);
    ok("e anche una soap: (prefisso semplice)", r.ok);
  }
  ok("un fault con prefisso SOAP-ENV: viene riconosciuto",
    m.leggiFault(fault("SOAP-ENV:Client", "Validation constraint violation")) !== null);
  ok("...e classificato richiesta malformata",
    m.leggiFault(fault("SOAP-ENV:Client", "Validation constraint violation")).classe === m.CLASSE.FAULT_FERMO);

  // --- NON si ritenta su errori di configurazione
  for (const s of [400, 401, 403, 404, 405]) {
    const r = await giro([{ status: s }]);
    ok(`HTTP ${s}: un solo tentativo, niente insistenza`, !r.ok && r.chiamate.length === 1);
  }

  // --- SI ritenta su errori transitori, fino a 3 volte oltre il primo
  let r = await giro([{ status: 500 }]);
  ok("HTTP 500: 1 tentativo + 3 ritentativi = 4", !r.ok && r.chiamate.length === 4);
  ok("HTTP 500: classificato server", r.classe === m.CLASSE.SERVER);

  r = await giro([{ status: 503 }, { status: 503 }, { status: 200, corpo: BUSTA_OK }]);
  ok("503 poi 200: riesce al terzo colpo", r.ok && r.chiamate.length === 3);

  r = await giro([{ status: 429 }, { status: 200, corpo: BUSTA_OK }]);
  ok("429 poi 200: riesce", r.ok && r.chiamate.length === 2);

  r = await giro([{ rete: "timeout" }, { status: 200, corpo: BUSTA_OK }]);
  ok("timeout poi 200: riesce", r.ok);
  r = await giro([{ rete: "ECONNRESET" }, { status: 200, corpo: BUSTA_OK }]);
  ok("connessione interrotta poi 200: riesce", r.ok);

  // --- il fault fermo non si ritenta, quello transitorio si'
  r = await giro([{ status: 200, corpo: fault("soap:Client", "Unauthorized") }]);
  ok("fault di autorizzazione: un solo tentativo", !r.ok && r.chiamate.length === 1);
  r = await giro([{ status: 200, corpo: fault("soap:Server", "temporarily unavailable") }]);
  ok("fault temporaneo: ritenta fino a 4", !r.ok && r.chiamate.length === 4);

  // --- XML non conforme: UN solo ritentativo, poi si molla
  r = await giro([{ status: 200, corpo: "<html>pagina di errore del gateway</html>" }]);
  ok("risposta non SOAP: un solo ritentativo (2 chiamate)", !r.ok && r.chiamate.length === 2);
  ok("risposta non SOAP: classificata xml", r.classe === m.CLASSE.XML);
  r = await giro([{ status: 200, corpo: "<html>errore</html>" }, { status: 200, corpo: BUSTA_OK }]);
  ok("non SOAP poi SOAP: il ritentativo la salva", r.ok);

  // --- IL CURSORE: identico in tutti i tentativi dello stesso giro
  r = await giro([{ status: 500 }, { status: 503 }, { rete: "timeout" }, { status: 200, corpo: BUSTA_OK }]);
  const cursori = new Set(r.chiamate.map((c) => c.ifModifiedSince));
  ok("il cursore resta lo stesso per tutti i tentativi", cursori.size === 1);
  ok("il cursore e' in formato RFC 1123 GMT",
    /^\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test([...cursori][0]));
  ok("la SOAPAction c'e' a ogni tentativo", r.chiamate.every((c) => !!c.soapAction));

  // --- il diario registra quello che serve a capire cosa e' successo
  r = await giro([{ status: 502 }, { status: 200, corpo: BUSTA_OK }]);
  ok("il diario conta i tentativi", r.diario.tentativi === 2);
  ok("il diario dice che c'era If-Modified-Since", r.diario.conIfModifiedSince === true);
  ok("il diario registra l'esito SOAP", r.diario.esitoSoap === "ok");
  ok("il diario registra l'esito XML", r.diario.esitoXml === "ok");
  r = await giro([{ status: 401 }]);
  ok("su errore il diario porta la classe", r.diario.classe === m.CLASSE.CONFIGURAZIONE);
  ok("su errore il diario porta lo stato HTTP", r.diario.httpStatus === 401);

  // --- deduplicazione per situationRecordCreationTime
  const doppione = (creation, km) => `<dx223:situation id="situation.1.1">
    <dx223:situationRecord id="situation.1.1.1.1" xsi:type="dx223:AbnormalTraffic">
      <dx223:situationRecordCreationTime>${creation}</dx223:situationRecordCreationTime>
      <dx223:situationRecordVersionTime>2026-08-02T10:00:00Z</dx223:situationRecordVersionTime>
      <dx223:generalPublicComment><dx223:comment><dx223:values><dx223:value lang="it-CH">Approvato: A2 Luzern -&gt; S. Gottardo Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] ${km}</dx223:value></dx223:values></dx223:comment></dx223:generalPublicComment>
    </dx223:situationRecord>
    <dx223:situationRecord id="situation.1.1.2.1" xsi:type="dx223:RoadOrCarriagewayOrLaneManagement">
      <dx223:situationRecordVersionTime>2026-08-02T10:00:00Z</dx223:situationRecordVersionTime>
      <dx223:generalPublicComment><dx223:comment><dx223:values><dx223:value lang="en-EN">lane closed</dx223:value></dx223:values></dx223:comment></dx223:generalPublicComment>
    </dx223:situationRecord>
  </dx223:situation>`;
  // stesso id due volte nella stessa risposta, il piu' recente per secondo
  const doppio = m.estraiSituazioni(
    doppione("2026-08-02T09:00:00.000Z", "2.0") + doppione("2026-08-02T09:05:00.000Z", "9.0"));
  ok("lo stesso id due volte da' UNA situazione", Object.keys(doppio.situazioni).length === 1);
  ok("vince il record con creationTime piu' recente",
    (doppio.situazioni["situation.1.1"].texts.it || "").includes("9.0"));
  // e vince anche se arriva prima nel documento
  const doppioInverso = m.estraiSituazioni(
    doppione("2026-08-02T09:05:00.000Z", "9.0") + doppione("2026-08-02T09:00:00.000Z", "2.0"));
  ok("vince il piu' recente anche se compare per primo",
    (doppioInverso.situazioni["situation.1.1"].texts.it || "").includes("9.0"));
  ok("creationTime viene estratto", !!doppio.situazioni["situation.1.1"].creationTime);
  // --- chi e' piu' recente: il versionTime, NON il creationTime ---
  //
  // Sui dati veri il creationTime resta fermo per tutta la vita del record
  // (542842: creato 08.05.2025, aggiornato il 09.05); e' il versionTime che
  // avanza a ogni mutazione. Usare il creationTime per ordinare ha respinto
  // un aggiornamento vero il 03.08.2026: coda da 8 a 9 km, messaggio
  // arrivato, scartato come doppione arretrato.
  ok("piuVecchio ordina sul versionTime",
    m.piuVecchio({ creationTime: "2026-08-03T05:35:00Z", versionTime: "2026-08-03T10:17:00Z" },
                 { creationTime: "2026-08-03T05:35:00Z", versionTime: "2026-08-03T12:40:00Z" }) === true);
  ok("  un aggiornamento con creationTime PIU' VECCHIO passa lo stesso",
    m.piuVecchio({ creationTime: "2026-08-03T05:35:00Z", versionTime: "2026-08-03T12:40:00Z" },
                 { creationTime: "2026-08-03T10:17:00Z", versionTime: "2026-08-03T10:17:00Z" }) === false);
  ok("  (era esattamente il caso che il codice vecchio respingeva)", true);
  ok("a parita' di versionTime decide il creationTime",
    m.piuVecchio({ creationTime: "2026-08-03T05:00:00Z", versionTime: "2026-08-03T10:00:00Z" },
                 { creationTime: "2026-08-03T06:00:00Z", versionTime: "2026-08-03T10:00:00Z" }) === true);
  ok("a parita' piena vince chi arriva dopo",
    m.piuVecchio({ creationTime: "2026-08-03T05:00:00Z", versionTime: "2026-08-03T10:00:00Z" },
                 { creationTime: "2026-08-03T05:00:00Z", versionTime: "2026-08-03T10:00:00Z" }) === false);
  ok("senza creationTime si ordina comunque sul versionTime",
    m.piuVecchio({ creationTime: null, versionTime: "2026-01-01T00:00:00Z" },
                 { creationTime: null, versionTime: "2026-06-01T00:00:00Z" }) === true);

  // --- il difetto del 03.08.2026: il testo su un record che non e' il primo
  //
  // Nel feed vero una <situation> contiene piu' <situationRecord>, e UNO SOLO
  // porta il commento nelle quattro lingue. La versione precedente scandiva
  // per record e buttava quelli senza italiano: se il testo non stava sul
  // primo, la situazione spariva del tutto.
  const testoInFondo = `<dx223:situation id="situation.910001.1">
    <dx223:situationRecord id="situation.910001.1.1.1" xsi:type="dx223:RoadOrCarriagewayOrLaneManagement">
      <dx223:situationRecordVersionTime>2026-08-03T06:00:00Z</dx223:situationRecordVersionTime>
      <dx223:generalPublicComment><dx223:comment><dx223:values><dx223:value lang="en-EN">lane closed</dx223:value></dx223:values></dx223:comment></dx223:generalPublicComment>
    </dx223:situationRecord>
    <dx223:situationRecord id="situation.910001.1.2.1" xsi:type="dx223:AbnormalTraffic">
      <dx223:situationRecordVersionTime>2026-08-03T06:05:00Z</dx223:situationRecordVersionTime>
      <dx223:generalPublicComment><dx223:comment><dx223:values><dx223:value lang="it-CH">Approvato: A2 Luzern -&gt; S. Gottardo Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] 4.0 Aggiunta 1: ritardi No. [min] 40</dx223:value><dx223:value lang="de-CH">Stau</dx223:value></dx223:values></dx223:comment></dx223:generalPublicComment>
    </dx223:situationRecord>
  </dx223:situation>`;
  const tardi = m.estraiSituazioni(testoInFondo).situazioni;
  ok("il testo su un record NON primo viene comunque trovato", !!tardi["situation.910001.1"]);
  ok("  la chiave e' la SITUAZIONE, non il record (R3)", Object.keys(tardi)[0] === "situation.910001.1");
  ok("  il tipo scelto e' quello della coda, non della chiusura di corsia",
    tardi["situation.910001.1"] && tardi["situation.910001.1"].type === "AbnormalTraffic");
  ok("  il versionTime e' il piu' recente fra i record",
    tardi["situation.910001.1"] && tardi["situation.910001.1"].versionTime === "2026-08-03T06:05:00Z");
  ok("  il tedesco raccolto dallo stesso record c'e'",
    tardi["situation.910001.1"] && !!tardi["situation.910001.1"].texts.de);

  // e una revoca dichiarata da un record qualsiasi vale per la situazione
  const revocaAltrove = testoInFondo.replace(
    "<dx223:situationRecordVersionTime>2026-08-03T06:00:00Z</dx223:situationRecordVersionTime>",
    "<dx223:situationRecordVersionTime>2026-08-03T06:00:00Z</dx223:situationRecordVersionTime><dx223:lifeCycleManagement><dx223:cancel>true</dx223:cancel></dx223:lifeCycleManagement>");
  const rev = m.estraiSituazioni(revocaAltrove).situazioni["situation.910001.1"];
  ok("una revoca dichiarata da UN QUALSIASI record vale per la situazione (R4)", rev && rev.revocata === true);

  // --- documento troncato: la busta si apre ma non si chiude ---
  //
  // Revisione del 03.08.2026: il controllo guardava solo l'intestazione, e un
  // documento tagliato a meta' da un guasto di rete passava, si lasciava
  // analizzare e produceva solo meno record — indistinguibile da "poche
  // novita'". Protocollo per l'XML non valido: UN ritentativo, poi quarantena.
  const TRONCATO = BUSTA_OK.slice(0, Math.floor(BUSTA_OK.length * 0.7));
  {
    const r = await giro([{ status: 200, corpo: TRONCATO }]);
    ok("un documento che non si chiude viene rifiutato", !r.ok && r.classe === m.CLASSE.XML);
    ok("  con un solo ritentativo (2 chiamate), come da protocollo", r.chiamate.length === 2);
    ok("  e la coda del documento finisce in quarantena", !!(r.diario && r.diario.quarantena));
  }
  {
    const r = await giro([{ status: 200, corpo: TRONCATO }, { status: 200, corpo: BUSTA_OK }]);
    ok("troncato poi intero: il ritentativo la salva", r.ok);
  }

  // --- percorso veloce (interattivo): fallisce presto, non trattiene l'app
  {
    copione = [{ status: 500 }]; chiamate = [];
    try { await m.fetchFeed(CURSORE, { veloce: true }); } catch {}
    ok("veloce: 1 tentativo + 1 ritentativo e basta", chiamate.length === 2);
  }
  {
    copione = [{ status: 429 }]; chiamate = [];
    try { await m.fetchFeed(CURSORE, { veloce: true }); } catch {}
    ok("veloce: sul 429 esce SUBITO, senza backoff lento", chiamate.length === 1);
  }
  {
    copione = [{ status: 503 }]; chiamate = [];
    try { await m.fetchFeed(CURSORE, { veloce: true }); } catch {}
    ok("veloce: sul 503 esce SUBITO", chiamate.length === 1);
  }

  // --- la strada, letta dall'inizio del messaggio ---
  const reali = [
    ["Approvato: A2 Luzern -> S. Gottardo tra Svincolo autostradale Erstfeld E Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] 8", "A2", true],
    ["Approvato: H2 Göschenen <-> Flüelen tra Luogo Erstfeld E Svincolo autostradale Göschenen Situazione: problemi di traffico", "H2", false],
    ["Revocato: H2 Airolo <-> Flüelen tra Svincolo autostradale Göschenen E Luogo Andermatt Situazione: problemi di traffico", "H2", false],
    ["Approvato: H11 Meiringen <-> Wassen Luogo Nessental Situazione: problemi di traffico cantiere", "H11", false],
    ["Approvato: A3W Diramazione Zürich Süd -> Wiedikon tra Raccordo autostradale E Svincolo", "A3W", false],
  ];
  for (const [testo, atteso, autostrada] of reali) {
    ok(`strada di "${testo.slice(0, 34)}…" = ${atteso}`, m.stradaDi(testo) === atteso);
    ok(`  conta per le code? ${autostrada ? "si" : "no"}`, m.sullaAutostrada(testo.toLowerCase()) === autostrada);
  }
  // il caso che il vecchio controllo sbagliava: A2 che NOMINA l'H2
  const deviazione = "Approvato: A2 Luzern -> S. Gottardo tra Erstfeld E Göschenen Situazione: colonna lunghezza [km] 8 Deviazione consigliata: H2 passo del S. Gottardo";
  ok("una coda A2 che nomina l'H2 resta una coda dell'A2", m.sullaAutostrada(deviazione.toLowerCase()) === true);
  ok("  (col vecchio controllo sarebbe stata scartata)", /\bh2\b/.test(deviazione.toLowerCase()));

  // --- il cursore segue il dato, non l'orologio (04.08.2026) -----------
  //
  // Il caso vero: la fonte pubblica un messaggio alle 10:13 ma lo rende
  // leggibile alle 10:50. Col cursore sull'orologio la finestra era gia'
  // passata oltre e il messaggio non lo avremmo visto mai piu'.
  const T = (s) => Date.parse("2026-08-04T" + s + "Z");

  const conVersionTime = (...tempi) =>
    `<dx223:d2LogicalModel>` + tempi.map((t, i) =>
      `<dx223:situation id="situation.90000${i}.1" version="1">` +
      `<dx223:situationRecord xsi:type="dx223:AbnormalTraffic" id="situation.90000${i}.1.1.1" version="1">` +
      `<dx223:situationRecordVersionTime xsi:type="dx223:DateTime">${t}</dx223:situationRecordVersionTime>` +
      `<dx223:generalPublicComment><dx223:comment><dx223:values>` +
      `<dx223:value lang="it-CH">Approvato: A1 Zurigo -> Berna Situazione: colonna</dx223:value>` +
      `</dx223:values></dx223:comment></dx223:generalPublicComment>` +
      `</dx223:situationRecord></dx223:situation>`).join("") +
    `</dx223:d2LogicalModel>`;

  const fronteFuoriCorridoio = m.estraiSituazioni(
    conVersionTime("2026-08-04T10:13:09Z", "2026-08-04T10:28:59Z")).frontiera;
  ok("la frontiera e' il versionTime piu' alto del documento",
    fronteFuoriCorridoio === T("10:28:59.000"));
  ok("  e la si legge anche su record che non toccano il corridoio",
    m.estraiSituazioni(conVersionTime("2026-08-04T10:28:59Z")).situazioni["situation.900000.1"] === undefined);
  ok("documento senza record: nessuna frontiera",
    m.estraiSituazioni("<dx223:d2LogicalModel></dx223:d2LogicalModel>").frontiera === null);

  ok("giro vuoto: il cursore NON avanza (la finestra si allarga)",
    m.prossimoCursore(null, T("10:07:06"), T("10:16:05")) === T("10:07:06"));
  ok("  e' questo che salva il messaggio in ritardo",
    m.prossimoCursore(T("10:13:09"), T("10:07:06"), T("10:50:00")) === T("10:13:09"));
  ok("col vecchio cursore sull'orologio quel messaggio era perso",
    T("10:16:05") > T("10:13:09"));
  ok("record tutti vecchi: non si retrocede",
    m.prossimoCursore(T("09:00:00"), T("10:07:06"), T("10:16:05")) === T("10:07:06"));
  ok("versionTime nel futuro: non si supera l'orologio",
    m.prossimoCursore(T("23:00:00"), T("10:07:06"), T("10:16:05")) === T("10:16:05"));
  ok("giro pieno e in orario: il cursore arriva al fronte",
    m.prossimoCursore(T("10:15:40"), T("10:07:06"), T("10:16:05")) === T("10:15:40"));

  // La finestra: pavimento di 60 minuti e tetto di 24 ore.
  const ORA = 3600 * 1000, MIN = 60 * 1000;
  const ADESSO = T("12:00:00");
  ok("nel giro normale comanda il cursore, senza pavimenti",
    m.inizioFinestra(ADESSO - 25 * MIN, ADESSO) === ADESSO - 25 * MIN);
  ok("cursore fermo da tre ore: si chiede da tre ore",
    m.inizioFinestra(ADESSO - 3 * ORA, ADESSO) === ADESSO - 3 * ORA);
  ok("dopo un fermo lunghissimo il tetto resta 24 ore",
    m.inizioFinestra(ADESSO - 40 * ORA, ADESSO) === ADESSO - 24 * ORA);

  // Il ripasso orario: la stessa finestra, con un pavimento di tre ore.
  ok("nel giro del ripasso il pavimento e' quello del ripasso",
    m.inizioFinestra(ADESSO - 1 * MIN, ADESSO, 6 * ORA) === ADESSO - 6 * ORA);
  ok("  ed e' cosi' che si richiude un buco di mezza giornata",
    m.inizioFinestra(ADESSO - 1 * MIN, ADESSO, 6 * ORA) < ADESSO - 1 * ORA);
  ok("  e un cursore finito davanti al fronte torna indietro col ripasso",
    m.inizioFinestra(ADESSO + 5 * MIN, ADESSO, 6 * ORA) === ADESSO - 6 * ORA);
  ok("nel ripasso, se il cursore e' gia' piu' indietro, resta lui",
    m.inizioFinestra(ADESSO - 8 * ORA, ADESSO, 6 * ORA) === ADESSO - 8 * ORA);
  ok("il tetto delle 24 ore vale anche nel ripasso",
    m.inizioFinestra(ADESSO - 40 * ORA, ADESSO, 6 * ORA) === ADESSO - 24 * ORA);
  // --- la chiave assente si riconosce subito -----------------------------
  //
  // Senza chiave la fonte risponderebbe 401 e il diario direbbe
  // "autorizzazione non valida": vero ma fuorviante, manderebbe a cercare una
  // chiave scaduta invece di una variabile d'ambiente mai impostata.
  {
    const salvata = process.env.OTD_KEY;
    delete process.env.OTD_KEY;
    const senzaChiave = new Function("require", sorgente +
      "\n;return { fetchFeed, CLASSE };")(richiedi);
    process.env.OTD_KEY = salvata;

    copione = [{ status: 200, corpo: BUSTA_OK }]; chiamate = [];
    let esito;
    try { await senzaChiave.fetchFeed(CURSORE); esito = { ok: true }; }
    catch (e) { esito = { ok: false, classe: e.classe, messaggio: e.message }; }
    ok("senza OTD_KEY non si chiama nemmeno la fonte", !esito.ok && chiamate.length === 0);
    ok("  ed e' un errore di configurazione, non da ritentare",
      esito.classe === m.CLASSE.CONFIGURAZIONE);
    ok("  il messaggio dice quale variabile manca",
      /OTD_KEY/.test(esito.messaggio || ""));
  }

  // --- il turno del ripasso -----------------------------------------------
  //
  // Le regole stanno in ripasso.js perche' il ripasso gira DENTRO il giro dei
  // 4 minuti (su Back4App si schedula un lavoro solo), ma il ritmo e la
  // profondita' si devono poter cambiare senza toccare il giro.
  const rip = richiedi("./ripasso.js");
  const T20 = 20 * 60 * 1000;
  ok("mai ripassato: si ripassa subito", rip.tocca(undefined, ADESSO) === true);
  ok("  e una data illeggibile vale come mai", rip.tocca("non una data", ADESSO) === true);
  ok("ripassato un minuto fa: no",
    rip.tocca(new Date(ADESSO - MIN).toISOString(), ADESSO) === false);
  ok("ripassato venti minuti fa: si'",
    rip.tocca(new Date(ADESSO - T20).toISOString(), ADESSO) === true);
  ok("il periodo e' venti minuti: un giro su cinque", rip.PERIODO_MS === T20);
  ok("la finestra del ripasso e' di sei ore", rip.FINESTRA_MS === 6 * ORA);

  let n = 0;
  console.log("=== gestione errori e ritentativi ===");
  for (const [nome, esito] of prove) { console.log(esito ? "  OK  " : "  NO  ", nome); if (esito) n++; }
  console.log(`\n${n}/${prove.length}`);
  process.exit(n === prove.length ? 0 : 1);
})();
