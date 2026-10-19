# Mappe e pagine: si devono capire al volo, anche dall'app GitHub sul telefono.
from datetime import datetime, timedelta
from config import COLORI, MISURE, SOGLIE, ZURIGO

LEGENDA = (("🟢", "fino a 2 min"), ("🟡", "meno di 10"), ("🟠", "meno di 40"), ("🔴", "40 o più"), ("⚪", "nessun dato"))

def pallino(v):
    if v is None or v == "":
        return "⚪"
    for soglia, simbolo in SOGLIE:
        if int(v) < soglia:
            return simbolo
    return "🔴"

# ---------------------------------------------------------------------------------------------
# Mappa della strada: dove c'è traffico in un dato momento. Una corsia per senso di marcia,
# tra Göschenen e Airolo due rami: galleria (in alto) e passo (in basso).

X = {"Erstfeld": 110, "Amsteg": 230, "Göschenen": 370, "Airolo": 680, "Faido": 820, "Biasca": 950}
# Il passo sta SOPRA la strada principale (si sale in montagna): la corsia «verso sud» del ramo è a Y_PASSO.
Y_GALLERIA, Y_PASSO, CORSIA = 190, 96, 14            # y della corsia «verso sud»; quella «verso nord» è CORSIA più in basso
CURVA = 110                                          # larghezza delle curve agli svincoli: più stretta e la corsia interna si accartoccia
X_ANDERMATT, X_VETTA = 450, 525
TRATTEGGIO = 66                                      # tratto di strada dritta coperto dalle curve a ogni svincolo

def _y_ramo(x):
    """Quota del ramo del passo: sale con una curva morbida (smoothstep) da Göschenen, scende allo stesso modo su Airolo."""
    x0, x1 = X["Göschenen"], X["Airolo"]
    t = min(1.0, (x - x0) / CURVA, (x1 - x) / CURVA)
    t = max(0.0, t)
    return Y_GALLERIA - (Y_GALLERIA - Y_PASSO) * (3 * t * t - 2 * t ** 3)

def _ramo_passo():
    return [(float(x), _y_ramo(x)) for x in range(X["Göschenen"], X["Airolo"] + 1, 2)]

def _nome(senso, tratta, percorso):
    lunga = {"NS": "NS Erstfeld-Biasca", "SN": "SN Biasca-Erstfeld"}
    corta = {"NS": "NS Amsteg-Faido", "SN": "SN Faido-Amsteg"}
    return f"{(lunga if tratta == 'lunga' else corta)[senso]} {percorso}"

def _valore(riga, nome):
    v = (riga or {}).get(nome, "")
    return None if v in ("", None) else int(v)

def situazione(righe_per_fonte, fonte_colore="apple"):
    """Ritardi per tratto di strada da una riga per fonte (stesso momento).
    centro = Amsteg–Faido; esterni = Erstfeld–Biasca meno Amsteg–Faido (i due estremi insieme)."""
    riga = righe_per_fonte.get(fonte_colore)
    s = {}
    for senso in ("NS", "SN"):
        for percorso in ("tunnel", "passo"):
            s[(senso, percorso)] = _valore(riga, _nome(senso, "corta", percorso))
        lunga, corta = _valore(riga, _nome(senso, "lunga", "tunnel")), _valore(riga, _nome(senso, "corta", "tunnel"))
        s[(senso, "esterni")] = None if lunga is None or corta is None else lunga - corta
    return s

def _parallela(punti, d):
    """La stessa linea spostata di d a destra del verso di percorrenza (giunti ad angolo), per affiancare le corsie."""
    import math
    if d == 0:
        return punti
    normali = []
    for (x1, y1), (x2, y2) in zip(punti, punti[1:]):
        l = math.hypot(x2 - x1, y2 - y1)
        normali.append((-(y2 - y1) / l, (x2 - x1) / l))
    out = []
    for i, (x, y) in enumerate(punti):
        a, b = normali[max(i - 1, 0)], normali[min(i, len(normali) - 1)]
        nx, ny = a[0] + b[0], a[1] + b[1]
        scala = d * 2 / (nx * nx + ny * ny)                       # spostamento d da entrambi i segmenti nel giunto
        out.append((x + nx * scala, y + ny * scala))
    return out

def _frecce(linea, al_contrario, passo=160):
    """Frecce (→) dentro la corsia nel senso di marcia: almeno una per tratto, così si leggono anche le diagonali degli svincoli."""
    import math
    out = []
    for (x1, y1), (x2, y2) in zip(linea, linea[1:]):
        lungo = math.hypot(x2 - x1, y2 - y1)
        if lungo < 12:
            continue
        angolo = math.degrees(math.atan2(y2 - y1, x2 - x1)) + (180 if al_contrario else 0)
        angolo = (angolo + 180) % 360 - 180
        n = max(1, int(lungo // passo))
        for i in range(n):
            t = (i + 0.5) / n
            out.append(f'<path class="freccia" transform="translate({x1 + (x2 - x1) * t:.1f},{y1 + (y2 - y1) * t:.1f}) rotate({angolo:.1f})" '
                       f'd="M-6,0 L5,0 M1.5,-3.5 L5,0 L1.5,3.5" fill="none" stroke="#1d2125" stroke-opacity="0.6" stroke-width="1.8" '
                       f'stroke-linecap="round" stroke-linejoin="round"/>')
    return out

def _frecce_a(linea, al_contrario, frazioni):
    """Frecce in punti precisi della linea (frazioni della lunghezza), orientate sulla tangente: servono nelle curve."""
    import math
    lunghi = [math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(linea, linea[1:])]
    totale, out = sum(lunghi), []
    for f in frazioni:
        resto, i = f * totale, 0
        while i < len(lunghi) - 1 and resto > lunghi[i]:
            resto -= lunghi[i]
            i += 1
        (x1, y1), (x2, y2) = linea[i], linea[i + 1]
        t = resto / lunghi[i] if lunghi[i] else 0
        angolo = math.degrees(math.atan2(y2 - y1, x2 - x1)) + (180 if al_contrario else 0)
        angolo = (angolo + 180) % 360 - 180
        out.append(f'<path class="freccia" transform="translate({x1 + (x2 - x1) * t:.1f},{y1 + (y2 - y1) * t:.1f}) rotate({angolo:.1f})" '
                   f'd="M-6,0 L5,0 M1.5,-3.5 L5,0 L1.5,3.5" fill="none" stroke="#1d2125" stroke-opacity="0.6" stroke-width="1.8" '
                   f'stroke-linecap="round" stroke-linejoin="round"/>')
    return out

def mappa(titolo, sit, numeri=(), sottotitolo=""):
    Y_TESTO = Y_GALLERIA + CORSIA + 56                            # prima riga di testo sotto la mappa
    W, H = 1000, Y_TESTO + 24 + 16 * len(numeri)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">',
         f"<title>{titolo}</title>", f'<rect width="{W}" height="{H}" rx="8" fill="#ffffff"/>',
         f'<text x="16" y="26" fill="#202124" font-size="15" font-weight="700">{titolo}</text>']
    if sottotitolo:
        o.append(f'<text x="16" y="44" fill="#5f6368" font-size="11">{sottotitolo}</text>')
    colore = lambda v: COLORI[pallino("" if v is None else v)]

    frecce = []                                                   # disegnate sopra tutte le corsie, alla fine

    def corsie(punti, y, chiave_sud, chiave_nord, classe="", frazioni=None, cavalcavia=False):
        for k, (senso, chiave) in enumerate((("NS", chiave_sud), ("SN", chiave_nord))):
            linea = _parallela(punti, k * CORSIA)
            pts = " ".join(f"{x:.1f},{yy:.1f}" for x, yy in linea)
            attr = f' class="{classe}"' if classe else ""
            if cavalcavia and senso == "SN":                      # bordo bianco: si vede che passa sopra la corsia «verso sud»
                o.append(f'<polyline points="{pts}" fill="none" stroke="#ffffff" stroke-width="16" stroke-linejoin="round"/>')
            o.append(f'<polyline{attr} points="{pts}" fill="none" stroke="{colore(sit.get(chiave))}" stroke-width="10" stroke-linejoin="round"/>')
            frecce.extend(_frecce_a(linea, senso == "SN", frazioni) if frazioni else _frecce(linea, senso == "SN"))

    # Prima la strada principale con la galleria, poi il ramo del passo sopra. Agli svincoli la corsia «verso nord»
    # del passo scavalca la corsia «verso sud» per raggiungere la sua (cavalcavia). Una freccia per curva e una in quota.
    o.append(f'<rect x="{X["Göschenen"] + 20}" y="{Y_GALLERIA - 10}" width="{X["Airolo"] - X["Göschenen"] - 40}" height="{CORSIA + 20}" rx="6" fill="#3c4043"/>')
    # In galleria le frecce stanno nel tratto centrale: vicino agli svincoli finirebbero sotto le curve del passo.
    margine = (CURVA + 15) / (X["Airolo"] - X["Göschenen"])
    for a, b, chiave in (("Erstfeld", "Amsteg", "esterni"), ("Amsteg", "Göschenen", "tunnel"), ("Göschenen", "Airolo", "tunnel"),
                         ("Airolo", "Faido", "tunnel"), ("Faido", "Biasca", "esterni")):
        frazioni = (margine + 0.02, 1 - margine - 0.02) if (a, b) == ("Göschenen", "Airolo") else None
        corsie([(X[a], Y_GALLERIA), (X[b], Y_GALLERIA)], 0, ("NS", chiave), ("SN", chiave), frazioni=frazioni)
    corsie(_ramo_passo(), 0, ("NS", "passo"), ("SN", "passo"), "corsia-passo", (0.19, 0.5, 0.81), cavalcavia=True)
    # Agli svincoli le curve coprono la strada dritta: un tratteggio grigio scuro (fuori dai colori delle code)
    # ne mostra la continuazione fino alla galleria, su tutte e due le corsie.
    for x0, x1 in ((X["Göschenen"], X["Göschenen"] + TRATTEGGIO), (X["Airolo"] - TRATTEGGIO, X["Airolo"])):
        for y in (Y_GALLERIA, Y_GALLERIA + CORSIA):
            o.append(f'<line class="continua" x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#3c4043" stroke-width="3" '
                     f'stroke-dasharray="6 4" stroke-linecap="butt"/>')
    o.extend(frecce)
    sotto_strada = Y_GALLERIA + CORSIA + 24                       # nomi sotto la strada principale: sopra c'è il passo
    o.append(f'<text x="{(X["Göschenen"] + X["Airolo"]) / 2:.0f}" y="{sotto_strada}" text-anchor="middle" fill="#202124" font-size="11" font-weight="600">Galleria 17 km</text>')
    o.append(f'<path d="M{X_VETTA - 12},{Y_PASSO - 9} L{X_VETTA},{Y_PASSO - 24} L{X_VETTA + 12},{Y_PASSO - 9} Z" fill="#3c4043"/>')
    o.append(f'<text x="{X_VETTA}" y="{Y_PASSO - 30}" text-anchor="middle" fill="#202124" font-size="11" font-weight="600">Passo 2106 m</text>')
    o.append(f'<text x="{X_ANDERMATT - 8}" y="{_y_ramo(X_ANDERMATT) - 12:.0f}" text-anchor="end" fill="#5f6368" font-size="11">Andermatt</text>')
    for n, x in X.items():
        o.append(f'<line x1="{x}" y1="{Y_GALLERIA - 6}" x2="{x}" y2="{Y_GALLERIA + CORSIA + 6}" stroke="#ffffff" stroke-width="2"/>')
        o.append(f'<text x="{x}" y="{sotto_strada}" text-anchor="middle" fill="#5f6368" font-size="11">{n}</text>')
    o.append(f'<text x="96" y="{Y_GALLERIA + 4}" text-anchor="end" fill="#5f6368" font-size="11">verso sud →</text>')
    o.append(f'<text x="96" y="{Y_GALLERIA + CORSIA + 4}" text-anchor="end" fill="#5f6368" font-size="11">← verso nord</text>')


    y = Y_TESTO
    for riga in numeri:
        if riga.startswith("Adesso conviene"):                    # la risposta alla domanda «galleria o passo?» in evidenza
            o.append(f'<text x="16" y="{y}" fill="#202124" font-size="12" font-weight="600">{riga}</text>')
            y += 20
        else:
            o.append(f'<text x="16" y="{y}" fill="#3c4043" font-size="11">{riga}</text>')
            y += 16
    x = 560                                                      # legenda in alto a destra
    for simbolo, testo in LEGENDA[:4]:
        o.append(f'<rect x="{x}" y="16" width="12" height="9" fill="{COLORI[simbolo]}"/>')
        o.append(f'<text x="{x + 16}" y="25" fill="#5f6368" font-size="10">{testo}</text>')
        x += 24 + 6 * len(testo)
    o.append("</svg>")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------------------------------------
# Pagine: il README mostra l'ultimo rilievo, una mappa per fonte; «◀ 15 minuti prima» porta alle pagine precedenti.
# Ogni mappa ha l'orario nel nome e non cambia più: a ogni giro si aggiungono solo le mappe nuove.

FONTI_MAPPA = (("apple", "Apple Maps"), ("tomtom", "TomTom"), ("google", "Google"))   # Waze tolto dal pannello (15.10): solo dati nei CSV
PASSI_STORIA = 12                      # 3 ore di quarti d'ora

def nome_mappa(quando, fonte):
    return f"mappe/{quando:%Y-%m-%d-%H%M}-{fonte}.svg"

def _tratta(riga, totali):
    """Erstfeld–Biasca, oppure Amsteg–Faido se la fonte non ha nessun dato della prima (Google dal 16.10)."""
    ha = lambda t: any(_valore(riga or {}, _nome(s, t, p)) is not None or _nome(s, t, p) in (totali or {})
                       for s in ("NS", "SN") for p in ("tunnel", "passo"))
    return "corta" if not ha("lunga") and ha("corta") else "lunga"

NOME_TRATTA = {"lunga": "Erstfeld–Biasca", "corta": "Amsteg–Faido"}

def numeri_fonte(riga, totali):
    """Righe di testo sotto la mappa: ritardo e tempo totale su Erstfeld–Biasca (o Amsteg–Faido), per senso e percorso."""
    tratta, out = _tratta(riga, totali), []
    for senso, testo in (("NS", "verso sud"), ("SN", "verso nord")):
        parti = []
        for perc, nome_p in (("tunnel", "galleria"), ("passo", "passo")):
            n = _nome(senso, tratta, perc)
            v, t = _valore(riga, n), (totali or {}).get(n)
            parti.append(f"{nome_p} " + ("nessun dato" if v is None else f"{'+' if v > 0 else ''}{v} min" + (f" · totale {t} min" if t is not None else "")))
        out.append(f"{NOME_TRATTA[tratta]} {testo}: " + "   |   ".join(parti))
    return out

def conviene(totali, riga=None):
    """Galleria o passo, con i tempi totali di una fonte su Erstfeld–Biasca. Differenza di un minuto o meno: fa lo stesso.
    Google non misura Erstfeld–Biasca (16.10): si usa Amsteg–Faido, e lo si scrive."""
    totali = totali or {}
    tratta = _tratta(riga, totali)
    parti = []
    for senso, testo in (("NS", "verso sud"), ("SN", "verso nord")):
        g, p = totali.get(_nome(senso, tratta, "tunnel")), totali.get(_nome(senso, tratta, "passo"))
        if g is None or p is None:
            parti.append(f"{testo} non si può dire (manca il tempo {'della galleria' if g is None else 'del passo'})")
        elif abs(g - p) <= 1:
            parti.append(f"{testo} fa lo stesso (galleria {g} min, passo {p} min)")
        elif g < p:
            parti.append(f"{testo} la galleria ({g} min contro {p} del passo)")
        else:
            parti.append(f"{testo} il passo ({p} min contro {g} della galleria)")
    return "Adesso conviene" + ("" if tratta == "lunga" else " (Amsteg–Faido)") + ": " + " · ".join(parti)

def con_cupra(totali, riga=None):
    """Riga in più quando la CUPRA accorcia il passo verso nord di almeno 2 minuti (1 è arrotondamento); altrimenti nessuna."""
    totali = totali or {}
    tratta = _tratta(riga, totali)
    g, p = totali.get(_nome("SN", tratta, "tunnel")), totali.get(_nome("SN", tratta, "passo"))
    c = totali.get(_nome("SN", tratta, "passo") + " CUPRA")
    if c is None or p is None or p - c < 2:
        return []
    confronto = "" if g is None else (" — fa lo stesso della galleria" if abs(g - c) <= 1 else
                                      f" — {'meglio' if c < g else 'peggio'} della galleria ({g} min)")
    return [f"Con la CUPRA, se aperta, verso nord il passo: {c} min invece di {p}{confronto}"]

def mappa_fonte(fonte, quando, riga=None, totali=None, ora_misura=None):
    etichetta = dict(FONTI_MAPPA)[fonte]
    titolo = f"{etichetta} — {quando:%H:%M}"
    sotto = f"misura delle {ora_misura}" if ora_misura and ora_misura != f"{quando:%Y-%m-%d %H:%M}" else ""
    if riga is None:
        return mappa(titolo, {}, ["nessun dato in questo quarto d'ora"], sotto)
    return mappa(titolo, situazione({fonte: riga}, fonte), [conviene(totali, riga)] + con_cupra(totali, riga) + numeri_fonte(riga, totali), sotto)

def pagine(adesso, esiste):
    """{percorso: testo markdown} per il README e le pagine storia/<minuti>.md; esiste(percorso) dice se una mappa c'è."""
    out = {}
    for k in range(PASSI_STORIA):
        quando = adesso - timedelta(minutes=15 * k)
        su = "" if k == 0 else "../"
        quanto = "adesso" if k == 0 else f"{15 * k} minuti fa" if k < 4 else (f"{k // 4} h {15 * (k % 4)} min fa" if k % 4 else f"{k // 4} h fa")
        link = []
        if k < PASSI_STORIA - 1:
            link.append(f"[◀ 15 minuti prima]({'storia/' if k == 0 else ''}{15 * (k + 1)}.md)")
        if k > 0:
            link.append(f"[Adesso]({su}README.md)")
            link.append(f"[15 minuti dopo ▶]({'../README.md' if k == 1 else f'{15 * (k - 1)}.md'})")
        righe = [f"# Gottardo — traffico alle {quando:%H:%M}", "", f"**{quando:%d.%m.%Y %H:%M}** (ora svizzera, {quanto})", "",
                 " · ".join(link), "",
                 " · ".join(f"{p} {t}" for p, t in LEGENDA[:4]), ""]
        for fonte, etichetta in FONTI_MAPPA:
            m = nome_mappa(quando, fonte)
            righe += [f"### {etichetta}", "", f"![{etichetta}]({su}{m})" if esiste(m) else "_nessuna mappa per questo quarto d'ora_", ""]
        righe += [" · ".join(link), ""]
        out["README.md" if k == 0 else f"storia/{15 * k}.md"] = "\n".join(righe)
    return out
