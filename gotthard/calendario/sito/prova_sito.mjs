// Prove della logica del calendario: node prova_sito.mjs
import assert from "node:assert/strict";
import { valida, unisci, base64, daBase64 } from "./logica.mjs";

const proposta = [
  { data: "2026-12-19", direzione: "south", livello: "molto critico", motivi: [{ tipo: "festa", festa: "pasqua" }] },
  { data: "2026-12-20", direzione: "south", livello: "critico", motivi: [{ tipo: "alta_stagione", regioni: 12 }] },
];

// correzioni ammesse e rifiutate
assert.deepEqual(valida({ south: { "2026-12-20": "molto" } }), { south: { "2026-12-20": "molto" }, north: {} });
assert.throws(() => valida({ east: {} }), /direzione/);
assert.throws(() => valida({ south: { "2026-13-40": "molto" } }), /data/);
assert.throws(() => valida({ south: { "2026-12-20": "rosso" } }), /livello/);
assert.throws(() => valida(null), /mancanti/);

// unione
const c = unisci(proposta, { south: { "2026-12-19": "normale", "2026-12-20": "molto", "2026-12-24": "critico" }, north: {} },
                 new Date("2026-11-08T12:00:00Z"));
assert.equal(c.pubblicato, "2026-11-08T12:00:00Z");
assert.deepEqual(c.giorni.map(g => [g.data, g.livello]), [["2026-12-20", "molto critico"], ["2026-12-24", "critico"]]);
assert.deepEqual(c.giorni[0].motivi, [{ tipo: "alta_stagione", regioni: 12 }], "i motivi della proposta restano");
assert.deepEqual(c.giorni[1].motivi, [{ tipo: "manuale" }], "un giorno aggiunto a mano lo dice");
assert.equal(proposta[1].livello, "critico", "la proposta non viene toccata");

// base64 con lettere accentate
assert.equal(daBase64(base64("Württemberg · Pâques")), "Württemberg · Pâques");

console.log("prove ok");
