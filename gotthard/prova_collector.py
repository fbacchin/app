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
c.send_push = lambda testo, dove=None: (inviate.append((testo, dove)), True)[1]
def testi():
    return [x[0] for x in inviate]

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
    return testi()

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

# =========================================================================
# Le soglie in km e i destinatari (05.09.2026)
#
# Il difetto che queste prove sorvegliano non e' ancora successo, ed e' il
# motivo per cui sono scritte adesso: una preferenza ASSENTE non significa
# "escluso", significa "mai scelta", cioe' il valore predefinito. Chi non
# aggiorna l'app non scrive mai quei campi. Sbagliare quel ramo lascerebbe la
# maggioranza dei dispositivi senza notifiche, e in silenzio.
# =========================================================================

def condizioni(dove):
    """Le condizioni in $and, come lista, per guardarci dentro."""
    return dove.get("$and", [])

d = c.destinatari(soglie=[c.SOGLIA_KM_PREDEFINITA])
varianti = condizioni(d)[0]["$or"]
ok("alla soglia predefinita rientra anche chi il campo non ce l'ha",
   {"pushCodaKm": {"$exists": False}} in varianti)
ok("  e chi l'ha scelta esplicitamente",
   {"pushCodaKm": {"$in": [c.SOGLIA_KM_PREDEFINITA]}} in varianti)

altra = [s for s in c.SOGLIE_KM if s != c.SOGLIA_KM_PREDEFINITA][0]
varianti = condizioni(c.destinatari(soglie=[altra]))[0]["$or"]
ok("a una soglia diversa dalla predefinita NON rientra chi non ha scelto",
   {"pushCodaKm": {"$exists": False}} not in varianti)

d = c.destinatari(soglie=[6], direzione="south")
ok("due filtri stanno in $and, non in due $or che si sovrascriverebbero",
   len(condizioni(d)) == 2 and "$or" not in d)
dirs = condizioni(d)[1]["$or"]
ok("la direzione ammette 'both', l'assenza e quella richiesta",
   {"pushDirezione": "both"} in dirs
   and {"pushDirezione": {"$exists": False}} in dirs
   and {"pushDirezione": "south"} in dirs)

d = c.destinatari(chiusure=True)
ok("le chiusure raggiungono chi non le ha mai spente",
   {"pushChiusure": {"$exists": False}} in condizioni(d)[0]["$or"])
ok("la coda non entra nel filtro delle chiusure",
   all("pushCodaKm" not in json.dumps(x) for x in condizioni(d)))

# --- la macchina a stati ---
def coda(km=None, minuti=None):
    return {"km": km, "wait": minuti}

def giro_code(sud, nord=None, quando=None):
    c.update_notifications({"south": sud, "north": nord or coda()}, quando or ADESSO)

def con_code(fn):
    with tempfile.TemporaryDirectory() as dd:
        c.HISTORY_FILE = Path(dd) / "history.json"
        inviate.clear()
        fn()
    return list(inviate)

fatte = con_code(lambda: giro_code(coda(km=3)))
ok("una coda di 3 km avvisa solo chi ha scelto 2", len(fatte) == 1
   and fatte[0][1]["$and"][0]["$or"][0] == {"pushCodaKm": {"$in": [2]}})

fatte = con_code(lambda: giro_code(coda(km=0.5)))
ok("mezzo chilometro non avvisa nessuno", fatte == [])

fatte = con_code(lambda: giro_code(coda(km=8)))
soglie = [x[1]["$and"][0]["$or"][0]["pushCodaKm"]["$in"][0] for x in fatte]
ok("una coda di 8 km avvisa le quattro soglie sotto, una volta ciascuna",
   sorted(soglie) == [2, 4, 6, 8])
ok("  e dalla piu' alta, cosi' nessuno riceve la soglia sbagliata per primo",
   soglie == [8, 6, 4, 2])

def cresce():
    giro_code(coda(km=3))
    giro_code(coda(km=5), quando=ADESSO + timedelta(minutes=5))
    giro_code(coda(km=7), quando=ADESSO + timedelta(minutes=10))
fatte = con_code(cresce)
soglie = [x[1]["$and"][0]["$or"][0]["pushCodaKm"]["$in"][0] for x in fatte]
ok("una coda che cresce non riavvisa chi ha gia' ricevuto",
   sorted(soglie) == [2, 4, 6] and len(soglie) == len(set(soglie)))

def cresce_e_finisce():
    giro_code(coda(km=5))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=10))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=40))
fatte = con_code(cresce_e_finisce)
ok("la fine arriva dopo la conferma", fatte[-1][0].endswith("queue cleared"))
finali = fatte[-1][1]["$and"][0]["$or"][0]["pushCodaKm"]["$in"]
ok("  e va SOLO a chi era stato avvisato dell'inizio", finali == [2, 4])
ok("  cioe' non a chi aveva scelto 6 e non ha mai saputo della coda",
   6 not in finali)

def finisce_senza_inizio():
    giro_code(coda(km=0))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=40))
ok("nessuna coda, nessun 'coda finita'", con_code(finisce_senza_inizio) == [])

# La coda scende, risale, riscende. Il minuto 35 e' scelto apposta: dista 25
# minuti dalla PRIMA discesa (piu' di CLEAR_CONFIRM) e 15 dalla seconda (meno).
# Se il conto alla rovescia non ripartisse, li' arriverebbe un "coda finita"
# mentre la coda c'e' ancora stata cinque minuti prima.
def rialza_la_testa(fino_a):
    giro_code(coda(km=5))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=10))
    giro_code(coda(km=5), quando=ADESSO + timedelta(minutes=15))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=20))
    giro_code(coda(km=0), quando=ADESSO + timedelta(minutes=fino_a))

fatte = con_code(lambda: rialza_la_testa(35))
ok("una coda che risale azzera il conto alla rovescia: al minuto 35 niente fine",
   [x for x in fatte if "cleared" in x[0]] == [])
fatte = con_code(lambda: rialza_la_testa(45))
ok("  e la fine arriva al minuto 45, venti dopo la discesa VERA",
   len([x for x in fatte if "cleared" in x[0]]) == 1)

fatte = con_code(lambda: giro_code(coda(minuti=30)))
soglie = [x[1]["$and"][0]["$or"][0]["pushCodaKm"]["$in"][0] for x in fatte]
ok("senza km si stimano dai minuti: 30 min = 3 km, avvisa solo il 2",
   soglie == [2])

# --- il passaggio dallo schema vecchio di push-state.json ---
def con_stato_vecchio(fase, km_ora):
    with tempfile.TemporaryDirectory() as dd:
        c.HISTORY_FILE = Path(dd) / "history.json"
        (Path(dd) / "push-state.json").write_text(json.dumps(
            {"south": {"phase": fase, "lastSent": None}}))
        inviate.clear()
        c.update_notifications({"south": coda(km=km_ora), "north": coda()}, ADESSO)
        return list(inviate)

ok("una coda gia' in corso al rilascio NON rimanda tutto da capo",
   con_stato_vecchio("queued", 7) == [])
ok("  e se era 'heavy' vale lo stesso", con_stato_vecchio("heavy", 7) == [])
ok("uno stato vecchio 'clear' non blocca invece una coda nuova",
   len(con_stato_vecchio("clear", 3)) == 1)

# --- l'attesa implausibile (04.09.2026) ---
ok("10 km con 10 minuti e' implausibile", c.attesa_implausibile(10, 10) is True)
ok("  e viene corretta a 100, cioe' km x 10",
   c.effective_wait({"km": 10, "wait": 10}) == 100)
ok("6 km con 60 minuti e' normale e non si tocca",
   c.effective_wait({"km": 6, "wait": 60}) == 60)
ok("6 km con 40 minuti resta com'e': la soglia non uniforma il traffico",
   c.effective_wait({"km": 6, "wait": 40}) == 40)
ok("pochi km e attesa lunga NON si corregge: e' l'area di dosaggio",
   c.effective_wait({"km": 0.5, "wait": 30}) == 30)
ok("sotto i 3 km non si controlla: i rapporti su numeri piccoli sono rumore",
   c.attesa_implausibile(2, 1) is False)
ok("senza km non si puo' giudicare", c.attesa_implausibile(None, 10) is False)

n = sum(1 for _, e in prove if e)
print("=== collector: corridoio, chiusura, push ===")
for nome, esito in prove:
    print("  OK  " if esito else "  NO  ", nome)
print(f"\n{n}/{len(prove)}")
sys.exit(0 if n == len(prove) else 1)
