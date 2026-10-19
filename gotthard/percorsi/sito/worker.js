// Pagina delle mappe su percorsi.bacchin.app. Legge le mappe dal repository PRIVATO a ogni richiesta
// (token in sola lettura nel segreto GITHUB_TOKEN). Davanti c'è Cloudflare Access con l'email dell'utente.
import { FONTI, FONTI_TRATTE, leggiDettaglio, mappaValida, momenti, quanto, tabelle } from "./logica.mjs";

const REPO = "https://api.github.com/repos/fbacchin/gottardo-percorsi-privati/contents";

// Mese corrente in ora svizzera, come i nomi dei CSV (dati/<fonte>-AAAA-MM-dettaglio.csv).
function mese(data) {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Zurich", year: "numeric", month: "2-digit" }).format(data);
}

// Righe recenti del CSV di dettaglio di una fonte; a inizio mese si ripiega sul mese prima.
// ponytail: nelle prime ore del mese non si uniscono i due file, la tabella mostra solo i quarti d'ora del mese nuovo
async function dettaglio(env, fonte) {
  const adesso = new Date();
  for (const data of [adesso, new Date(adesso.getTime() - 3 * 3600e3)]) {
    const r = await github(env, `/dati/${fonte}-${mese(data)}-dettaglio.csv`, "application/vnd.github.raw");
    if (r.ok) return leggiDettaglio(await r.text());
  }
  return [];
}

function github(env, percorso, accetta) {
  return fetch(REPO + percorso, {
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: accetta, "User-Agent": "gottardo-percorsi-sito" },
  });
}

export default {
  async fetch(richiesta, env) {
    // Seconda difesa: senza Access (header messo da Cloudflare) non si serve niente, nemmeno per errore di configurazione.
    // ponytail: si controlla la presenza dell'header, non la firma del JWT di Access; workers.dev è spento in wrangler.toml
    if (!richiesta.headers.get("cf-access-authenticated-user-email")) {
      return new Response("Accesso solo tramite Cloudflare Access.", { status: 403 });
    }
    const url = new URL(richiesta.url);

    const html = { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" };
    if (url.pathname === "/") return new Response(PAGINA, { headers: html });
    if (url.pathname === "/tratte") return new Response(TRATTE_PAGINA, { headers: html });
    if (url.pathname === "/api/tratte") {
      const perFonte = Object.fromEntries(await Promise.all(FONTI_TRATTE.map(async ([f]) => [f, await dettaglio(env, f)])));
      return Response.json({ fonti: FONTI_TRATTE, momenti: tabelle(perFonte) }, { headers: { "cache-control": "no-store" } });
    }
    if (url.pathname === "/api/momenti") {
      const r = await github(env, "/mappe", "application/vnd.github+json");
      if (!r.ok) return Response.json({ errore: r.status }, { status: 502 });
      const elenco = momenti((await r.json()).map((f) => f.name)).map((m, i) => ({ ...m, quanto: quanto(i) }));
      return Response.json({ fonti: FONTI, momenti: elenco }, { headers: { "cache-control": "no-store" } });
    }
    const nome = url.pathname.replace(/^\/mappe\//, "");
    if (url.pathname.startsWith("/mappe/") && mappaValida(nome)) {
      const r = await github(env, "/mappe/" + nome, "application/vnd.github.raw");
      if (!r.ok) return new Response("Mappa non trovata", { status: 404 });
      // Le mappe non cambiano più dopo essere state create: si possono tenere in cache.
      return new Response(r.body, { headers: { "content-type": "image/svg+xml", "cache-control": "private, max-age=86400" } });
    }
    return new Response("Non trovato", { status: 404 });
  },
};

const STILE = `  :root { --fondo: #eef1f4; --testo: #1d2125; --tenue: #5f6670; --scheda: #ffffff; --bordo: #d9dee4; --accento: #1f5f8b; }
  @media (prefers-color-scheme: dark) { :root { --fondo: #15191d; --testo: #e8ebee; --tenue: #9aa3ad; --scheda: #1f252b; --bordo: #303840; --accento: #7fb6dc; } }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fondo); color: var(--testo); font: 16px/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
  header { position: sticky; top: 0; z-index: 1; background: var(--fondo); border-bottom: 1px solid var(--bordo); padding: 12px 16px; }
  .riga { max-width: 1040px; margin: 0 auto; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
  h1 { font-size: 15px; font-weight: 600; margin: 0; color: var(--tenue); letter-spacing: .02em; }
  .ora { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .quanto { color: var(--tenue); }
  nav { margin-left: auto; display: flex; gap: 8px; }
  button { font: inherit; font-size: 15px; padding: 8px 14px; border-radius: 8px; border: 1px solid var(--bordo); background: var(--scheda); color: var(--testo); cursor: pointer; }
  button:disabled { opacity: .4; cursor: default; }
  button:focus-visible { outline: 2px solid var(--accento); outline-offset: 2px; }
  main { max-width: 1040px; margin: 0 auto; padding: 16px; display: grid; gap: 16px; }
  figure { margin: 0; }
  figure img { width: 100%; height: auto; display: block; border-radius: 8px; border: 1px solid var(--bordo); }
  .vuota { padding: 24px 16px; border: 1px dashed var(--bordo); border-radius: 8px; color: var(--tenue); }
  a { color: var(--accento); }
  .nota { color: var(--tenue); font-size: 13px; max-width: 1040px; margin: 0 auto; padding: 0 16px 24px; }
`;

const PAGINA = `<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gottardo — traffico</title>
<style>
${STILE}</style>
</head>
<body>
<header><div class="riga">
  <div><h1>Gottardo — traffico</h1><span class="ora" id="ora">…</span> <span class="quanto" id="quanto"></span></div>
  <nav>
    <button id="prima" aria-label="15 minuti prima">◀ 15 min prima</button>
    <button id="adesso">Adesso</button>
    <button id="dopo" aria-label="15 minuti dopo">15 min dopo ▶</button>
  </nav>
</div></header>
<main id="mappe"></main>
<p class="nota"><a href="/tratte">Tempi per tratta: galleria e passo a confronto →</a></p>
<p class="nota">Una mappa per fonte. Corsia in alto verso sud, in basso verso nord; tra Göschenen e Airolo la galleria (sopra) e il passo (sotto). Google misura una volta all'ora. La pagina si aggiorna da sola quando arriva un rilievo nuovo.</p>
<script>
  let fonti = [], momenti = [], i = 0;
  const el = (id) => document.getElementById(id);
  function mostra() {
    const m = momenti[i];
    if (!m) { el("ora").textContent = "nessun dato"; return; }
    el("ora").textContent = m.quando.slice(11);
    el("quanto").textContent = m.quando.slice(8, 10) + "." + m.quando.slice(5, 7) + " · " + m.quanto;
    el("prima").disabled = i >= momenti.length - 1;
    el("dopo").disabled = el("adesso").disabled = i === 0;
    el("mappe").replaceChildren(...fonti.map(([fonte, etichetta]) => {
      const f = document.createElement("figure");
      if (m.file[fonte]) {
        const img = document.createElement("img");
        img.src = "/mappe/" + m.file[fonte]; img.alt = etichetta + " alle " + m.quando.slice(11); img.loading = "lazy";
        f.append(img);
      } else {
        const d = document.createElement("div"); d.className = "vuota"; d.textContent = etichetta + ": nessuna mappa per questo quarto d'ora"; f.append(d);
      }
      return f;
    }));
  }
  async function carica() {
    const r = await fetch("/api/momenti", { cache: "no-store" });
    if (!r.ok) return;
    const d = await r.json();
    const corrente = momenti[i] && momenti[i].quando;
    fonti = d.fonti; momenti = d.momenti;
    i = i === 0 || !corrente ? 0 : Math.max(0, momenti.findIndex((m) => m.quando === corrente));
    mostra();
  }
  el("prima").onclick = () => { i = Math.min(i + 1, momenti.length - 1); mostra(); };
  el("dopo").onclick = () => { i = Math.max(i - 1, 0); mostra(); };
  el("adesso").onclick = () => { i = 0; mostra(); };
  carica();
  setInterval(() => { if (i === 0) carica(); }, 60000);
</script>
</body>
</html>`;


// Tempi per tratta: per ogni tratta galleria, passo e differenza, una colonna per fonte. Stessi pulsanti della pagina delle mappe.
const TRATTE_PAGINA = `<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gottardo — tratte</title>
<style>${STILE}
  main > * { min-width: 0; }
  section { background: var(--scheda); border: 1px solid var(--bordo); border-radius: 8px; padding: 12px 10px 4px; overflow-x: auto; }
  h2 { font-size: 17px; margin: 0 0 8px; } h2 span { font-weight: 400; color: var(--tenue); font-size: 14px; }
  /* Larghezze fisse e uguali in tutte le tabelle (19.10, richiesta dell'utente): ogni fonte sta sempre nello stesso posto. */
  table { table-layout: fixed; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 8px 4px; border-top: 1px solid var(--bordo); vertical-align: top; }
  thead th { border-top: 0; font-size: 13px; color: var(--tenue); font-weight: 600; }
  tbody th { font-weight: 600; }
  td b { font-size: 17px; } .tempo { white-space: nowrap; } td small, th small { display: block; color: var(--tenue); font-size: 12px; font-weight: 400; }
  .pallino { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; vertical-align: 1px; }
  .diff td, .diff th { background: color-mix(in srgb, var(--accento) 8%, transparent); }
  .tenue { color: var(--tenue); }
</style>
</head>
<body>
<header><div class="riga">
  <div><h1>Gottardo — tempi per tratta</h1><span class="ora" id="ora">…</span> <span class="quanto" id="quanto"></span></div>
  <nav>
    <button id="prima" aria-label="15 minuti prima">◀ 15 min prima</button>
    <button id="adesso">Adesso</button>
    <button id="dopo" aria-label="15 minuti dopo">15 min dopo ▶</button>
  </nav>
</div></header>
<p class="nota" style="padding-top:12px"><a href="/">← Mappe</a></p>
<main id="tratte"></main>
<p class="nota">Tempo con traffico; sotto, il ritardo rispetto alla strada libera secondo la fonte. «Passo − galleria» = minuti in più passando dal passo (negativo: il passo è più rapido). Google misura una volta all'ora, solo Amsteg–Faido, Göschenen–Airolo e Faido → Airolo verso nord: si mostra la sua ultima misura, con l'ora. «Passo con la CUPRA» (verso nord) = il passo senza il ritardo su Faido → Airolo: con la coda al portale sud la corsia CUPRA porta chi va ai passi fino all'uscita di Airolo senza fare la coda. Vale solo quando la corsia è aperta, e l'USTRA non pubblica quando lo è. Le tratte separate hanno una sola strada, l'autostrada. «Contatori ASTRA» = velocità delle auto misurata nell'ultimo minuto dai contatori dell'USTRA lungo la tratta (una o due stazioni), applicata a tutta la tratta: sotto il tempo c'è la velocità media, non il ritardo, perché questa fonte non dà il tempo a strada libera. Con poco traffico la velocità viene da pochi veicoli. «Percorso diverso» = la fonte ha calcolato un'altra strada, i km lo dicono.</p>
<script>
  const COLORI = [[3, "#2fb350"], [10, "#ffcc00"], [40, "#ff6f00"]];
  const colore = (v) => (COLORI.find(([s]) => v < s) || [0, "#c62828"])[1];
  let fonti = [], momenti = [], i = 0;
  const el = (id) => document.getElementById(id);
  const crea = (tag, testo, classe) => { const e = document.createElement(tag); if (testo != null) e.textContent = testo; if (classe) e.className = classe; return e; };
  function cella(c) {
    const td = crea("td");
    if (!c) { td.append(crea("span", "—", "tenue")); return td; }
    if (c.esito !== "ok") { td.append(crea("span", c.esito, "tenue")); if (c.km != null) td.append(crea("small", c.km + " km")); return td; }
    const p = crea("span", null, "pallino"); p.style.background = c.ritardo == null ? "#d5d8dc" : colore(c.ritardo);
    const t = crea("span", null, "tempo"); t.append(p, crea("b", c.totale + " min"));
    td.append(t, crea("small", c.ritardo == null ? c.velocita + " km/h" : (c.ritardo > 0 ? "+" : "") + c.ritardo + " min"), crea("small", c.km + " km"));
    return td;
  }
  const differenza = (d) => d == null ? cella(null) : crea("td", (d > 0 ? "+" : "") + d + " min");
  let colonne = [];
  // Etichette 28 % della scheda, ogni fonte 18 %: la tabella è larga solo quanto le sue colonne, così una tabella
  // con 3 fonti non allarga le colonne per riempire lo spazio e resta allineata a quelle con 4.
  const ETICHETTA = 28, FONTE = 18;
  function tabella() {
    const t = crea("table"), cg = crea("colgroup"), totale = ETICHETTA + FONTE * colonne.length;
    t.style.width = totale + "%"; t.style.minWidth = (ETICHETTA + FONTE * colonne.length) * 5.6 + "px";
    const col = (w) => { const c = crea("col"); c.style.width = (100 * w / totale) + "%"; return c; };
    cg.append(col(ETICHETTA), ...colonne.map(() => col(FONTE)));
    t.append(cg);
    return t;
  }
  function riga(titolo, fn, classe) {
    const tr = crea("tr", null, classe); tr.append(crea("th", titolo));
    for (const [f] of colonne) tr.append(fn(f));
    return tr;
  }
  function mostra() {
    const m = momenti[i];
    if (!m) { el("ora").textContent = "nessun dato"; return; }
    el("ora").textContent = m.quando.slice(11);
    el("quanto").textContent = m.quando.slice(8, 10) + "." + m.quando.slice(5, 7) + " · " + m.quanto;
    el("prima").disabled = i >= momenti.length - 1;
    el("dopo").disabled = el("adesso").disabled = i === 0;
    // Le stesse colonne in tutte le schede dello stesso tipo: le fonti con almeno un dato in una di esse.
    // I contatori ASTRA misurano solo le tratte separate, e stanno per ultimi: le altre fonti restano allineate.
    const colonneTratte = fonti.filter(([f]) => m.tratte.some((t) => t.fonti[f] && (t.fonti[f].galleria || t.fonti[f].passo)));
    const colonneSeparate = fonti.filter(([f]) => m.separate.some((g) => g.righe.some((r) => r.fonti[f] && r.fonti[f].cella)));
    el("tratte").replaceChildren(...m.tratte.map((t) => {
      const s = crea("section"), h = crea("h2", t.nome + " "); h.append(crea("span", t.senso)); s.append(h);
      colonne = colonneTratte;
      const tab = tabella(), testa = crea("tr"); testa.append(crea("th"));
      for (const [f, nome] of colonne) {
        const th = crea("th", nome), ora = t.fonti[f] && t.fonti[f].ora;
        if (ora && ora !== m.quando) th.append(crea("small", "alle " + ora.slice(11)));
        testa.append(th);
      }
      const thead = crea("thead"); thead.append(testa);
      const tbody = crea("tbody");
      tbody.append(
        riga("Galleria", (f) => cella(t.fonti[f] && t.fonti[f].galleria)),
        riga("Passo", (f) => cella(t.fonti[f] && t.fonti[f].passo)),
        riga("Passo − galleria", (f) => differenza(t.fonti[f] && t.fonti[f].differenza), "diff"));
      // Verso nord: il passo con la CUPRA, solo se almeno una fonte lo ha.
      if (colonne.some(([f]) => t.fonti[f] && t.fonti[f].cupra)) tbody.append(
        riga("Passo con la CUPRA", (f) => cella(t.fonti[f] && t.fonti[f].cupra)),
        riga("Passo con la CUPRA − galleria", (f) => differenza(t.fonti[f] && t.fonti[f].differenzaCupra), "diff"));
      tab.append(thead, tbody); s.append(tab);
      return s;
    }), ...m.separate.map((g) => {
      colonne = colonneSeparate;
      const s = crea("section"), h = crea("h2", "Tratte separate "); h.append(crea("span", g.senso)); s.append(h);
      const tab = tabella(), testa = crea("tr"); testa.append(crea("th"));
      for (const [, nome] of colonne) testa.append(crea("th", nome));
      const thead = crea("thead"); thead.append(testa);
      const tbody = crea("tbody");
      for (const r of g.righe) {
        const tr = crea("tr"); tr.append(crea("th", r.nome));
        for (const [f] of colonne) tr.append(cella(r.fonti[f] && r.fonti[f].cella));
        tbody.append(tr);
      }
      tab.append(thead, tbody); s.append(tab);
      return s;
    }));
  }
  async function carica() {
    const r = await fetch("/api/tratte", { cache: "no-store" });
    if (!r.ok) return;
    const d = await r.json();
    const corrente = momenti[i] && momenti[i].quando;
    fonti = d.fonti; momenti = d.momenti;
    i = i === 0 || !corrente ? 0 : Math.max(0, momenti.findIndex((m) => m.quando === corrente));
    mostra();
  }
  el("prima").onclick = () => { i = Math.min(i + 1, momenti.length - 1); mostra(); };
  el("dopo").onclick = () => { i = Math.max(i - 1, 0); mostra(); };
  el("adesso").onclick = () => { i = 0; mostra(); };
  carica();
  setInterval(() => { if (i === 0) carica(); }, 60000);
</script>
</body>
</html>`;
