// Prova di direzione e imbocco letti dalla fonte invece che indovinati.
//
// Non ci sono testi inventati: si carica una risposta VERA del feed
// (feed.campione.xml, archivio del 03.08.2026) e si guarda cosa dice il
// codice nuovo sulle situazioni del corridoio. Le attese sono scritte a mano
// leggendo i messaggi, uno per uno.

const fs = require("fs");
const path = require("path");

class FakeObject {
  constructor(cls) { this.className = cls; this.attributes = {}; }
  set(k, v) { this.attributes[k] = v; } get(k) { return this.attributes[k]; }
  async save() { return this; }
}
class FakeQuery {
  constructor(cls) { this.className = cls; }
  equalTo() { return this; } greaterThanOrEqualTo() { return this; }
  lessThan() { return this; } descending() { return this; } ascending() { return this; }
  select() { return this; } limit() { return this; }
  async find() { return []; } async first() { return undefined; }
}
global.Parse = { Object: FakeObject, Query: FakeQuery, Cloud: { define() {}, job() {} } };
global.Parse.Object.saveAll = async () => {};
global.Parse.Object.destroyAll = async () => {};

const sorgente = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");
// `require` come lo vede il Cloud Code: i percorsi relativi partono da
// cloud/, non da qui, altrimenti il require di ripasso.js non si risolve.
const richiedi = (p) => require(p.startsWith(".") ? require("path").join(__dirname, "..", p) : p);
const m = new Function("require", sorgente + `
;return { estraiSituazioni, direzioneDi, direzioneDalTesto, allImbocco,
          etichettaDirezione, costruisciPayload, stradaDi, sullaAutostrada,
          attesaDi, queueKm, waitMinutes,
          PUNTI_LATO_URI, PUNTI_LATO_TICINO };`)(richiedi);

let ok = 0, ko = 0;
function prova(atteso, avuto, titolo) {
  const a = JSON.stringify(atteso), b = JSON.stringify(avuto);
  if (a === b) { ok++; console.log("  OK   " + titolo); }
  else { ko++; console.log("  KO   " + titolo + "\n       atteso " + a + ", avuto " + b); }
}

// ---------------------------------------------------------------- il feed
// Il feed VERO d'archivio, 1037 situazioni: le prove sulla direzione si fanno
// sui messaggi che la fonte ha davvero mandato, non su XML inventati. Sta
// compresso perche' in chiaro sono 13 MB.
const xml = require("zlib")
  .gunzipSync(fs.readFileSync(path.join(__dirname, "feed.campione.xml.gz")))
  .toString("utf8");
const { situazioni } = m.estraiSituazioni(xml);
const di = (id) => situazioni[id];
const dir = (id) => {
  const s = di(id);
  return s ? m.direzioneDi(s, (s.texts.it || "").toLowerCase()) : "MANCA";
};
const imbocco = (id, d) => {
  const s = di(id);
  return s ? m.allImbocco(s, d, (s.texts.it || "").toLowerCase()) : "MANCA";
};

console.log("\n— la direzione arriva dal campo della fonte —");
// "A2 Chiasso -> S. Gottardo": da sud verso nord. <alertCDirectionCoded>positive
prova("north", dir("situation.542842.1"), "542842 Chiasso -> Gottardo = nord (positive)");
// "A2 S. Gottardo -> Chiasso": verso sud. negative
prova("south", dir("situation.509979.1"), "509979 Gottardo -> Chiasso = sud (negative)");
prova("south", dir("situation.604725.1"), "604725 Gottardo -> Chiasso = sud (negative)");
prova("north", dir("situation.604727.1"), "604727 Chiasso -> Gottardo = nord (positive)");
// "A2 Lucerna -> S. Gottardo": chi parte da Lucerna scende. negative
prova("south", dir("situation.555401.1"), "555401 Lucerna -> Gottardo = sud (negative)");

console.log("\n— 'both' e' una risposta: il messaggio vale nei due sensi —");
prova("both", di("situation.546704.1").direzioneFonte, "546704 H2 Airolo <-> Flüelen: la fonte dice both");
prova(null, dir("situation.546704.1"), "  e quindi la direzione resta vuota");
prova("entrambe", m.etichettaDirezione(null, di("situation.546704.1")),
      "  in tabella si legge 'entrambe', non 'non indicata'");
prova("non indicata", m.etichettaDirezione(null, { texts: {} }),
      "una situazione senza il campo invece e' 'non indicata'");

console.log("\n— quello che i marcatori nel testo non vedevano —");
// H2 Airolo <-> Göschenen: nessun marcatore lo riconosce, la fonte lo dichiara.
prova(null, m.direzioneDalTesto(
  (di("situation.639174.1").texts.it || "").toLowerCase()), "639174 col testo: non so");
prova("both", di("situation.639174.1").direzioneFonte, "639174 con la fonte: both");
// 342097: galleria, "Chiasso -> S. Gottardo" — qui il marcatore c'era gia'
prova("north", m.direzioneDalTesto(
  (di("situation.342097.1").texts.it || "").toLowerCase()), "342097 col testo: nord");
prova("north", dir("situation.342097.1"), "342097 con la fonte: nord — d'accordo");

console.log("\n— l'imbocco viene dai punti, non dai nomi nella frase —");
// 555401: "tra Svincolo Wassen E Svincolo Göschenen" = 10458 + 10460, lato Uri.
prova(["10458", "10460"], di("situation.555401.1").punti.sort(), "555401: Wassen + Göschenen");
prova(true, imbocco("situation.555401.1", "south"), "  e' l'imbocco di chi va a sud");
prova(false, imbocco("situation.555401.1", "north"), "  non e' quello di chi va a nord");
// 542842: "tra Svincolo Quinto E Area di dosaggio Airolo" = 10461 + 14913, lato Ticino.
prova(["10461", "14913"], di("situation.542842.1").punti.sort(), "542842: Quinto + dosaggio Airolo");
prova(true, imbocco("situation.542842.1", "north"), "  e' l'imbocco di chi va a nord");
prova(false, imbocco("situation.542842.1", "south"), "  non e' quello di chi va a sud");
// 639408: "tra Svincolo Göschenen E Svincolo Airolo" — tocca tutti e due i lati.
prova(true, imbocco("situation.639408.1", "south"), "639408 Göschenen+Airolo: vale a sud");
prova(true, imbocco("situation.639408.1", "north"), "  e vale anche a nord");

console.log("\n— senza codici noti si torna ai nomi —");
const vecchia = {   // com'e' salvata nel magazzino da prima del 03.08.2026
  id: "situation.999.1", type: "AbnormalTraffic", versionTime: new Date().toISOString(),
  revocata: false,
  texts: { it: "Approvato: A2 Luzern -> S. Gottardo tra Svincolo autostradale Wassen E Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] 8 Causa: traffico congestionato Aggiunta 1: ritardi No. [min] 80" },
};
const bassa = vecchia.texts.it.toLowerCase();
prova("south", m.direzioneDi(vecchia, bassa), "niente campo: la direzione torna dal testo");
prova(true, m.allImbocco(vecchia, "south", bassa), "niente punti: l'imbocco torna dai nomi");
prova(false, m.allImbocco(vecchia, "north", bassa), "  e resta dalla parte giusta");

console.log("\n— le code finiscono sulla scheda giusta —");
const magazzino = {};
for (const id of ["situation.555401.1", "situation.542842.1"]) {
  // 555401 e' una revoca nell'archivio: qui interessa il piazzamento, non lo stato
  magazzino[id] = Object.assign({}, situazioni[id],
    { revocata: false, versionTime: new Date().toISOString() });
}
const p = m.costruisciPayload(magazzino, {}, "incrementale", 2, Date.now());
prova(1, p.south.km, "la coda con Wassen/Göschenen sta sulla scheda sud");
prova(1, p.north.km, "quella con Quinto/Airolo sulla scheda nord");
prova(["north", "south"], p.events.map((e) => e.direction).sort(), "e i due avvisi hanno la loro direzione");

console.log("\n— i minuti stimati dai km quando la fonte non li scrive —");
// Testo VERO del 03.08.2026: la coda al portale nord con i km e senza i minuti.
const senzaMinuti = "Approvato: A2 Luzern -> S. Gottardo tra Svincolo autostradale Erstfeld E Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] 10 Causa: traffico congestionato";
const conMinuti = "Approvato: A2 Chiasso -> S. Gottardo tra Svincolo autostradale Quinto E Parcheggio Area di dosaggio Airolo Situazione: colonna lunghezza [km] 5 Causa: traffico congestionato Aggiunta 1: ritardi No. [min] 50";
const cantiere = "Approvato: A2 S. Gottardo -> Chiasso tra Svincolo autostradale Quinto E Svincolo autostradale Faido Situazione: problemi di traffico cantiere, lunghezza [km] 1.6 Limitazione del traffico: corsia d'emergenza chiusa";
prova(null, m.waitMinutes(senzaMinuti), "il testo i minuti non ce li ha");
prova({ minuti: 100, stimata: true },
      m.attesaDi("AbnormalTraffic", senzaMinuti, m.queueKm(senzaMinuti)), "10 km -> 100 min, segnati come stima");
prova({ minuti: 50, stimata: false },
      m.attesaDi("AbnormalTraffic", conMinuti, m.queueKm(conMinuti)), "se i minuti ci sono si prendono quelli");
prova({ minuti: null, stimata: false },
      m.attesaDi("MaintenanceWorks", cantiere, m.queueKm(cantiere)), "un cantiere non diventa un'attesa");

const oraIso = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
const magStima = {
  "situation.777.1": {
    id: "situation.777.1", type: "AbnormalTraffic", versionTime: oraIso, revocata: false,
    direzioneFonte: "negative", punti: ["10455", "10460"], texts: { it: senzaMinuti },
  },
};
const ps = m.costruisciPayload(magStima, {}, "incrementale", 1, Date.now());
prova(10, ps.south.km, "la scheda sud prende i km");
prova(100, ps.south.wait, "e i minuti stimati, invece del trattino");
prova(true, ps.events[0].waitStimato, "l'evento dice che quei minuti sono una stima");

console.log("\n— 'non indicato' non e' 'entrambe' —");
prova(true, ps.events[0].directionStated, "direzione dichiarata dalla fonte");
const magMuto = {
  "situation.778.1": {
    id: "situation.778.1", type: "MaintenanceWorks", versionTime: oraIso, revocata: false,
    texts: { it: "Approvato: A2 Göschenen: raccordo autostradale chiuso in entrata" },
  },
};
const pm = m.costruisciPayload(magMuto, {}, "incrementale", 1, Date.now());
prova(null, pm.events[0].direction, "senza direzione");
prova(false, pm.events[0].directionStated, "e senza nemmeno il campo: il client dira' 'non indicato'");

console.log(`\n${ok}/${ok + ko}`);
process.exit(ko ? 1 : 0);
