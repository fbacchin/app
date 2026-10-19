# Banco di prova di gottardo-percorsi. Uso: python3 prova_percorsi.py
# Ogni funzione prova_* è una prova; i campioni sono risposte VERE delle fonti.
import sys, traceback

def prova_misure():
    from config import MISURE, PUNTI, VALICO
    assert len(MISURE) == 22 and len({m[0] for m in MISURE}) == 22      # 19.10: + 2 passo verso nord con la CUPRA
    for nome, o, d, percorso in MISURE:
        assert o in PUNTI and d in PUNTI and percorso in ("tunnel", "passo", "diretto", "cupra")
        assert nome.startswith("NS " if PUNTI[o][0] > PUNTI[d][0] else "SN ")   # nord = latitudine maggiore
    assert VALICO in PUNTI

import os, tempfile, csv
from datetime import datetime, timedelta, timezone

def prova_ritardo_ed_esiti():
    from archivio import risultato, ritardo_min, controlla_distanza
    assert ritardo_min(risultato("x", 3900, 3180, 83000)) == 12
    assert ritardo_min(risultato("x", 3000, 3180, 83000)) == -3          # di notte si scrive com'è
    assert ritardo_min(risultato("x", esito="percorso non trovato")) is None
    rif = {"x": 83000}
    assert controlla_distanza(risultato("x", 3900, 3180, 84000), rif)["esito"] == "ok"
    assert controlla_distanza(risultato("x", 3900, 3180, 97000), rif)["esito"] == "percorso diverso"
    assert ritardo_min(controlla_distanza(risultato("x", 3900, 3180, 97000), rif)) is None   # mai un tempo della strada sbagliata
    assert controlla_distanza(risultato("x", 3900, 3180, 97000), {})["esito"] == "ok"        # senza riferimento, nessun controllo

def prova_riga_sintetica():
    from archivio import risultato, riga_sintetica, INTESTAZIONE
    from config import MISURE
    rs = [risultato(m[0], 3600 + 60 * i, 3600, 80000) for i, m in enumerate(MISURE)]
    rs[1] = risultato(MISURE[1][0], esito="percorso non trovato")
    riga = riga_sintetica("2026-10-16 17:15", rs)
    assert len(riga) == len(INTESTAZIONE) and INTESTAZIONE[0] == "ora" and INTESTAZIONE[-1] == "esito"
    assert riga[0] == "2026-10-16 17:15" and riga[1] == 0 and riga[2] == "" and riga[3] == 2
    assert riga[-1] == f"{MISURE[1][0]}: percorso non trovato"
    assert riga_sintetica("t", [risultato(m[0], 60, 60, 1) for m in MISURE])[-1] == "ok"

def prova_scrittura_in_cima_e_mese():
    from archivio import aggiungi_in_cima, file_mese, ultime_24h, INTESTAZIONE
    from config import ZURIGO
    with tempfile.TemporaryDirectory() as d:
        ott = datetime(2026, 10, 31, 23, 45, tzinfo=ZURIGO)
        p = file_mese(d, "apple", ott)
        assert p.endswith("apple-2026-10.csv")
        assert file_mese(d, "apple", ott + timedelta(minutes=15)).endswith("apple-2026-11.csv")
        vuota = [""] * (len(INTESTAZIONE) - 2)
        for ora in ("2026-10-31 23:15", "2026-10-31 23:30", "2026-10-31 23:45"):
            aggiungi_in_cima(p, INTESTAZIONE, [[ora] + vuota + ["ok"]])
        righe = list(csv.reader(open(p, encoding="utf-8")))
        assert righe[0] == INTESTAZIONE
        assert [r[0] for r in righe[1:]] == ["2026-10-31 23:45", "2026-10-31 23:30", "2026-10-31 23:15"]
        # ultime 24 ore attraverso il cambio di mese: legge anche il file del mese prima
        nov = datetime(2026, 11, 1, 0, 15, tzinfo=ZURIGO)
        aggiungi_in_cima(file_mese(d, "apple", nov), INTESTAZIONE, [["2026-11-01 00:15"] + vuota + ["ok"]])
        assert [r["ora"] for r in ultime_24h(d, "apple", nov)] == ["2026-11-01 00:15", "2026-10-31 23:45", "2026-10-31 23:30", "2026-10-31 23:15"]

def prova_quote():
    from archivio import consenti, registra
    from config import ZURIGO
    uso, ott = {}, datetime(2026, 10, 20, 12, 0, tzinfo=ZURIGO)
    for _ in range(600):
        assert consenti(uso, "google", 8, ott); registra(uso, "google", 8, ott)
    assert not consenti(uso, "google", 8, ott)                             # 4.800: tetto raggiunto
    assert consenti(uso, "google", 8, datetime(2026, 11, 1, 0, 0, tzinfo=ZURIGO))   # mese nuovo
    registra(uso, "tomtom", 2000, ott)
    assert not consenti(uso, "tomtom", 8, ott) and consenti(uso, "tomtom", 8, ott + timedelta(days=1))   # tetto giornaliero
    assert consenti(uso, "apple", 5, ott)                                  # nessun tetto

import json as _json
def _campione(nome):
    return _json.load(open(nome, encoding="utf-8"))

def prova_pem_su_una_riga():
    from fonti import pem
    corpo = "MIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQg" + "A" * 80
    completo = pem(corpo)
    assert completo.startswith("-----BEGIN PRIVATE KEY-----\n") and completo.endswith("-----END PRIVATE KEY-----\n")
    assert pem(completo) == completo and pem(completo.replace("\n", " ")) == completo

def prova_apple_coppie():
    from fonti import richieste_apple
    r = richieste_apple()
    assert len(r) == 13 and sum(len(d) for _, d in r) == 26 and all(len(d) <= 10 for _, d in r)   # 16.10: con Göschenen–Airolo e le tratte separate

def prova_apple_campione():
    from fonti import apple
    from config import PUNTI, chiamate
    c = _campione("privati/campioni/apple-etas.json")
    origine = "origin=%s,%s" % PUNTI["Erstfeld"]
    chiama = lambda metodo, url, intestazioni=None, corpo=None: (c["codice"], c["risposta"]) if origine in url else (200, {"etas": []})
    rs = apple("t", chiama)
    assert [r["misura"] for r in rs] == [m[0] for m in chiamate("apple")]   # le CUPRA si calcolano dopo, nel giro
    tunnel = [r for r in rs if r["misura"] == "NS Erstfeld-Biasca tunnel"][0]   # nel campione
    assert tunnel["esito"] == "ok" and tunnel["con_traffico_s"] >= tunnel["senza_traffico_s"] > 0 and tunnel["distanza_m"] > 50000
    per_nome = {r["misura"]: r for r in rs}
    assert per_nome["NS Erstfeld-Biasca passo"]["esito"] == "percorso non trovato"   # manca Passo→Biasca: mai un tempo a metà
    assert per_nome["SN Biasca-Erstfeld tunnel"]["esito"] == "percorso non trovato"

def prova_apple_errore():
    from fonti import apple
    rs = apple("t", lambda *a, **k: (503, None))
    assert all(r["esito"] == "errore 503" and r["con_traffico_s"] is None for r in rs)

def prova_tomtom_campioni():
    from fonti import da_tomtom
    t = _campione("privati/campioni/tomtom-tunnel.json"); p = _campione("privati/campioni/tomtom-passo.json")
    rt, rp = da_tomtom("a", t["codice"], t["risposta"]), da_tomtom("b", p["codice"], p["risposta"])
    assert rt["esito"] == rp["esito"] == "ok" and rp["distanza_m"] > rt["distanza_m"] + 8000
    assert da_tomtom("c", 400, {"detailedError": {"code": "NO_ROUTE_FOUND"}})["esito"] == "percorso non trovato"
    assert da_tomtom("c", 403, None)["esito"] == "errore 403"

def prova_tomtom_otto_misure():
    from fonti import tomtom
    from config import chiamate
    rs = tomtom("k", lambda *a, **k: (500, None))
    assert [r["misura"] for r in rs] == [m[0] for m in chiamate("tomtom")] and len(rs) == 20 and all(r["esito"] == "errore 500" for r in rs)

def prova_google_campioni():
    from fonti import da_google
    t = _campione("privati/campioni/google-tunnel.json"); p = _campione("privati/campioni/google-passo.json")
    [rt], [rp] = da_google("a", t["codice"], t["risposta"]), da_google("b", p["codice"], p["risposta"])
    assert rt["esito"] == rp["esito"] == "ok" and isinstance(rt["con_traffico_s"], int) and rp["distanza_m"] > rt["distanza_m"] + 8000
    assert da_google("c", 200, {})[0]["esito"] == "percorso non trovato"
    assert [r["esito"] for r in da_google("c", 429, None, "SN Faido-Airolo")] == ["errore 429", "errore 429"]   # il tratto segue il passo
    assert da_google("b", p["codice"], p["risposta"], "SN Faido-Airolo")[1]["esito"] == "manca il tratto"      # risposta senza legs: niente tempi inventati

def prova_google_otto_misure():
    """Google resta a 8 misure: Amsteg–Faido e Göschenen–Airolo, niente Erstfeld–Biasca (decisione dell'utente, 16.10)."""
    from fonti import google
    corpi = []
    rs = google("k", lambda metodo, url, intestazioni=None, corpo=None: corpi.append(corpo) or (500, None))
    assert len(corpi) == 8 and len(rs) == 9 and all(r["esito"] == "errore 500" for r in rs)   # 19.10: + Faido→Airolo, senza chiamate in più
    assert {r["misura"].split()[1] for r in rs} == {"Amsteg-Faido", "Faido-Amsteg", "Göschenen-Airolo", "Airolo-Göschenen", "Faido-Airolo"}

def prova_google_sosta_ad_airolo():
    """19.10 (CUPRA): il passo Faido→Amsteg si chiede con una sosta ad Airolo; il primo tratto è Faido→Airolo, con i suoi tempi."""
    from fonti import google
    from config import PUNTI
    corpi = []
    def chiama(metodo, url, intestazioni=None, corpo=None):
        corpi.append(corpo)
        return 200, {"routes": [{"duration": "4200s", "staticDuration": "3700s", "distanceMeters": 64500,
                                 "legs": [{"duration": "1500s", "staticDuration": "900s", "distanceMeters": 19800},
                                          {"duration": "2700s", "staticDuration": "2800s", "distanceMeters": 44700}]}]}
    rs = {r["misura"]: r for r in google("k", chiama)}
    passo = next(c for c in corpi if c["origin"]["location"]["latLng"]["latitude"] == PUNTI["Faido"][0] and "intermediates" in c)
    assert [("via" in t, t["location"]["latLng"]["latitude"]) for t in passo["intermediates"]] == [(False, PUNTI["Airolo"][0]), (True, PUNTI["Passo"][0])]
    assert sum("intermediates" in c and len(c["intermediates"]) == 2 for c in corpi) == 1             # solo quel passo
    assert rs["SN Faido-Airolo"] == {"misura": "SN Faido-Airolo", "con_traffico_s": 1500, "senza_traffico_s": 900, "distanza_m": 19800, "esito": "ok"}
    assert rs["SN Faido-Amsteg passo"]["con_traffico_s"] == 4200

def prova_cupra():
    """Passo verso nord con la CUPRA = passo misurato meno il ritardo su Faido→Airolo (mai sotto zero)."""
    from archivio import con_cupra, risultato
    nomi = ["SN Biasca-Erstfeld passo CUPRA", "SN Faido-Amsteg passo CUPRA"]
    rs = [risultato("SN Biasca-Erstfeld passo", 5400, 4300, 90600), risultato("SN Faido-Amsteg passo", 4200, 3700, 64400),
          risultato("SN Faido-Airolo", 1500, 900, 19850)]
    c = {r["misura"]: r for r in con_cupra(rs, nomi)}
    assert c["SN Biasca-Erstfeld passo CUPRA"] == risultato("SN Biasca-Erstfeld passo CUPRA", 4800, 4300, 90600)   # 10 minuti di coda in meno
    assert c["SN Faido-Amsteg passo CUPRA"]["con_traffico_s"] == 3600
    piu_veloce = con_cupra(rs[:2] + [risultato("SN Faido-Airolo", 850, 900, 19850)], nomi)
    assert [r["con_traffico_s"] for r in piu_veloce] == [5400, 4200]                     # Faido→Airolo più rapido del previsto: niente da togliere
    assert [r["esito"] for r in con_cupra(rs[:2], nomi)] == ["manca Faido-Airolo"] * 2
    diverso = con_cupra([{**rs[0], "esito": "percorso diverso"}, rs[2]], nomi)
    assert [r["esito"] for r in diverso] == ["percorso diverso", "manca il passo"]       # mai un tempo dalla strada sbagliata
    assert con_cupra(rs, ["SN Faido-Amsteg passo CUPRA"])[0]["misura"] == "SN Faido-Amsteg passo CUPRA"   # Google: solo la sua

def prova_mappa_riga_cupra():
    from pagina import con_cupra
    t = {"SN Faido-Amsteg tunnel": 40, "SN Faido-Amsteg passo": 62, "SN Faido-Amsteg passo CUPRA": 52}
    assert con_cupra(t) == ["Con la CUPRA, se aperta, verso nord il passo: 52 min invece di 62 — peggio della galleria (40 min)"]
    assert con_cupra({**t, "SN Faido-Amsteg passo CUPRA": 61}) == []                     # 1 minuto: arrotondamento, nessuna riga
    assert "fa lo stesso" in con_cupra({**t, "SN Faido-Amsteg passo CUPRA": 41})[0]

def prova_colonne_nuove_nei_csv():
    """16.10: quattro colonne nuove in coda. Le righe vecchie si riallineano per nome; Google lascia vuote le sue."""
    from archivio import INTESTAZIONE, aggiungi_in_cima, riga_sintetica, risultato
    from config import MISURE
    d = tempfile.mkdtemp(); p = os.path.join(d, "x.csv")
    vecchia = ["ora"] + [m[0] for m in MISURE[:8]] + ["esito"]
    aggiungi_in_cima(p, vecchia, [["2026-10-16 12:00"] + ["1"] * 8 + ["ok"]])
    nuova = riga_sintetica("2026-10-16 13:00", [risultato(m[0], 120, 60, 1) for m in MISURE[:8]])
    aggiungi_in_cima(p, INTESTAZIONE, [nuova])
    righe = list(csv.DictReader(open(p)))
    assert [r["ora"] for r in righe] == ["2026-10-16 13:00", "2026-10-16 12:00"]
    assert righe[1]["esito"] == "ok" and righe[1][MISURE[0][0]] == "1" and righe[1][MISURE[11][0]] == ""
    assert righe[0]["esito"] == "ok" and righe[0][MISURE[0][0]] == "1" and righe[0][MISURE[8][0]] == ""

def prova_pallini():
    from pagina import pallino
    # Fino a 2 minuti è verde: 1-2 minuti sono arrotondamento, non coda (richiesta dell'utente, 15.10 sera).
    assert [pallino(v) for v in ("", "0", "-2", "1", "2", "3", "9", "10", "39", "40", "120")] == ["⚪", "🟢", "🟢", "🟢", "🟢", "🟡", "🟡", "🟠", "🟠", "🔴", "🔴"]

def prova_tempi_totali():
    from archivio import aggiungi_in_cima, file_mese, righe_dettaglio, risultato, ultimi_totali, INTESTAZIONE_DETTAGLIO
    from config import MISURE, ZURIGO
    adesso = datetime(2026, 10, 16, 17, 15, tzinfo=ZURIGO)
    with tempfile.TemporaryDirectory() as d:
        p = file_mese(d, "apple", adesso, "-dettaglio")
        vecchi = [risultato(m[0], 3000, 2900, 75000) for m in MISURE]
        nuovi = [risultato(m[0], 3840, 3120, 75000) for m in MISURE]
        nuovi[1] = risultato(MISURE[1][0], esito="errore 503")
        aggiungi_in_cima(p, INTESTAZIONE_DETTAGLIO, righe_dettaglio("2026-10-16 17:00", "x", vecchi))
        aggiungi_in_cima(p, INTESTAZIONE_DETTAGLIO, righe_dettaglio("2026-10-16 17:15", "x", nuovi))
        totali = ultimi_totali(d, "apple", adesso)
        assert totali[MISURE[0][0]] == 64 and MISURE[1][0] not in totali     # solo l'ultimo giro, senza le misure fallite

def prova_situazione():
    from pagina import situazione
    from config import MISURE
    riga = {m[0]: "0" for m in MISURE}
    riga.update({"SN Biasca-Erstfeld tunnel": "58", "SN Faido-Amsteg tunnel": "50", "SN Faido-Amsteg passo": "6", "NS Amsteg-Faido tunnel": ""})
    s = situazione({"apple": riga})
    assert s[("SN", "tunnel")] == 50 and s[("SN", "esterni")] == 8 and s[("SN", "passo")] == 6
    assert s[("NS", "tunnel")] is None and s[("NS", "esterni")] is None       # manca il centro: niente differenza inventata
    assert situazione({}) == {k: None for k in s}                               # fonte assente: tutto grigio

def prova_corsie_parallele():
    from pagina import _parallela
    assert _parallela([(0, 0), (10, 0)], 14) == [(0, 14), (10, 14)]
    assert [tuple(round(v, 6) for v in p) for p in _parallela([(0, 0), (10, 0), (10, 10)], 2)] == [(0, 2), (8, 2), (8, 10)]

def prova_mappe_per_fonte():
    from pagina import mappa_fonte
    from config import MISURE, ZURIGO
    q = datetime(2026, 10, 18, 15, 15, tzinfo=ZURIGO)
    riga = {m[0]: "12" for m in MISURE}
    svg = mappa_fonte("google", q, riga, {"NS Erstfeld-Biasca tunnel": 64}, ora_misura="2026-10-18 15:00")
    assert "Google — 15:15" in svg and "misura delle 2026-10-18 15:00" in svg and "+12 min · totale 64 min" in svg and "#ff6f00" in svg
    assert "misura delle" not in mappa_fonte("apple", q, riga, ora_misura="2026-10-18 15:15")
    assert "nessun dato in questo quarto d'ora" in mappa_fonte("tomtom", q)
    from pagina import FONTI_MAPPA
    assert [f for f, _ in FONTI_MAPPA] == ["apple", "tomtom", "google"]            # Waze tolto dal pannello (richiesta dell'utente, 15.10)

def prova_pagine_e_link():
    from pagina import pagine, nome_mappa, PASSI_STORIA
    from config import ZURIGO
    adesso = datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO)
    p = pagine(adesso, lambda m: "-google" not in m)                             # mappe Google mancanti
    assert set(p) == {"README.md"} | {f"storia/{15 * k}.md" for k in range(1, PASSI_STORIA)}
    assert "[◀ 15 minuti prima](storia/15.md)" in p["README.md"] and "15 minuti dopo" not in p["README.md"]
    assert f"![Apple Maps]({nome_mappa(adesso, 'apple')})" in p["README.md"]
    s15 = p["storia/15.md"]
    assert "[◀ 15 minuti prima](30.md)" in s15 and "[15 minuti dopo ▶](../README.md)" in s15 and "[Adesso](../README.md)" in s15
    assert "](../mappe/2026-10-18-1445-apple.svg)" in s15 and "_nessuna mappa per questo quarto d'ora_" in s15
    ultima = p[f"storia/{15 * (PASSI_STORIA - 1)}.md"]
    assert "15 minuti prima" not in ultima and f"[15 minuti dopo ▶]({15 * (PASSI_STORIA - 2)}.md)" in ultima

import io, contextlib, glob, json

SEGRETI_FINTI = {"APPLE_MAPS_KEY_ID": "SEGRETO-KID", "APPLE_TEAM_ID": "SEGRETO-TEAM", "APPLE_MAPS_PRIVATE_KEY": "SEGRETO-PEM",
                 "TOMTOM_KEY": "SEGRETO-TOMTOM", "GOOGLE_ROUTES_KEY": "SEGRETO-GOOGLE", "OPENWEBNINJA_KEY": "SEGRETO-OWN", "APIFY_TOKEN": "SEGRETO-APIFY"}

def _giro_finto(adesso, chiama, env=SEGRETI_FINTI, d=None):
    from giro import giro
    d = d or tempfile.mkdtemp()
    pub, priv = os.path.join(d, "pub"), os.path.join(d, "priv")
    uscita = io.StringIO()
    with contextlib.redirect_stdout(uscita), contextlib.redirect_stderr(uscita):
        giro(adesso, env, pub, priv, chiama)
    return pub, priv, uscita.getvalue()

def _tutti_i_file(*cartelle):
    return "".join(open(p, encoding="utf-8").read() for c in cartelle for p in glob.glob(c + "/**/*", recursive=True) if os.path.isfile(p))

def prova_giro_segreti_mai_in_uscita():
    from config import ZURIGO
    def chiama_che_fallisce(metodo, url, intestazioni=None, corpo=None):
        raise RuntimeError("errore con dentro " + url + str(intestazioni))   # il caso peggiore: un'eccezione che si porta dietro l'URL
    pub, priv, uscita = _giro_finto(datetime(2026, 10, 16, 17, 0, tzinfo=ZURIGO), chiama_che_fallisce)
    tutto = uscita + _tutti_i_file(pub, priv)
    assert not any(s in tutto for s in SEGRETI_FINTI.values()), "un segreto è finito in uscita o nei file"

def prova_giro_cosa_e_dove():
    from config import ZURIGO
    risposte = lambda metodo, url, intestazioni=None, corpo=None: (503, None)
    pub, priv, _ = _giro_finto(datetime(2026, 10, 16, 17, 16, 30, tzinfo=ZURIGO), risposte, {"TOMTOM_KEY": "k", "GOOGLE_ROUTES_KEY": "g"})
    assert os.path.exists(f"{priv}/dati/tomtom-2026-10.csv") and os.path.exists(f"{priv}/dati/tomtom-2026-10-dettaglio.csv")
    assert "2026-10-16 17:15" in open(f"{priv}/dati/tomtom-2026-10.csv", encoding="utf-8").read()   # ora del quarto d'ora
    assert not glob.glob(f"{priv}/dati/apple-*")                               # senza chiave la fonte non gira
    assert not glob.glob(f"{priv}/dati/google-*")                              # :15, non è il giro dell'ora
    assert not os.path.exists(pub) or not _tutti_i_file(pub)                   # nel pubblico non si scrive niente
    assert os.path.exists(f"{priv}/mappe/2026-10-16-1715-tomtom.svg") and not glob.glob(f"{priv}/mappe/*-apple.svg")
    assert os.path.exists(f"{priv}/README.md") and os.path.exists(f"{priv}/storia/15.md")
    pub, priv, _ = _giro_finto(datetime(2026, 10, 16, 18, 0, tzinfo=ZURIGO), risposte, {"GOOGLE_ROUTES_KEY": "g", "OPENWEBNINJA_KEY": "o", "APIFY_TOKEN": "a"})
    assert os.path.exists(f"{priv}/dati/google-2026-10.csv")
    assert not glob.glob(f"{priv}/dati/waze-*")                                # Waze non si raccoglie più (richiesta dell'utente, 15.10)
    uso = json.load(open(f"{priv}/uso.json"))
    assert uso == {"google": {"2026-10": 8}}

def prova_giro_orarie_tra_un_ora_e_l_altra():
    """Alle :15 la mappa di Google e quelle di Waze usano la misura delle :00, con l'ora scritta sotto il titolo."""
    from config import ZURIGO
    c = _campione("privati/campioni/google-tunnel.json")
    def risposte(metodo, url, intestazioni=None, corpo=None):
        # Google non misura più Erstfeld–Biasca (16.10): il campione della galleria fatto passare per Amsteg–Faido (50 km)
        if "googleapis" in url: return c["codice"], {**c["risposta"], "routes": [{**c["risposta"]["routes"][0], "distanceMeters": 50000}]}
        return 503, None
    d = tempfile.mkdtemp()
    env = {"GOOGLE_ROUTES_KEY": "g", "OPENWEBNINJA_KEY": "o"}
    _giro_finto(datetime(2026, 10, 16, 18, 0, tzinfo=ZURIGO), risposte, env, d)
    _, priv, _ = _giro_finto(datetime(2026, 10, 16, 18, 15, tzinfo=ZURIGO), risposte, env, d)
    g = open(f"{priv}/mappe/2026-10-16-1815-google.svg", encoding="utf-8").read()
    assert "misura delle 2026-10-16 18:00" in g and "totale" in g and "Amsteg–Faido" in g
    assert not glob.glob(f"{priv}/mappe/*-openwebninja.svg") and not glob.glob(f"{priv}/dati/waze-*")   # Waze: niente
    assert json.load(open(f"{priv}/uso.json"))["google"]["2026-10"] == 8   # alle :15 Google non è stato chiamato

def prova_giro_cancella_mappe_vecchie():
    from config import ZURIGO
    d = tempfile.mkdtemp(); priv = os.path.join(d, "priv"); os.makedirs(f"{priv}/mappe")
    for nome in ("2026-10-16-1415-apple.svg", "2026-10-16-1430-apple.svg", "appunti.txt"):   # 12 pagine: la più vecchia è 14:30
        open(f"{priv}/mappe/{nome}", "w").write("x")
    _giro_finto(datetime(2026, 10, 16, 17, 15, tzinfo=ZURIGO), lambda *a, **k: (503, None), {"TOMTOM_KEY": "k"}, d)
    rimaste = sorted(os.listdir(f"{priv}/mappe"))
    assert "2026-10-16-1415-apple.svg" not in rimaste and "2026-10-16-1430-apple.svg" in rimaste and "appunti.txt" in rimaste

def prova_giro_quota_esaurita():
    from config import ZURIGO
    from giro import giro
    d = tempfile.mkdtemp(); priv = os.path.join(d, "priv"); os.makedirs(priv)
    json.dump({"google": {"2026-10": 4800}}, open(f"{priv}/uso.json", "w"))
    chiamate = []
    giro(datetime(2026, 10, 16, 18, 0, tzinfo=ZURIGO), {"GOOGLE_ROUTES_KEY": "g"}, os.path.join(d, "pub"), priv,
         lambda *a, **k: chiamate.append(1) or (200, {}))
    assert not chiamate                                                        # nessuna richiesta oltre il tetto
    assert "quota esaurita" in open(f"{priv}/dati/google-2026-10.csv", encoding="utf-8").read()

def prova_tomtom_429_si_riprova():
    """15.10.2026: 8 richieste di fila → le ultime 3 con 429 (troppe al secondo per il piano gratuito)."""
    from fonti import tomtom
    c = _campione("privati/campioni/tomtom-tunnel.json")
    chiamate, pause = [], []
    def chiama(metodo, url, intestazioni=None, corpo=None):
        chiamate.append(url)
        return (429, None) if len(chiamate) in (5, 6) else (c["codice"], c["risposta"])
    rs = tomtom("k", chiama, attesa=pause.append)
    assert all(r["esito"] == "ok" for r in rs) and len(chiamate) == len(rs) + 2   # due 429 riprovati
    assert pause and all(p > 0 for p in pause)
    sempre = tomtom("k", lambda *a, **k: (429, None), attesa=lambda s: None)
    assert all(r["esito"] == "errore 429" for r in sempre)                 # dopo i tentativi si arrende, senza inventare

def prova_riferimenti():
    from config import RIFERIMENTI_M, MISURE
    from archivio import risultato, controlla_distanza
    assert set(RIFERIMENTI_M) == {m[0] for m in MISURE if m[3] != "cupra"}   # le CUPRA prendono la distanza del passo, già controllata
    for m in MISURE:
        if m[3] == "passo":
            assert RIFERIMENTI_M[m[0]] > RIFERIMENTI_M[m[0].replace("passo", "tunnel")] * 1.05   # le due strade si distinguono
    # 15.10.2026 17:30, TomTom: «galleria» verso nord sul passo (90,9 km) e «passo» verso sud con 16 km in più (106 km)
    assert controlla_distanza(risultato("SN Biasca-Erstfeld tunnel", 4553, 4434, 90948))["esito"] == "percorso diverso"
    assert controlla_distanza(risultato("NS Erstfeld-Biasca passo", 5363, 5245, 105999))["esito"] == "percorso diverso"
    assert controlla_distanza(risultato("NS Erstfeld-Biasca tunnel", 2928, 2914, 75536))["esito"] == "ok"

def prova_apple_valico_in_richieste_separate():
    """Revisione: col passo chiuso Apple potrebbe rifiutare tutta la richiesta; il valico non va mescolato alle altre destinazioni."""
    from fonti import apple, richieste_apple
    from config import VALICO, chiamate
    for origine, destinazioni in richieste_apple():
        assert VALICO not in destinazioni or destinazioni == [VALICO] or origine == VALICO
    c = _campione("privati/campioni/apple-etas.json")["risposta"]["etas"][0]      # Erstfeld→Biasca
    def chiama(metodo, url, intestazioni=None, corpo=None):
        if "46.5588,8.5621" in url: return 400, {"error": "no route"}           # tutto ciò che tocca il valico
        n = url.split("destinations=")[1].split("&")[0].count("|") + 1
        return 200, {"etas": [{**c, "destination": {"latitude": float(d.split(",")[0]), "longitude": float(d.split(",")[1])}}
                              for d in url.split("destinations=")[1].split("&")[0].split("|")]}
    rs = {r["misura"]: r for r in apple("t", chiama)}
    assert all(rs[m[0]]["esito"] == "ok" for m in chiamate("apple") if m[3] != "passo")
    assert all(rs[m[0]]["esito"] == "errore 400" for m in chiamate("apple") if m[3] == "passo")

def prova_giro_errore_a_meta_conta_le_quote():
    """Revisione: un'eccezione dopo registra() non deve far perdere il conteggio né fermare le altre fonti."""
    from config import ZURIGO
    import fonti
    d = tempfile.mkdtemp()
    vero = fonti.da_google
    from config import RIFERIMENTI_M
    fonti.da_google = lambda nome, codice, r, tratto=None: [{"misura": n, "con_traffico_s": None, "senza_traffico_s": 1,
                                                            "distanza_m": RIFERIMENTI_M[n], "esito": "ok"} for n in [nome] + [tratto] * bool(tratto)]   # ok ma senza tempo: TypeError più avanti
    try:
        _, priv, uscita = _giro_finto(datetime(2026, 10, 16, 18, 0, tzinfo=ZURIGO), lambda *a, **k: (503, None),
                                      {"GOOGLE_ROUTES_KEY": "g", "OPENWEBNINJA_KEY": "o"}, d)
    finally:
        fonti.da_google = vero
    uso = json.load(open(f"{priv}/uso.json"))
    assert uso["google"]["2026-10"] == 8                                        # contato anche se il giro si è rotto dopo
    assert "google errore TypeError" in uscita and os.path.exists(f"{priv}/README.md")

def prova_frecce_del_senso_di_marcia():
    """Richiesta dell'utente: frecce dentro le corsie, soprattutto agli svincoli di Göschenen e Airolo."""
    import re
    from pagina import mappa_fonte
    from config import MISURE, ZURIGO
    svg = mappa_fonte("apple", datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO), {m[0]: "0" for m in MISURE}, {})
    angoli = [float(a) for a in re.findall(r'class="freccia" transform="translate\([0-9.]+,[0-9.]+\) rotate\((-?[0-9.]+)\)', svg)]
    assert len(angoli) >= 16
    from pagina import X, Y_GALLERIA
    xs = [float(x) for x, y in re.findall(r'class="freccia" transform="translate\(([0-9.]+),([0-9.]+)\)', svg) if abs(float(y) - Y_GALLERIA) < 1]
    for a, b in (("Erstfeld", "Amsteg"), ("Amsteg", "Göschenen"), ("Airolo", "Faido"), ("Faido", "Biasca")):
        assert len([x for x in xs if X[a] < x < X[b]]) == 1, (a, b)                       # una sola freccia nei tratti corti
    assert 'd="M-6,0 L5,0 M1.5,-3.5 L5,0 L1.5,3.5"' in svg                                   # freccia «→» con l'asta, richiesta dell'utente
    assert any(abs(a) < 1 for a in angoli) and any(abs(abs(a) - 180) < 1 for a in angoli)       # verso sud → destra, verso nord → sinistra
    assert any(30 < a < 90 for a in angoli) and any(-90 < a < -30 for a in angoli)                # in discesa e in salita sui rami del passo

def prova_quale_conviene():
    """Richiesta dell'utente: in ogni mappa una riga che dica se conviene la galleria o il passo, con i totali di quella fonte."""
    from pagina import conviene, mappa_fonte
    from config import MISURE, ZURIGO
    t = {"NS Erstfeld-Biasca tunnel": 50, "NS Erstfeld-Biasca passo": 71,
         "SN Biasca-Erstfeld tunnel": 94, "SN Biasca-Erstfeld passo": 60}
    assert conviene(t) == "Adesso conviene: verso sud la galleria (50 min contro 71 del passo) · verso nord il passo (60 min contro 94 della galleria)"
    assert conviene({"NS Erstfeld-Biasca tunnel": 50, "NS Erstfeld-Biasca passo": 51, "SN Biasca-Erstfeld tunnel": 49}) == \
        "Adesso conviene: verso sud fa lo stesso (galleria 50 min, passo 51 min) · verso nord non si può dire (manca il tempo del passo)"
    assert conviene({}) == "Adesso conviene: verso sud non si può dire (manca il tempo della galleria) · verso nord non si può dire (manca il tempo della galleria)"
    svg = mappa_fonte("apple", datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO), {m[0]: "0" for m in MISURE}, t)
    assert 'font-weight="600">Adesso conviene: verso sud la galleria' in svg

def prova_passo_sopra_e_curve():
    """Richiesta dell'utente: il passo sopra la strada principale (si sale in montagna), curve morbide agli svincoli."""
    import re, math
    from pagina import mappa_fonte, Y_GALLERIA
    from config import MISURE, ZURIGO
    svg = mappa_fonte("apple", datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO), {m[0]: "0" for m in MISURE}, {})
    passo = re.findall(r'<polyline class="corsia-passo" points="([^"]+)"', svg)
    assert len(passo) == 2
    for pts in passo:
        p = [tuple(map(float, c.split(","))) for c in pts.split()]
        assert len(p) >= 20 and max(y for _, y in p) <= Y_GALLERIA + 14 + 0.5 and min(y for _, y in p) < Y_GALLERIA - 50   # sale sopra
        angoli = [math.degrees(math.atan2(y2 - y1, x2 - x1)) for (x1, y1), (x2, y2) in zip(p, p[1:])]
        assert max(abs(b - a) for a, b in zip(angoli, angoli[1:])) < 20                                         # niente spigoli

def prova_frecce_fuori_dalle_curve():
    """Richiesta dell'utente: sulla strada principale nessuna freccia sotto le curve degli svincoli."""
    import re
    from pagina import mappa_fonte, X, CURVA, Y_GALLERIA, CORSIA
    from config import MISURE, ZURIGO
    svg = mappa_fonte("apple", datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO), {m[0]: "0" for m in MISURE}, {})
    sulla_strada = [float(x) for x, y in re.findall(r'class="freccia" transform="translate\(([0-9.]+),([0-9.]+)\)', svg)
                    if abs(float(y) - Y_GALLERIA) < 1 or abs(float(y) - Y_GALLERIA - CORSIA) < 1]
    for x0, x1 in ((X["Göschenen"], X["Göschenen"] + CURVA), (X["Airolo"] - CURVA, X["Airolo"])):
        assert not [x for x in sulla_strada if x0 - 5 < x < x1 + 5], (x0, x1)
    assert len([x for x in sulla_strada if X["Göschenen"] < x < X["Airolo"]]) >= 2 * 2   # in galleria restano frecce in tutti e due i sensi

def prova_tratteggio_strada_agli_svincoli():
    """Richiesta dell'utente: dove le curve del passo coprono la strada dritta, un tratteggio ne mostra la continuazione verso la galleria."""
    import re
    from pagina import mappa_fonte, X, Y_GALLERIA, CORSIA
    from config import MISURE, ZURIGO
    svg = mappa_fonte("apple", datetime(2026, 10, 18, 15, 0, tzinfo=ZURIGO), {m[0]: "0" for m in MISURE}, {})
    linee = re.findall(r'<line class="continua" x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"[^>]*stroke-dasharray', svg)
    assert len(linee) == 4                                                        # 2 svincoli × 2 corsie
    assert {round(float(y)) for _, y, _, _ in linee} == {Y_GALLERIA, Y_GALLERIA + CORSIA}
    assert svg.index('class="continua"') > svg.index('class="corsia-passo"')       # sopra le curve, altrimenti non si vede

def prova_conviene_senza_erstfeld_biasca():
    """Google non misura Erstfeld–Biasca (16.10): la riga usa Amsteg–Faido e lo dice."""
    from pagina import conviene
    assert conviene({"NS Amsteg-Faido tunnel": 40, "NS Amsteg-Faido passo": 55, "SN Faido-Amsteg tunnel": 60, "SN Faido-Amsteg passo": 50}) == \
        "Adesso conviene (Amsteg–Faido): verso sud la galleria (40 min contro 55 del passo) · verso nord il passo (50 min contro 60 della galleria)"
    assert conviene({"NS Erstfeld-Biasca tunnel": 50, "NS Amsteg-Faido tunnel": 40}).startswith("Adesso conviene: verso sud non si può dire")

def prova_tolleranza_tratte_corte():
    from archivio import risultato, controlla_distanza
    assert controlla_distanza(risultato("NS Erstfeld-Amsteg", 300, 300, 8188))["esito"] == "ok"                 # TomTom, 0,8 km sotto Apple
    assert controlla_distanza(risultato("NS Airolo-Faido", 1400, 1300, 30436))["esito"] == "percorso diverso"   # il giro di TomTom dal vecchio punto

def _xml_astra(valori):
    """Risposta DATEX II minima come quella dei contatori: {record: (auto/h, km/h)}."""
    righe = "".join(
        f'<siteMeasurements><measurementSiteReference id="{rid}"/><measurementTimeDefault>2026-10-19T14:22:00Z</measurementTimeDefault>'
        f'<measuredValue index="11"><measuredValue><basicData><vehicleFlow><vehicleFlowRate>{q}</vehicleFlowRate></vehicleFlow></basicData></measuredValue></measuredValue>'
        + (f'<measuredValue index="12"><measuredValue><basicData><averageVehicleSpeed><speed>{v}</speed></averageVehicleSpeed></basicData></measuredValue></measuredValue>' if v else "")
        + '</siteMeasurements>' for rid, (q, v) in valori.items())
    return f'<Envelope xmlns="http://datex2.eu/schema/2/2_0"><Body><d2LogicalModel><payloadPublication>{righe}</payloadPublication></d2LogicalModel></Body></Envelope>'.encode()

def prova_astra():
    """19.10: contatori ASTRA sulle tratte separate. Velocità pesata sul flusso delle corsie, tratta divisa tra le sue stazioni."""
    from fonti import astra, letture_astra, velocita_astra
    from config import CORSIE_ASTRA, RIFERIMENTI_M, SENSO_ASTRA
    valori = {f"{s}.{c}": (600, 100) for s, sensi in CORSIE_ASTRA.items() for cs in sensi.values() for c in cs}
    valori["CH:0293.03"], valori["CH:0293.04"] = (300, 30), (900, 10)          # Quinto, un senso in coda
    valori["CH:0204.01"] = valori["CH:0204.02"] = (0, None)                    # nessuna auto in quel minuto
    letture = letture_astra(_xml_astra(valori))
    assert letture["CH:0293.03"] == ("2026-10-19T14:22:00Z", 300.0, 30.0, None, None)
    assert velocita_astra(letture, "CH:0293", "positive") == (300 * 30 + 900 * 10) / 1200     # 15 km/h
    assert velocita_astra(letture, "CH:0204", "negative") is None
    grezze = []
    rs = {r["misura"]: r for r in astra("k", lambda corpo, chiave: (200, _xml_astra(valori)), grezze)}
    assert len(rs) == 8 and len(grezze) == len(valori) and grezze[0][0] == "CH:0166.01"
    nome = {"SN": "SN Faido-Airolo", "NS": "NS Airolo-Faido"}
    coda, libero = rs[nome[SENSO_ASTRA["positive"]]], rs[nome[SENSO_ASTRA["negative"]]]   # il senso «positive» è quello in coda
    assert coda["con_traffico_s"] == round(RIFERIMENTI_M[coda["misura"]] / (15 / 3.6)) and coda["senza_traffico_s"] is None
    assert libero["con_traffico_s"] == round(RIFERIMENTI_M[libero["misura"]] / (100 / 3.6))
    assert rs["NS Faido-Biasca"]["esito"] == "nessun veicolo misurato" and rs["SN Biasca-Faido"]["esito"] == "ok"
    assert all(r["esito"] == "errore 403" for r in astra("k", lambda corpo, chiave: (403, b"")))
    from archivio import ritardo_min, riga_sintetica
    assert ritardo_min(libero) is None and "NS Faido-Biasca: nessun veicolo misurato" in riga_sintetica("t", list(rs.values()))[-1]

def prova_giro_astra():
    """Il giro scrive i CSV dei contatori (anche le letture grezze per corsia) nel privato, e nessuna mappa."""
    from config import ZURIGO, CORSIE_ASTRA
    from giro import giro
    d = tempfile.mkdtemp(); priv = os.path.join(d, "priv")
    valori = {f"{s}.{c}": (600, 100) for s, sensi in CORSIE_ASTRA.items() for cs in sensi.values() for c in cs}
    giro(datetime(2026, 10, 19, 16, 15, tzinfo=ZURIGO), {"OTD_CONTATORI_KEY": "k"}, os.path.join(d, "pub"), priv,
         lambda *a, **k: (503, None), lambda corpo, chiave: (200, _xml_astra(valori)))
    for suffisso in ("", "-dettaglio", "-stazioni"):
        assert os.path.exists(f"{priv}/dati/astra-2026-10{suffisso}.csv"), suffisso
    righe = list(csv.DictReader(open(f"{priv}/dati/astra-2026-10-stazioni.csv", encoding="utf-8")))
    assert len(righe) == len(valori) and righe[0]["ora"] == "2026-10-19 16:15" and righe[0]["auto_kmh"] == "100.0"
    assert not glob.glob(f"{priv}/mappe/*-astra.svg") and not os.path.exists(os.path.join(d, "pub"))

if __name__ == "__main__":
    prove = [(n, f) for n, f in sorted(globals().items()) if n.startswith("prova_") and callable(f)]
    falliti = 0
    for nome, f in prove:
        try: f(); print("ok  ", nome)
        except Exception: falliti += 1; print("NO  ", nome); traceback.print_exc()
    print(f"{len(prove) - falliti}/{len(prove)}")
    sys.exit(1 if falliti else 0)

