// Prova di aggiornaTabelle senza toccare il database.
//
// Il corridoio di notte e' sgombro: il magazzino e' vuoto e il ciclo degli
// Avvisi non scrive niente, quindi il codice nuovo non si vedrebbe girare
// fino alla prossima coda vera. Qui si carica main.js con un Parse finto e
// gli si danno in pasto situazioni costruite a mano: la coda con km e minuti,
// quella senza direzione, e la revoca — che il magazzino ha gia' fatto
// sparire e che deve comparire lo stesso in tabella.

const fs = require("fs");
const path = require("path");

// --- Parse finto: registra cosa verrebbe scritto, non scrive niente ---
const tabelle = { Attuale: [], Storico: [], Avvisi: [], Chiamate: [] };

class FakeObject {
  constructor(cls) { this.className = cls; this.attributes = {}; this._nuovo = true; }
  set(k, v) { this.attributes[k] = v; }
  get(k) { return this.attributes[k]; }
  async save() {
    if (this._nuovo) { tabelle[this.className].push(this); this._nuovo = false; }
    return this;
  }
}

class FakeQuery {
  constructor(cls) { this.className = cls; this.filtri = []; }
  equalTo(k, v) { this.filtri.push((o) => o.attributes[k] === v); return this; }
  greaterThanOrEqualTo() { return this; }
  lessThan() { return this; }
  descending() { this.desc = true; return this; }
  ascending() { return this; }
  select() { return this; }
  limit() { return this; }
  async find() { return tabelle[this.className].filter((o) => this.filtri.every((f) => f(o))); }
  async first() { return (await this.find())[0]; }
}

global.Parse = {
  Object: FakeObject,
  Query: FakeQuery,
  Cloud: { define() {}, job() {} },
};
global.Parse.Object.saveAll = async (righe) => { for (const r of righe) await r.save(); };
global.Parse.Object.destroyAll = async () => {};

// --- si carica main.js e si pesca aggiornaTabelle ---
const sorgente = fs.readFileSync(
  path.join(__dirname, "..", "main.js"), "utf8");
// eval in uno scope suo: i nomi di main.js non devono scontrarsi con i nostri
// `require` come lo vede il Cloud Code: i percorsi relativi partono da
// cloud/, non da qui, altrimenti il require di ripasso.js non si risolve.
const richiedi = (p) => require(p.startsWith(".") ? require("path").join(__dirname, "..", p) : p);
const modulo = new Function("require",
  sorgente + "\n;return { aggiornaTabelle, costruisciPayload };")(richiedi);
const aggiornaTabelle = modulo.aggiornaTabelle;
const costruisciPayload = modulo.costruisciPayload;
const applicaRevocheManuali = modulo.applicaRevocheManuali; // deve essere undefined: la revoca a mano non e piu appiccicosa

// --- le situazioni finte ---
const ora = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
const prima = new Date(Date.now() - 9 * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");

// I testi sono presi PARI PARI dal feed (archivio del 02.08.2026): il primo
// tentativo con testi inventati falliva perche' avevo messo mezza frase fra
// "colonna" e "lunghezza", mentre il VMZ scrive "colonna lunghezza [km] 2.0".
// Le regex sono tarate sul formato vero: le prove vanno fatte su quello.
const coda = {
  id: "situation.999001.1.1.1", type: "AbnormalTraffic", versionTime: prima, revocata: false,
  texts: {
    it: "Approvato: A2 Luzern -> S. Gottardo tra Svincolo autostradale Wassen E Svincolo autostradale Göschenen Situazione: colonna lunghezza [km] 2.0 Causa: traffico congestionato Aggiunta 1: ritardi No. [min] 20",
    de: "Freigegeben: A2 Luzern -> Gotthard zwischen Anschluss Wassen und Anschluss Göschenen Sachlage: Stau Länge [km] 2.0",
    fr: "Approuvé: A2 Lucerne -> Gothard entre jonction Wassen et jonction Göschenen Situation: bouchon longueur [km] 2.0",
  },
};
const cantiere = {
  id: "situation.999002.1.1.1", type: "MaintenanceWorks", versionTime: prima, revocata: false,
  texts: {
    it: "A2 Göschenen -> Airolo: lavori di manutenzione nella galleria del San Gottardo",
    de: "A2 Göschenen -> Airolo: Bauarbeiten im Gotthard-Strassentunnel",
    fr: "A2 Göschenen -> Airolo: travaux dans le tunnel du Saint-Gothard",
  },
};
const revocata = {
  id: "situation.999003.1.1.1", type: "AbnormalTraffic", versionTime: ora, revocata: true,
  texts: {
    it: "Revocato: A2 Chiasso -> S. Gottardo tra Svincolo autostradale Quinto E Parcheggio Area di dosaggio Airolo Situazione: colonna lunghezza [km] 1.0 Causa: traffico congestionato",
    de: "Aufgehoben: A2 Chiasso -> Gotthard zwischen Anschluss Quinto und Parkplatz Dosierstelle Airolo",
    fr: "Révoqué: A2 Chiasso -> Gothard entre jonction Quinto et parking zone de dosage Airolo",
  },
};

// magazzino = cio' che e' vivo (la revoca e' gia' stata tolta da R4)
const magazzino = { [coda.id]: coda, [cantiere.id]: cantiere };
// situazioni = cio' che il feed ha mandato IN QUESTO GIRO
const situazioni = { [revocata.id]: revocata };   // la coda non e' stata ripubblicata

const payload = costruisciPayload(magazzino, {}, "incrementale", 1234, Date.now());

// Il cantiere lo revochiamo A MANO dall'app Gottardo Dati: la riga esiste
// gia' in tabella, revocata, mentre la situazione e' ancora VIVA nel
// magazzino. E' il caso in cui il lavoro pianificato potrebbe rimettere
// `revocato: false` e cancellare in silenzio la correzione dell'utente.
const rigaManuale = new FakeObject("Avvisi");
rigaManuale.set("situationId", cantiere.id);
rigaManuale.set("revocato", true);
rigaManuale.set("revocaManuale", true);
rigaManuale.set("revocatoAlle", new Date());
rigaManuale.set("primaVista", new Date(Date.parse(prima) - 3600e3));
tabelle.Avvisi.push(rigaManuale);
rigaManuale._nuovo = false;
const primaVistaOriginale = rigaManuale.get("primaVista").getTime();

(async () => {
  await aggiornaTabelle(payload, magazzino, situazioni);

  console.log("=== payload: stato delle direzioni ===");
  console.log("sud :", JSON.stringify(payload.south), " fonte:", payload.sources.south);
  console.log("nord:", JSON.stringify(payload.north), " fonte:", payload.sources.north);

  console.log("\n=== Attuale ===");
  for (const r of tabelle.Attuale) {
    console.log(r.get("direzione"), "|", r.get("km"), "km |", r.get("attesa"), "min |", r.get("stato"));
  }

  console.log("\n=== Storico ===");
  for (const r of tabelle.Storico) {
    console.log(r.get("campione").toISOString(),
      "| sud", r.get("sudKm"), r.get("sudMin"), "tenuto:", r.get("sudTenuto"),
      "| nord", r.get("nordKm"), r.get("nordMin"), "tenuto:", r.get("nordTenuto"));
  }

  console.log("\n=== Avvisi ===");
  for (const r of tabelle.Avvisi) {
    console.log(r.get("situationId"), "|", r.get("direzione"),
      "| km", r.get("km"), "| attesa", r.get("attesa"),
      "| revocato", r.get("revocato"),
      "| primaVista", r.get("primaVista") && r.get("primaVista").toISOString().slice(11, 19),
      "| ultimaVista", r.get("ultimaVista") && r.get("ultimaVista").toISOString().slice(11, 19));
    console.log("   it:", (r.get("testo") || "").slice(0, 60));
    console.log("   de:", (r.get("testoDe") || "").slice(0, 40), "| fr:", (r.get("testoFr") || "").slice(0, 40));
  }

  // --- controlli ---
  console.log("\n=== controlli ===");
  const avviso = (id) => tabelle.Avvisi.find((r) => r.get("situationId") === id);
  const prove = [
    ["la coda finisce nello stato sud (2 km, 20 min)", payload.south.km === 2 && payload.south.wait === 20],
    ["il nord resta vuoto", payload.north.km === null && payload.north.wait === null],
    ["il campione sud e' marcato TENUTO (non ripubblicata in questo giro)", tabelle.Storico[0].get("sudTenuto") === true],
    ["il campione nord non e' tenuto (non c'e' niente da tenere)", tabelle.Storico[0].get("nordTenuto") === false],
    ["l'avviso di coda e' in tabella", !!avviso(coda.id)],
    ["il cantiere e' in tabella", !!avviso(cantiere.id)],
    ["la REVOCA e' in tabella anche se non e' nel magazzino", !!avviso(revocata.id)],
    ["la revoca e' marcata revocata", avviso(revocata.id) && avviso(revocata.id).get("revocato") === true],
    ["la revoca ha l'ora della revoca", !!(avviso(revocata.id) && avviso(revocata.id).get("revocatoAlle"))],
    ["la coda NON e' marcata revocata", avviso(coda.id) && avviso(coda.id).get("revocato") === false],
    ["km e minuti estratti dal testo dell'avviso", avviso(coda.id) && avviso(coda.id).get("km") === 2 && avviso(coda.id).get("attesa") === 20],
    ["la revoca ha km e attesa esplicitamente nulli, non 'undefined'",
      avviso(revocata.id) && avviso(revocata.id).get("km") === null && avviso(revocata.id).get("attesa") === null],
    ["direzione riconosciuta", avviso(coda.id) && avviso(coda.id).get("direzione") === "sud"],
    ["tedesco presente", !!(avviso(coda.id) && avviso(coda.id).get("testoDe"))],
    ["francese presente", !!(avviso(coda.id) && avviso(coda.id).get("testoFr"))],
    ["il cantiere non ha km ne' attesa", avviso(cantiere.id) && avviso(cantiere.id).get("km") === null],
    // La correzione a mano deve sopravvivere al giro successivo del lavoro
    // pianificato, altrimenti il pulsante nell'app e' una finzione.
    ["la REVOCA A MANO sopravvive al giro pianificato",
      avviso(cantiere.id) && avviso(cantiere.id).get("revocato") === true],
    ["resta marcata come manuale", avviso(cantiere.id) && avviso(cantiere.id).get("revocaManuale") === true],
    ["l'ora della revoca a mano non viene sovrascritta",
      avviso(cantiere.id) && !!avviso(cantiere.id).get("revocatoAlle")],
    ["primaVista non viene riscritta su una riga che esisteva gia'",
      avviso(cantiere.id) && avviso(cantiere.id).get("primaVista").getTime() === primaVistaOriginale],
    ["ma i dati dell'avviso restano aggiornati (ultimaVista avanza)",
      avviso(cantiere.id) && avviso(cantiere.id).get("ultimaVista").getTime() > primaVistaOriginale],
    ["non si sono create righe doppie per lo stesso id",
      tabelle.Avvisi.filter((r) => r.get("situationId") === cantiere.id).length === 1],
  ];

  // --- la revoca a mano contro il magazzino ---
  //
  // Vale UNA VOLTA: toglie la situazione adesso, e non viene ricordata. Se
  // la fonte la ripubblica, torna — perche' significa che la coda c'e'
  // davvero. Il pulsante tappa una revoca non arrivata, non zittisce la
  // fonte. Qui si riproduce cio' che fa la funzione `revoca` sul magazzino.
  const magazzinoDopoRevoca = { [coda.id]: coda, [cantiere.id]: cantiere };
  delete magazzinoDopoRevoca[coda.id];
  prove.push(["la revoca a mano toglie la situazione dal magazzino", !magazzinoDopoRevoca[coda.id]]);
  prove.push(["e non tocca le altre", !!magazzinoDopoRevoca[cantiere.id]]);

  // Giro successivo: la fonte ripubblica lo stesso id. R3 sostituisce per id
  // sul magazzino rimasto, senza consultare nessun elenco di revoche a mano.
  const giroDopo = Object.assign({}, magazzinoDopoRevoca);
  giroDopo[coda.id] = coda;   // <- quello che fa R3 in sincronizza()
  prove.push(["se la fonte la ripubblica, la situazione TORNA (la fonte ha l'ultima parola)",
    !!giroDopo[coda.id]]);

  // E non deve essere rimasto in giro nessun elenco di revoche appiccicose.
  prove.push(["non esiste piu' un elenco di revoche a mano da riapplicare",
    typeof applicaRevocheManuali === "undefined"]);
  prove.push(["ne' un campo revocheManuali nello stato salvato",
    !fs.readFileSync(path.join(__dirname, "..", "main.js"), "utf8").includes("revocheManuali")]);
  let ok = 0;
  for (const [nome, esito] of prove) {
    console.log(esito ? "  OK  " : "  NO  ", nome);
    if (esito) ok++;
  }
  console.log(`\n${ok}/${prove.length}`);
  process.exit(ok === prove.length ? 0 : 1);
})();
