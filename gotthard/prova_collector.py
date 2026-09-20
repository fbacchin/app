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

# --- la riapertura dice la direzione (ADEV-678, 12.09.2026) ---------------
def riapre_sud():
    giro(chiuso("south"))
    giro(aperto(revocato=True))
ok("chiusura verso sud: la riapertura dice verso sud",
   con_stato_pulito(riapre_sud) ==
   ["🚧 Gotthard tunnel closed southbound", "✅ Gotthard tunnel reopened southbound"])

def riapre_nord_senza_revoca():
    giro(chiuso("north"))
    giro(aperto(), ADESSO + timedelta(minutes=5))
    giro(aperto(), ADESSO + timedelta(minutes=26))
ok("  anche verso nord, e anche quando la riapertura arriva per conferma",
   con_stato_pulito(riapre_nord_senza_revoca) ==
   ["🚧 Gotthard tunnel closed northbound", "✅ Gotthard tunnel reopened northbound"])

def si_allarga():
    giro(chiuso("south"))
    giro(chiuso(None), ADESSO + timedelta(minutes=5))   # ora in entrambi i sensi
    giro(aperto(revocato=True), ADESSO + timedelta(minutes=10))
ok("una chiusura che si allarga ai due sensi riapre senza direzione",
   con_stato_pulito(si_allarga) ==
   ["🚧 Gotthard tunnel closed southbound", "✅ Gotthard tunnel reopened"])

def buco_senza_perdere_la_direzione():
    giro(chiuso("south"))
    giro(aperto(), ADESSO + timedelta(minutes=5))          # buco del feed
    giro(chiuso("south"), ADESSO + timedelta(minutes=10))
    giro(aperto(revocato=True), ADESSO + timedelta(minutes=15))
ok("un buco del feed non fa dimenticare la direzione",
   con_stato_pulito(buco_senza_perdere_la_direzione) ==
   ["🚧 Gotthard tunnel closed southbound", "✅ Gotthard tunnel reopened southbound"])

with tempfile.TemporaryDirectory() as d:
    c.HISTORY_FILE = Path(d) / "history.json"
    inviate.clear()
    c.update_tunnel_notifications(chiuso("south"), ADESSO)
    salvato = json.loads((Path(d) / "push-state.json").read_text())["tunnel"]
    c.update_tunnel_notifications(aperto(revocato=True), ADESSO)
    dopo = json.loads((Path(d) / "push-state.json").read_text())["tunnel"]
ok("la direzione sta nello stato mentre e' chiuso, e sparisce alla riapertura",
   salvato.get("direzione") == "south" and "direzione" not in dopo)

# Il doppione del 12.09 veniva dal workflow, non da qui: lo stato del giro
# delle 13:01 non era stato salvato perche' il git push era stato rifiutato,
# e il giro delle 13:06 ripartiva da «closed». Questa prova fissa il
# presupposto su cui regge la correzione nel workflow: se lo stato E' salvato,
# un giro successivo non rimanda nulla.
def stato_salvato_nessun_doppione():
    giro(chiuso("south"))
    giro(aperto(revocato=True), ADESSO + timedelta(minutes=10))
    giro(aperto(revocato=True), ADESSO + timedelta(minutes=15))
ok("con lo stato salvato, la riapertura parte una volta sola",
   con_stato_pulito(stato_salvato_nessun_doppione) ==
   ["🚧 Gotthard tunnel closed southbound", "✅ Gotthard tunnel reopened southbound"])

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

# --- la chiusura notturna ricorrente (07.09.2026) ---
#
# Il 07.09.2026 alle 20:00 il tunnel e' stato chiuso per cantiere, ogni notte
# fino al 25 settembre, e non e' partita nessuna notifica. Il messaggio
# arrivava — il collector legge il feed intero — ma `duringTheNight` lo
# faceva scartare come "non sappiamo quando". L'orario c'era, negli estremi
# del periodo. Il record e' quello vero: situation.645705.1.1.1.
import xml.etree.ElementTree as _ET

_NOTTURNO = _ET.fromstring("""
<situationRecord xmlns="http://datex2.eu/schema/2/2_0">
  <validity>
    <validityStatus>active</validityStatus>
    <validityTimeSpecification>
      <overallStartTime>2026-08-17T12:38:00.000000Z</overallStartTime>
      <validPeriod>
        <startOfPeriod>2026-09-07T18:00:00.000000Z</startOfPeriod>
        <endOfPeriod>2026-09-25T03:00:00.000000Z</endOfPeriod>
      </validPeriod>
    </validityTimeSpecification>
    <validityExtension>
      <elementEnumerationExtension>
        <element>validityStatus</element><value>duringTheNight</value>
      </elementEnumerationExtension>
    </validityExtension>
  </validity>
</situationRecord>""")

def _alle(giorno, ora, minuto=0):
    return datetime(2026, 9, giorno, ora, minuto, tzinfo=timezone.utc)

ok("la chiusura notturna vale alle 18:00Z, cioe' le 20:00 in Svizzera",
   c.in_vigore(_NOTTURNO, _alle(7, 18)) is True)
ok("  mezz'ora prima ancora no", c.in_vigore(_NOTTURNO, _alle(7, 17, 30)) is False)
ok("  a mezzanotte passata si', la finestra scavalca il giorno",
   c.in_vigore(_NOTTURNO, _alle(8, 1)) is True)
ok("  un minuto prima delle 03:00Z ancora si'",
   c.in_vigore(_NOTTURNO, _alle(8, 2, 59)) is True)
ok("  alle 03:00Z, cioe' le 05:00, ha finito",
   c.in_vigore(_NOTTURNO, _alle(8, 3)) is False)
ok("  a mezzogiorno no: e' una chiusura notturna, non continua",
   c.in_vigore(_NOTTURNO, _alle(8, 10)) is False)
ok("  e si ripete la settimana dopo", c.in_vigore(_NOTTURNO, _alle(14, 22)) is True)
ok("  l'ultima notte e' quella del 25", c.in_vigore(_NOTTURNO, _alle(25, 2)) is True)
ok("  finito l'inviluppo non vale piu'", c.in_vigore(_NOTTURNO, _alle(26, 21)) is False)

_OPACO = _ET.fromstring(_ET.tostring(_NOTTURNO).decode().replace(
    "duringTheNight", "severalTimes"))
ok("severalTimes resta scartato: non da' nessuna finestra da cui dedurre",
   c.in_vigore(_OPACO, _alle(7, 19)) is False)

_SENZA_PERIODO = _ET.fromstring("""
<situationRecord xmlns="http://datex2.eu/schema/2/2_0"><validity>
  <validityExtension><elementEnumerationExtension>
    <element>validityStatus</element><value>duringTheNight</value>
  </elementEnumerationExtension></validityExtension>
</validity></situationRecord>""")
ok("ricorrente SENZA periodo: la finestra non c'e', e non si inventa",
   c.in_vigore(_SENZA_PERIODO, _alle(7, 19)) is False)

_CONTINUO = _ET.fromstring("""
<situationRecord xmlns="http://datex2.eu/schema/2/2_0"><validity>
  <validityTimeSpecification><validPeriod>
    <startOfPeriod>2026-09-07T18:00:00Z</startOfPeriod>
    <endOfPeriod>2026-09-25T03:00:00Z</endOfPeriod>
  </validPeriod></validityTimeSpecification>
</validity></situationRecord>""")
ok("senza qualificatore lo stesso periodo e' continuo: vale anche a mezzogiorno",
   c.in_vigore(_CONTINUO, _alle(8, 10)) is True)

# --- i giorni della settimana dalla nota interna (ADEV-698, 19.09.2026) -----
# Il 18 e il 19.09.2026, venerdi' e sabato sera, l'app dava il tunnel chiuso
# ed era aperto. Il record vero porta «Mo-FR, jeweils in den Nächten von 20:00
# bis 05:00 Uhr»; il calendario ufficiale dice «4 notti, da lunedì sera a
# venerdì mattina». Il 14 e il 21 settembre 2026 sono lunedi'. Stessi casi
# delle prove del proxy: le due regole devono dire la stessa cosa.
# La nota VERA come sta nel magazzino (letta il 20.09.2026): il numero della
# perturbazione sulla prima riga, i giorni sulla seconda.
_NOTA_VERA = "ID116422\nMo-FR, jeweils in den Nächten von 20:00 bis 05:00 Uhr."
_v = lambda nota, g, h, mi=0: c.in_vigore(_NOTTURNO, _alle(g, h, mi), nota)
ok("Mo-Fr: lunedi' alle 20:00 chiuso", _v(_NOTA_VERA, 14, 18) is True)
ok("  lunedi' a mezzanotte e mezza chiuso", _v(_NOTA_VERA, 14, 22, 30) is True)
ok("  giovedi' alle 23:00 chiuso", _v(_NOTA_VERA, 17, 21) is True)
ok("  venerdi' alle 04:00 chiuso", _v(_NOTA_VERA, 18, 2) is True)
ok("  venerdi' alle 21:56 APERTO (il caso del 18.09)", _v(_NOTA_VERA, 18, 19, 56) is False)
ok("  sabato alle 00:30 APERTO", _v(_NOTA_VERA, 18, 22, 30) is False)
ok("  sabato alle 20:05 APERTO (il caso del 19.09)", _v(_NOTA_VERA, 19, 18, 5) is False)
ok("  domenica alle 23:00 APERTO", _v(_NOTA_VERA, 20, 21) is False)
ok("  lunedi' 21 alle 20:00 di nuovo chiuso", _v(_NOTA_VERA, 21, 18) is True)
ok("  martedi' 22 alle 03:00 chiuso", _v(_NOTA_VERA, 22, 1) is True)
ok("So - Fr: domenica sera chiuso", _v("So - Fr, nachts", 20, 21) is True)
ok("  venerdi' sera aperto", _v("So - Fr, nachts", 18, 21) is False)
ok("So/Mo Do/Fr: la notte di domenica chiusa", _v("So/Mo Do/Fr", 20, 21) is True)
ok("  quella di lunedi' aperta", _v("So/Mo Do/Fr", 21, 21) is False)
ok("nota assente: come prima, chiuso anche il sabato", _v(None, 19, 21) is True)
ok("  «Mo Do» non la leggiamo: chiuso", _v("Mo Do", 19, 21) is True)
ok("  «Mo-» nemmeno: chiuso", _v("Mo-", 19, 21) is True)
ok("  «Do/Sa» non e' una notte: chiuso", _v("Do/Sa", 19, 21) is True)
ok("  «Montag bis Freitag» non e' una sigla: chiuso", _v("Montag bis Freitag", 19, 21) is True)
ok("  una riga che non comincia coi giorni: chiuso", _v("Umleitung, Mo-Fr", 19, 21) is True)
ok("  i giorni valgono da qualunque riga", _v("ID116422\nBaustelle\nSo/Mo Do/Fr", 21, 21) is False)

# Dal documento: la nota sta in un record, il testo in un altro della stessa
# situazione, come nel feed vero. Si ferma l'orologio di `extract`.
_DOC_NOTA = f"""<?xml version="1.0" encoding="UTF-8"?>
<d2LogicalModel xmlns="http://datex2.eu/schema/2/2_0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<situation id="situation.645705"><situationRecord xsi:type="RoadOrCarriagewayOrLaneManagement" id="situation.645705.1.1.1">
  <situationRecordVersionTime>2026-08-17T12:41:48Z</situationRecordVersionTime>
  <validity><validityStatus>active</validityStatus><validityTimeSpecification>
    <overallStartTime>2026-08-17T12:38:00Z</overallStartTime>
    <validPeriod><startOfPeriod>2026-09-07T18:00:00Z</startOfPeriod>
      <endOfPeriod>2026-09-25T03:00:00Z</endOfPeriod></validPeriod>
  </validityTimeSpecification>
  <validityExtension><elementEnumerationExtension><element>validityStatus</element>
    <value>duringTheNight</value></elementEnumerationExtension></validityExtension></validity>
  <generalPublicComment><comment><values><value lang="it-CH">Approvato: A2 Chiasso &lt;-&gt; S. Gottardo Galleria Galleria San Gottardo Situazione: tunnel chiuso cantiere</value></values></comment>
    <commentType>description</commentType></generalPublicComment>
  <groupOfLocations><specificLocation>11187</specificLocation></groupOfLocations>
  <alertCDirectionCoded>both</alertCDirectionCoded>
</situationRecord>
<situationRecord xsi:type="RoadOrCarriagewayOrLaneManagement" id="situation.645705.1.1.2">
  <situationRecordVersionTime>2026-08-17T12:41:48Z</situationRecordVersionTime>
  <generalPublicComment><comment><values><value lang="de-CH">{_NOTA_VERA}</value></values></comment>
    <commentType>internalNote</commentType></generalPublicComment>
</situationRecord></situation></d2LogicalModel>"""

class _Orologio(datetime):
    fermo = None
    @classmethod
    def now(cls, tz=None):
        return cls.fermo
_vero = c.datetime
c.datetime = _Orologio
try:
    _Orologio.fermo = _alle(19, 18, 5)
    ok("dal documento, sabato alle 20:05: tunnel APERTO", c.extract(_DOC_NOTA)[4]["chiuso"] is False)
    _Orologio.fermo = _alle(21, 18, 5)
    ok("  lunedi' alle 20:05: tunnel chiuso", c.extract(_DOC_NOTA)[4]["chiuso"] is True)
finally:
    c.datetime = _vero

n = sum(1 for _, e in prove if e)
print("=== collector: corridoio, chiusura, push ===")
for nome, esito in prove:
    print("  OK  " if esito else "  NO  ", nome)
print(f"\n{n}/{len(prove)}")
sys.exit(0 if n == len(prove) else 1)
