#!/usr/bin/env python3
"""Prova del collector: filtro del corridoio, chiusura del tunnel, push.

Il difetto che queste prove sorvegliano e' successo davvero: il 03.08.2026
alle 22:16 il Gottardo e' rimasto chiuso per ore e nessuno dei due lettori se
n'e' accorto, perche' entrambi cercavano il tunnel per nome e la fonte quella
volta l'aveva scritto in un altro modo.

Le push non partono: send_push e' sostituito da una scatola che le raccoglie.
"""

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

QUI = Path(__file__).parent
COLLECT = QUI / "collect.py"

spec = importlib.util.spec_from_file_location("collect", COLLECT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

prove = []
def ok(nome, esito):
    prove.append((nome, bool(esito)))

# --- le push finiscono qui invece che ai telefoni ------------------------
inviate = []
c.send_push = lambda testo: (inviate.append(testo), True)[1]

# --- un documento come li manda la fonte ---------------------------------
def documento(situazioni):
    corpo = ""
    for s in situazioni:
        validita = "<validityStatus>active</validityStatus><validityTimeSpecification>"
        if s.get("inizio"):
            validita += f"<overallStartTime>{s['inizio']}</overallStartTime>"
        if s.get("periodo"):
            da, a = s["periodo"]
            validita += "<validPeriod>" + f"<startOfPeriod>{da}</startOfPeriod>"
            if a:
                validita += f"<endOfPeriod>{a}</endOfPeriod>"
            validita += "</validPeriod>"
        validita += "</validityTimeSpecification>"
        if s.get("qualificatore"):
            validita += ("<validityExtension><elementEnumerationExtension>"
                         "<element>validityStatus</element>"
                         f"<value>{s['qualificatore']}</value>"
                         "</elementEnumerationExtension></validityExtension>")
        valori = "".join(
            f'<value lang="{l}-CH">{t}</value>' for l, t in s["testi"].items())
        punti = "".join(
            f"<groupOfLocations><specificLocation>{p}</specificLocation>"
            f"</groupOfLocations>" for p in s.get("punti", []))
        direzione = (f"<alertCDirectionCoded>{s['direzione']}</alertCDirectionCoded>"
                     if s.get("direzione") else "")
        corpo += (
            f'<situationRecord xsi:type="{s.get("tipo", "RoadOrCarriagewayOrLaneManagement")}"'
            f' id="{s["id"]}">'
            f"<situationRecordVersionTime>{s['vt']}</situationRecordVersionTime>"
            f"<validity>{validita}</validity>"
            f"<generalPublicComment><comment><values>{valori}</values></comment>"
            f"<commentType>description</commentType></generalPublicComment>"
            f"{punti}{direzione}</situationRecord>")
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<d2LogicalModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            + corpo + "</d2LogicalModel>")

ADESSO = datetime.now(timezone.utc)
def fra(minuti):
    return (ADESSO + timedelta(minutes=minuti)).isoformat().replace("+00:00", "Z")

# --- i messaggi veri ------------------------------------------------------
CHIUSURA_ORA = {
    "id": "situation.999001.1.1.1", "vt": fra(-5), "punti": ["11187"],
    "inizio": fra(-5), "periodo": (fra(-6), None),
    "qualificatore": "untilFurtherNotice", "direzione": "both",
    "testi": {"it": "Approvato: A2 S. Gottardo -&gt; Chiasso Galleria Galleria San Gottardo "
                    "Situazione: tunnel chiuso Causa: problemi tecnici"},
}
CANTIERE_PROGRAMMATO = {
    "id": "situation.642392.1.1.1", "vt": fra(-60), "punti": ["11187"],
    "inizio": "2026-08-05T13:00:00Z",
    "periodo": ("2026-08-10T21:00:00Z", "2026-08-28T03:00:00Z"),
    "qualificatore": "duringTheNight", "direzione": "both",
    "testi": {"it": "Approvato: A2 Chiasso &lt;-&gt; S. Gottardo Galleria Galleria San Gottardo "
                    "Situazione: tunnel chiuso cantiere Durata: durante la notte probabile "
                    "10.08.2026 23:00 fino 28.08.2026 05:00"},
}
CHIUSURA_UN_SENSO = dict(CHIUSURA_ORA, id="situation.999002.1.1.1", direzione="negative")
CHIUSURA_REVOCATA = dict(
    CHIUSURA_ORA, id="situation.999003.1.1.1",
    testi={"it": "Revocato: A2 S. Gottardo -&gt; Chiasso Galleria Galleria San Gottardo "
                 "Situazione: tunnel chiuso Causa: problemi tecnici"})
ALTRA_GALLERIA = {
    "id": "situation.999004.1.1.1", "vt": fra(-5), "punti": ["27447"],
    "testi": {"it": "Approvato: A2 S. Gottardo -&gt; Luzern Galleria Galleria Naxberg "
                    "Situazione: tunnel chiuso cantiere"},
}
TUNNEL_ALTROVE = {
    "id": "situation.999005.1.1.1", "vt": fra(-5), "punti": ["25954"],
    "testi": {"it": "Approvato: A8 Brienz &lt;-&gt; Sarnen Galleria Galleria Giswil "
                    "Situazione: tunnel chiuso cantiere"},
}

def leggi(*situazioni):
    return c.extract(documento(list(situazioni)))

# --- il filtro del corridoio ---------------------------------------------
_, eventi, _, _, _ = leggi(CHIUSURA_ORA)
ok("la chiusura scritta 'Galleria San Gottardo' entra nel corridoio",
   any(e["id"] == "situation.999001.1.1.1" for e in eventi))
ok("  (nel testo non c'e' 'galleria del', che era l'unica forma in lista)",
   "galleria del" not in CHIUSURA_ORA["testi"]["it"].lower())

_, eventi, _, _, _ = leggi(TUNNEL_ALTROVE)
ok("un tunnel chiuso sull'A8 resta fuori", not eventi)

soloCodice = dict(CHIUSURA_ORA, id="situation.999006.1.1.1",
                  testi={"it": "Approvato: A2 in entrambe le direzioni "
                               "Situazione: tunnel chiuso per problemi tecnici"})
_, eventi, _, _, _ = leggi(soloCodice)
ok("il solo punto 11187 basta a far entrare il messaggio", len(eventi) == 1)

# --- riconoscimento della chiusura ---------------------------------------
ok("'tunnel chiuso' + punto del tunnel + in vigore = chiuso",
   leggi(CHIUSURA_ORA)[4]["chiuso"] is True)
ok("il cantiere programmato NON risulta chiuso",
   leggi(CANTIERE_PROGRAMMATO)[4]["chiuso"] is False)
ok("  ma il messaggio resta fra gli avvisi",
   len(leggi(CANTIERE_PROGRAMMATO)[1]) == 1)
ok("la Naxberg chiusa non e' il Gottardo chiuso",
   leggi(ALTRA_GALLERIA)[4]["chiuso"] is False)
ok("la revoca di una chiusura si registra come revoca",
   leggi(CHIUSURA_REVOCATA)[4]["revocato"] is True)
ok("  e non come chiusura", leggi(CHIUSURA_REVOCATA)[4]["chiuso"] is False)
ok("la direzione si legge dal campo codificato: negative = sud",
   leggi(CHIUSURA_UN_SENSO)[4]["direzione"] == "south")
ok("  e 'both' non e' un senso preciso",
   leggi(CHIUSURA_ORA)[4]["direzione"] is None)

# --- le due push ----------------------------------------------------------
def con_stato_pulito(fn):
    with tempfile.TemporaryDirectory() as d:
        c.HISTORY_FILE = Path(d) / "history.json"
        (Path(d)).mkdir(exist_ok=True)
        inviate.clear()
        fn()
    return list(inviate)

def giro(tunnel, quando=None):
    c.update_tunnel_notifications(tunnel, quando or ADESSO)

def chiuso(direzione=None):
    return {"chiuso": True, "revocato": False, "direzione": direzione, "testo": "x"}
def aperto(revocato=False):
    return {"chiuso": False, "revocato": revocato, "direzione": None, "testo": None}

inviate_1 = con_stato_pulito(lambda: (giro(chiuso()), giro(chiuso())))
ok("la chiusura manda UNA push, non una a ogni giro", inviate_1 == ["🚧 Gotthard tunnel closed"])

inviate_2 = con_stato_pulito(lambda: giro(chiuso("south")))
ok("chiusura a senso unico: la push lo dice",
   inviate_2 == ["🚧 Gotthard tunnel closed southbound"])
inviate_3 = con_stato_pulito(lambda: giro(chiuso("north")))
ok("  e anche verso nord", inviate_3 == ["🚧 Gotthard tunnel closed northbound"])

def revoca_subito():
    giro(chiuso())
    giro(aperto(revocato=True))
ok("la revoca fa partire subito la riapertura",
   con_stato_pulito(revoca_subito) ==
   ["🚧 Gotthard tunnel closed", "✅ Gotthard tunnel reopened"])

def sparisce_senza_revoca():
    giro(chiuso())
    giro(aperto(), ADESSO + timedelta(minutes=5))    # troppo presto
    giro(aperto(), ADESSO + timedelta(minutes=10))
ok("senza revoca non si annuncia subito la riapertura",
   con_stato_pulito(sparisce_senza_revoca) == ["🚧 Gotthard tunnel closed"])

def sparisce_e_resta_sparita():
    giro(chiuso())
    giro(aperto(), ADESSO + timedelta(minutes=5))
    giro(aperto(), ADESSO + timedelta(minutes=26))   # oltre CLEAR_CONFIRM
ok("...ma dopo la conferma sì",
   con_stato_pulito(sparisce_e_resta_sparita) ==
   ["🚧 Gotthard tunnel closed", "✅ Gotthard tunnel reopened"])

def buco_e_ritorno():
    giro(chiuso())
    giro(aperto(), ADESSO + timedelta(minutes=5))    # buco del feed
    giro(chiuso(), ADESSO + timedelta(minutes=10))   # era ancora chiuso
    giro(aperto(), ADESSO + timedelta(minutes=15))
    giro(aperto(), ADESSO + timedelta(minutes=30))   # la conferma riparte da 15
ok("un buco del feed non fa annunciare una riapertura falsa",
   con_stato_pulito(buco_e_ritorno) == ["🚧 Gotthard tunnel closed"])

ok("tunnel sempre aperto: nessuna push",
   con_stato_pulito(lambda: (giro(aperto()), giro(aperto()))) == [])

# --- lo stato non calpesta quello delle code ------------------------------
with tempfile.TemporaryDirectory() as d:
    c.HISTORY_FILE = Path(d) / "history.json"
    stato = Path(d) / "push-state.json"
    stato.write_text(json.dumps({"south": {"phase": "queued", "lastSent": None}}))
    inviate.clear()
    c.update_tunnel_notifications(chiuso(), ADESSO)
    dopo = json.loads(stato.read_text())
    ok("la chiusura scrive la sua chiave senza toccare quelle delle direzioni",
       dopo.get("south", {}).get("phase") == "queued" and dopo["tunnel"]["phase"] == "closed")

n = sum(1 for _, e in prove if e)
print("=== collector: corridoio, chiusura, push ===")
for nome, esito in prove:
    print("  OK  " if esito else "  NO  ", nome)
print(f"\n{n}/{len(prove)}")
sys.exit(0 if n == len(prove) else 1)
