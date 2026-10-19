// Logica pura della pagina, condivisa dal Worker e dalle prove (node sito/prova_sito.mjs).

export const FONTI = [
  ["apple", "Apple Maps"], ["tomtom", "TomTom"], ["google", "Google"],   // Waze tolto dal pannello (15.10): solo dati nei CSV
];
// Pagina Tratte: anche i contatori ASTRA (19.10), che non hanno mappe.
export const FONTI_TRATTE = [...FONTI, ["astra", "Contatori ASTRA"]];
const NOME_MAPPA = /^(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})-(apple|tomtom|google)\.svg$/;

// Solo nomi di mappa validi: niente percorsi arbitrari verso il repository.
export function mappaValida(nome) {
  return NOME_MAPPA.test(nome);
}

// Elenco dei file → momenti, dal più recente: [{ quando: "2026-10-15 18:00", file: { apple: "…svg", … } }]
export function momenti(nomi) {
  const per = new Map();
  for (const nome of nomi) {
    const m = NOME_MAPPA.exec(nome);
    if (!m) continue;
    const quando = `${m[1]} ${m[2]}:${m[3]}`;
    if (!per.has(quando)) per.set(quando, {});
    per.get(quando)[m[4]] = nome;
  }
  return [...per.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1)).map(([quando, file]) => ({ quando, file }));
}

// «adesso», «15 minuti fa», «1 h 30 min fa» rispetto al momento più recente.
export function quanto(indice) {
  if (indice === 0) return "adesso";
  const min = indice * 15;
  if (min < 60) return `${min} minuti fa`;
  const h = Math.floor(min / 60), r = min % 60;
  return r ? `${h} h ${r} min fa` : `${h} h fa`;
}

// --- Tabella delle tratte: galleria e passo a confronto, per fonte ---

export const TRATTE = [
  ["Erstfeld → Biasca", "verso sud", "NS Erstfeld-Biasca"], ["Biasca → Erstfeld", "verso nord", "SN Biasca-Erstfeld"],
  ["Amsteg → Faido", "verso sud", "NS Amsteg-Faido"], ["Faido → Amsteg", "verso nord", "SN Faido-Amsteg"],
  ["Göschenen → Airolo", "verso sud", "NS Göschenen-Airolo"], ["Airolo → Göschenen", "verso nord", "SN Airolo-Göschenen"],
];
// Tratte separate (16.10): una sola strada, in ordine di marcia.
export const SEPARATE = [
  ["verso sud", [["Erstfeld → Amsteg", "NS Erstfeld-Amsteg"], ["Amsteg → Göschenen", "NS Amsteg-Göschenen"], ["Airolo → Faido", "NS Airolo-Faido"], ["Faido → Biasca", "NS Faido-Biasca"]]],
  ["verso nord", [["Biasca → Faido", "SN Biasca-Faido"], ["Faido → Airolo", "SN Faido-Airolo"], ["Göschenen → Amsteg", "SN Göschenen-Amsteg"], ["Amsteg → Erstfeld", "SN Amsteg-Erstfeld"]]],
];
const ORARIE = new Set(["google"]);   // come config.ORARIE: misurano solo al minuto :00
const COLONNE = ["ora", "ora_utc", "misura", "con_traffico_s", "senza_traffico_s", "distanza_m", "esito"];

// CSV di dettaglio → righe; si leggono solo le prime `quante` (le più recenti stanno in cima): 22 misure a giro, 16 giri.
export function leggiDettaglio(testo, quante = 1 + 22 * 16) {
  return testo.split("\n", quante).slice(1).map((riga) => {
    const campi = []; let c = "", virgolette = false;
    for (const ch of riga.replace(/\r$/, "")) {
      if (ch === '"') virgolette = !virgolette;
      else if (ch === "," && !virgolette) { campi.push(c); c = ""; }
      else c += ch;
    }
    campi.push(c);
    return campi.length === COLONNE.length ? Object.fromEntries(COLONNE.map((k, i) => [k, campi[i]])) : null;
  }).filter(Boolean);
}

const minuti = (ora) => Date.parse(ora.replace(" ", "T") + ":00Z") / 60000;

function cella(r) {
  if (!r) return null;
  const km = Math.round(Number(r.distanza_m) / 1000);
  if (r.esito !== "ok") return { esito: r.esito, km: r.distanza_m ? km : null };
  // Contatori ASTRA: nessun tempo «senza traffico», quindi nessun ritardo; si dà la velocità media sulla tratta.
  if (r.senza_traffico_s === "") return { esito: "ok", totale: Math.round(r.con_traffico_s / 60), ritardo: null, velocita: Math.round(r.distanza_m / r.con_traffico_s * 3.6), km };
  return { esito: "ok", totale: Math.round(r.con_traffico_s / 60), ritardo: Math.round((r.con_traffico_s - r.senza_traffico_s) / 60), km };
}

// { fonte: righe } → ultimi `n` quarti d'ora, dal più recente, con galleria, passo e differenza per tratta e fonte.
// Le fonti orarie mostrano l'ultima misura dell'ora (con la sua ora), le altre solo la misura di quel quarto d'ora.
export function tabelle(perFonte, n = 12) {
  const ore = [...new Set(Object.values(perFonte).flat().map((r) => r.ora))].sort().reverse().slice(0, n);
  return ore.map((quando, i) => {
    const misura = {};
    for (const [fonte, righe] of Object.entries(perFonte)) {
      const valide = righe.filter((r) => r.ora === quando || (ORARIE.has(fonte) && r.ora < quando && minuti(quando) - minuti(r.ora) < 60));
      const ultima = valide.map((r) => r.ora).sort().pop();
      misura[fonte] = { ora: ultima || null, righe: valide.filter((r) => r.ora === ultima) };
    }
    const tratte = TRATTE.map(([nome, senso, chiave]) => ({
      nome, senso,
      fonti: Object.fromEntries(Object.entries(misura).map(([fonte, m]) => {
        const galleria = cella(m.righe.find((r) => r.misura === chiave + " tunnel"));
        const passo = cella(m.righe.find((r) => r.misura === chiave + " passo"));
        const differenza = galleria?.esito === "ok" && passo?.esito === "ok" ? passo.totale - galleria.totale : null;
        // Passo verso nord con la CUPRA (19.10): solo le tratte che ce l'hanno, altrimenti null.
        const cupra = cella(m.righe.find((r) => r.misura === chiave + " passo CUPRA"));
        const differenzaCupra = galleria?.esito === "ok" && cupra?.esito === "ok" ? cupra.totale - galleria.totale : null;
        return [fonte, { ora: m.ora, galleria, passo, differenza, cupra, differenzaCupra }];
      })),
    }));
    const separate = SEPARATE.map(([senso, elenco]) => ({
      senso,
      righe: elenco.map(([nome, chiave]) => ({
        nome, fonti: Object.fromEntries(Object.entries(misura).map(([fonte, m]) => [fonte, { ora: m.ora, cella: cella(m.righe.find((r) => r.misura === chiave)) }])),
      })),
    }));
    return { quando, quanto: quanto(i), tratte, separate };
  });
}
