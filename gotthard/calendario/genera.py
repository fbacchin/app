"""Proposta dei giorni critici al Gottardo (ADEV-802, regola approvata l'08.11.2026).

Legge le ferie ufficiali (ferie.json) e calcola le festivita' mobili; scrive per
ogni giorno e direzione «critico» o «molto critico» con i motivi. Niente
previsioni: solo il motivo per cui il giorno e' a rischio.

    python3 genera.py ferie.json DA A > proposta.json

Motivi strutturati (l'app li traduce, la pagina privata li scrive in italiano):
    {"tipo": "inizio_ferie" | "fine_ferie", "nome": "...", "regione": "DE-BW", "fonte": "https://..."}
    {"tipo": "festa", "festa": "pasqua" | "ascensione" | "pentecoste" | "corpus_domini"
                              | "festa_nazionale_ch" | "ognissanti"}
    {"tipo": "alta_stagione", "regioni": 12}
"""
import datetime as dt
import json
import sys
from collections import defaultdict

G = dt.timedelta(days=1)
CRITICO, MOLTO = 1, 2
ALTA_STAGIONE = 10
# Regioni le cui ferie non passano dal Gottardo. La Baviera va in Italia dal
# Brennero: nello storico l'inizio e la fine delle sue vacanze d'autunno
# (30.10 e 6-8.11.2026) non hanno portato nessuna coda, mentre le ferie brevi
# di Berna, Paesi Bassi nord e Baden-Wuerttemberg si' (decisione del 09.11).
ESCLUSE = {"DE-BY"}


def pasqua(anno):
    """Domenica di Pasqua, calendario gregoriano (algoritmo di Gauss/Meeus)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(anno, mese, giorno)


def sabato_di_partenza(inizio):
    """Il sabato del fine settimana in cui si parte per ferie che cominciano
    `inizio`: il primo sabato da due giorni prima in poi (lunedi' -> sabato
    prima, sabato -> se stesso, giovedi' -> il sabato dopo)."""
    d = inizio - 2 * G
    return d + ((5 - d.weekday()) % 7) * G


def giorni_di_partenza(inizio):
    """I giorni di partenza verso sud. Ferie che cominciano da martedi' a
    giovedi': l'ultimo giorno di scuola e il primo libero (Natale 2026 in
    Germania: mercoledi' 23 -> 22 e 23). Altrimenti venerdi' e sabato del fine
    settimana di partenza (correzione 1 approvata l'08.11)."""
    if 1 <= inizio.weekday() <= 3:
        return (inizio - G, inizio)
    sabato = sabato_di_partenza(inizio)
    return (sabato - G, sabato)


def giorni_di_rientro(fine):
    """Venerdi', sabato e domenica del rientro verso nord: nello storico il
    venerdi' pesa quanto gli altri due (correzione 2 approvata l'08.11)."""
    domenica = domenica_di_rientro(fine)
    return (domenica - 2 * G, domenica - G, domenica)


def domenica_di_rientro(fine):
    """La domenica del rientro da ferie che finiscono `fine` (ultimo giorno
    libero): la prima domenica da `fine` in poi."""
    return fine + ((6 - fine.weekday()) % 7) * G


def festivita(anno):
    """Festivita' con regola fissa: (giorni verso sud, giorni verso nord,
    livello, motivo)."""
    p = pasqua(anno)
    asc = p + 39 * G
    pent = p + 49 * G
    corpus = p + 60 * G
    voci = [
        ([p - 3 * G, p - G], [p + G], MOLTO, "pasqua"),
        ([asc - G], [asc + 3 * G], MOLTO, "ascensione"),
        ([pent - G], [pent + G], MOLTO, "pentecoste"),
        ([corpus - G], [corpus + 3 * G], CRITICO, "corpus_domini"),
    ]
    for giorno, nome in ((dt.date(anno, 8, 1), "festa_nazionale_ch"),
                         (dt.date(anno, 11, 1), "ognissanti")):
        # Ponte: la vigilia verso sud, l'ultimo giorno del fine settimana lungo
        # verso nord. Se la festa cade nel fine settimana resta la vigilia.
        fine = giorno
        if giorno.weekday() == 4:          # venerdi': si rientra domenica
            fine = giorno + 2 * G
        elif giorno.weekday() == 3:        # giovedi': ponte fino a domenica
            fine = giorno + 3 * G
        voci.append(([giorno - G], [fine], CRITICO, nome))
    return voci


def genera(ferie, da, a):
    ferie = [f for f in ferie if f["regione"] not in ESCLUSE]
    giorni = defaultdict(lambda: {"livello": 0, "motivi": []})

    def segna(giorno, direzione, livello, voce):
        """`voce` e' un motivo strutturato: {"tipo": ...} piu' i campi del tipo.
        Niente testo: l'app lo compone nella lingua di chi legge."""
        if not (da <= giorno <= a):
            return
        g = giorni[(giorno, direzione)]
        g["livello"] = max(g["livello"], livello)
        voce = {k: v for k, v in voce.items() if v is not None}
        if voce not in g["motivi"]:
            g["motivi"].append(voce)

    # Ferie: inizio verso sud, fine verso nord. «Molto critico» quando nello
    # stesso fine settimana cominciano (o finiscono) almeno due regioni.
    partenze, rientri = defaultdict(list), defaultdict(list)
    for f in ferie:
        partenze[giorni_di_partenza(dt.date.fromisoformat(f["inizio"]))].append(f)
        rientri[giorni_di_rientro(dt.date.fromisoformat(f["fine"]))].append(f)
    for giorni_p, elenco in partenze.items():
        livello = MOLTO if len({f["regione"] for f in elenco}) >= 2 else CRITICO
        for f in elenco:
            for giorno in giorni_p:
                segna(giorno, "south", livello, {"tipo": "inizio_ferie", "nome": f["nome"],
                                                 "regione": f["regione"], "fonte": f.get("fonte")})
    for giorni_r, elenco in rientri.items():
        livello = MOLTO if len({f["regione"] for f in elenco}) >= 2 else CRITICO
        for f in elenco:
            for giorno in giorni_r:
                segna(giorno, "north", livello, {"tipo": "fine_ferie", "nome": f["nome"],
                                                 "regione": f["regione"], "fonte": f.get("fonte")})

    for anno in range(da.year, a.year + 1):
        for sud, nord, livello, nome in festivita(anno):
            for giorno in sud:
                segna(giorno, "south", livello, {"tipo": "festa", "festa": nome})
            for giorno in nord:
                segna(giorno, "north", livello, {"tipo": "festa", "festa": nome})

    # Alta stagione (approvata l'08.11): con almeno ALTA_STAGIONE regioni in
    # ferie nello stesso giorno, ogni giorno e' critico nei due sensi.
    regioni = defaultdict(set)
    for f in ferie:
        d = max(dt.date.fromisoformat(f["inizio"]), da)
        while d <= min(dt.date.fromisoformat(f["fine"]), a):
            regioni[d].add(f["regione"])
            d += G
    for giorno, insieme in regioni.items():
        if len(insieme) >= ALTA_STAGIONE:
            for direzione in ("south", "north"):
                segna(giorno, direzione, CRITICO, {"tipo": "alta_stagione", "regioni": len(insieme)})

    nomi = {CRITICO: "critico", MOLTO: "molto critico"}
    return [{"data": g.isoformat(), "direzione": d, "livello": nomi[v["livello"]], "motivi": v["motivi"]}
            for (g, d), v in sorted(giorni.items())]


def prova():
    assert pasqua(2026) == dt.date(2026, 4, 5) and pasqua(2027) == dt.date(2027, 3, 28)
    lun, sab, gio = dt.date(2026, 8, 3), dt.date(2026, 7, 4), dt.date(2026, 7, 30)
    assert sabato_di_partenza(lun) == dt.date(2026, 8, 1)
    assert sabato_di_partenza(sab) == sab
    assert sabato_di_partenza(gio) == dt.date(2026, 8, 1)
    assert domenica_di_rientro(dt.date(2026, 8, 16)) == dt.date(2026, 8, 16)   # domenica
    assert domenica_di_rientro(dt.date(2026, 8, 7)) == dt.date(2026, 8, 9)     # venerdi'
    assert giorni_di_partenza(dt.date(2026, 12, 23)) == (dt.date(2026, 12, 22), dt.date(2026, 12, 23))
    assert giorni_di_partenza(gio) == (dt.date(2026, 7, 29), gio)
    assert giorni_di_partenza(lun) == (dt.date(2026, 7, 31), dt.date(2026, 8, 1))
    assert giorni_di_rientro(dt.date(2026, 8, 16))[0] == dt.date(2026, 8, 14)
    f = [{"regione": "A", "nome": "Estate", "inizio": "2026-08-03", "fine": "2026-08-30"},
         {"regione": "B", "nome": "Estate", "inizio": "2026-08-01", "fine": "2026-08-14"}]
    r = {(x["data"], x["direzione"]): x["livello"] for x in genera(f, dt.date(2026, 7, 1), dt.date(2026, 9, 30))}
    assert r[("2026-08-01", "south")] == "molto critico" and r[("2026-07-31", "south")] == "molto critico"
    assert r[("2026-08-16", "north")] == "critico" and r[("2026-08-30", "north")] == "critico"
    assert r[("2026-08-14", "north")] == "critico" and r[("2026-08-28", "north")] == "critico"
    assert ("2026-08-02", "south") not in r
    baviera = [{"regione": "DE-BY", "nome": "Herbst", "inizio": "2026-11-02", "fine": "2026-11-06"}]
    assert not [m for x in genera(baviera, dt.date(2026, 10, 1), dt.date(2026, 11, 30)) for m in x["motivi"]
                if m["tipo"].endswith("_ferie")], "la Baviera non conta"


if __name__ == "__main__":
    prova()
    if len(sys.argv) == 4:
        dati = json.load(open(sys.argv[1]))
        print(json.dumps(genera(dati["ferie"], dt.date.fromisoformat(sys.argv[2]),
                                dt.date.fromisoformat(sys.argv[3])), ensure_ascii=False, indent=1))
