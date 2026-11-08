// Logica del calendario dei giorni critici (ADEV-802), senza rete: la usano il
// Worker e le prove (prova_sito.mjs).

export const LIVELLI = ["normale", "critico", "molto"];
const DIREZIONI = ["south", "north"];
const DATA = /^\d{4}-\d{2}-\d{2}$/;

/** Correzioni ammesse: {south: {"2026-12-19": "molto"}, north: {...}}. Errore se no. */
export function valida(correzioni) {
  if (!correzioni || typeof correzioni !== "object") throw new Error("correzioni mancanti");
  const pulite = { south: {}, north: {} };
  for (const dir of Object.keys(correzioni)) {
    if (!DIREZIONI.includes(dir)) throw new Error(`direzione sconosciuta: ${dir}`);
    for (const [data, livello] of Object.entries(correzioni[dir] ?? {})) {
      if (!DATA.test(data) || Number.isNaN(Date.parse(data))) throw new Error(`data non valida: ${data}`);
      if (!LIVELLI.includes(livello)) throw new Error(`livello non valido: ${livello}`);
      pulite[dir][data] = livello;
    }
  }
  return pulite;
}

/**
 * Il calendario da pubblicare: la proposta automatica con sopra le correzioni.
 * «normale» toglie il giorno; un giorno alzato a mano che la proposta non ha
 * porta il motivo {"tipo": "manuale"}.
 */
export function unisci(proposta, correzioni, adesso = new Date()) {
  const giorni = new Map(proposta.map(g => [`${g.data}|${g.direzione}`, structuredClone(g)]));
  for (const dir of DIREZIONI) {
    for (const [data, livello] of Object.entries(correzioni[dir] ?? {})) {
      const chiave = `${data}|${dir}`;
      if (livello === "normale") { giorni.delete(chiave); continue; }
      const nome = livello === "molto" ? "molto critico" : "critico";
      const g = giorni.get(chiave) ?? { data, direzione: dir, motivi: [{ tipo: "manuale" }] };
      g.livello = nome;
      giorni.set(chiave, g);
    }
  }
  const elenco = [...giorni.values()].sort((a, b) =>
    a.data.localeCompare(b.data) || a.direzione.localeCompare(b.direzione));
  return { pubblicato: adesso.toISOString().replace(/\.\d{3}Z$/, "Z"), giorni: elenco };
}

/** Base64 di un testo UTF-8, a pezzi per non sforare lo stack con file grandi. */
export function base64(testo) {
  const byte = new TextEncoder().encode(testo);
  let binario = "";
  for (let i = 0; i < byte.length; i += 0x8000) binario += String.fromCharCode(...byte.subarray(i, i + 0x8000));
  return btoa(binario);
}

export function daBase64(b64) {
  const binario = atob(b64.replace(/\n/g, ""));
  return new TextDecoder().decode(Uint8Array.from(binario, c => c.charCodeAt(0)));
}
