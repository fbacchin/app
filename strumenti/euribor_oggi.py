#!/usr/bin/env python3
"""Genera euribor-oggi.html dai CSV pubblici dei tassi e aggiorna sitemap.xml.

Legge https://fbacchin.github.io/app/Euribor/EURIBOR.csv ed ESTER.csv (le stesse
serie usate dall'app Euribor X), calcola variazioni e lettura della curva e
scrive la pagina con i valori già dentro, così Google li vede senza JavaScript.

Gira ogni giorno lavorativo da .github/workflows/euribor-oggi.yml. Se il fixing
non è cambiato, la pagina risulta identica e il workflow non committa niente.
Solo libreria standard: nessuna dipendenza da installare.
"""
import csv, html, io, json, math, os, re, sys, urllib.request
from datetime import date, timedelta

BASE = "https://fbacchin.github.io/app/Euribor/"
QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGINA = os.path.join(QUI, "euribor-oggi.html")
SITEMAP = os.path.join(QUI, "sitemap.xml")
URL = "https://bacchin.app/euribor-oggi"
CSS_V = "2026-10-06a"
APP_STORE = "https://apps.apple.com/it/app/id951735963"
DASHBOARD = "https://fbacchin.github.io/finance/ecb_euribor_dashboard.html"
TENOR = [("1W", "1 settimana"), ("1M", "1 mese"), ("3M", "3 mesi"), ("6M", "6 mesi"), ("12M", "12 mesi")]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def scarica(nome):
    with urllib.request.urlopen(BASE + nome, timeout=30) as r:
        testo = r.read().decode("utf-8-sig")
    serie = {}
    for riga in csv.DictReader(io.StringIO(testo)):
        g, m, a = riga["Date"].split(".")
        d = date(int(a), int(m), int(g))
        for k, v in riga.items():
            if k in ("Date", "Week day") or not (v or "").strip():
                continue
            serie.setdefault(k, {})[d] = float(v)
    return {k: sorted(v.items()) for k, v in serie.items()}


def al(serie, giorno):
    """Ultimo valore disponibile alla data indicata o prima."""
    ultimo = None
    for d, v in serie:
        if d > giorno:
            break
        ultimo = (d, v)
    return ultimo


def meno_mesi(d, n):
    m = d.month - n
    a = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    giorni = [31, 29 if a % 4 == 0 and (a % 100 or a % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(a, m, min(d.day, giorni))


def pct(v, cifre=3):
    return f"{v:.{cifre}f}".replace(".", ",").replace("-", "−") + "%"


def pb(delta, prosa=False):
    x = round(delta * 100, 1)
    if abs(x) < 0.05:
        return "invariato"
    intero = prosa and abs(x) == int(abs(x))
    s = (f"{abs(x):.0f}" if intero else f"{abs(x):.1f}").replace(".", ",")
    return ("+" if x > 0 else "−") + s + " pb"


def freccia(delta):
    x = round(delta * 100, 1)
    return "▲" if x > 0.05 else ("▼" if x < -0.05 else "=")


def data_lunga(d):
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def data_media(d):
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def euro(x):
    return f"{x:,.0f}".replace(",", ".") + " €"


def rata(indice, spread=1.0, capitale=100_000, anni=20):
    tasso = max(indice + spread, 0) / 100 / 12
    n = anni * 12
    return capitale / n if tasso == 0 else capitale * tasso / (1 - (1 + tasso) ** -n)


def lettura(s3, s12, oggi):
    d0, v = s3[-1]
    prec = s3[-2][1]
    frasi = []
    diff = v - prec
    if abs(diff) < 0.0005:
        frasi.append(f"Nel fixing di {data_lunga(d0)} l'Euribor a 3 mesi è rimasto fermo a {pct(v)}.")
    else:
        frasi.append(f"Nel fixing di {data_lunga(d0)} l'Euribor a 3 mesi è {'salito' if diff > 0 else 'sceso'} "
                     f"di {pb(abs(diff), True)[1:]}, a {pct(v)}.")
        segno, serie = (1 if diff > 0 else -1), 0
        for i in range(len(s3) - 1, 0, -1):
            dd = s3[i][1] - s3[i - 1][1]
            if abs(dd) < 0.0005 or (dd > 0) != (segno > 0):
                break
            serie += 1
        if serie >= 3:
            frasi.append(f"È il {serie}° {'rialzo' if segno > 0 else 'ribasso'} di fila.")
    rif_m = al(s3, meno_mesi(d0, 1))
    if rif_m:
        dm = v - rif_m[1]
        if abs(dm) < 0.0005:
            frasi.append(f"Rispetto a un mese fa ({data_media(rif_m[0])}) è allo stesso livello.")
        else:
            frasi.append(f"In un mese è {'salito' if dm > 0 else 'sceso'} di {pb(abs(dm), True)[1:]}: "
                         f"il {data_media(rif_m[0])} era a {pct(rif_m[1])}.")
    anno = [(d, x) for d, x in s3 if d > d0 - timedelta(days=365)]
    dmin, vmin = min(anno, key=lambda t: (t[1], -t[0].toordinal()))
    dmax, vmax = max(anno, key=lambda t: (t[1], t[0].toordinal()))
    if abs(v - vmin) < 0.0005 and dmin == d0:
        frasi.append("È il valore più basso degli ultimi dodici mesi.")
    elif abs(v - vmax) < 0.0005 and dmax == d0:
        frasi.append("È il valore più alto degli ultimi dodici mesi.")
    else:
        frasi.append(f"Negli ultimi dodici mesi è andato da un minimo di {pct(vmin)} ({data_media(dmin)}) "
                     f"a un massimo di {pct(vmax)} ({data_media(dmax)}).")
    p1 = " ".join(frasi)

    v12 = al(s12, d0)[1]
    sp = (v12 - v) * 100
    sp_txt = f"{abs(sp):.0f} punti base".replace(".", ",")
    if sp > 10:
        p2 = (f"L'Euribor a 12 mesi ({pct(v12)}) è sopra quello a 3 mesi di {sp_txt}. Quando la scadenza lunga "
              "rende più di quella corta, il mercato non si aspetta tagli dei tassi nei prossimi mesi: "
              "semmai tassi stabili o in leggera salita.")
    elif sp < -10:
        p2 = (f"L'Euribor a 12 mesi ({pct(v12)}) è sotto quello a 3 mesi di {sp_txt}. Quando la scadenza lunga "
              "rende meno di quella corta, il mercato si aspetta tassi più bassi nei prossimi mesi.")
    else:
        p2 = (f"L'Euribor a 12 mesi ({pct(v12)}) e quello a 3 mesi sono quasi alla pari "
              f"(differenza di {sp_txt}): il mercato si aspetta tassi stabili nei prossimi mesi.")

    r_oggi = rata(v)
    rif_a = al(s3, d0 - timedelta(days=365))
    p3 = (f"Su un mutuo a tasso variabile da {euro(100000)} a 20 anni, indicizzato all'Euribor 3 mesi con uno "
          f"spread dell'1%, la rata con l'ultimo fixing è di circa {euro(r_oggi)} al mese")
    if rif_a:
        dr = r_oggi - rata(rif_a[1])
        p3 += (f": {euro(abs(dr))} {'in più' if dr > 0 else 'in meno'} rispetto a un anno fa, quando l'indice era a "
               f"{pct(rif_a[1])}." if abs(dr) >= 1 else ", praticamente come un anno fa.")
    else:
        p3 += "."
    return [p1, p2, p3]


def grafico(serie_12m, d0):
    inizio = d0 - timedelta(days=365)
    linee = [(k, [(d, v) for d, v in serie_12m[k] if d >= inizio]) for k in ("3M", "12M")]
    tutti = [v for _, s in linee for _, v in s]
    passo = next(p for p in (0.1, 0.2, 0.25, 0.5, 1.0) if (max(tutti) - min(tutti)) / p <= 5)
    lo, hi = math.floor(min(tutti) / passo) * passo, math.ceil(max(tutti) / passo) * passo
    W, H, sx, dx, su, giu = 1000, 320, 56, 16, 16, 34
    def x(d): return sx + (d - inizio).days / 365 * (W - sx - dx)
    def y(v): return su + (hi - v) / (hi - lo) * (H - su - giu)
    parti = [f'<svg class="grafico" viewBox="0 0 {W} {H}" role="img" aria-label="Euribor 3 e 12 mesi, ultimi dodici mesi">']
    for i in range(round((hi - lo) / passo) + 1):
        v = lo + passo * i
        parti.append(f'<line x1="{sx}" x2="{W - dx}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="g-riga"/>'
                     f'<text x="{sx - 8}" y="{y(v) + 4:.1f}" class="g-asse" text-anchor="end">{pct(v, 2)}</text>')
    m = date(inizio.year, inizio.month, 1)
    while m <= d0:
        if m >= inizio and (m.month - 1) % 3 == 0:
            parti.append(f'<text x="{x(m):.1f}" y="{H - 10}" class="g-asse" text-anchor="middle">{MESI[m.month - 1][:3]} {str(m.year)[2:]}</text>')
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for k, s in linee:
        punti = " ".join(f"{x(d):.1f},{y(v):.1f}" for d, v in s)
        parti.append(f'<polyline points="{punti}" class="g-linea g-{k.lower()}"/>')
    parti.append("</svg>")
    return "\n".join(parti)


FAQ = [
    ("Che cos'è l'Euribor?",
     "È il tasso medio a cui le principali banche dell'area euro si prestano denaro senza garanzie. Lo calcola ogni "
     "giorno lavorativo l'EMMI (European Money Markets Institute) per cinque scadenze: 1 settimana, 1, 3, 6 e 12 mesi. "
     "È l'indice a cui è agganciata la maggior parte dei mutui e dei finanziamenti a tasso variabile in Italia."),
    ("Quale Euribor usa il mio mutuo?",
     "Lo trovi nel contratto, alla voce che descrive il tasso: di solito è l'Euribor a 1 o a 3 mesi, più uno spread "
     "fisso stabilito dalla banca. Il contratto dice anche ogni quanto la rata viene ricalcolata e quale fixing si usa, "
     "per esempio la media del mese precedente o il valore di un giorno preciso."),
    ("Quando viene pubblicato?",
     "L'EMMI pubblica l'Euribor ogni giorno lavorativo del calendario TARGET, verso le 11 ora di Bruxelles. Questa pagina "
     "si aggiorna in automatico quando il nuovo fixing è disponibile nei dati pubblici, di norma entro il giorno "
     "lavorativo successivo. Nei fine settimana e nei festivi TARGET non esce nessun fixing."),
    ("Che cos'è l'€STR?",
     "È il tasso a un giorno (overnight) del mercato monetario in euro, calcolato dalla Banca Centrale Europea. Misura il "
     "costo del denaro da un giorno all'altro ed è il riferimento più vicino alle decisioni della BCE; l'Euribor a 1 "
     "settimana gli si muove intorno."),
    ("Cosa vuol dire «pb»?",
     "Punti base: un centesimo di punto percentuale. Se l'Euribor passa dal 2,620% al 2,633% è salito di 1,3 punti base."),
]


def pagina(eur, est):
    s3 = eur["3M"]
    d0, v3 = s3[-1]
    v12 = al(eur["12M"], d0)[1]
    righe, cifre = [], []
    for k, nome in TENOR:
        s = eur.get(k, [])
        u = al(s, d0)
        if not u:
            continue
        idx = [d for d, _ in s].index(u[0])
        prec = s[idx - 1][1] if idx else u[1]
        def var(rif):
            r = al(s, rif)
            return pb(u[1] - r[1]) if r else "—"
        righe.append(f"<tr><th scope=\"row\">Euribor {nome}</th><td class=\"num\">{pct(u[1])}</td>"
                     f"<td class=\"num\">{pb(u[1] - prec)}</td><td class=\"num\">{var(u[0] - timedelta(days=7))}</td>"
                     f"<td class=\"num\">{var(meno_mesi(u[0], 1))}</td><td class=\"num\">{var(u[0] - timedelta(days=365))}</td></tr>")
        cifre.append(f'<div class="cifra"><div class="cifra__nome">{nome}</div><div class="cifra__valore">{pct(u[1])}</div>'
                     f'<div class="cifra__var">{freccia(u[1] - prec)} {pb(u[1] - prec)}</div></div>')
    se = est["ON"]
    de, ve = se[-1]
    pe = se[-2][1]
    cifre.insert(0, f'<div class="cifra"><div class="cifra__nome">€STR</div><div class="cifra__valore">{pct(ve)}</div>'
                    f'<div class="cifra__var">{freccia(ve - pe)} {pb(ve - pe)}</div></div>')
    righe.append(f"<tr><th scope=\"row\">€STR <span class=\"nota\">({data_media(de)})</span></th><td class=\"num\">{pct(ve)}</td>"
                 f"<td class=\"num\">{pb(ve - pe)}</td><td class=\"num\">{pb(ve - al(se, de - timedelta(days=7))[1])}</td>"
                 f"<td class=\"num\">{pb(ve - al(se, meno_mesi(de, 1))[1])}</td><td class=\"num\">{pb(ve - al(se, de - timedelta(days=365))[1])}</td></tr>")
    p = lettura(s3, eur["12M"], d0)
    breve = f"{d0.day} {MESI[d0.month - 1]}"
    titolo = f"Euribor oggi, {breve}: 3 mesi {pct(v3)}, 12 mesi {pct(v12)}"
    descr = (f"Euribor di {data_lunga(d0)}: 1 mese {pct(al(eur['1M'], d0)[1])}, 3 mesi {pct(v3)}, 6 mesi "
             f"{pct(al(eur['6M'], d0)[1])}, 12 mesi {pct(v12)}. Variazioni, grafico di un anno e cosa significa per la rata del mutuo.")
    faq_html = "\n".join(f"    <h3>{html.escape(q, quote=False)}</h3>\n    <p>{html.escape(a, quote=False)}</p>" for q, a in FAQ)
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
        ensure_ascii=False)
    E = lambda t: html.escape(t, quote=False)
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{html.escape(titolo)}</title>
<meta name="description" content="{html.escape(descr)}">
<meta property="og:title" content="{html.escape(titolo)}">
<meta property="og:description" content="{html.escape(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{URL}">
<meta property="og:image" content="https://bacchin.app/og.png">
<meta property="og:locale" content="it_IT">
<meta name="theme-color" content="#171A1F">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23171A1F'/%3E%3Ccircle cx='32' cy='32' r='11' fill='%23F2A93B'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/fonts/fonts.css">
<link rel="stylesheet" href="/stile.css?v={CSS_V}">
<link rel="canonical" href="{URL}">
<script type="application/ld+json">{faq_ld}</script>
<style>
  .dato-grande__griglia {{ grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }}
  .cifra__var {{ font-family: var(--dato); font-size: 12px; color: var(--nebbia); margin-top: 2px; white-space: nowrap; }}
  .tabella {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 15px; }}
  .tabella th, .tabella td {{ padding: 10px 8px; border-bottom: 1px solid var(--linea); text-align: left; }}
  .tabella thead th {{ font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--nebbia); font-weight: 600; }}
  .tabella .num {{ font-family: var(--dato); text-align: right; white-space: nowrap; }}
  .tabella .nota {{ color: var(--nebbia); font-size: 13px; font-weight: 400; }}
  .scorre {{ overflow-x: auto; }}
  @media (max-width: 700px) {{
    .tabella {{ font-size: 13.5px; }}
    .tabella th, .tabella td {{ padding: 9px 5px; }}
    .tabella tr > :nth-child(4), .tabella tr > :nth-child(6) {{ display: none; }}
    .tabella .nota {{ display: block; }}
  }}
  .grafico {{ width: 100%; height: auto; margin-top: 8px; }}
  .g-riga {{ stroke: var(--linea); stroke-width: 1; }}
  .g-asse {{ fill: var(--nebbia); font-family: var(--dato); font-size: 13px; }}
  .g-linea {{ fill: none; stroke-width: 2.5; stroke-linejoin: round; }}
  .g-3m {{ stroke: var(--ambra); }}
  .g-12m {{ stroke: var(--gesso); opacity: .75; }}
  .legenda {{ font-family: var(--dato); font-size: 12px; color: var(--nebbia); margin-top: 6px; }}
  .legenda .a {{ color: var(--ambra); }} .legenda .g {{ color: var(--gesso); }}
  .racconto h3 {{ font-size: 17px; margin: 22px 0 6px; }}
  .invito {{ margin-top: 36px; padding: 22px; background: var(--pannello); border: 1px solid var(--linea); border-radius: 14px; }}
  .invito a {{ color: var(--ambra); }}
</style>
</head>
<body>
<div class="foglio">

  <header class="testata">
    <a class="etichetta" href="/">Fabrizio Bacchin</a>
    <a class="etichetta" href="/#t-app">Tutte le app</a>
  </header>

  <div class="app-hero">
    <h1>Euribor oggi</h1>
    <p class="tesi">I tassi Euribor del <strong>fixing di {data_lunga(d0)}</strong>, con la variazione rispetto al giorno prima, il grafico dell'ultimo anno e <strong>cosa significa per la rata di un mutuo variabile</strong>. La pagina si aggiorna da sola ogni giorno lavorativo.</p>
    <div class="dato-grande">
      <div class="dato-grande__griglia">
        {''.join(cifre)}
      </div>
      <div class="dato-grande__quando">Euribor: fixing del {data_media(d0)} · €STR: {data_media(de)} · variazioni in punti base (pb) rispetto al fixing precedente</div>
    </div>
  </div>

  <div class="racconto">
    <h2>La lettura di oggi</h2>
    <p>{E(p[0])}</p>
    <p>{E(p[1])}</p>
    <p>{E(p[2])}</p>

    <h2>Le variazioni</h2>
    <div class="scorre">
    <table class="tabella">
      <thead><tr><th scope="col">Tasso</th><th scope="col" class="num">Valore</th><th scope="col" class="num">Giorno</th><th scope="col" class="num">Settimana</th><th scope="col" class="num">Mese</th><th scope="col" class="num">Anno</th></tr></thead>
      <tbody>
      {''.join(righe)}
      </tbody>
    </table>
    </div>

    <h2>Gli ultimi dodici mesi</h2>
    {grafico(eur, d0)}
    <p class="legenda"><span class="a">━ Euribor 3 mesi</span> &nbsp; <span class="g">━ Euribor 12 mesi</span></p>

    <div class="invito">
      <p><strong>Lo stesso, sul telefono.</strong> <a href="{APP_STORE}">Euribor X</a> mostra i fixing di ogni giorno con i grafici storici e un simulatore di mutuo, anche senza rete. Gratis su iPhone e iPad.</p>
      <p>Per esplorare tutto lo storico e confrontarlo con il tasso BCE c'è la <a href="{DASHBOARD}">dashboard BCE &amp; Euribor</a>.</p>
    </div>

    <h2>Domande frequenti</h2>
{faq_html}

    <dl class="scheda-tecnica">
      <div><dt>Dati</dt><dd>Euribor (EMMI) ed €STR (BCE) — <a href="{BASE}EURIBOR.csv">EURIBOR.csv</a> · <a href="{BASE}ESTER.csv">ESTER.csv</a>, le stesse serie usate dall'app</dd></div>
      <div><dt>Esempio di rata</dt><dd>Mutuo da 100.000 € a 20 anni, rata mensile ad ammortamento francese, Euribor 3 mesi + 1%. È un esempio: la rata vera dipende da contratto, spread e calendario di revisione.</dd></div>
      <div><dt>Aggiornamento</dt><dd>Ogni giorno lavorativo, in automatico</dd></div>
    </dl>
  </div>

  <footer class="piede">
    <span class="etichetta">© {d0.year} Fabrizio Bacchin</span>
    <nav class="piede__link etichetta">
      <a href="mailto:info@bacchin.app">info@bacchin.app</a>
      <a href="/privacy">Privacy e assistenza</a>
    </nav>
  </footer>

</div>
</body>
</html>
""", d0


def aggiorna_sitemap(d0):
    with open(SITEMAP, encoding="utf-8") as f:
        s = f.read()
    voce = f"  <url>\n    <loc>{URL}</loc>\n    <lastmod>{d0.isoformat()}</lastmod>\n  </url>\n"
    if f"<loc>{URL}</loc>" in s:
        s = re.sub(rf"  <url>\n    <loc>{re.escape(URL)}</loc>\n    <lastmod>[^<]*</lastmod>\n  </url>\n", voce, s)
    else:
        s = s.replace("</urlset>", voce + "</urlset>")
    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write(s)


def main():
    eur, est = scarica("EURIBOR.csv"), scarica("ESTER.csv")
    testo, d0 = pagina(eur, est)
    with open(PAGINA, "w", encoding="utf-8") as f:
        f.write(testo)
    aggiorna_sitemap(d0)
    print(f"euribor-oggi.html: fixing del {d0.isoformat()}")


if __name__ == "__main__":
    main()
