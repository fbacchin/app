// Prova delle correzioni a mano fatte da Gottardo Dati.
//
// Due storici, due strade diverse per correggerli, e un difetto possibile per
// ognuna. Sulla tabella `Storico` di Back4App: correggere una riga e lasciare
// in cache la risposta gia' pronta, cosi' che per un minuto l'app continui a
// servire il numero vecchio. Su `history.json` di GitHub: riserializzare il
// file col JSON di JavaScript, che scrive `2` dove Python scrive `2.0`, e
// consegnare cinquecento righe di diff spacciate per una correzione.
//
// La prova che conta e' l'ultima: il file vero d'archivio, riscritto senza
// toccarlo, deve tornare identico byte per byte.

const fs = require("fs");
const path = require("path");

process.env.OTD_KEY = "chiave-finta-per-le-prove";

const prove = [];
function ok(nome, esito) { prove.push([nome, !!esito]); }
function alza(nome, fn, pezzo) {
  try { fn(); ok(nome, false); }
  catch (e) { ok(nome + (pezzo ? " (" + pezzo + ")" : ""), String(e.message).includes(pezzo || "")); }
}

// --- Parse finto ----------------------------------------------------------
const tabelle = { Attuale: [], Storico: [], Avvisi: [], Chiamate: [], Stato: [] };
let contatore = 0;

class FakeObject {
  constructor(cls) {
    this.className = cls;
    this.attributes = {};
    this.id = "obj" + (++contatore);
    this._nuovo = true;
  }
  set(k, v) { this.attributes[k] = v; }
  get(k) { return this.attributes[k]; }
  unset(k) { delete this.attributes[k]; }
  async save() {
    if (this._nuovo) { tabelle[this.className].push(this); this._nuovo = false; }
    return this;
  }
  async destroy() {
    tabelle[this.className] = tabelle[this.className].filter((o) => o !== this);
    return this;
  }
}

class FakeQuery {
  constructor(cls) { this.className = cls; this.filtri = []; }
  equalTo(k, v) { this.filtri.push((o) => o.attributes[k] === v); return this; }
  greaterThanOrEqualTo() { return this; }
  lessThan() { return this; }
  descending() { return this; }
  ascending() { return this; }
  select() { return this; }
  limit() { return this; }
  async find() { return tabelle[this.className].filter((o) => this.filtri.every((f) => f(o))); }
  async first() { return (await this.find())[0]; }
  async get(id) {
    const trovato = tabelle[this.className].find((o) => o.id === id);
    if (!trovato) { const e = new Error("Object not found."); e.code = 101; throw e; }
    return trovato;
  }
}

const funzioni = {};
global.Parse = {
  Object: FakeObject,
  Query: FakeQuery,
  Cloud: { define(nome, fn) { funzioni[nome] = fn; }, job() {} },
};
global.Parse.Object.saveAll = async (righe) => { for (const r of righe) await r.save(); };
global.Parse.Object.destroyAll = async () => {};

// --- si carica main.js ----------------------------------------------------
const sorgente = fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8");
const richiedi = (p) => require(p.startsWith(".") ? path.join(__dirname, "..", p) : p);
const modulo = new Function("require", sorgente +
  "\n;return { correggiFileStorico, comeIlCollector, leggiValore };")(richiedi);
const { correggiFileStorico, comeIlCollector, leggiValore } = modulo;

// =========================================================================
// 1. Come si legge un valore che arriva dall'app
// =========================================================================
ok("vuoto vuol dire niente: e' cosi' che si cancella un numero",
   leggiValore("sudKm", "numero", "") === null);
ok("  e anche null", leggiValore("sudKm", "numero", null) === null);
ok("un intero resta intero", leggiValore("sudMin", "intero", "20") === 20);
ok("un intero arrotonda: i minuti non hanno decimali",
   leggiValore("sudMin", "intero", "20.6") === 21);
ok("un decimale resta decimale", leggiValore("sudKm", "numero", "2.5") === 2.5);
alza("una coda negativa non e' un dato: si rifiuta",
     () => leggiValore("sudKm", "numero", "-1"), "numero non negativo");
alza("e nemmeno una parola",
     () => leggiValore("sudKm", "numero", "due"), "numero non negativo");
ok("il booleano passa com'e'", leggiValore("sudTenuto", "booleano", true) === true);
ok("  e 'false' non diventa vero", leggiValore("sudTenuto", "booleano", false) === false);

// =========================================================================
// 2. history.json: la forma del collector, riprodotta esattamente
// =========================================================================
const CAMPIONI = [
  { time: "2026-08-04T20:00:00Z", southDelay: 0, northDelay: 20, southQueueKm: null, northQueueKm: 2.0 },
  { time: "2026-08-04T20:05:00Z", southDelay: 10, northDelay: 0, southQueueKm: 1.5, northQueueKm: null },
  { time: "2026-08-04T20:10:00Z", southDelay: 0, northDelay: 0, southQueueKm: null, northQueueKm: null,
    southHeld: true, northHeld: false },
];
const FILE = comeIlCollector(CAMPIONI);

ok("un km tondo si scrive 2.0 come lo scrive Python, non 2",
   FILE.includes('"northQueueKm": 2.0'));
ok("  e JSON.stringify da solo lo scriverebbe 2 — e' il motivo della funzione",
   JSON.stringify({ northQueueKm: 2.0 }).includes('"northQueueKm":2'));
ok("un km con la virgola resta com'e'", FILE.includes('"southQueueKm": 1.5'));
ok("i minuti restano interi", FILE.includes('"northDelay": 20'));
ok("il vuoto e' null, non zero", FILE.includes('"southQueueKm": null'));
ok("i booleani del 'tenuto' si scrivono per esteso",
   FILE.includes('"southHeld": true') && FILE.includes('"northHeld": false'));
ok("rileggerlo da' gli stessi campioni",
   JSON.stringify(JSON.parse(FILE)) === JSON.stringify(CAMPIONI));

// =========================================================================
// 3. Correggere un campione tocca solo le righe di quel campione
// =========================================================================
function righeDiverse(prima, dopo) {
  const a = prima.split("\n"), b = dopo.split("\n");
  let n = 0;
  for (let i = 0; i < Math.max(a.length, b.length); i++) if (a[i] !== b[i]) n++;
  return n;
}

const corretto = correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "modifica",
  { southQueueKm: "3", southDelay: "30" });
ok("la correzione scrive il campo chiesto", corretto.corretto.southQueueKm === 3);
ok("  e lo scrive nel file", corretto.testo.includes('"southQueueKm": 3.0'));
ok("  con la forma di Python anche se il numero e' tondo",
   !corretto.testo.includes('"southQueueKm": 3,'));
ok("i minuti nuovi ci sono", corretto.testo.includes('"southDelay": 30'));
ok("il diff e' di due righe, non dell'intero file",
   righeDiverse(FILE, corretto.testo) === 2);
ok("gli altri due campioni sono intatti",
   JSON.parse(corretto.testo)[0].northQueueKm === 2
   && JSON.parse(corretto.testo)[2].southHeld === true);

const svuotato = correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "modifica", { southQueueKm: "" });
ok("svuotare un km scrive null, non zero",
   JSON.parse(svuotato.testo)[1].southQueueKm === null);

const tolto = correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "cancella");
ok("cancellare toglie il campione", JSON.parse(tolto.testo).length === 2);
ok("  quello giusto", !tolto.testo.includes("20:05:00Z"));
ok("  e lascia gli altri nell'ordine di prima",
   JSON.parse(tolto.testo).map((c) => c.time).join(" ") ===
   "2026-08-04T20:00:00Z 2026-08-04T20:10:00Z");
ok("  e lo dice", tolto.cancellato === true);

alza("un campione che non c'e' non si corregge di nascosto",
     () => correggiFileStorico(FILE, "2026-08-04T23:59:00Z", "modifica", { southDelay: "1" }),
     "campione sconosciuto");
alza("una correzione senza campi e' un errore, non un commit vuoto",
     () => correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "modifica", {}),
     "nessun campo");
alza("un campo fuori elenco non passa: `time` e' l'identita' del campione",
     () => correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "modifica",
       { time: "2026-01-01T00:00:00Z" }), "nessun campo");
alza("una coda negativa si rifiuta anche qui",
     () => correggiFileStorico(FILE, "2026-08-04T20:05:00Z", "modifica", { southQueueKm: "-2" }),
     "numero non negativo");

// La guardia: se il file non ha la forma del collector, ci si ferma.
alza("un file riformattato blocca la scrittura invece di riscriverlo tutto",
     () => correggiFileStorico(JSON.stringify(CAMPIONI), "2026-08-04T20:05:00Z",
       "modifica", { southDelay: "1" }), "non ha piu' la forma");

// =========================================================================
// 4. Il file vero d'archivio: riscritto senza toccarlo, deve tornare identico
// =========================================================================
const VERO = path.join(__dirname, "..", "..", "data", "history.json");
if (fs.existsSync(VERO)) {
  const testo = fs.readFileSync(VERO, "utf8");
  ok("history.json vero: riscriverlo senza cambiarlo lo lascia identico byte per byte",
     comeIlCollector(JSON.parse(testo)) === testo);
  const campioni = JSON.parse(testo);
  const ultimo = campioni[campioni.length - 1].time;
  const dopo = correggiFileStorico(testo, ultimo, "modifica", { southDelay: "7" });
  ok("  e correggerne uno cambia una riga sola",
     righeDiverse(testo, dopo.testo) === 1);
} else {
  ok("history.json vero non e' in questa copia: prova saltata", true);
}

// =========================================================================
// 5. La tabella Storico su Back4App
// =========================================================================
async function tabella() {
  tabelle.Storico = [];
  tabelle.Stato = [];

  const riga = new Parse.Object("Storico");
  riga.set("campione", new Date("2026-08-04T20:05:00Z"));
  riga.set("sudKm", 1.5);
  riga.set("sudMin", 10);
  riga.set("nordKm", null);
  riga.set("nordMin", 0);
  await riga.save();

  const stato = new Parse.Object("Stato");
  stato.set("builtAt", new Date());
  await stato.save();

  const correggi = funzioni.correggiStorico;
  ok("la funzione correggiStorico e' registrata", typeof correggi === "function");

  await correggi({ params: { objectId: riga.id, codice: "gottardo-manuale-2026",
    valori: { sudKm: "2.5", sudMin: "25" } } })
    .then((r) => {
      ok("corregge i campi chiesti", riga.get("sudKm") === 2.5 && riga.get("sudMin") === 25);
      ok("  e risponde con quello che ha scritto", r.corretto.sudKm === 2.5);
    });
  ok("non tocca i campi non chiesti", riga.get("nordMin") === 0);
  ok("la riga resta marcata: un numero scritto da noi non si confonde con uno letto",
     riga.get("corretto") === true && riga.get("correttoAlle") instanceof Date);
  ok("il campione non si puo' spostare nel tempo",
     riga.get("campione").toISOString() === "2026-08-04T20:05:00.000Z");
  ok("la risposta in cache viene buttata, altrimenti l'app serve il numero vecchio",
     tabelle.Stato[0].get("builtAt") === undefined);

  await correggi({ params: { objectId: riga.id, codice: "gottardo-manuale-2026",
    valori: { sudKm: "" } } });
  ok("svuotare un km lo toglie del tutto", riga.get("sudKm") === undefined);

  let errore = null;
  await correggi({ params: { objectId: riga.id, codice: "sbagliato", valori: { sudKm: "1" } } })
    .catch((e) => { errore = e.message; });
  ok("senza il codice non si scrive niente", errore === "codice non valido");
  ok("  e il valore e' rimasto quello di prima", riga.get("sudKm") === undefined);

  errore = null;
  await correggi({ params: { objectId: riga.id, codice: "gottardo-manuale-2026", valori: {} } })
    .catch((e) => { errore = e.message; });
  ok("una correzione senza campi non marca la riga come corretta", /nessun campo/.test(errore));

  errore = null;
  await correggi({ params: { objectId: "non-esiste", codice: "gottardo-manuale-2026",
    valori: { sudKm: "1" } } }).catch((e) => { errore = e.message; });
  ok("una riga che non c'e' da' errore", /not found/i.test(errore || ""));

  tabelle.Stato[0].set("builtAt", new Date());
  const esito = await correggi({ params: { objectId: riga.id, codice: "gottardo-manuale-2026",
    azione: "cancella" } });
  ok("cancellare toglie la riga dalla tabella", tabelle.Storico.length === 0);
  ok("  e dice quale campione era", esito.campione === "2026-08-04T20:05:00.000Z");
  ok("  e butta anche lei la cache", tabelle.Stato[0].get("builtAt") === undefined);

  ok("la funzione storicoGitHub e' registrata", typeof funzioni.storicoGitHub === "function");
  let senzaToken = null;
  await funzioni.storicoGitHub({ params: { codice: "gottardo-manuale-2026", azione: "leggi" } })
    .catch((e) => { senzaToken = e.message; });
  ok("senza GH_TOKEN lo dice invece di provare e prendersi un 404",
     /GH_TOKEN assente/.test(senzaToken || ""));
}

tabella().then(() => {
  const n = prove.filter(([, e]) => e).length;
  console.log("=== correzioni a mano: Storico e history.json ===");
  for (const [nome, esito] of prove) console.log(esito ? "  OK  " : "  NO  ", nome);
  console.log("\n" + n + "/" + prove.length);
  process.exit(n === prove.length ? 0 : 1);
});
