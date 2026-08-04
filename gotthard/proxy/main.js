/**
 * Proxy del feed "Traffic Situations" per Gottardo Live (dalla v1.2.7).
 *
 * RISCRITTO DA ZERO il 02.08.2026 seguendo il cookbook ufficiale:
 * https://opentransportdata.swiss/en/cookbook/road-traffic-cookbook/traffic-situations/
 *
 * Le regole del cookbook, trascritte alla lettera:
 *
 *  R1. "One query per day without If-Modified-Since and then only queries
 *      with If-Modified-Since with a timestamp no more than 5 minutes in the
 *      past. When the application that retrieves the data is restarted, a
 *      query can also be made without If-Modified-Since."
 *      -> SCOSTAMENTO DICHIARATO (03.08.2026): la lettura senza
 *         If-Modified-Since non si fa MAI. Misurato: contiene 17 situazioni
 *         del corridoio, 10 con piu' di sei mesi, tutte `active` e mai
 *         revocate — e' l'archivio dell'aperto-e-mai-chiuso, non lo stato
 *         attuale. Si legge solo il flusso incrementale (i tre casi del
 *         cookbook); dopo un fermo si allarga la finestra invece di
 *         ripiegare sulla lettura piena.
 *
 *  R2. If-Modified-Since "according to the standardized use of
 *      If-Modified-Since headers, e.g. Thu, 05 Mar 2026 08:00:00 GMT.
 *      The timestamp is interpreted as UTC!"
 *      -> formato RFC 1123 in GMT. (L'altro esempio del cookbook, quello
 *         ISO, e' stato provato il 02.08.2026: il server lo IGNORA e
 *         risponde per intero. Si usa solo l'RFC.)
 *
 *  R3. "An update replaces the original message. An update is always linked
 *      to a base situation via the <situation id=xxx> attribute."
 *      -> nel magazzino si sostituisce per id.
 *
 *  R4. "From the moment a traffic situation is revoked, the situation
 *      remains active and available on the platform for 60 minutes, with
 *      the revoked status entered in the element <value>" — e l'esempio
 *      mostra <lifeCycleManagement><cancel>true</cancel>.
 *      -> revoca riconosciuta dal cancel strutturato O dal prefisso nel
 *         testo; sincronizzando almeno ogni 5 minuti (R1) nessuna revoca
 *         puo' sfuggire, perche' resta in linea 60 minuti.
 *
 *  R5. Header obbligatori SOAPAction e Authorization; User-Agent e
 *      Accept-Encoding esplicti come da pagina "howto-access-api".
 *
 *  R6. Quota: "260,000 per 6 months, corresponding to the real-time data
 *      update interval of 1x per minute."
 *      -> la cache di 60 s limita la fonte a una chiamata al minuto, il
 *         ritmo per cui il piano e' dichiaratamente dimensionato.
 *
 * ARCHITETTURA (03.08.2026, richiesta dell'utente): l'app e' un CLIENTE e
 * basta. Questa funzione risponde con l'INTERA schermata — code, avvisi,
 * revoche E la serie del grafico — cosi' il telefono disegna e non decide.
 * Lo storico resta su GitHub (flusso del collector, INTOCCATO: lo legge
 * anche la 1.1.1 pubblicata): qui viene solo letto e incorporato.
 * Una sola tabella, Stato, a riga singola: appunti di sincronizzazione,
 * risposta pronta e contatore, tutto in un posto.
 *
 * Il payload e' un SOPRAINSIEME del precedente: la 1.2.7 continua a
 * funzionare, la 1.2.8 usera' anche `history`.
 */

// La chiave sta nel Cloud Code e non in Parse Config: Config e' leggibile
// dai client, il Cloud Code no.
// LA CHIAVE STA NELL'AMBIENTE, non nel codice. Variabile `OTD_KEY` nelle
// impostazioni dell'app su Back4App (Server Settings -> Environment Variables).
//
// Fino al 04.08.2026 il sorgente portava un segnaposto `__OTD_KEY__` che un
// passo di build sostituiva prima di distribuire, e quel passo produceva un
// secondo file — quello vero, con la chiave dentro — che non poteva essere
// versionato. Un file solo, senza segreti, si puo' tenere nella repo accanto
// alle sue prove; e non c'e' piu' modo di distribuire per sbaglio il file
// sbagliato.
const OTD_KEY = (typeof process !== "undefined" && process.env && process.env.OTD_KEY) || "";

const ENDPOINT = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull";
const SOAP_ACTION = "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages";

// "The body of the request message is always the same" (cookbook, Body).
const SOAP_BODY = `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <d2LogicalModel xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2" xmlns="http://datex2.eu/schema/2/2_0">
    <exchange>
        <supplierIdentification>
            <country>ch</country>
            <nationalIdentifier>FEDRO</nationalIdentifier>
        </supplierIdentification>
        <subscription>
            <operatingMode>operatingMode1</operatingMode>
            <subscriptionStartTime>2025-01-01T08:00:00.00+01:00</subscriptionStartTime>
            <subscriptionState>active</subscriptionState>
            <updateMethod>singleElementUpdate</updateMethod>
            <target>
                <address></address>
                <protocol>http</protocol>
            </target>
        </subscription>
    </exchange>
    </d2LogicalModel>
  </soap:Body>
</soap:Envelope>`;

// ------------------------------------------------------------------ tempi
// R6, riletta dopo il contingentamento del 03.08.2026: la fonte deve vedere
// UN lettore a ritmo costante — il lavoro pianificato, ogni 4 minuti. La
// funzione serve la risposta che il job ha preparato, e chiama la fonte in
// proprio SOLO se il job risulta fermo da piu' di due giri.
const PAYLOAD_FRESCO_MS = 10 * 60 * 1000;    // due giri del job + margine
const LUCCHETTO_SYNC_MS = 2 * 60 * 1000;     // un solo sync per volta
const INCREMENTALE_MAX_MS = 5 * 60 * 1000;   // R1: oltre, vale come riavvio
const FINESTRA_MASSIMA_MS = 24 * 3600 * 1000; // tetto alla finestra dopo un fermo lungo
const STALE_LIMIT_MS = 20 * 60 * 1000;       // cache scaduta servita sui guasti
const MEMORIA_REVOCHE_MS = 60 * 60 * 1000;   // R4: i 60 min della piattaforma
// NIENTE PAVIMENTO ALLA FINESTRA NORMALE. Provato il 04.08.2026 e tolto lo
// stesso giorno: imporre 60 minuti a tutte le richieste non serviva. Col
// cursore sul versionTime (vedi prossimoCursore) la finestra sta gia' da
// sola sui 20-30 minuti, perche' tanto e' il ritardo con cui la fonte
// pubblica; e l'unico caso che il pavimento copriva — cursore finito davanti
// al fronte del dato, risposte vuote, nessun appiglio per correggersi — lo
// copre gia' il ripasso, che rimette in riga il cursore al primo giro largo.
// Due reti per lo stesso buco, e la piu' costosa pagata quindici volte l'ora.

// IL RIPASSO — la lettura a finestra larga — NON sta qui: e' un lavoro suo,
// in ripasso.js, con la sua schedulazione. Vedi quel file per il perche'.
const FINESTRA_CODE_MS = 6 * 3600 * 1000;    // schede: messaggi di coda freschi
const FINESTRA_EVENTI_MS = 12 * 3600 * 1000; // lista avvisi
const POTATURA_MS = 13 * 3600 * 1000;        // il magazzino tiene solo il mostrabile

// Le regole del ripasso — ogni quanto, e quanto indietro — stanno in un file
// loro. Qui serve `tocca()`, che sincronizza consulta a ogni giro.
const ripasso = require("./ripasso.js");

// ------------------------------------------------- filtri del corridoio
// Identici a gotthard/collect.py: e' il filtro collaudato sul campo.
// I nomi con cui la fonte chiama LA GALLERIA. Ne usa piu' d'uno, e alterna
// senza regola: "Galleria Galleria del S. Gottardo" e "Galleria Galleria San
// Gottardo", senza "del". La lista aveva solo le forme col "del", e il
// 03.08.2026 alle 22:16 la chiusura del tunnel — scritta nell'altro modo —
// e' stata scartata all'ingresso: l'app non se n'e' accorta per tutta la
// notte, e nemmeno il collector, che ha la stessa lista. Il tedesco scrive
// "Gotthard-Tunnel" col trattino, che non combaciava con nessuna delle due
// forme che avevamo.
const NOMI_TUNNEL = [
  "galleria del s. gottardo", "galleria del san gottardo",
  "galleria s. gottardo", "galleria san gottardo",
  "gotthardtunnel", "gotthard tunnel", "gotthard-tunnel",
];
const CORRIDOR = [
  ...NOMI_TUNNEL,
  "göschenen", "goeschenen", "airolo", "wassen", "amsteg", "erstfeld",
  "quinto", "faido", "area di dosaggio",
];

// --- chiusura del tunnel
//
// La fonte annuncia la chiusura con "Situazione: tunnel chiuso" e NON annuncia
// la riapertura: quando il tunnel riapre, revoca il messaggio di chiusura
// (R4). Controllato su 18 record di chiusura in dodici catture del feed fra
// il maggio 2025 e l'agosto 2026: "tunnel aperto" non compare mai. Percio'
// qui si cerca solo la chiusura, e la fine la da' il ciclo di vita come per
// qualunque altro avviso.
const FRASI_CHIUSURA = [
  "tunnel chiuso",        // it
  "tunnel gesperrt",      // de
  "tunnel fermé", "tunnel ferme",   // fr, con e senza accento
  "tunnel closed",        // en
];
/**
 * L'etichetta in testa all'avviso, nella lingua del testo e nel senso di
 * marcia che la fonte dichiara.
 *
 * Il senso conta: una galleria non si chiude per forza in tutti e due i
 * versi. Su 17 chiusure d'archivio 13 sono `both`, 3 non dicono niente e una
 * — situation.639533, "A1 Morat -> Bern … tunnel chiuso" — e' a senso unico.
 * Scriverci sopra "TUNNEL CHIUSO" farebbe credere che sia chiuso del tutto.
 *
 * Quando la direzione non c'e' l'etichetta resta secca: non vuol dire "in
 * entrambi i sensi", vuol dire che non lo sappiamo, e l'avviso finisce gia'
 * nel gruppo "Direzione non indicata".
 *
 * "Verso sud" e' la direzione di MARCIA, come sulle schede: verso sud si esce
 * dal portale di Airolo. `Richtung Süden`/`Richtung Norden` sono le parole
 * che usa la fonte stessa.
 */
const ETICHETTA_CHIUSURA = {
  both: {
    it: "TUNNEL CHIUSO",
    de: "TUNNEL GESCHLOSSEN",
    fr: "TUNNEL FERMÉ",
    en: "TUNNEL CLOSED",
  },
  south: {
    it: "TUNNEL CHIUSO VERSO SUD",
    de: "TUNNEL GESCHLOSSEN RICHTUNG SÜDEN",
    fr: "TUNNEL FERMÉ VERS LE SUD",
    en: "TUNNEL CLOSED SOUTHBOUND",
  },
  north: {
    it: "TUNNEL CHIUSO VERSO NORD",
    de: "TUNNEL GESCHLOSSEN RICHTUNG NORDEN",
    fr: "TUNNEL FERMÉ VERS LE NORD",
    en: "TUNNEL CLOSED NORTHBOUND",
  },
};

// Le parole con cui il feed apre ogni messaggio: dicono come sta il messaggio
// nel sistema VMZ — approvato, revocato — non cosa succede in strada. Servono
// per togliere quel prefisso quando davanti ci mettiamo la nostra etichetta,
// altrimenti si legge "TUNNEL CHIUSO: Approvato: A2 ...". Stessa lista del
// client (GotthardProxyService.senzaPrefissoDiStato).
const PREFISSI_DI_STATO = new Set([
  "approvato", "revocato",
  "freigegeben", "aufgehoben",
  "libéré", "libere", "révoqué", "revoque",
  "approved", "revoked",
]);
const SOUTH_MARKERS = [
  "luzern -> s. gottardo", "lucerna -> s. gottardo",
  "basilea -> s. gottardo", "basel -> s. gottardo",
  "s. gottardo -> chiasso", "in direzione sud", "richtung süden",
];
const NORTH_MARKERS = [
  "chiasso -> s. gottardo",
  "s. gottardo -> luzern", "s. gottardo -> lucerna",
  "s. gottardo -> basilea", "s. gottardo -> basel",
  "in direzione nord", "richtung norden",
];
const SOUTH_PORTAL = ["göschenen", "goeschenen", "wassen", "amsteg", "erstfeld"];
const NORTH_PORTAL = ["airolo", "quinto", "faido", "dosaggio"];
// R4: lo stato di revoca compare anche nel testo del <value>
const REVOKED_PREFIXES = ["revocato", "aufgehoben", "révoqué"];

// ------------------------------------- direzione e luoghi, come li dice la fonte
//
// I marcatori qui sopra e i nomi dei portali sono una lettura del testo: si
// cercava "Luzern -> S. Gottardo" nella frase per capire dove andava chi era in
// coda, e "Göschenen" per capire davanti a quale imbocco. Funzionava, ma era
// pattern matching su una frase mentre ACCANTO alla frase c'e' il dato: la
// fonte dichiara sia la direzione sia i punti, in campi propri.
//
// Da qui in giu' i marcatori restano solo come ripiego per le situazioni
// salvate nel magazzino prima del 03.08.2026, che questi campi non li hanno.

/**
 * <alertCDirectionCoded>: positive / negative / both.
 *
 * Che `positive` sia il nord non e' una scelta: e' misurato su tutto
 * l'archivio locale (5 risposte complete, 1579 messaggi con luoghi leggibili).
 * Dove i marcatori sanno rispondere, deduzione e dato codificato dicono la
 * stessa cosa 50 volte su 50, con ZERO contraddizioni e zero casi in cui noi
 * diciamo una direzione e la fonte dice "both". Nella stessa risposta pero'
 * ci sono 306 messaggi in cui noi rispondevamo "non so" e la fonte diceva
 * positive o negative: e' quello che perdevamo.
 *
 * Controprova fuori autostrada, dove i marcatori non arrivano mai:
 * situation.642690.1 "H2 Airolo -> Flüelen" — da sud a nord — e' `positive`.
 *
 * "both" e' una risposta, non un vuoto: il messaggio vale nei due sensi.
 */
const DIREZIONE_CODIFICATA = { positive: "north", negative: "south" };

/**
 * <specificLocation>: il punto AlertC (tabella svizzera n. 9, versione 7.5).
 *
 * Un codice non cambia con la lingua del messaggio ne' con come e' scritta
 * Göschenen, e dice il punto esatto invece del nome che compare nella frase.
 * La tabella non e' inventata: ogni codice qui sotto e' stato ricavato
 * incrociando i 1579 messaggi dell'archivio finche' per quel codice e' rimasto
 * un solo nome possibile (p.es. 10458+10460 = "tra Svincolo Wassen E Svincolo
 * Göschenen", 10456+10460 = "tra Svincolo Amsteg E Svincolo Göschenen": il
 * codice comune ai due messaggi e' Göschenen).
 *
 * Si allunga cosi' e non altrimenti. 10455 e' entrato il 03.08.2026 dalla coda
 * vera delle 13:52 — "tra Svincolo autostradale Erstfeld E Svincolo
 * autostradale Göschenen", punti 10455 e 10460 — dove Göschenen era gia'
 * fissato: resta Erstfeld, e non c'e' niente da indovinare. Un codice che non
 * si riesce a chiudere cosi' NON si mette: la funzione qui sotto ripiega sui
 * nomi, che e' quello che facevamo prima, non un salto nel buio.
 *
 * Lato Uri, a NORD del tunnel: qui si incolonna chi sta andando a SUD.
 */
const PUNTI_LATO_URI = new Set([
  "10455",   // Svincolo autostradale Erstfeld (A2)
  "11588",   // Erstfeld (abitato, sulla strada del fondovalle)
  "10456",   // Svincolo autostradale Amsteg
  "10458",   // Svincolo autostradale Wassen
  "10460",   // Svincolo autostradale Göschenen (A2)
  "10459",   // Svincolo autostradale Göschenen (H2, strada del passo)
  "27447",   // Galleria Naxberg
]);
/** Lato Ticino, a SUD del tunnel: qui si incolonna chi sta andando a NORD. */
const PUNTI_LATO_TICINO = new Set([
  "10275",   // Svincolo autostradale Airolo
  "11320",   // Airolo (abitato)
  "14913",   // Parcheggio Area di dosaggio Airolo
  "27706",   // Svincolo autostradale Airolo-Nufenen
  "10461",   // Svincolo autostradale Quinto
  "10462",   // Svincolo autostradale Faido
  "11598",   // Faido (abitato)
]);
/**
 * Il tunnel stesso. Non e' ne' un imbocco ne' l'altro: e' il punto che i
 * messaggi sulla galleria portano quando parlano della galleria e non della
 * coda a monte — le chiusure, i cantieri notturni, i limiti di larghezza.
 * Verificato su tre messaggi con diciture diverse (287191, 342097, 642392):
 * il testo cambia, il codice no.
 */
const PUNTO_TUNNEL = "11187";

/** Tutti i punti che bastano da soli a dire "questo riguarda il Gottardo". */
const PUNTI_CORRIDOIO = new Set([
  PUNTO_TUNNEL, ...PUNTI_LATO_URI, ...PUNTI_LATO_TICINO,
]);

// Fuori tabella di proposito: Biasca (10463) e' a una quarantina di chilometri
// dal portale. Le due liste arrivano dove arriva CORRIDOR e non piu' in la':
// una colonna a Biasca e' traffico della valle Leventina, non l'attesa al
// tunnel, e non deve finire sulla scheda del Gottardo.

// ------------------------------------------------------------- parsing

function decodeEntities(text) {
  return text
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&amp;/g, "&");
}

function queueKm(text) {
  const patterns = [
    /(?:colonna|coda|stau)[^.;]{0,40}?lunghezza\s*\[km\]\s*(\d+(?:[.,]\d+)?)/i,
    /(?:coda|colonna|stau|bouchon|queue)[^.;]{0,60}?(\d+(?:[.,]\d+)?)\s*km/i,
  ];
  for (const re of patterns) {
    const m = text.match(re);
    if (m) return parseFloat(m[1].replace(",", "."));
  }
  return null;
}

function waitMinutes(text) {
  const lower = text.toLowerCase();
  let m = lower.match(/ritardi\s*no\.\s*\[min\]\s*(\d+)/);
  if (m) return parseInt(m[1], 10);
  m = lower.match(/ritardi\s*no\.\s*\[h\]\s*(\d+(?:[.,]\d+)?)/);
  if (m) {
    // L'etichetta [h] non e' affidabile: "[h] 70" su 7 km erano 70 MINUTI
    // (02.08.2026). Si crede alle ore solo se il risultato e' plausibile.
    const valore = parseFloat(m[1].replace(",", "."));
    const minuti = Math.round(valore * 60);
    return minuti <= 360 ? minuti : Math.round(valore);
  }
  m = lower.match(/(\d+)\s*(?:ora|ore|stunde|stunden|heure|heures)(?:\D{1,8}(\d+)\s*min)?/);
  if (m) return parseInt(m[1], 10) * 60 + parseInt(m[2] || "0", 10);
  m = lower.match(/(?:fino a|bis zu|jusqu'à)\s*(\d+)\s*min/);
  if (m) return parseInt(m[1], 10);
  return null;
}

/**
 * L'attesa quando la fonte pubblica i chilometri ma non i minuti.
 *
 * Il 03.08.2026 una coda al portale nord e' arrivata con "lunghezza [km] 10"
 * e nessun "ritardi No. [min]": la scheda mostrava i chilometri e un trattino
 * al posto dei minuti. Il rapporto non e' inventato, e' quello che il VMZ usa
 * quando li scrive tutti e due — 1/10, 2/20, 5/50, 6/60, 8/80, 9/90, 11/110
 * nelle code di quella stessa giornata: **10 minuti per chilometro**.
 *
 * Vale solo per i messaggi di coda. Un cantiere che dichiara "lunghezza
 * [km] 0.1" parla della zona di lavori, non di un incolonnamento, e
 * moltiplicarla darebbe un'attesa che non esiste.
 */
const MINUTI_PER_KM = 10;
function attesaDi(type, testo, km) {
  const letta = waitMinutes(testo);
  if (letta !== null) return { minuti: letta, stimata: false };
  if (km === null || type !== "AbnormalTraffic") return { minuti: null, stimata: false };
  return { minuti: Math.round(km * MINUTI_PER_KM), stimata: true };
}

/** Ripiego: la direzione indovinata dai marcatori nel testo. Vedi sopra. */
function direzioneDalTesto(lower) {
  const south = SOUTH_MARKERS.some((s) => lower.includes(s));
  const north = NORTH_MARKERS.some((s) => lower.includes(s));
  if (south && !north) return "south";
  if (north && !south) return "north";
  return null;
}

/**
 * La direzione di marcia della situazione: "south", "north" o null.
 *
 * Prima viene la fonte. Se ha dichiarato "both" la risposta e' null — non
 * perche' non lo sappiamo, ma perche' il messaggio vale nei due sensi: e' il
 * dato, e non si torna a indovinare per contraddirlo.
 */
function direzioneDi(s, lower) {
  if (s && s.direzioneFonte) return DIREZIONE_CODIFICATA[s.direzioneFonte] || null;
  return direzioneDalTesto(lower);
}

/**
 * La situazione tocca l'imbocco da cui arriva chi viaggia verso `d`?
 *
 * Chi va a sud si incolonna sul lato Uri, a nord del tunnel; chi va a nord sul
 * lato Ticino. Prima si cercavano i nomi dei paesi nella frase; adesso si
 * guardano i punti che la fonte dichiara per codice. I nomi restano solo se di
 * codici noti non ce n'e' nemmeno uno — magazzino vecchio, o un messaggio del
 * corridoio ancorato a un punto fuori dalle due liste.
 */
function allImbocco(s, d, lower) {
  const punti = (s && s.punti) || [];
  const noti = punti.filter((p) => PUNTI_LATO_URI.has(p) || PUNTI_LATO_TICINO.has(p));
  if (noti.length) {
    const attesi = d === "south" ? PUNTI_LATO_URI : PUNTI_LATO_TICINO;
    return noti.some((p) => attesi.has(p));
  }
  const nomi = d === "south" ? SOUTH_PORTAL : NORTH_PORTAL;
  return nomi.some((k) => lower.includes(k));
}

// L'H2 e' la strada del passo: cita gli stessi luoghi del tunnel ma non deve
// alimentarne le schede (02.08.2026: 60 min del valico su entrambe le carte).
/**
 * La strada di cui parla il messaggio, letta dall'INIZIO.
 *
 * I messaggi VMZ cominciano sempre con lo stato e poi la strada:
 *   "Approvato: A2 Luzern -> S. Gottardo tra ..."
 *   "Revocato: H2 Airolo <-> Flüelen tra ..."
 *
 * Prima si cercava "h2" in qualunque punto del testo: bastava un messaggio
 * dell'A2 che nominasse il passo — una deviazione consigliata — perche' quella
 * coda dell'autostrada sparisse dai chilometri. La strada e' un dato che il
 * messaggio dichiara in testa, non qualcosa da indovinare cercando dappertutto.
 */
function stradaDi(testo) {
  // Senza `i` la funzione fallisce quando le arriva il testo gia' minuscolo —
  // ed e' proprio cosi' che la chiama sullaAutostrada(). Preso dalle prove.
  const m = String(testo || "").match(/^\s*(?:[A-Za-zÀ-ÿ]+\s*:\s*)?([AHNJ]\d{1,3}[A-Z]?)\b/i);
  return m ? m[1].toUpperCase() : null;
}

/**
 * I chilometri di coda si contano SOLO sull'A2, l'autostrada del tunnel.
 * L'H2 e' la strada del passo: resta come avviso — a chi valuta il passo come
 * alternativa serve saperlo — ma non tocca i numeri delle schede.
 * Se la strada non si riconosce si ripiega sulla vecchia regola, che almeno
 * esclude il passo.
 */
function sullaAutostrada(lower) {
  const strada = stradaDi(lower);
  if (strada) return strada === "A2";
  return !/\bh2\b/.test(lower);
}

// I qualificatori che dicono "solo in certe ore", senza dire quali. Quando
// c'e' uno di questi la fonte NON ci mette in mano gli orari, quindi non
// possiamo affermare che la chiusura sia in corso adesso: il messaggio resta
// fra gli avvisi, ma senza l'etichetta. `untilFurtherNotice` invece non e'
// una restrizione oraria — e' l'opposto, dice che vale da adesso e basta —
// ed e' proprio come era scritta la chiusura del 03.08.2026.
const QUALIFICATORI_A_ORARIO = new Set([
  "duringTheNight", "duringTheDayTime", "severalTimes",
]);

/**
 * Il messaggio e' in vigore ADESSO, o parla di qualcosa di programmato?
 *
 * Tre domande, tutte a dati dichiarati dalla fonte:
 *   - vale solo in certe ore che non conosciamo? allora no;
 *   - comincia dopo adesso? allora no;
 *   - ha dei periodi di validita'? allora adesso deve cadere dentro uno.
 *
 * Un messaggio senza niente di tutto questo vale adesso: e' il caso normale
 * di una coda o di un incidente. Vale anche per le voci di magazzino
 * salvate prima del 04.08.2026, che questi campi non ce li hanno.
 */
function inVigore(s, adesso) {
  if ((s.qualificatori || []).some((q) => QUALIFICATORI_A_ORARIO.has(q))) return false;
  if (s.inizioValidita && Date.parse(s.inizioValidita) > adesso) return false;
  const periodi = s.periodi || [];
  if (!periodi.length) return true;
  return periodi.some((p) =>
    (!p.da || Date.parse(p.da) <= adesso) && (!p.a || Date.parse(p.a) >= adesso));
}

/**
 * Il messaggio parla di una chiusura DELLA GALLERIA DEL GOTTARDO?
 *
 * Non basta trovare "tunnel chiuso": nel corridoio ci sono altre gallerie
 * (la Naxberg, la Piumogna) e chiuderne una non e' chiudere il Gottardo.
 * Perche' sia il nostro tunnel serve una di queste tre prove, in ordine di
 * solidita':
 *
 *   - porta il punto AlertC del tunnel (11187): e' la fonte che lo dice;
 *   - lo chiama per nome nel testo;
 *   - tocca un punto dal lato di Uri E uno dal lato del Ticino, cioe' i due
 *     imbocchi: in mezzo c'e' solo la galleria. E' il caso di
 *     situation.639408 e 641977, "tra Göschenen E Airolo ... tunnel chiuso".
 */
function chiusuraDelTunnel(s, lower) {
  const testi = Object.values((s && s.texts) || {}).join(" ").toLowerCase();
  if (!FRASI_CHIUSURA.some((f) => testi.includes(f))) return false;
  const punti = (s && s.punti) || [];
  if (punti.includes(PUNTO_TUNNEL)) return true;
  if (NOMI_TUNNEL.some((n) => (lower || testi).includes(n))) return true;
  return punti.some((p) => PUNTI_LATO_URI.has(p))
      && punti.some((p) => PUNTI_LATO_TICINO.has(p));
}

/** "Approvato: A2 Luzern…" -> "A2 Luzern…". Solo i prefissi noti. */
function senzaPrefissoDiStato(testo) {
  const t = String(testo || "");
  const i = t.indexOf(":");
  if (i < 0) return t;
  if (!PREFISSI_DI_STATO.has(t.slice(0, i).trim().toLowerCase())) return t;
  return t.slice(i + 1).trim();
}

/**
 * I testi con "TUNNEL CHIUSO" davanti, ognuno nella sua lingua.
 *
 * Il feed pubblica in italiano, tedesco e francese: quelle tre prendono
 * l'etichetta giusta. L'inglese c'e' in tabella per quando arrivera' — la
 * fonte oggi non lo manda, e chi ha il telefono in inglese legge il ripiego
 * italiano, quindi vedra' "TUNNEL CHIUSO". Per avere "TUNNEL CLOSED" li'
 * l'etichetta va messa dal client, che le lingue le ha.
 */
function conEtichettaChiusura(texts, direzione) {
  const perLingua = ETICHETTA_CHIUSURA[direzione] || ETICHETTA_CHIUSURA.both;
  const fuori = {};
  for (const [lingua, testo] of Object.entries(texts || {})) {
    const etichetta = perLingua[lingua];
    fuori[lingua] = etichetta
      ? etichetta + ": " + senzaPrefissoDiStato(testo)
      : testo;
  }
  return fuori;
}

function iso(msOrDate) {
  return new Date(msOrDate).toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * Estrae dal documento le situazioni del corridoio, con chiave l'id (R3).
 * Scansione a stringa, niente DOM: 21 MB non entrano in una Cloud Function.
 */
function estraiSituazioni(xml) {
  const situazioni = {};
  let recordTotali = 0;

  // IL FRONTE DEL DATO: il versionTime piu' alto presente nel documento,
  // contando TUTTI i record — anche quelli che non riguardano il corridoio.
  // E' il punto fino a cui la fonte ci ha davvero raccontato qualcosa, e da
  // qui riparte il cursore del giro dopo (vedi sincronizza).
  //
  // Va letto su tutto il documento e non sulle sole situazioni del corridoio:
  // sul Gottardo puo' non cambiare nulla per un'ora, e un cursore fermo su
  // quello che interessa a noi farebbe crescere la finestra senza motivo.
  let frontiera = null;
  for (const t of xml.matchAll(
    /<(?:[\w.-]+:)?situationRecordVersionTime\b[^>]*>([\s\S]*?)<\//g)) {
    const v = Date.parse(t[1].trim());
    if (!isNaN(v) && (frontiera === null || v > frontiera)) frontiera = v;
  }

  // Si scandisce per <situation>, non per <situationRecord>. La differenza
  // non e' di stile: una situazione contiene PIU' record, e uno solo porta il
  // testo nelle quattro lingue. Gli altri portano il tipo, le chiusure di
  // corsia, la revoca — e nella versione precedente venivano buttati tutti
  // (`if (!it) continue`), 12 su 18 in una risposta incrementale reale del
  // 03.08.2026. Quella era una regola inventata da me, non del cookbook.
  const sitRe = /<(?:[\w.-]+:)?situation\s([^>]*)>/g;
  const confini = [];
  let s;
  while ((s = sitRe.exec(xml)) !== null) {
    // <situationRecord> comincia per "situation" ma non e' una <situation>:
    // il \s nella regex lo esclude gia', ma restano <situationExtension> ecc.
    if (/^<(?:[\w.-]+:)?situation\s/.test(xml.slice(s.index, s.index + 40))) {
      confini.push({ start: s.index, attrs: s[1] });
    }
  }

  for (let i = 0; i < confini.length; i++) {
    const blocco = xml.slice(confini[i].start,
      i + 1 < confini.length ? confini[i + 1].start : xml.length);

    // R3: la chiave e' la SITUAZIONE. "An update is always linked to a base
    // situation via the <situation id=xxx> attribute" — un aggiornamento
    // sostituisce l'originale solo se le due cose hanno la stessa chiave.
    const idMatch = confini[i].attrs.match(/\bid\s*=\s*"([^"]*)"/);
    if (!idMatch) continue;
    const id = idMatch[1];

    const records = [...blocco.matchAll(/<(?:[\w.-]+:)?situationRecord\s([^>]*)>/g)];
    recordTotali += records.length;
    if (!records.length) continue;

    // Il testo si prende da qualunque record lo porti, in tutte le lingue.
    const texts = {};
    const commentRe = /<(?:[\w.-]+:)?generalPublicComment\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?generalPublicComment>/g;
    let c;
    while ((c = commentRe.exec(blocco)) !== null) {
      const body = c[1];
      const ctype = body.match(/<(?:[\w.-]+:)?commentType\b[^>]*>([\s\S]*?)<\//);
      if (ctype && ctype[1].trim() === "internalNote") continue;
      const valueRe = /<(?:[\w.-]+:)?value\b([^>]*)>([\s\S]*?)<\/(?:[\w.-]+:)?value>/g;
      let v;
      while ((v = valueRe.exec(body)) !== null) {
        const langMatch = v[1].match(/lang\s*=\s*"([^"]*)"/);
        const lang = langMatch ? langMatch[1].slice(0, 2).toLowerCase() : "";
        const piece = decodeEntities(v[2]).trim();
        if (!lang || !piece || (texts[lang] || "").includes(piece)) continue;
        texts[lang] = texts[lang] ? texts[lang] + " — " + piece : piece;
      }
    }
    // I punti AlertC toccati dalla situazione, primari e secondari insieme:
    // qui interessa QUALI luoghi sono coinvolti, non l'ordine del segmento.
    const punti = [...new Set(
      [...blocco.matchAll(/<(?:[\w.-]+:)?specificLocation\b[^>]*>\s*(\d+)\s*</g)]
        .map((p) => p[1]))];

    const it = texts.it;
    if (!it) continue;
    const lower = it.toLowerCase();
    // DENTRO IL CORRIDOIO PER CODICE, o in mancanza per nome.
    //
    // Il codice viene prima perche' e' un dato che la fonte dichiara, mentre
    // il nome e' prosa e cambia forma. Il 03.08.2026 la chiusura del tunnel
    // portava il punto 11187 — lo stesso di tutti gli altri messaggi sulla
    // galleria — ma nel testo si chiamava "Galleria San Gottardo" invece che
    // "Galleria del S. Gottardo", e per quella sola parola l'abbiamo buttata.
    // Il nome resta come ripiego per i messaggi che il codice non ce l'hanno.
    if (!punti.some((p) => PUNTI_CORRIDOIO.has(p))
        && !CORRIDOR.some((k) => lower.includes(k))) continue;

    // Il tempo della situazione e' il piu' recente fra tutti i suoi record:
    // se una parte e' stata aggiornata, la situazione e' aggiornata.
    let versionTime = null, creationTime = null;
    for (const t of blocco.matchAll(/<(?:[\w.-]+:)?situationRecordVersionTime\b[^>]*>([\s\S]*?)<\//g)) {
      const v = Date.parse(t[1].trim());
      if (!isNaN(v) && (versionTime === null || v > versionTime)) versionTime = v;
    }
    for (const t of blocco.matchAll(/<(?:[\w.-]+:)?situationRecordCreationTime\b[^>]*>([\s\S]*?)<\//g)) {
      const v = Date.parse(t[1].trim());
      if (!isNaN(v) && (creationTime === null || v > creationTime)) creationTime = v;
    }
    if (versionTime === null) continue;

    // Il tipo: fra i record della situazione conta quello che descrive la
    // coda. Se c'e' un AbnormalTraffic vince lui, altrimenti il primo.
    const tipi = records
      .map((r) => (r[1].match(/\b(?:[\w.-]+:)?type\s*=\s*"(?:[\w.-]+:)?([^"]*)"/) || [])[1])
      .filter(Boolean);
    const type = tipi.includes("AbnormalTraffic") ? "AbnormalTraffic" : (tipi[0] || "");

    // R4: la revoca vale se la dichiara UN QUALSIASI record della situazione,
    // o se il testo pubblico la annuncia col prefisso.
    const cancel = /<(?:[\w.-]+:)?cancel\b[^>]*>\s*true\s*</.test(blocco);
    const prefisso = REVOKED_PREFIXES.some((p) => lower.startsWith(p));

    // La direzione dichiarata. I record di una situazione possono portarne
    // piu' d'una: se uno dice "both" e un altro un senso preciso vince il
    // preciso — "both" e' il caso generale del messaggio, il senso e' il
    // dettaglio. Se invece due record si contraddicono (positive E negative)
    // non si tira a sorte: si lascia in bianco.
    const dichiarate = new Set();
    for (const d of blocco.matchAll(/<(?:[\w.-]+:)?alertCDirectionCoded\b[^>]*>([\s\S]*?)<\//g)) {
      const v = d[1].trim();
      if (v) dichiarate.add(v);
    }
    const nette = [...dichiarate].filter((v) => v !== "both");
    const direzioneFonte = nette.length === 1 ? nette[0]
      : nette.length === 0 && dichiarate.has("both") ? "both"
      : null;

    // LA VALIDITA', come la dichiara la fonte. Serve a distinguere una
    // chiusura IN CORSO da una PROGRAMMATA: senza, il 04.08.2026 il cantiere
    // notturno del 10-28 agosto sarebbe finito a schermo come "TUNNEL CHIUSO"
    // mentre il tunnel era aperto.
    let inizioValidita = null;
    for (const t of blocco.matchAll(/<(?:[\w.-]+:)?overallStartTime\b[^>]*>([\s\S]*?)<\//g)) {
      const v = Date.parse(t[1].trim());
      if (!isNaN(v) && (inizioValidita === null || v < inizioValidita)) inizioValidita = v;
    }
    const periodi = [];
    for (const p of blocco.matchAll(
      /<(?:[\w.-]+:)?validPeriod\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?validPeriod>/g)) {
      const da = Date.parse(((p[1].match(/<(?:[\w.-]+:)?startOfPeriod\b[^>]*>([\s\S]*?)<\//) || [])[1] || "").trim());
      const a = Date.parse(((p[1].match(/<(?:[\w.-]+:)?endOfPeriod\b[^>]*>([\s\S]*?)<\//) || [])[1] || "").trim());
      periodi.push({ da: isNaN(da) ? null : iso(da), a: isNaN(a) ? null : iso(a) });
    }
    // Il qualificatore sta in un'estensione, non nel DATEX standard. Quattro
    // valori in 34548 blocchi d'archivio: duringTheNight, duringTheDayTime,
    // untilFurtherNotice, severalTimes.
    const qualificatori = [...new Set(
      [...blocco.matchAll(/<element>validityStatus<\/element>\s*<value>([^<]+)<\/value>/g)]
        .map((q) => q[1].trim()))];

    const nuovo = {
      id,
      type,
      inizioValidita: inizioValidita === null ? null : iso(inizioValidita),
      periodi,
      qualificatori,
      versionTime: iso(versionTime),
      creationTime: creationTime === null ? null : iso(creationTime),
      revocata: cancel || prefisso,
      direzioneFonte,
      punti,
      texts,
    };

    // Stessa situazione due volte nello stesso documento: vince la piu'
    // recente. L'ordine nel documento non e' garantito.
    const gia = situazioni[id];
    if (gia && piuVecchio(nuovo, gia)) continue;
    situazioni[id] = nuovo;
  }
  return { situazioni, recordTotali, frontiera };
}

/**
 * Registra una chiamata al feed nella tabella Chiamate, riuscita o no.
 *
 * Stanotte una lettura completa ha svuotato il magazzino e per sapere se era
 * sana o troncata ho dovuto interrogare il collector: da qui non c'era modo
 * di dirlo. Senza questo diario un difetto del trasporto si vede solo
 * dall'effetto, cioe' troppo tardi e sul dato sbagliato.
 *
 * Non puo' far fallire il giro: e' un registro, non un ingranaggio.
 */
async function registraChiamata(diario) {
  if (!diario) return;
  try {
    const r = new Parse.Object("Chiamate");
    r.set("quando", diario.quando);
    r.set("esito", diario.classe);
    r.set("httpStatus", diario.httpStatus === undefined ? null : diario.httpStatus);
    r.set("esitoSoap", diario.esitoSoap || null);
    r.set("esitoXml", diario.esitoXml || null);
    r.set("tentativi", diario.tentativi);
    r.set("durataMs", diario.durataMs);
    r.set("modo", diario.modo || null);
    r.set("conIfModifiedSince", diario.conIfModifiedSince);
    r.set("ifModifiedSince", diario.ifModifiedSince);
    r.set("byte", diario.byte === undefined ? null : diario.byte);
    r.set("recordTotali", diario.recordTotali === undefined ? null : diario.recordTotali);
    r.set("situazioni", diario.situazioni === undefined ? null : diario.situazioni);
    // Il fronte del dato e quanto e' indietro rispetto all'orologio: e' la
    // grandezza che il 04.08.2026 ci ha resi ciechi per mezza giornata senza
    // che nel diario ce ne fosse traccia.
    r.set("frontiera", diario.frontiera === undefined ? null : diario.frontiera);
    r.set("ritardoFonteMs",
      diario.ritardoFonteMs === undefined ? null : diario.ritardoFonteMs);
    r.set("errore", diario.errore || null);
    r.set("quarantena", diario.quarantena || null);
    r.set("idVisti", diario.idVisti || null);
    await r.save(null, { useMasterKey: true });
  } catch (e) {
    console.error("diario non scritto:", e.message);
  }
}

/**
 * `a` e' piu' vecchio di `b`?
 *
 * Il segnale di recenza e' il **versionTime**: e' quello che avanza a ogni
 * aggiornamento (R3). Il `creationTime` NON avanza — dice quando il record e'
 * nato e resta fermo per tutta la sua vita:
 *
 *   situation.542842.1  creationTime 2025-05-08  versionTime 2025-05-09
 *
 * Nella specifica del trasporto il creationTime e' la "chiave secondaria di
 * RICONCILIAZIONE", cioe' identita', non ordinamento. Averlo usato per
 * ordinare e' costato l'aggiornamento delle 12:40 del 03.08.2026: la coda e'
 * passata da 8 a 9 km, il messaggio e' arrivato, ed e' stato respinto come
 * doppione arretrato. Serve solo a distinguere due record diversi che
 * dichiarano lo stesso versionTime.
 */
/**
 * Da che istante si chiede il documento, dato il punto in cui e' il cursore.
 *
 * Si parte dal cursore. Due soli vincoli:
 *   - tetto 24 ore, perche' dopo un fermo lungo non si chiede l'archivio;
 *   - `minimo`, se passato: la partenza non e' piu' recente di tanto. Nel
 *     giro pianificato non si passa e comanda il cursore; lo passa il
 *     ripasso (ripasso.js) per chiedere una finestra larga.
 */
function inizioFinestra(partenza, adesso, minimo) {
  const dalCursore = Math.max(partenza, adesso - FINESTRA_MASSIMA_MS);
  if (!minimo) return dalCursore;   // assente, zero, null: comanda il cursore
  return Math.min(dalCursore, adesso - minimo);
}

/**
 * Dove si ferma il cursore dopo un giro riuscito.
 *
 * `frontiera` e' il versionTime piu' alto che la fonte ci ha consegnato in
 * questo giro, `frontePrecedente` quello dove eravamo. Tre regole:
 *
 *   - niente record -> il cursore NON si muove (la finestra si allarga, ed
 *     e' cosi' che un messaggio in ritardo ci raggiunge lo stesso);
 *   - record tutti vecchi -> non si retrocede;
 *   - versionTime nel futuro -> non si supera l'orologio.
 */
function prossimoCursore(frontiera, frontePrecedente, adesso) {
  if (frontiera === null || frontiera === undefined) return frontePrecedente;
  return Math.min(Math.max(frontiera, frontePrecedente), adesso);
}

function piuVecchio(a, b) {
  if (a.versionTime !== b.versionTime) return a.versionTime < b.versionTime;
  if (a.creationTime && b.creationTime) return a.creationTime < b.creationTime;
  return false;   // a parita' vince chi arriva dopo
}

// ---------------------------------------------------------------- rete
//
// Gestione errori e politica di ritentativi, secondo le regole di trasporto
// del portale. Il principio che tiene insieme tutto e' uno solo:
//
//   il cursore di lettura (If-Modified-Since) avanza SOLO dopo che la
//   chiamata e' andata a buon fine da capo a fondo — HTTP valido, SOAP
//   valido, XML leggibile, dato persistito.
//
// Se avanzasse dopo una chiamata fallita a meta', i messaggi entrati in
// quella finestra sarebbero persi PER SEMPRE: nessuna lettura successiva
// tornerebbe a cercarli. Dall'esterno somiglia a "la fonte omette le cose" —
// ed e' il motivo per cui questa parte va fatta bene prima di accusare
// chiunque.

const zlib = require("zlib");

/** Le classi di errore, con la reazione che ciascuna prescrive. */
const CLASSE = {
  OK: "ok",
  CONFIGURAZIONE: "configurazione",   // 400/401/403: chiave o header sbagliati
  ENDPOINT: "endpoint",               // 404/405: URL o SOAPAction sbagliata
  RETE: "rete",                       // timeout, DNS, connessione interrotta
  THROTTLING: "throttling",           // 429
  SERVER: "server",                   // 5xx
  FAULT_FERMO: "fault-fermo",         // SOAP Fault non transitorio
  FAULT_TRANSITORIO: "fault-transitorio",
  XML: "xml",                         // risposta non leggibile
};

/** Su queste non si ritenta: ritentare non puo' cambiare l'esito. */
const NON_RITENTABILI = [CLASSE.CONFIGURAZIONE, CLASSE.ENDPOINT, CLASSE.FAULT_FERMO];

// Backoff esponenziale. Il jitter serve a non far ripartire tutti i container
// nello stesso istante dopo un guasto della fonte.
const BACKOFF = [2000, 5000, 15000];
const BACKOFF_LENTO = [15000, 30000, 60000];   // 429 e 503: la fonte chiede spazio
const MAX_RITENTATIVI = 3;                     // oltre al tentativo iniziale
const TIMEOUT_MS = 90 * 1000;                  // il feed pieno e' grosso

class ErroreFeed extends Error {
  constructor(classe, messaggio, dettaglio) {
    super(messaggio);
    this.classe = classe;
    this.dettaglio = dettaglio || null;
    this.ritentabile = !NON_RITENTABILI.includes(classe);
  }
}

function attesa(ms) {
  // jitter pieno: fra meta' e tutto il ritardo previsto
  const conJitter = ms / 2 + Math.random() * (ms / 2);
  return new Promise((r) => setTimeout(r, conJitter));
}

/** Dallo stato HTTP alla classe di errore. */
function classificaHttp(status) {
  if (status >= 200 && status < 300) return CLASSE.OK;
  if (status === 429) return CLASSE.THROTTLING;
  if (status === 404 || status === 405) return CLASSE.ENDPOINT;
  if (status === 400 || status === 401 || status === 403) return CLASSE.CONFIGURAZIONE;
  if (status >= 500) return CLASSE.SERVER;
  return CLASSE.CONFIGURAZIONE;   // gli altri 4xx sono problemi nostri
}

/**
 * Cerca un SOAP Fault e lo classifica.
 *
 * Si guarda solo l'inizio del documento: un fault sta nel Body e arriva
 * subito, mentre una risposta buona e' lunga 21 MB e potrebbe contenere la
 * parola "fault" dentro il testo di un avviso.
 */
function leggiFault(xml) {
  const testa = xml.slice(0, 8192);
  if (!/<(?:[\w.-]+:)?Fault[\s>]/i.test(testa)) return null;

  const stringa = (testa.match(/<faultstring[^>]*>([\s\S]*?)<\/faultstring>/i) || [])[1] || "";
  const codice = (testa.match(/<faultcode[^>]*>([\s\S]*?)<\/faultcode>/i) || [])[1] || "";
  const tutto = (stringa + " " + codice).toLowerCase();

  // Le prime tre categorie sono colpa nostra: ritentare non serve finche'
  // non si corregge la configurazione.
  let categoria, classe;
  if (/header|soapaction|missing|mancante/.test(tutto)) {
    categoria = "header mancante o non valido"; classe = CLASSE.FAULT_FERMO;
  } else if (/auth|unauthor|forbidden|token|key|subscription/.test(tutto)) {
    categoria = "autorizzazione non valida"; classe = CLASSE.FAULT_FERMO;
  } else if (/malform|invalid|parse|schema|client/.test(tutto)) {
    categoria = "richiesta malformata"; classe = CLASSE.FAULT_FERMO;
  } else if (/timeout|temporar|unavailable|busy|overload|server/.test(tutto)) {
    categoria = "errore temporaneo del servizio"; classe = CLASSE.FAULT_TRANSITORIO;
  } else {
    // Uno sconosciuto lo si ritenta una volta: se e' fermo si ripresentera'.
    categoria = "fault sconosciuto"; classe = CLASSE.FAULT_TRANSITORIO;
  }
  return { categoria, classe, faultstring: stringa.trim().slice(0, 300), faultcode: codice.trim() };
}

/** Una risposta che non e' una busta SOAP non e' leggibile, punto. */
function bustaValida(xml) {
  return /<(?:[\w.-]+:)?Envelope[\s>]/i.test(xml.slice(0, 4096));
}

/**
 * Un solo tentativo. Distingue i tre esiti che il trasporto puo' dare:
 * errore HTTP, fault SOAP, risposta valida (fosse anche vuota di contenuto).
 */
async function tentaFeed(imsDate, diario) {
  if (!OTD_KEY) {
    // Senza chiave la fonte risponde 401 e il diario direbbe "autorizzazione
    // non valida": vero ma fuorviante, manderebbe a cercare una chiave
    // scaduta invece di una variabile assente.
    throw new ErroreFeed(CLASSE.CONFIGURAZIONE,
      "variabile d'ambiente OTD_KEY assente: impostarla nelle Server Settings di Back4App");
  }
  const headers = {
    Authorization: "Bearer " + OTD_KEY,                 // R5
    SOAPAction: SOAP_ACTION,                            // R5
    "Content-Type": "text/xml; charset=utf-8",
    "User-Agent": "GottardoLive/1.2 (+https://fbacchin.github.io/app/gotthard/support-gotthard.html)",
    "Accept-Encoding": "gzip, br, deflate",
  };
  if (imsDate) {
    headers["If-Modified-Since"] = imsDate.toUTCString(); // R2: RFC 1123 GMT
  }

  const taglia = new AbortController();
  const sveglia = setTimeout(() => taglia.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(ENDPOINT, {
      method: "POST", headers, body: SOAP_BODY, redirect: "follow", signal: taglia.signal,
    });
  } catch (e) {
    // Timeout, DNS, connessione interrotta: non sappiamo nemmeno se la
    // richiesta e' arrivata. Si ritenta con lo STESSO cursore.
    throw new ErroreFeed(CLASSE.RETE, "rete: " + (e.name === "AbortError" ? "timeout" : e.message));
  } finally {
    clearTimeout(sveglia);
  }

  diario.httpStatus = res.status;
  const classe = classificaHttp(res.status);
  if (classe !== CLASSE.OK) {
    throw new ErroreFeed(classe, "HTTP " + res.status);
  }

  // Il server comprime a prescindere dall'Accept-Encoding: si guardano i
  // byte. res.text() sul gzip grezzo = documento illeggibile in silenzio
  // (successo il 02.08, prima release del proxy).
  const buf = Buffer.from(await res.arrayBuffer());
  const plain = buf[0] === 0x1f && buf[1] === 0x8b ? zlib.gunzipSync(buf) : buf;
  const xml = plain.toString("utf8");
  diario.byte = xml.length;

  const fault = leggiFault(xml);
  if (fault) {
    diario.esitoSoap = "fault: " + fault.categoria;
    throw new ErroreFeed(fault.classe, "SOAP Fault — " + fault.categoria, fault);
  }
  diario.esitoSoap = "ok";

  if (!bustaValida(xml)) {
    diario.esitoXml = "non conforme";
    // Quarantena: si conserva l'inizio del corpo. Senza, di una risposta
    // illeggibile resta solo la lunghezza — e da "837 byte" non si capisce
    // se e' un contingentamento, una pagina d'errore o un guasto nostro.
    diario.quarantena = xml.slice(0, 1000);
    throw new ErroreFeed(CLASSE.XML, "risposta non conforme: nessuna busta SOAP in " + xml.length + " byte");
  }
  // La busta deve anche CHIUDERSI: un documento tagliato a meta' da un guasto
  // di rete supererebbe il controllo dell'intestazione, si lascerebbe
  // analizzare senza errori e produrrebbe solo meno record — indistinguibile
  // da "poche novita'". La classe e' XML: un ritentativo solo, poi quarantena.
  if (!/<\/(?:[\w.-]+:)?Envelope>\s*$/.test(xml.slice(-2000))) {
    diario.esitoXml = "troncato";
    diario.quarantena = xml.slice(-1000);
    throw new ErroreFeed(CLASSE.XML, "documento troncato: la busta non si chiude (" + xml.length + " byte)");
  }
  diario.esitoXml = "ok";
  return xml;
}

/**
 * La chiamata al feed, con la politica di ritentativi.
 *
 * `imsDate` e' il cursore e resta INVARIATO per tutti i tentativi dello
 * stesso giro: e' la stessa finestra di lettura, non una nuova.
 */
async function fetchFeed(imsDate, opzioni) {
  // `veloce` e' il percorso interattivo: una richiesta dell'app non puo'
  // aspettare i backoff da 15-60 secondi pensati per il lavoro pianificato —
  // Back4App uccide la funzione e l'app riceve un 408 (successo il
  // 03.08.2026, con la coda formata e il contingentamento in corso).
  const veloce = !!(opzioni && opzioni.veloce);
  const maxRitentativi = veloce ? 1 : MAX_RITENTATIVI;
  const diario = {
    quando: new Date(),
    endpoint: ENDPOINT,
    soapAction: SOAP_ACTION,
    conIfModifiedSince: !!imsDate,
    ifModifiedSince: imsDate ? imsDate.toUTCString() : null,
    tentativi: 0,
    httpStatus: null,
    esitoSoap: null,
    esitoXml: null,
    byte: null,
    classe: null,
    errore: null,
  };
  const inizio = Date.now();
  let ultimo;

  for (let tentativo = 0; tentativo <= maxRitentativi; tentativo++) {
    diario.tentativi = tentativo + 1;
    try {
      const xml = await tentaFeed(imsDate, diario);
      diario.classe = CLASSE.OK;
      diario.durataMs = Date.now() - inizio;
      return { xml, diario };
    } catch (e) {
      ultimo = e instanceof ErroreFeed ? e : new ErroreFeed(CLASSE.RETE, String(e.message || e));
      diario.classe = ultimo.classe;
      diario.errore = ultimo.message;

      if (!ultimo.ritentabile) break;      // configurazione o endpoint: inutile insistere
      // L'XML illeggibile si ritenta UNA volta sola: se la risposta e'
      // malformata due volte di fila non e' un incidente di percorso.
      if (ultimo.classe === CLASSE.XML && tentativo >= 1) break;
      if (tentativo === maxRitentativi) break;

      // Sul contingentamento il percorso veloce NON aspetta il backoff lento:
      // la fonte sta chiedendo spazio, e trattenere la richiesta dell'app per
      // 60 secondi non gliene da' — si esce e si serve la risposta scaduta.
      const lento = ultimo.classe === CLASSE.THROTTLING || diario.httpStatus === 503;
      if (lento && veloce) break;
      await attesa((lento ? BACKOFF_LENTO : BACKOFF)[tentativo]);
    }
  }

  diario.durataMs = Date.now() - inizio;
  ultimo.diario = diario;
  throw ultimo;
}

// ------------------------------------------- storico (nostro, non di GitHub)

// Lo storico del grafico si costruisce QUI, un campione per giro, dalla
// stessa lettura del feed che alimenta le schede. Fino al 03.08.2026 lo si
// specchiava da history.json del collector; ora che il lavoro pianificato
// gira ogni 4 minuti 24 ore su 24, la copertura c'e' anche senza di lui e la
// misura viene dalla fonte per la via nuova, senza intermediari.
//
// I file su GitHub restano dove sono e come sono: li scrive il collector, li
// legge la 1.1.1 pubblicata sullo Store. Questo codice non li tocca piu',
// ne' in lettura ne' in scrittura.
const STORICO_FINESTRA_MS = 24 * 3600 * 1000;

/**
 * Rilegge dalla tabella Storico la serie da mandare all'app, nel formato che
 * il grafico gia' si aspetta (lo stesso di history.json: cambia la sorgente,
 * non la forma). In ordine cronologico, come lo vuole una curva.
 */
async function leggiStorico() {
  const q = new Parse.Query("Storico");
  q.greaterThanOrEqualTo("campione", new Date(Date.now() - STORICO_FINESTRA_MS));
  q.ascending("campione");
  q.limit(1000);
  const righe = await q.find({ useMasterKey: true });
  return righe.map((r) => ({
    time: iso(r.get("campione").getTime()),
    southQueueKm: r.get("sudKm") === undefined ? null : r.get("sudKm"),
    southDelay: r.get("sudMin") || 0,
    northQueueKm: r.get("nordKm") === undefined ? null : r.get("nordKm"),
    northDelay: r.get("nordMin") || 0,
    southHeld: !!r.get("sudTenuto"),
    northHeld: !!r.get("nordTenuto"),
  }));
}

// ------------------------------------------------------------ magazzino

const STATO_CLASS = "Stato";   // riga unica: appunti di sync + risposta pronta

/**
 * Il magazzino si SALVA come elenco e si LAVORA come mappa per id.
 *
 * Non e' un vezzo: Parse rifiuta i punti nelle chiavi degli oggetti annidati
 * ("Nested keys should not contain the '$' or '.' characters"), e gli id
 * delle situazioni sono fatti di punti. Salvato come mappa, il magazzino
 * passava solo da VUOTO: il primo giro con dentro una coda vera e' esploso
 * (03.08.2026, 07:16 e 07:20) — e i dati della coda, appena arrivati, sono
 * andati persi nel salvataggio. Di notte, a corridoio sgombro, il difetto
 * era invisibile.
 */
function daMagazzinoSalvato(salvato) {
  if (Array.isArray(salvato)) {
    const m = {};
    for (const s of salvato) if (s && s.id) m[s.id] = s;
    return m;
  }
  // forma vecchia (mappa): di fatto sempre vuota, per il difetto qui sopra
  return salvato || {};
}

/**
 * Un giro di sincronizzazione secondo R1-R4.
 */
async function sincronizza(opzioni) {
  const adesso = Date.now();
  const query = new Parse.Query(STATO_CLASS);
  query.descending("updatedAt");
  const row = (await query.first({ useMasterKey: true })) || new Parse.Object(STATO_CLASS);
  const stato = row.get("stato") || null;

  // UN sync per volta. Il 03.08.2026 alle 07:27:59 e 07:28:06 due
  // sincronizzazioni simultanee (job + chiamata dell'app) hanno colpito la
  // fonte a 7 secondi di distanza, e insieme ai ritentativi hanno innescato
  // la raffica di 429/503 che ci ha resi ciechi proprio mentre la coda si
  // formava. Il lucchetto scade da solo dopo 2 minuti: un processo morto non
  // blocca niente, e dopo un sync fallito nessuno rimartella subito.
  const lucchetto = row.get("syncAlle");
  if (lucchetto && adesso - lucchetto.getTime() < LUCCHETTO_SYNC_MS) {
    const e = new Error("sincronizzazione gia' in corso");
    e.sincronizzazioneInCorso = true;
    throw e;
  }
  row.set("syncAlle", new Date(adesso));
  await row.save(null, { useMasterKey: true });

  // SOLO LETTURE INCREMENTALI. Deciso il 03.08.2026, dopo aver misurato che
  // cosa contiene davvero una lettura senza If-Modified-Since:
  //
  //   - 17 situazioni del corridoio, di cui 10 con piu' di SEI MESI;
  //   - tutte dichiarate `validityStatus: active`, `informationStatus: real`,
  //     senza `overallEndTime`, mai revocate — per la fonte sono ancora
  //     aperte. Una di queste e' una coda di 1 km ad Airolo del maggio 2025,
  //     indistinguibile per struttura da una coda viva;
  //   - nessuna di quelle situazioni compare mai in un incrementale: sono
  //     ferme da mesi, e l'incrementale porta solo cio' che cambia.
  //
  // La lettura senza If-Modified-Since NON e' una fotografia del presente:
  // e' l'archivio di tutto cio' che e' stato aperto e mai chiuso. Costruirci
  // sopra il magazzino significa riempirlo di fossili dichiarati vivi.
  // L'incrementale invece e' il flusso degli eventi: nuova informazione,
  // mutazione, revoca — i tre casi del cookbook, e nient'altro.
  const modo = "incrementale";

  // IL CURSORE. Resta questo per tutti i tentativi del giro, e avanza solo
  // se arriviamo in fondo. Margine di 1 minuto all'indietro: la sostituzione
  // per id (R3) e' idempotente, rivedere un aggiornamento non costa nulla,
  // perderlo si'.
  //
  // IL CURSORE MISURA IL TEMPO DEL DATO, NON IL NOSTRO OROLOGIO. Fino al
  // 04.08.2026 `ultimaSync` veniva messo a `adesso`, e per mezza giornata
  // l'app ha mostrato una coda di 1 km mentre ce n'erano 4 a nord e 3 a sud.
  // Misurato quel giorno, due letture complete sulla stessa chiave a 12
  // minuti di distanza:
  //
  //   alle 10:45  il record piu' recente disponibile portava vt 10:09:57
  //   alle 10:57  il record piu' recente disponibile portava vt 10:41:53
  //
  // cioe' un messaggio diventa leggibile parecchi minuti DOPO l'orario che
  // porta scritto: il fronte del dato era indietro di 35 minuti, poi di 16.
  // Chiedendo "cosa e' cambiato negli ultimi 5 minuti" la risposta vuota da
  // 837 byte era corretta — la domanda era sbagliata. E quando il messaggio
  // affiorava, portava vt 10:13 mentre il cursore stava gia' a 10:15: quel
  // messaggio non lo avremmo visto mai piu'.
  //
  // Percio' `ultimaSync` diventa la FRONTIERA: il versionTime piu' alto che
  // la fonte ci ha davvero consegnato. Un giro che non porta nulla non muove
  // il cursore, e la finestra si allarga da sola esattamente quanto serve a
  // coprire il ritardo. Non puo' scavalcare il fronte per costruzione.
  //
  // SCOSTAMENTO DICHIARATO dal cookbook: R1 vuole un If-Modified-Since "no
  // more than 5 minutes in the past", e prevede la lettura senza cursore al
  // riavvio. Qui la lettura senza cursore non si fa mai (vedi sopra), quindi
  // dopo un fermo si allarga la finestra fino a coprirlo davvero: perdere i
  // messaggi di quel buco sarebbe peggio che mandare una finestra larga. Il
  // tetto delle 24 ore evita richieste patologiche dopo un fermo lungo. La
  // finestra larga non costa quanto sembra: la risposta pesa quanto i
  // cambiamenti che contiene, non quanto l'intervallo richiesto.
  const ultima = stato && stato.ultimaSync ? Date.parse(stato.ultimaSync) : NaN;
  const partenza = isNaN(ultima) ? adesso - INCREMENTALE_MAX_MS : ultima - 60 * 1000;
  // LA FINESTRA LARGA. Due strade portano qui: il lavoro `ripassa` lanciato
  // a mano, che passa `finestraMinima`; e il turno periodico, che tocca una
  // volta ogni PERIODO. Fuori da questi due casi comanda il cursore.
  const largo = (opzioni && opzioni.finestraMinima)
    || (ripasso.tocca(stato && stato.ultimoRipasso, adesso) ? ripasso.FINESTRA_MS : 0);
  const cursore = new Date(inizioFinestra(partenza, adesso, largo || undefined));

  let diario, situazioni, recordTotali, frontiera;
  try {
    const r = await fetchFeed(cursore, opzioni);
    diario = r.diario;
    ({ situazioni, recordTotali, frontiera } = estraiSituazioni(r.xml));
  } catch (e) {
    // Chiamata non conclusa: si registra e si esce SENZA salvare nulla.
    // Il cursore resta dov'era, quindi il prossimo giro ritorna a chiedere
    // la stessa finestra e nessun messaggio va perduto.
    await registraChiamata(e.diario);
    throw e;
  }
  diario.modo = (opzioni && opzioni.etichettaModo) || (largo ? "ripasso" : modo);
  diario.recordTotali = recordTotali;
  diario.situazioni = Object.keys(situazioni).length;

  // La frontiera nuova: mai indietro rispetto a dove eravamo (una risposta di
  // soli record vecchi non ci fa retrocedere) e mai oltre adesso (un
  // versionTime nel futuro non deve spostare il cursore in avanti). Se il
  // giro non ha portato nessun record, il cursore resta dov'era e la
  // prossima finestra sara' piu' larga di questa.
  const frontePrecedente = isNaN(ultima) ? adesso - INCREMENTALE_MAX_MS : ultima;
  const nuovoCursore = prossimoCursore(frontiera, frontePrecedente, adesso);
  diario.frontiera = frontiera === null ? null : iso(frontiera);
  diario.ritardoFonteMs = frontiera === null ? null : Math.max(0, adesso - frontiera);
  // Gli id arrivati in questo giro. Il 03.08.2026 un incrementale ha portato
  // 5 record e 0 situazioni del corridoio, e non c'e' stato modo di sapere se
  // la coda del Gottardo fosse fra quei record e l'avessimo filtrata, o se non
  // fosse mai arrivata. Con gli id in chiaro la prossima volta si sa subito.
  diario.idVisti = Object.keys(situazioni).slice(0, 40).join(" ") || null;

  // Zero record e' la normalita': l'incrementale porta solo i cambiamenti, e
  // per minuti interi sul Gottardo puo' non cambiare nulla. Il guasto vero —
  // risposta illeggibile, busta assente, documento troncato — viene gia'
  // intercettato nel trasporto, che in quei casi fallisce invece di
  // consegnare un documento vuoto (vedi tentaFeed).

  // Ciclo di vita: i TRE casi del cookbook, e nessun altro.
  //
  //   nuova informazione  -> entra nel magazzino
  //   mutazione           -> sostituisce per id (R3), solo in avanti
  //   revoca              -> chiude (R4)
  //
  // L'assenza non e' uno dei tre: se una situazione non compare in una
  // risposta, il suo dato NON cambia. Questa e' la regola che tiene in piedi
  // tutto il resto.
  //
  // Una revoca non si cancella subito: resta come lapide per 60 minuti, il
  // tempo per cui la piattaforma la tiene disponibile. Serve all'ordine: se
  // dopo la revoca arriva un aggiornamento arretrato per lo stesso id, la
  // lapide lo respinge invece di resuscitare una coda finita.
  let magazzino;
  const revoche = (stato && stato.revoche) || {};

  const incorpora = (s) => {
    const gia = magazzino[s.id];
    // R3 sostituisce per id, ma solo in avanti: un record piu' vecchio di
    // quello che abbiamo non e' un aggiornamento, e' un doppione arretrato.
    if (gia && piuVecchio(s, gia)) return;
    magazzino[s.id] = s.revocata
      ? Object.assign({}, s, {
          revocata: true,
          // La lapide porta la data della PRIMA volta che abbiamo visto la
          // revoca. Con la finestra che si allarga lo stesso record di revoca
          // puo' tornare piu' giri di fila: ristampare la data la terrebbe in
          // vita oltre i 60 minuti che le spettano.
          revocataAlle: (gia && gia.revocataAlle) || iso(adesso),
        })
      : s;
  };

  // Il magazzino si porta avanti SEMPRE e non si azzera mai. Il 03.08.2026
  // alle 07:40 il codice lo ricostruiva da una singola risposta: quella
  // risposta non conteneva le code attive, e la coda e' sparita dall'app
  // finche' la fonte non ha cambiato i chilometri. Le revoche arrivano
  // davvero — misurato: 13 avvisi su 14 in 48 ore chiusi con revoca
  // esplicita — quindi ci si fida del ciclo di vita, non delle assenze.
  magazzino = daMagazzinoSalvato(stato && stato.magazzino);
  for (const s of Object.values(situazioni)) incorpora(s);

  // Le lapidi scadute si tolgono: passati i 60 minuti nessun messaggio
  // arretrato per quell'id puo' piu' arrivare.
  const sogliaLapidi = iso(adesso - MEMORIA_REVOCHE_MS);
  for (const [id, s] of Object.entries(magazzino)) {
    if (s.revocata && (s.revocataAlle || "") < sogliaLapidi) delete magazzino[id];
  }

  // Memoria delle revoche per direzione: il client ci smonta le tenute.
  // Finestra allineata ai 60 minuti di disponibilita' della piattaforma (R4).
  for (const s of Object.values(situazioni)) {
    if (!s.revocata || s.type !== "AbnormalTraffic") continue;
    const lower = (s.texts.it || "").toLowerCase();
    if (!sullaAutostrada(lower)) continue;   // una revoca sul passo non chiude il tunnel
    const dir = direzioneDi(s, lower);
    for (const d of dir ? [dir] : ["south", "north"]) {
      if (!allImbocco(s, d, lower)) continue;
      if (!revoche[d] || revoche[d] < s.versionTime) revoche[d] = s.versionTime;
    }
  }
  const sogliaRevoche = iso(adesso - MEMORIA_REVOCHE_MS);
  for (const d of Object.keys(revoche)) {
    if (revoche[d] < sogliaRevoche) delete revoche[d];
  }

  // Potatura: si tiene solo cio' che puo' ancora comparire a schermo.
  const sogliaPotatura = iso(adesso - POTATURA_MS);
  for (const id of Object.keys(magazzino)) {
    if (magazzino[id].versionTime < sogliaPotatura) delete magazzino[id];
  }

  // QUI il cursore avanza, e non un istante prima. `ultimaSync` e il
  // magazzino si salvano insieme, in una scrittura sola: o passano tutti e
  // due o nessuno dei due. Se qualcosa e' andato storto piu' su, siamo gia'
  // usciti per eccezione e la finestra verra' richiesta di nuovo.
  //
  // Il valore salvato e' la FRONTIERA del dato, non `adesso`: vedi il blocco
  // sul cursore piu' su. Un giro riuscito ma vuoto lascia il cursore fermo,
  // ed e' quello che tiene aperta la finestra finche' il messaggio in
  // ritardo non affiora.
  row.unset("syncAlle");   // il lucchetto si apre insieme all'avanzamento
  row.set("stato", {
    ultimaSync: iso(nuovoCursore),
    // Il turno del ripasso si segna solo se il giro e' arrivato in fondo,
    // esattamente come il cursore: un giro fallito non consuma il turno.
    ultimoRipasso: largo ? iso(adesso) : ((stato && stato.ultimoRipasso) || null),
    // Elenco, NON mappa: gli id contengono punti e Parse li rifiuta come
    // chiavi annidate (vedi daMagazzinoSalvato).
    magazzino: Object.values(magazzino),
    revoche,
  });
  row.increment("incrementali");
  await row.save(null, { useMasterKey: true });

  // Registrato solo adesso: "riuscita" vuol dire arrivata fino alla
  // persistenza, non solo fino a un HTTP 200.
  await registraChiamata(diario);

  // `situazioni` sono i record letti IN QUESTO GIRO (in un incrementale: solo
  // cio' che e' cambiato). Servono alla tabella Avvisi per due cose che il
  // magazzino non puo' dire: quali avvisi sono stati appena ripubblicati
  // (quindi freschi, non tenuti) e quali sono stati revocati — la revoca
  // toglie la voce dal magazzino (R4), ma nella tabella va annotata.
  return { magazzino, situazioni, revoche, modo, recordTotali, riga: row };
}

// --------------------------------- payload (stesso formato di prima)

function costruisciPayload(magazzino, revoche, modo, recordTotali, adesso) {
  const state = { south: { km: null, wait: null }, north: { km: null, wait: null } };
  // Da quale situazione viene il numero mostrato, per direzione. Serve allo
  // Storico per dire se il campione e' una lettura fresca o un valore tenuto
  // dal magazzino perche' la fonte non l'ha ripubblicato in questo giro.
  const fonti = { south: null, north: null };
  const events = [];

  for (const s of Object.values(magazzino)) {
    if (s.revocata) continue;   // e' una lapide: tenuta per la deduplicazione, non da mostrare
    const it = s.texts.it || "";
    const lower = it.toLowerCase();
    const eta = adesso - Date.parse(s.versionTime);
    if (eta > FINESTRA_EVENTI_MS) continue;

    const km = queueKm(it);
    const attesa = attesaDi(s.type, it, km);
    const wait = attesa.minuti;
    const direction = direzioneDi(s, lower);
    // `strada` dice di quale strada parla l'avviso: A2 e' l'autostrada del
    // tunnel, H2 la strada del passo. Serve a chi legge per capire se il
    // passo e' un'alternativa percorribile — informazione che nel testo c'e'
    // ma sepolta, e che l'app puo' mostrare a colpo d'occhio.
    //
    // `directionStated` dice se la DIREZIONE e' un dato o un vuoto: senza,
    // il client non puo' distinguere "vale nei due sensi" (la fonte lo
    // dichiara) da "non si sa", e finiva per scrivere "entrambe le direzioni"
    // anche sul secondo caso.
    // La chiusura del tunnel e' l'unica notizia che vale piu' di una coda:
    // l'etichetta va in testa al testo cosi' si legge subito, e il campo
    // `chiusura` la dichiara per chi disegna — un colore, un bollino — senza
    // dover rileggere la frase.
    // "Chiusura" vuol dire chiusa ADESSO. Un cantiere notturno programmato
    // per la settimana prossima resta un avviso normale, senza etichetta.
    const chiusura = chiusuraDelTunnel(s, lower) && inVigore(s, adesso);
    events.push({ id: s.id, type: s.type, direction, strada: stradaDi(it),
                  directionStated: !!s.direzioneFonte,
                  versionTime: s.versionTime, km, wait,
                  waitStimato: attesa.stimata, chiusura,
                  texts: chiusura ? conEtichettaChiusura(s.texts, direction) : s.texts });

    // Stato delle code: solo A2, solo messaggi freschi, solo coi portali.
    if (s.type !== "AbnormalTraffic" || (km === null && wait === null)) continue;
    if (eta > FINESTRA_CODE_MS) continue;
    if (!sullaAutostrada(lower)) continue;
    for (const d of direction ? [direction] : ["south", "north"]) {
      if (!allImbocco(s, d, lower)) continue;
      if (km !== null && km > (state[d].km || 0)) { state[d].km = km; fonti[d] = s.id; }
      if (wait !== null && wait > (state[d].wait || 0)) {
        state[d].wait = wait;
        if (!fonti[d]) fonti[d] = s.id;
      }
    }
  }

  events.sort((a, b) => (b.versionTime > a.versionTime ? 1 : b.versionTime < a.versionTime ? -1 : 0));
  events.sort((a, b) => {
    const an = a.km !== null || a.wait !== null;
    const bn = b.km !== null || b.wait !== null;
    return an === bn ? 0 : an ? -1 : 1;
  });

  return {
    time: iso(adesso),
    south: state.south,
    north: state.north,
    events: events.slice(0, 20),
    revocations: revoche,
    recordsSeen: recordTotali,
    syncMode: modo,
    sources: fonti,
  };
}

// --------------------------------------- tabelle leggibili (per l'utente)

// Tre tabelle da sfogliare nel cruscotto come un foglio di calcolo (e da
// esportare in CSV col bottone del dashboard). Non le legge nessun client:
// esistono per l'occhio umano. In un database le righe non stanno "in cima":
// nel cruscotto si ordina per la colonna data, discendente, e l'ultimo dato
// e' il primo che si vede.
//
//   Attuale — sempre 2 righe (sud, nord): la fotografia di adesso
//   Storico — un campione per giro, dalla lettura del feed di questo giro
//   Avvisi  — una riga per avviso, con revoca annotata, finestra 48 ore
//
// Dal 03.08.2026 Storico e Avvisi NON sono piu' copie dei file del collector:
// nascono qui, dalla stessa sincronizzazione R1-R4 che alimenta le schede.
// I file su GitHub restano intatti — li scrive il collector, li legge la
// 1.1.1 pubblicata sullo Store — ma questo codice non li guarda piu'.
const FINESTRA_TABELLE_MS = 48 * 3600 * 1000;

// Passo minimo fra due campioni dello Storico. Il lavoro pianificato gira
// ogni 4 minuti; un "Run now" a mano non deve infilare un campione a 10
// secondi dal precedente e sporcare il passo della curva.
const PASSO_STORICO_MS = 3 * 60 * 1000;

/** La riga della tabella Avvisi per quell'id, nuova se non c'e'. */
async function rigaAvviso(id) {
  const q = new Parse.Query("Avvisi");
  q.equalTo("situationId", id);
  return (await q.first({ useMasterKey: true })) || new Parse.Object("Avvisi");
}

/**
 * L'etichetta per la colonna "direzione" della tabella Avvisi.
 *
 * "entrambe" e "non indicata" non sono la stessa cosa e in tabella non devono
 * leggersi uguali: la prima e' la fonte che dichiara `both` — il messaggio
 * vale nei due sensi — la seconda e' un messaggio che la direzione non la dice
 * (o una situazione entrata nel magazzino prima che leggessimo il campo).
 * Fino al 03.08.2026 finivano tutte e due sotto "entrambe", ed e' quello che
 * faceva scrivere "entrambe le direzioni" anche quando nessuno l'aveva detto.
 */
function etichettaDirezione(d, s) {
  if (d === "south") return "sud";
  if (d === "north") return "nord";
  return s && s.direzioneFonte ? "entrambe" : "non indicata";
}

async function aggiornaTabelle(payload, magazzino, situazioni) {
  const adesso = Date.now();

  // --- Attuale: upsert delle due righe per direzione
  for (const [dir, nome] of [["south", "sud"], ["north", "nord"]]) {
    const q = new Parse.Query("Attuale");
    q.equalTo("direzione", nome);
    const riga = (await q.first({ useMasterKey: true })) || new Parse.Object("Attuale");
    const lato = payload[dir] || {};
    const evento = (payload.events || []).find((e) =>
      e.direction === dir && (e.km !== null || e.wait !== null));
    riga.set("direzione", nome);
    riga.set("km", lato.km);
    riga.set("attesa", lato.wait);
    riga.set("stato", lato.km || lato.wait ? "coda" : "libera");
    riga.set("aggiornatoAlle", evento ? new Date(evento.versionTime) : new Date(adesso));
    riga.set("testo", evento ? (evento.texts.it || "") : "");
    await riga.save(null, { useMasterKey: true });
  }

  // --- Storico: un campione per giro, da quello che abbiamo appena letto.
  //
  // "Tenuto" qui ha un significato preciso e verificabile: il numero viene da
  // una situazione che in QUESTO giro la fonte non ha ripubblicato, e che sta
  // ancora nel magazzino perche' nessuna revoca l'ha chiusa (R3/R4). Non e'
  // una supposizione dell'app come nella 1.2.7: e' il ciclo di vita del
  // cookbook, annotato mentre accade.
  const ultimoQ = new Parse.Query("Storico");
  ultimoQ.descending("campione");
  ultimoQ.select("campione");
  const ultimo = await ultimoQ.first({ useMasterKey: true });
  if (!ultimo || adesso - ultimo.get("campione").getTime() >= PASSO_STORICO_MS) {
    const fonti = payload.sources || {};
    const tenuto = (dir) => !!fonti[dir] && !situazioni[fonti[dir]];
    const riga = new Parse.Object("Storico");
    riga.set("campione", new Date(adesso));
    riga.set("sudKm", payload.south.km);
    riga.set("sudMin", payload.south.wait || 0);
    riga.set("nordKm", payload.north.km);
    riga.set("nordMin", payload.north.wait || 0);
    riga.set("sudTenuto", tenuto("south"));
    riga.set("nordTenuto", tenuto("north"));
    await riga.save(null, { useMasterKey: true });
  }

  // --- Avvisi: una riga per situationId, dal magazzino.
  //
  // Il magazzino e' l'archivio: tiene le situazioni vive per id finche' non
  // arriva la revoca (R4) o finche' non invecchiano. Qui si riversa in
  // tabella. `primaVista` si scrive solo alla nascita della riga — e' la
  // prima volta che quell'avviso ci e' passato davanti — mentre `ultimaVista`
  // avanza a ogni giro in cui l'avviso e' ancora nel magazzino.
  for (const s of Object.values(magazzino)) {
    if (s.revocata) continue;   // lapide: la sua riga e' gia' marcata revocata
    const riga = await rigaAvviso(s.id);
    const it = s.texts.it || "";
    riga.set("situationId", s.id);
    riga.set("direzione", etichettaDirezione(direzioneDi(s, it.toLowerCase()), s));
    riga.set("strada", stradaDi(it));   // A2 = tunnel, H2 = passo
    const kmRiga = queueKm(it);
    const attesaRiga = attesaDi(s.type, it, kmRiga);
    riga.set("km", kmRiga);
    riga.set("attesa", attesaRiga.minuti);
    // Segnata, non nascosta: chi guarda la tabella deve poter vedere quali
    // minuti li ha scritti la fonte e quali li abbiamo stimati dai km.
    riga.set("attesaStimata", attesaRiga.stimata);
    // Il feed pubblica in tre lingue: la tabella le riporta tutte e tre, e
    // se e' una chiusura del tunnel ognuna porta la sua etichetta in testa.
    const chiusuraRiga = chiusuraDelTunnel(s, it.toLowerCase()) && inVigore(s, adesso);
    const testi = chiusuraRiga
      ? conEtichettaChiusura(s.texts, direzioneDi(s, it.toLowerCase()))
      : s.texts;
    riga.set("chiusura", chiusuraRiga);
    riga.set("testo", testi.it || "");
    riga.set("testoDe", testi.de || "");
    riga.set("testoFr", testi.fr || "");
    riga.set("versionTime", new Date(s.versionTime));
    if (!riga.get("primaVista")) riga.set("primaVista", new Date(s.versionTime));
    riga.set("ultimaVista", new Date(adesso));
    if (!riga.get("revocato")) riga.set("revocato", false);
    await riga.save(null, { useMasterKey: true });
  }

  // Le revoche lette in questo giro: il magazzino le ha gia' fatte sparire
  // (R4), quindi il ciclo qui sopra non le vede. Nella tabella pero' la fine
  // di un avviso e' un'informazione da conservare, non da cancellare.
  for (const s of Object.values(situazioni)) {
    if (!s.revocata) continue;
    // Una lettura completa riporta ANCHE roba vecchissima: il 03.08.2026 sono
    // arrivate due revoche di 433 e 395 giorni fa, e senza questo filtro
    // finivano in tabella con `ultimaVista` a adesso — cioe' spacciate per
    // notizie fresche, e per giunta immuni alla potatura a 48 ore.
    if (adesso - Date.parse(s.versionTime) > FINESTRA_TABELLE_MS) continue;
    const riga = await rigaAvviso(s.id);
    if (!riga.get("situationId")) {
      // Revoca di un avviso mai visto vivo (successo prima che il lavoro
      // pianificato esistesse): si registra comunque, con quel che si ha.
      const it = s.texts.it || "";
      riga.set("situationId", s.id);
      riga.set("direzione", etichettaDirezione(direzioneDi(s, it.toLowerCase()), s));
      // Espliciti a null, non lasciati vuoti: una colonna assente e una
      // colonna vuota si leggono diverse nel cruscotto.
      riga.set("km", null);
      riga.set("attesa", null);
      const chiusuraRev = chiusuraDelTunnel(s, it.toLowerCase()) && inVigore(s, adesso);
      const testiRev = chiusuraRev
        ? conEtichettaChiusura(s.texts, direzioneDi(s, it.toLowerCase()))
        : s.texts;
      riga.set("chiusura", chiusuraRev);
      riga.set("testo", testiRev.it || "");
      riga.set("testoDe", testiRev.de || "");
      riga.set("testoFr", testiRev.fr || "");
      riga.set("versionTime", new Date(s.versionTime));
      riga.set("primaVista", new Date(s.versionTime));
      riga.set("ultimaVista", new Date(adesso));
    }
    riga.set("revocato", true);
    if (!riga.get("revocatoAlle")) riga.set("revocatoAlle", new Date(s.versionTime));
    await riga.save(null, { useMasterKey: true });
  }

  // --- potatura a 48 ore: le tabelle sono da sfogliare, non da archiviare
  const soglia = new Date(adesso - FINESTRA_TABELLE_MS);
  for (const [classe, campo] of [["Storico", "campione"], ["Avvisi", "ultimaVista"],
                                 ["Chiamate", "quando"]]) {
    const q = new Parse.Query(classe);
    q.lessThan(campo, soglia);
    q.limit(200);
    const vecchie = await q.find({ useMasterKey: true });
    if (vecchie.length) await Parse.Object.destroyAll(vecchie, { useMasterKey: true });
  }
}

// ----------------------------------------------------- la funzione

/**
 * Rimette nello schermo pronto lo storico appena letto dalla tabella.
 *
 * Le schede e gli avvisi possono venire dalla cache — e' il modo in cui la
 * fonte vede un solo lettore a ritmo costante (R6) — ma il grafico no: si
 * rilegge a ogni chiamata dell'app. Costa una query e nessun contatto con la
 * fonte, e in cambio la curva si ridisegna sempre su quello che c'e' DAVVERO
 * in tabella. Se una riga dello Storico e' stata corretta a mano fra un giro
 * pianificato e l'altro, la correzione si vede al primo aggiornamento invece
 * di aspettare fino a quattro minuti.
 *
 * Se la lettura fallisce si tiene la curva che il payload aveva gia': un
 * grafico di qualche minuto fa e' meglio di un grafico vuoto.
 */
async function conStoricoFresco(payload) {
  try {
    payload.history = await leggiStorico();
  } catch (e) {
    payload.historyError = String(e.message || e);
  }
  return payload;
}

Parse.Cloud.define("gotthard", async () => {
  // Tutto vive nella stessa riga di Stato: appunti di sincronizzazione,
  // risposta pronta, contatore. La legge sincronizza(), la scriviamo qui.
  const query = new Parse.Query(STATO_CLASS);
  query.descending("updatedAt");
  const riga = await query.first({ useMasterKey: true }).catch(() => null);
  const builtAt = riga && riga.get("builtAt");
  const eta = builtAt ? Date.now() - builtAt.getTime() : Infinity;

  if (riga) {
    riga.increment("calls");
    await riga.save(null, { useMasterKey: true }).catch(() => {});
  }

  // Percorso normale: si serve la risposta preparata dal lavoro pianificato.
  // La fonte vede cosi' UN solo lettore a ritmo costante (R6). La funzione
  // chiama la fonte in proprio SOLTANTO se il job risulta fermo da piu' di
  // due giri — ed e' un ripiego, non il funzionamento previsto.
  if (riga && eta <= PAYLOAD_FRESCO_MS) {
    return await conStoricoFresco(Object.assign({}, riga.get("payload"), {
      cached: true, cacheAgeSeconds: Math.round(eta / 1000),
    }));
  }

  let payload;
  try {
    // `veloce`: niente backoff da 15-60 s dentro una richiesta interattiva —
    // Back4App la ucciderebbe (408) e l'utente non vedrebbe nulla comunque.
    payload = await giroCompleto(riga, { veloce: true });
  } catch (error) {
    // Guasto della fonte o sync gia' in corso altrove: risposta scaduta
    // finche' plausibile, poi errore vero.
    if (riga && riga.get("payload") && eta <= STALE_LIMIT_MS) {
      return await conStoricoFresco(Object.assign({}, riga.get("payload"), {
        cached: true, stale: true,
        cacheAgeSeconds: Math.round(eta / 1000),
        feedError: String(error.message || error),
      }));
    }
    throw error;
  }

  return Object.assign({}, payload, { cached: false, cacheAgeSeconds: 0 });
});

/**
 * Un giro completo: sincronizza con la fonte, costruisce la schermata,
 * aggiorna le tabelle leggibili, salva tutto in Stato. Usato sia dalla
 * funzione (quando la risposta in cache e' scaduta) sia dal lavoro
 * pianificato che gira ogni 4 minuti.
 */
async function giroCompleto(rigaNota, opzioni) {
  const dati = await sincronizza(opzioni);

  const payload = costruisciPayload(
    dati.magazzino, dati.revoche, dati.modo, dati.recordTotali, Date.now());

  // L'ordine conta. Prima si scrivono le tabelle — fra cui il campione di
  // Storico di questo giro — poi si rilegge la serie da li' per il grafico:
  // cosi' la curva che l'app riceve comprende anche la lettura appena fatta,
  // invece di essere sempre indietro di un giro.
  //
  // Le tabelle non possono far fallire la risposta: se il database fa i
  // capricci, l'app riceve comunque le schede e gli avvisi.
  try {
    await aggiornaTabelle(payload, dati.magazzino, dati.situazioni);
  } catch (e) {
    payload.tabelleError = String(e.message || e);
  }

  try {
    payload.history = await leggiStorico();
  } catch (e) {
    // Un grafico di qualche minuto fa e' meglio di un grafico vuoto.
    const vecchio = rigaNota && rigaNota.get("payload");
    payload.history = (vecchio && vecchio.history) || [];
    payload.historyError = String(e.message || e);
  }

  const riga = dati.riga;   // la stessa riga usata da sincronizza()
  riga.set("payload", payload);
  riga.set("builtAt", new Date());
  await riga.save(null, { useMasterKey: true }).catch(() => {});
  return payload;
}

/**
 * Il lavoro pianificato: ogni 4 minuti, con o senza utenti collegati.
 * Tiene fresche le tre tabelle leggibili E la risposta pronta — cosi' le
 * chiamate dell'app diventano quasi sempre un servizio dalla cache, e la
 * fonte riceve un ritmo costante e prevedibile (cookbook R6).
 * Il ritmo di 4 minuti tiene l'If-Modified-Since (ultimaSync - 1 min di
 * margine) entro i 5 minuti che il cookbook prescrive (R1).
 */
Parse.Cloud.job("aggiorna", async (request) => {
  const payload = await giroCompleto(null);
  request.message("aggiornato: " + payload.syncMode +
    ", eventi " + payload.events.length +
    ", storico " + (payload.history || []).length);
});

// ------------------------------------------------- revoca a mano (Gottardo Dati)

/**
 * Mette o toglie la revoca su un avviso, dall'app Gottardo Dati.
 *
 * Esiste come funzione e non come scrittura diretta perche' la tabella Avvisi
 * ha le scritture chiuse alla master key, che nell'app non c'e' e non deve
 * esserci. Qui la master key resta sul server e il client puo' fare solo
 * questa cosa, su questo campo.
 *
 * Il codice non e' un segreto — la chiave client sta dentro un'app, quindi e'
 * leggibile da chiunque la scompatti — ma impedisce che una chiamata a caso
 * o dimenticata cambi lo stato senza che qualcuno l'abbia voluto. Stessa
 * logica del vecchio `overrideCode` delle scavalcature manuali.
 */
const CODICE_REVOCA = "gottardo-manuale-2026";

Parse.Cloud.define("revoca", async (request) => {
  const { situationId, revocato, codice } = request.params || {};
  if (codice !== CODICE_REVOCA) throw new Error("codice non valido");
  if (!situationId) throw new Error("manca situationId");

  const riga = await rigaAvviso(situationId);
  if (!riga.get("situationId")) throw new Error("avviso sconosciuto: " + situationId);

  // Assente o true = si mette la revoca; solo un false esplicito la toglie.
  const attiva = revocato !== false;
  riga.set("revocato", attiva);
  if (attiva) {
    // "La data del momento": l'istante in cui la revoca e' stata messa a
    // mano, non il versionTime dell'avviso — sono due cose diverse e la
    // seconda direbbe il falso.
    riga.set("revocatoAlle", new Date());
  } else {
    riga.unset("revocatoAlle");
  }
  // Chi l'ha revocato: la fonte o noi. In una tabella di dati questa
  // distinzione vale quanto il dato.
  riga.set("revocaManuale", attiva);
  await riga.save(null, { useMasterKey: true });

  // E ora la parte che conta davvero: il magazzino. La tabella Avvisi e' una
  // fotografia; il magazzino e' cio' che l'app mostra agli utenti. Correggere
  // solo la fotografia lascerebbe l'avviso a schermo sui telefoni.
  // Il magazzino: e' da li' che l'app pesca quello che mostra agli utenti,
  // quindi correggere la sola tabella lascerebbe l'avviso a schermo.
  //
  // La rimozione vale UNA VOLTA e non viene ricordata. Se al giro successivo
  // la fonte ripubblica quella situazione, R3 la rimette e l'avviso torna —
  // ed e' giusto cosi': significa che la coda c'e' davvero, e la fonte ha
  // l'ultima parola sulla nostra correzione. Il pulsante serve a tappare un
  // messaggio di revoca che non ci e' arrivato, non a zittire la fonte.
  const q = new Parse.Query(STATO_CLASS);
  q.descending("updatedAt");
  const rigaStato = await q.first({ useMasterKey: true });
  let toltoDalMagazzino = false;
  if (rigaStato && attiva) {
    const stato = rigaStato.get("stato") || {};
    const mag = daMagazzinoSalvato(stato.magazzino);
    toltoDalMagazzino = !!mag[situationId];
    delete mag[situationId];
    stato.magazzino = Object.values(mag);   // elenco, come in sincronizza()
    rigaStato.set("stato", stato);
  }
  if (rigaStato) {
    // Anche la risposta gia' pronta va buttata, altrimenti per un minuto —
    // finche' non scade la cache — l'app continua a servire lo schermo
    // vecchio, con dentro l'avviso appena revocato. Togliendo la revoca vale
    // lo stesso: si vuole vedere subito la situazione tornare.
    rigaStato.unset("builtAt");
    await rigaStato.save(null, { useMasterKey: true });
  }

  return {
    situationId,
    revocato: attiva,
    revocatoAlle: attiva ? riga.get("revocatoAlle").toISOString() : null,
    toltoDalMagazzino,
  };
});

// ------------------------------------------------- il ripasso
//
// Registra il lavoro `ripassa` per i lanci a mano. Il ripasso periodico
// invece NON e' un lavoro suo: gira dentro `aggiorna`, e la decisione la
// prende `ripasso.tocca()` dentro sincronizza — vedi il file per il perche'.
ripasso.registraLavoro(giroCompleto);
