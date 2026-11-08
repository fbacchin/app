// Pagina privata del calendario dei giorni critici (ADEV-802):
// calendario.bacchin.app, dietro Cloudflare Access (solo Fabrizio).
//
// Legge da GitHub la proposta automatica (gotthard/calendario/proposta.json,
// scritta da genera.py) e le correzioni di Fabrizio (correzioni.json). «Pubblica»
// salva le correzioni e scrive gotthard/data/calendario.json, il file che leggono
// l'app e il widget. Segreto: GITHUB_TOKEN, scrittura su fbacchin/app.
import PAGINA from "./pagina.html";
import { valida, unisci, base64, daBase64 } from "./logica.mjs";

const AMMESSO = "bacchin@mac.com";
const ORIGINE = "https://calendario.bacchin.app";
const API = "https://api.github.com/repos/fbacchin/app/contents/";
const FILE = {
  proposta: "gotthard/calendario/proposta.json",
  correzioni: "gotthard/calendario/correzioni.json",
  calendario: "gotthard/data/calendario.json",
};

async function leggi(env, percorso) {
  const r = await fetch(API + percorso, { headers: intestazioni(env) });
  if (r.status === 404) return { dati: null, sha: null };
  if (!r.ok) throw new Error(`GitHub ${r.status} leggendo ${percorso}`);
  const j = await r.json();
  return { dati: JSON.parse(daBase64(j.content)), sha: j.sha };
}

async function scrivi(env, percorso, dati, sha, messaggio) {
  const r = await fetch(API + percorso, {
    method: "PUT",
    headers: { ...intestazioni(env), "Content-Type": "application/json" },
    body: JSON.stringify({
      message: messaggio,
      content: base64(JSON.stringify(dati, null, 1) + "\n"),
      ...(sha ? { sha } : {}),
    }),
  });
  if (!r.ok) throw new Error(`GitHub ${r.status} scrivendo ${percorso}`);
}

function intestazioni(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "gottardo-calendario",
  };
}

const json = (dati, status = 200) =>
  new Response(JSON.stringify(dati), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

export default {
  async fetch(richiesta, env) {
    // Cloudflare Access mette questa intestazione solo dopo il login; il
    // Worker risponde comunque solo all'indirizzo ammesso.
    if (richiesta.headers.get("cf-access-authenticated-user-email") !== AMMESSO) {
      return new Response("Accesso solo tramite Cloudflare Access.", { status: 403 });
    }
    const url = new URL(richiesta.url);
    try {
      if (richiesta.method === "GET" && url.pathname === "/") {
        return new Response(PAGINA, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
      }
      if (richiesta.method === "GET" && url.pathname === "/api/stato") {
        const [proposta, correzioni, calendario] = await Promise.all(
          [FILE.proposta, FILE.correzioni, FILE.calendario].map(p => leggi(env, p)));
        return json({
          proposta: proposta.dati ?? [],
          correzioni: correzioni.dati ?? { south: {}, north: {} },
          pubblicato: calendario.dati?.pubblicato ?? null,
        });
      }
      if (richiesta.method === "POST" && url.pathname === "/api/pubblica") {
        // Solo dalla pagina stessa: niente pubblicazioni da altri siti.
        if (richiesta.headers.get("Origin") !== ORIGINE) return json({ errore: "origine non ammessa" }, 403);
        const correzioni = valida((await richiesta.json()).correzioni);
        const [proposta, vecchie, calendario] = await Promise.all(
          [FILE.proposta, FILE.correzioni, FILE.calendario].map(p => leggi(env, p)));
        const nuovo = unisci(proposta.dati ?? [], correzioni);
        await scrivi(env, FILE.correzioni, correzioni, vecchie.sha, "calendario: correzioni di Fabrizio (ADEV-802)");
        await scrivi(env, FILE.calendario, nuovo, calendario.sha, "calendario: pubblicato (ADEV-802)");
        return json({ pubblicato: nuovo.pubblicato, giorni: nuovo.giorni.length });
      }
      return new Response("Non trovato.", { status: 404 });
    } catch (e) {
      return json({ errore: e.message }, 400);
    }
  },
};
