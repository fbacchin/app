// Prove della pagina. Uso: node sito/prova_sito.mjs
import assert from "node:assert/strict";
import { mappaValida, momenti, quanto } from "./logica.mjs";

assert.ok(mappaValida("2026-10-15-1800-apple.svg"));
for (const cattivo of ["../README.md", "2026-10-15-1800-apple.svg/../../uso.json", "dati/apple-2026-10.csv", "2026-10-15-1800-altro.svg"])
  assert.ok(!mappaValida(cattivo), cattivo);

const m = momenti(["2026-10-15-1745-apple.svg", "2026-10-15-1800-tomtom.svg", "2026-10-15-1800-apple.svg", "appunti.txt"]);
assert.deepEqual(m.map((x) => x.quando), ["2026-10-15 18:00", "2026-10-15 17:45"]);
assert.deepEqual(m[0].file, { apple: "2026-10-15-1800-apple.svg", tomtom: "2026-10-15-1800-tomtom.svg" });

assert.deepEqual([0, 1, 3, 4, 6, 11].map(quanto), ["adesso", "15 minuti fa", "45 minuti fa", "1 h fa", "1 h 30 min fa", "2 h 45 min fa"]);
import { FONTI } from "./logica.mjs";
assert.deepEqual(FONTI.map(([f]) => f), ["apple", "tomtom", "google"]);   // Waze tolto dal pannello
console.log("prove della pagina: ok");

import { leggiDettaglio, tabelle } from "./logica.mjs";
const intestazione = "ora,ora_utc,misura,con_traffico_s,senza_traffico_s,distanza_m,esito\n";
const apple = leggiDettaglio(intestazione +
  "2026-10-15 22:30,2026-10-15T20:30Z,NS Erstfeld-Biasca tunnel,2955,2877,75432,ok\n" +
  "2026-10-15 22:30,2026-10-15T20:30Z,NS Erstfeld-Biasca passo,4291,3976,90007,ok\n" +
  "2026-10-15 22:15,2026-10-15T20:15Z,NS Erstfeld-Biasca tunnel,2930,2877,75432,ok\n" +
  "2026-10-15 22:15,2026-10-15T20:15Z,NS Erstfeld-Bia");   // ultima riga tagliata: si scarta
assert.equal(apple.length, 3);
const google = leggiDettaglio(intestazione +
  "2026-10-15 22:00,2026-10-15T20:00Z,NS Erstfeld-Biasca tunnel,2922,2914,75536,ok\n" +
  "2026-10-15 22:00,2026-10-15T20:00Z,NS Erstfeld-Biasca passo,6150,6084,105891,percorso diverso\n" +
  "2026-10-15 21:00,2026-10-15T19:00Z,NS Erstfeld-Biasca tunnel,2900,2914,75536,ok\n");
const t = tabelle({ apple, google });
assert.deepEqual(t.map((x) => x.quando), ["2026-10-15 22:30", "2026-10-15 22:15", "2026-10-15 22:00", "2026-10-15 21:00"]);
const eb = t[0].tratte[0];
assert.equal(eb.nome, "Erstfeld → Biasca");
assert.equal(t[0].tratte.length, 6);
assert.deepEqual(t[0].separate.map((g) => g.righe.length), [4, 4]);
assert.equal(t[0].separate[0].righe[0].fonti.apple.cella, null);            // nessuna riga di Erstfeld–Amsteg nel campione
assert.deepEqual(eb.fonti.apple.galleria, { esito: "ok", totale: 49, ritardo: 1, km: 75 });
assert.deepEqual(eb.fonti.apple.passo, { esito: "ok", totale: 72, ritardo: 5, km: 90 });
assert.equal(eb.fonti.apple.differenza, 23);
assert.equal(eb.fonti.google.ora, "2026-10-15 22:00");                     // Google: ultima misura dell'ora
assert.deepEqual(eb.fonti.google.passo, { esito: "percorso diverso", km: 106 });
assert.equal(eb.fonti.google.differenza, null);
assert.equal(t[1].tratte[0].fonti.apple.passo, null);                      // nessuna riga: cella vuota
assert.equal(t[3].tratte[0].fonti.apple.ora, null);                        // Apple non c'era alle 21:00
const sep = tabelle({ apple: leggiDettaglio(intestazione + "2026-10-16 20:00,2026-10-16T18:00Z,SN Faido-Airolo,900,780,18964,ok\n") });
assert.equal(sep[0].separate[1].righe[1].nome, "Faido → Airolo");
assert.deepEqual(sep[0].separate[1].righe[1].fonti.apple.cella, { esito: "ok", totale: 15, ritardo: 2, km: 19 });
// 19.10: passo verso nord con la CUPRA, solo dove c'è
const cu = tabelle({ apple: leggiDettaglio(intestazione +
  "2026-10-19 16:00,2026-10-19T14:00Z,SN Faido-Amsteg tunnel,2400,2300,49800,ok\n" +
  "2026-10-19 16:00,2026-10-19T14:00Z,SN Faido-Amsteg passo,3720,3300,64400,ok\n" +
  "2026-10-19 16:00,2026-10-19T14:00Z,SN Faido-Amsteg passo CUPRA,3120,3300,64400,ok\n") });
const fa = cu[0].tratte.find((t) => t.nome === "Faido → Amsteg").fonti.apple;
assert.deepEqual([fa.passo.totale, fa.cupra.totale, fa.differenza, fa.differenzaCupra], [62, 52, 22, 12]);
assert.equal(cu[0].tratte.find((t) => t.nome === "Amsteg → Faido").fonti.apple.cupra, null);   // verso sud non c'è
console.log("prove della tabella: ok");
