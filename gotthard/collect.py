#!/usr/bin/env python3
"""Raccoglitore storico per Gottardo Live.

Interroga l'API "Traffic Situations" di opentransportdata.swiss (DATEX II),
estrae lo stato delle code ai portali del tunnel del San Gottardo e accoda
un campione a data/history.json (finestra mobile di 48 ore).

Pensato per girare via GitHub Actions ogni ~10 minuti.
Richiede la variabile d'ambiente OTD_API_KEY.
"""

import gzip
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENDPOINT = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
SOAP_ACTION = "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages"

SOAP_BODY = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <d2LogicalModel xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2" xmlns="http://datex2.eu/schema/2/2_0">
    <exchange>
        <supplierIdentification>
            <country>ch</country>
            <nationalIdentifier>FEDRO</nationalIdentifier>
        </supplierIdentification>
        <subscription>
            <operatingMode>operatingMode1</operatingMode>
            <subscriptionStartTime>2025-01-01T08:00:00.00+01:00</subscriptionStartTime>
            <subscriptionState>active</subscriptionState>
            <updateMethod>singleElementUpdate</updateMethod>
            <target>
                <address></address>
                <protocol>http</protocol>
            </target>
        </subscription>
    </exchange>
    </d2LogicalModel>
  </soap:Body>
</soap:Envelope>
"""

# Località del corridoio del tunnel (stesso filtro dell'app iOS)
# I nomi con cui la fonte chiama LA GALLERIA. Ne usa piu' d'uno e alterna
# senza regola: "Galleria Galleria del S. Gottardo" e "Galleria Galleria San
# Gottardo", senza "del". La lista aveva solo le forme col "del", e il
# 03.08.2026 alle 22:16 la chiusura del tunnel — scritta nell'altro modo — e'
# stata scartata all'ingresso: ne' l'app ne' questo collector se ne sono
# accorti per tutta la notte. Il tedesco scrive "Gotthard-Tunnel" col trattino.
NOMI_TUNNEL = [
    "galleria del s. gottardo", "galleria del san gottardo",
    "galleria s. gottardo", "galleria san gottardo",
    "gotthardtunnel", "gotthard tunnel", "gotthard-tunnel",
]
CORRIDOR = NOMI_TUNNEL + [
    "göschenen", "goeschenen", "airolo", "wassen", "amsteg", "erstfeld",
    "quinto", "faido", "area di dosaggio",
]

# --- il corridoio per CODICE, non per nome ---
# I punti AlertC (tabella svizzera n. 9) che la fonte dichiara nei messaggi.
# Il codice viene prima del nome perche' e' un dato, mentre il nome e' prosa e
# cambia forma: la chiusura del 03.08 portava 11187 come tutti gli altri
# messaggi sulla galleria, ma si chiamava in un modo che non avevamo in lista.
PUNTO_TUNNEL = "11187"                     # la galleria del San Gottardo
PUNTI_LATO_URI = {                         # a nord del tunnel
    "10455",   # Svincolo autostradale Erstfeld
    "11588",   # Erstfeld (abitato)
    "10456",   # Svincolo autostradale Amsteg
    "10458",   # Svincolo autostradale Wassen
    "10460",   # Svincolo autostradale Göschenen (A2)
    "10459",   # Svincolo autostradale Göschenen (H2)
    "27447",   # Galleria Naxberg
}
PUNTI_LATO_TICINO = {                      # a sud del tunnel
    "10275",   # Svincolo autostradale Airolo
    "11320",   # Airolo (abitato)
    "14913",   # Parcheggio Area di dosaggio Airolo
    "27706",   # Svincolo autostradale Airolo-Nufenen
    "10461",   # Svincolo autostradale Quinto
    "10462",   # Svincolo autostradale Faido
    "11598",   # Faido (abitato)
}
PUNTI_CORRIDOIO = {PUNTO_TUNNEL} | PUNTI_LATO_URI | PUNTI_LATO_TICINO

# --- chiusura del tunnel ---
# La fonte annuncia la chiusura con "Situazione: tunnel chiuso" e NON annuncia
# la riapertura: revoca il messaggio di chiusura. Controllato su 18 record di
# chiusura in dodici catture del feed: "tunnel aperto" non compare mai.
FRASI_CHIUSURA = [
    "tunnel chiuso",                    # it
    "tunnel gesperrt",                  # de
    "tunnel fermé", "tunnel ferme",     # fr
    "tunnel closed",                    # en
]
# I qualificatori che dicono "solo in certe ore" senza dire quali: con uno di
# questi non possiamo affermare che la chiusura sia in corso adesso. Quattro
# valori in 34548 blocchi d'archivio; `untilFurtherNotice` non e' fra questi
# perche' non e' una restrizione — dice "da adesso e fino a nuovo avviso", ed
# e' come era scritta la chiusura del 03.08.2026.
QUALIFICATORI_A_ORARIO = {"duringTheNight", "duringTheDayTime", "severalTimes"}

# La direzione come la dichiara la fonte, non come la si indovina dal testo.
# Verificato il 03.08.2026 su 50 concordanze e zero contraddizioni.
DIREZIONE_CODIFICATA = {"positive": "north", "negative": "south"}
SOUTH_MARKERS = [
    "luzern -> s. gottardo", "lucerna -> s. gottardo",
    "basilea -> s. gottardo", "basel -> s. gottardo",
    "s. gottardo -> chiasso", "in direzione sud", "richtung süden",
]
NORTH_MARKERS = [
    "chiasso -> s. gottardo",
    "s. gottardo -> luzern", "s. gottardo -> lucerna",
    "s. gottardo -> basilea", "s. gottardo -> basel",
    "in direzione nord", "richtung norden",
]
SOUTH_PORTAL = ["göschenen", "goeschenen", "wassen", "amsteg", "erstfeld"]
NORTH_PORTAL = ["airolo", "quinto", "faido", "dosaggio"]

# Un messaggio di coda è considerato attuale solo se aggiornato di recente
# (il feed contiene record "attivi" mai chiusi, vecchi di mesi).
# NB: durante una coda stabile il versionTime può restare fermo a lungo
# (es. plateau a 50 min per un'ora): la finestra deve essere ampia — 6 ore,
# come nell'app. La fine reale di una coda arriva come revoca/rimozione
# del messaggio dal feed, non per scadenza del timestamp.
FRESHNESS = timedelta(hours=6)

# Stima del ritardo quando il messaggio riporta solo i km di coda
MINUTES_PER_KM = 10

# --- Notifiche push (Back4App) ---
# Inviate quando una coda si forma (>= NOTIFY_START), diventa pesante
# (>= NOTIFY_HEAVY, una volta) e quando si dissolve (< NOTIFY_CLEAR).
# Lo stato per direzione vive in data/push-state.json (committato) e un
# cooldown evita raffiche di notifiche.
PUSH_APP_ID = os.environ.get("B4A_APP_ID", "")
PUSH_MASTER_KEY = os.environ.get("B4A_MASTER_KEY", "")
NOTIFY_START = 20   # minuti di attesa: coda formata
NOTIFY_HEAVY = 60   # minuti: escalation "coda pesante"
NOTIFY_CLEAR = 10   # sotto questa soglia la coda è considerata finita
PUSH_COOLDOWN = timedelta(minutes=45)
# La coda deve restare sotto NOTIFY_CLEAR per almeno questo tempo prima di
# annunciare "finita": sull'area di dosaggio di Airolo il messaggio ufficiale
# viene revocato e riemesso a impulsi, quindi un singolo buco nel feed non
# significa che il traffico è tornato scorrevole.
CLEAR_CONFIRM = timedelta(minutes=20)
# Tetto della TENUTA anti-lampeggio (hold_through_gaps): quanto a lungo un
# messaggio assente senza revoca viene considerato "buco del feed" e non
# "coda finita". È separato da CLEAR_CONFIRM (che governa solo la notifica
# di fine coda): il 01.08.2026 il feed è rimasto muto per 59 minuti con la
# coda ferma a 8 km, quindi 20 minuti non bastavano. Con le revoche a fare
# da interruttore, una fine annunciata azzera comunque subito.
HOLD_WINDOW = timedelta(minutes=60)

HISTORY_FILE = Path(__file__).parent / "data" / "history.json"
WINDOW = timedelta(hours=48)

# Archivio degli avvisi ufficiali. Il feed ritira i messaggi a impulsi (lo
# stesso lampeggio che colpiva le code): un avviso che sparisce per un giro
# non è un avviso finito. Qui si accumulano per id, con firstSeen/lastSeen e
# l'eventuale revoca esplicita, così l'app ha una lista stabile e si ottiene
# uno storico degli avvisi che il feed da solo non conserva.
ALERTS_FILE = Path(__file__).parent / "data" / "alerts.json"
ALERTS_WINDOW = timedelta(hours=48)

# Registro di cio' che l'API comunica sul corridoio: una riga per ogni
# comparsa, cambiamento o revoca. NON si salva il documento grezzo — 7-22 MB a
# chiamata, quattro gigabyte al giorno, e il 99,8% non riguarda il Gottardo.
# Serve a rispondere a posteriori alla domanda "e' davvero arrivata una
# revoca?": il 02.08.2026 non e' stato possibile, perche' un'ora dopo il
# messaggio non era piu' nel feed e restavano solo indizi indiretti.
FEED_LOG_FILE = Path(__file__).parent / "data" / "feed-log.jsonl"
FEED_LOG_WINDOW = timedelta(days=14)


def local(tag):
    return tag.split("}")[-1]


def localtype(value):
    return value.split(":")[-1]


def parse_time(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def queue_km(text):
    for pattern in (
        r"(?:colonna|coda|stau)[^.;]{0,40}?lunghezza\s*\[km\]\s*(\d+(?:[.,]\d+)?)",
        r"(?:coda|colonna|stau|bouchon|queue)[^.;]{0,60}?(\d+(?:[.,]\d+)?)\s*km",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def wait_minutes(text):
    lower = text.lower()
    match = re.search(r"ritardi\s*no\.\s*\[min\]\s*(\d+)", lower)
    if match:
        return int(match.group(1))
    # Il VMZ pubblica l'attesa anche in ORE, coi decimali: "[h] 1.333" = 80 min.
    # Senza questo caso il campo restava vuoto e si ripiegava sulla stima dai
    # km (~10 min/km): con "[h] 2" su 6 km si mostravano 60 minuti invece di 120.
    match = re.search(r"ritardi\s*no\.\s*\[h\]\s*(\d+(?:[.,]\d+)?)", lower)
    if match:
        valore = float(match.group(1).replace(",", "."))
        # L'etichetta [h] NON e' affidabile: il 02.08.2026 il feed ha pubblicato
        # "colonna lunghezza [km] 7.0 ... ritardi No. [h] 70", cioe' 70 MINUTI
        # (coerenti con 7 km) marcati come ore. Interpretandolo alla lettera
        # uscivano 4200 minuti, settanta ore.
        # Regola: si crede all'etichetta solo se il risultato resta plausibile.
        # Oltre le 6 ore nessuna attesa al Gottardo e' credibile — le giornate
        # peggiori arrivano a 3-4 ore — quindi il numero era in minuti.
        minuti = round(valore * 60)
        return minuti if minuti <= 360 else round(valore)
    match = re.search(
        r"(\d+)\s*(?:ora|ore|stunde|stunden|heure|heures)(?:\D{1,8}(\d+)\s*min)?", lower
    )
    if match:
        return int(match.group(1)) * 60 + int(match.group(2) or 0)
    match = re.search(r"(?:fino a|bis zu|jusqu'à)\s*(\d+)\s*min", lower)
    if match:
        return int(match.group(1))
    return None


def direction_of(lower):
    has_south = any(m in lower for m in SOUTH_MARKERS)
    has_north = any(m in lower for m in NORTH_MARKERS)
    if has_south and not has_north:
        return "south"
    if has_north and not has_south:
        return "north"
    return None


def fetch_feed(api_key):
    """Scarica il feed, con retry sugli errori transitori del server.

    Nei giorni di punta (1. agosto…) opentransportdata.swiss risponde a
    tratti 503: perdere l'intero giro per un errore momentaneo crea buchi
    di 10-20 minuti nello storico. Si riprova due volte a distanza di 25
    secondi; se il server resta giù, l'eccezione emerge come prima (il
    giro salta, la tenuta copre il buco)."""
    request = urllib.request.Request(
        ENDPOINT,
        data=SOAP_BODY.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "SOAPAction": SOAP_ACTION,
            "Content-Type": "text/xml; charset=utf-8",
            # La documentazione di opentransportdata.swiss chiede uno
            # User-Agent esplicito e la dichiarazione della compressione.
            # Prima si mandava "Python-urllib/3.x": ipotesi (02.08.2026, NON
            # dimostrata) sul perche' certe risposte omettano messaggi che
            # esistono. La sonda TCS misura se cambia qualcosa.
            "User-Agent": "GottardoLive-collector/1.0 (+https://github.com/fbacchin/app)",
            "Accept-Encoding": "gzip, br, deflate",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == 2:
                raise
            print(f"feed {exc.code}, riprovo fra 25 s (tentativo {attempt + 1}/3)")
            time.sleep(25)
    # Il server comprime in gzip a prescindere dall'Accept-Encoding
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def sulla_autostrada(lower):
    """Vero se il messaggio riguarda l'A2 (autostrada e galleria), non l'H2.

    L'H2 e' la strada del PASSO: il percorso che si prende per EVITARE la
    galleria. I suoi messaggi citano Airolo e Goeschenen esattamente come
    quelli del tunnel, quindi superano il filtro dei portali, e quando non
    hanno una direzione riconoscibile finiscono su ENTRAMBE le schede.

    Osservato il 02.08.2026: "H2 Airolo -> Flüelen tra Passo del S. Gottardo E
    Svincolo Goeschenen ... ritardi No. [min] 60" ha portato a 60 minuti sia il
    sud (reale: 40) sia il nord (reale: 50), vincendo per la regola del massimo.

    Si ESCLUDE l'H2 invece di RICHIEDERE l'A2: se un domani un messaggio del
    tunnel non riportasse la sigla, richiederla lo farebbe sparire — e uno zero
    falso e' il difetto peggiore che questo progetto possa produrre.

    Vale solo per lo stato delle code e per le revoche. Negli AVVISI il
    messaggio resta: una coda al passo e' informazione utile a chi guida.
    """
    return not re.search(r"\bh2\b", lower)


def punti_di(record):
    """I punti AlertC toccati dal record, primari e secondari insieme."""
    return {
        (e.text or "").strip()
        for e in record.iter()
        if local(e.tag) == "specificLocation" and (e.text or "").strip().isdigit()
    }


def direzione_codificata(record):
    """Il senso di marcia come lo dichiara la fonte, o None.

    Un record puo' portarne piu' d'uno: se uno dice "both" e un altro un senso
    preciso vince il preciso. Se due si contraddicono si lascia in bianco.
    """
    valori = {
        (e.text or "").strip()
        for e in record.iter()
        if local(e.tag) == "alertCDirectionCoded" and (e.text or "").strip()
    }
    nette = valori - {"both"}
    if len(nette) == 1:
        return DIREZIONE_CODIFICATA.get(nette.pop())
    return None


def in_vigore(record, now):
    """Il messaggio vale ADESSO, o parla di qualcosa di programmato?

    Tre domande, tutte su dati dichiarati dalla fonte:
      - vale solo in certe ore che non conosciamo? allora no;
      - comincia dopo adesso? allora no;
      - ha dei periodi di validita'? allora adesso deve cadere dentro uno.

    Senza niente di tutto questo vale adesso: e' il caso normale di una coda.
    """
    for ext in (e for e in record.iter() if local(e.tag) == "validityExtension"):
        for enum in (x for x in ext.iter()
                     if local(x.tag) == "elementEnumerationExtension"):
            nome = next((c.text for c in enum if local(c.tag) == "element"), "")
            valore = next((c.text for c in enum if local(c.tag) == "value"), "")
            if ((nome or "").strip() == "validityStatus"
                    and (valore or "").strip() in QUALIFICATORI_A_ORARIO):
                return False

    inizi = [t for t in (parse_time((e.text or "").strip())
                         for e in record.iter()
                         if local(e.tag) == "overallStartTime") if t]
    if inizi and min(inizi) > now:
        return False

    periodi = [p for p in record.iter() if local(p.tag) == "validPeriod"]
    if not periodi:
        return True
    for p in periodi:
        da = next((parse_time((c.text or "").strip()) for c in p
                   if local(c.tag) == "startOfPeriod"), None)
        a = next((parse_time((c.text or "").strip()) for c in p
                  if local(c.tag) == "endOfPeriod"), None)
        if (da is None or da <= now) and (a is None or a >= now):
            return True
    return False


def chiusura_del_tunnel(texts, punti):
    """Il messaggio parla di una chiusura DELLA GALLERIA DEL GOTTARDO?

    Non basta trovare "tunnel chiuso": nel corridoio ci sono altre gallerie
    (la Naxberg, la Piumogna) e chiuderne una non e' chiudere il Gottardo.
    Serve una di queste tre prove, in ordine di solidita': il punto AlertC del
    tunnel, il nome nel testo, oppure il fatto che il messaggio tocchi un
    punto dal lato di Uri E uno dal lato del Ticino — in mezzo c'e' solo la
    galleria (e' il caso di situation.639408, "tra Göschenen E Airolo").
    """
    testi = " ".join(v for v in texts.values() if v).lower()
    if not any(f in testi for f in FRASI_CHIUSURA):
        return False
    if PUNTO_TUNNEL in punti:
        return True
    if any(n in testi for n in NOMI_TUNNEL):
        return True
    return bool(punti & PUNTI_LATO_URI) and bool(punti & PUNTI_LATO_TICINO)


def extract(xml_data):
    """Ritorna (stato code, eventi corridoio).

    - stato: {south: {km, wait}, north: {...}} dai messaggi di coda freschi (6h)
    - eventi: tutti i messaggi del corridoio delle ultime 12 ore, con i testi
      in tutte le lingue del feed, per il fallback dell'app quando l'API
      diretta non è disponibile (limite 5 chiamate/minuto sulla chiave).
    """
    root = ET.fromstring(xml_data)
    xsi_type = "{http://www.w3.org/2001/XMLSchema-instance}type"
    now = datetime.now(timezone.utc)
    state = {"south": {"km": None, "wait": None}, "north": {"km": None, "wait": None}}
    events = []
    revocations = set()
    revoked_ids = {}
    tunnel = {"chiuso": False, "revocato": False, "direzione": None, "testo": None}

    for record in (e for e in root.iter() if local(e.tag) == "situationRecord"):
        typename = localtype(record.get(xsi_type, ""))

        # commenti pubblici in tutte le lingue (esclude le note interne)
        texts = {}
        for gpc in (c for c in record.iter() if local(c.tag) == "generalPublicComment"):
            ctype = next(
                (ct.text for ct in gpc.iter() if local(ct.tag) == "commentType"), ""
            )
            if ctype == "internalNote":
                continue
            for value in (v for v in gpc.iter() if local(v.tag) == "value"):
                lang = (value.get("lang") or "")[:2].lower()
                chunk = (value.text or "").strip()
                if lang and chunk:
                    texts[lang] = (texts[lang] + " — " + chunk) if texts.get(lang) else chunk

        text = texts.get("it")
        if not text:
            continue

        lower = text.lower()
        revoked = lower.startswith(("revocato", "aufgehoben", "révoqué"))

        # Dentro il corridoio per CODICE, o in mancanza per nome.
        punti = punti_di(record)
        if not (punti & PUNTI_CORRIDOIO) and not any(k in lower for k in CORRIDOR):
            continue

        # La chiusura del tunnel: si registra qui, prima che la revoca faccia
        # uscire di scena il messaggio, perche' la revoca E' la riapertura.
        if chiusura_del_tunnel(texts, punti):
            if revoked:
                tunnel["revocato"] = True
            elif in_vigore(record, now):
                tunnel["chiuso"] = True
                tunnel["direzione"] = direzione_codificata(record)
                tunnel["testo"] = text

        version_time = parse_time(
            next(
                (e.text for e in record.iter()
                 if local(e.tag) == "situationRecordVersionTime"),
                "",
            )
        )
        if version_time is None:
            continue
        age = now - version_time

        km = queue_km(text)
        wait = wait_minutes(text)
        direction = direction_of(lower)

        # La revoca è l'unico modo in cui la fonte annuncia che una coda è
        # finita: la si annota per direzione, poi il messaggio esce di scena
        # (non va né fra gli avvisi mostrati né nello stato).
        if revoked:
            if typename == "AbnormalTraffic" and age <= FRESHNESS and sulla_autostrada(lower):
                for d in ([direction] if direction else ["south", "north"]):
                    portal = SOUTH_PORTAL if d == "south" else NORTH_PORTAL
                    if any(k in lower for k in portal):
                        revocations.add(d)
            record_id = record.get("id", "")
            if record_id:
                # Si conserva anche il TESTO della revoca: e' il documento che
                # prova la fine della coda. Il 02.08.2026 non e' stato
                # possibile verificarne una a un'ora di distanza, perche' del
                # messaggio restava solo l'orario in cui l'avevamo visto.
                revoked_ids[record_id] = {
                    "at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "testo": text,
                }
            continue

        # eventi: finestra 12 ore, come la lista avvisi dell'app
        if age <= timedelta(hours=12):
            events.append({
                "id": record.get("id", ""),
                "type": typename,
                "direction": direction,
                "versionTime": version_time.astimezone(timezone.utc)
                    .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "km": km,
                "wait": wait,
                "texts": texts,
            })

        # stato code: solo messaggi di coda freschi, riferiti ai portali
        if typename != "AbnormalTraffic" or (km is None and wait is None):
            continue
        if age > FRESHNESS:
            continue
        if not sulla_autostrada(lower):
            continue
        candidates = [direction] if direction else ["south", "north"]
        for d in candidates:
            portal = SOUTH_PORTAL if d == "south" else NORTH_PORTAL
            if not any(k in lower for k in portal):
                continue
            if km is not None and km > (state[d]["km"] or 0):
                state[d]["km"] = km
            if wait is not None and wait > (state[d]["wait"] or 0):
                state[d]["wait"] = wait

    events.sort(key=lambda e: (
        not (e["km"] is not None or e["wait"] is not None),
        e["versionTime"],
    ), reverse=False)
    events.sort(key=lambda e: e["versionTime"], reverse=True)
    events.sort(key=lambda e: not (e["km"] is not None or e["wait"] is not None))
    return state, events[:20], revocations, revoked_ids, tunnel


def delay_minutes(entry):
    if entry["wait"] is not None:
        return entry["wait"]
    if entry["km"] is not None:
        return round(entry["km"] * MINUTES_PER_KM)
    return 0


def send_push(alert):
    """Invia una notifica al canale global via Back4App (Master Key)."""
    if not PUSH_APP_ID or not PUSH_MASTER_KEY:
        return False
    request = urllib.request.Request(
        "https://parseapi.back4app.com/push",
        data=json.dumps({
            "where": {"channels": "global", "deviceType": "ios"},
            "data": {"alert": alert, "sound": "default", "badge": "Increment"},
        }).encode("utf-8"),
        headers={
            "X-Parse-Application-Id": PUSH_APP_ID,
            "X-Parse-Master-Key": PUSH_MASTER_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            ok = response.status < 300
            print(f"push inviato ({response.status}): {alert}")
            return ok
    except Exception as exc:  # la notifica non deve mai rompere il campionamento
        print(f"push fallito: {exc}")
        return False


def effective_wait(entry):
    if entry["wait"] is not None:
        return entry["wait"]
    if entry["km"] is not None:
        return round(entry["km"] * MINUTES_PER_KM)
    return 0


def update_notifications(state, now):
    """Confronta lo stato attuale con l'ultimo notificato e invia se serve."""
    state_file = HISTORY_FILE.parent / "push-state.json"
    try:
        push_state = json.loads(state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        push_state = {}

    labels = {"south": "Southbound", "north": "Northbound"}
    for direction in ("south", "north"):
        wait = effective_wait(state[direction])
        km = state[direction]["km"]
        entry = push_state.get(direction, {})
        phase = entry.get("phase", "clear")
        last_sent = parse_time(entry.get("lastSent") or "")
        clear_since = parse_time(entry.get("clearSince") or "")
        cooling = last_sent is not None and now - last_sent < PUSH_COOLDOWN

        # Tiene traccia da quando la coda è sotto soglia, a prescindere da
        # invii e cooldown: se torna sopra, la fine non era reale e il
        # conteggio riparte da zero (vedi CLEAR_CONFIRM).
        if phase in ("queued", "heavy"):
            clear_since = None if wait >= NOTIFY_CLEAR else (clear_since or now)
        else:
            clear_since = None

        km_part = f"{km:g} km queue · " if km else "queue · "
        message = None
        new_phase = phase
        if phase == "clear" and wait >= NOTIFY_START:
            message = f"🚦 {labels[direction]}: {km_part}~{wait} min wait"
            new_phase = "queued"
        elif phase == "queued" and wait >= NOTIFY_HEAVY:
            message = f"⚠️ {labels[direction]}: heavy queue — {km_part}~{wait} min wait"
            new_phase = "heavy"
        elif (phase in ("queued", "heavy") and clear_since is not None
              and now - clear_since >= CLEAR_CONFIRM):
            message = f"✅ {labels[direction]}: queue cleared"
            new_phase = "clear"

        if message and not cooling and send_push(message):
            phase = new_phase
            last_sent = now
            if new_phase == "clear":
                clear_since = None

        new_entry = {
            "phase": phase,
            "lastSent": last_sent.isoformat().replace("+00:00", "Z") if last_sent else None,
        }
        if clear_since is not None:
            new_entry["clearSince"] = clear_since.isoformat().replace("+00:00", "Z")
        push_state[direction] = new_entry

    state_file.write_text(json.dumps(push_state, indent=1))


# I testi delle due notifiche, nello stile delle altre (inglese, con emoji).
TUNNEL_CHIUSO = {
    None: "🚧 Gotthard tunnel closed",
    "south": "🚧 Gotthard tunnel closed southbound",
    "north": "🚧 Gotthard tunnel closed northbound",
}
TUNNEL_RIAPERTO = "✅ Gotthard tunnel reopened"


def update_tunnel_notifications(tunnel, now):
    """Una push quando il tunnel chiude, una quando riapre.

    Due inneschi per la riapertura, perche' uno solo non basta:

      - la REVOCA vista nel feed, che e' il modo in cui la fonte annuncia la
        riapertura (non esiste un messaggio "tunnel aperto": verificato, in
        dodici catture non compare mai). Ma la revoca resta disponibile 60
        minuti, e un giro saltato la fa perdere per sempre;
      - in mancanza, la chiusura che non risulta piu' in vigore e resta cosi'
        per CLEAR_CONFIRM. La conferma evita di annunciare una riapertura per
        un buco del feed, esattamente come per la fine di una coda.

    Niente cooldown: se il tunnel chiude mentre e' appena partita la notifica
    di una coda, quella notizia non puo' aspettare 45 minuti.
    """
    state_file = HISTORY_FILE.parent / "push-state.json"
    try:
        push_state = json.loads(state_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        push_state = {}

    entry = push_state.get("tunnel", {})
    phase = entry.get("phase", "open")
    open_since = parse_time(entry.get("openSince") or "")

    if tunnel["chiuso"]:
        open_since = None
        if phase != "closed":
            testo = TUNNEL_CHIUSO.get(tunnel["direzione"], TUNNEL_CHIUSO[None])
            if send_push(testo):
                phase = "closed"
    elif phase == "closed":
        if tunnel["revocato"]:
            if send_push(TUNNEL_RIAPERTO):
                phase = "open"
                open_since = None
        else:
            open_since = open_since or now
            if now - open_since >= CLEAR_CONFIRM and send_push(TUNNEL_RIAPERTO):
                phase = "open"
                open_since = None
    else:
        open_since = None

    nuovo = {"phase": phase}
    if open_since is not None:
        nuovo["openSince"] = open_since.isoformat().replace("+00:00", "Z")
    push_state["tunnel"] = nuovo
    state_file.write_text(json.dumps(push_state, indent=1))


def hold_through_gaps(state, revocations, history, now):
    """Un messaggio assente non significa «coda finita».

    La fonte annuncia la fine con una revoca esplicita (prefisso «Revocato:»).
    Se il messaggio sparisce senza revoca è quasi sempre un buco del feed
    (all'area di dosaggio di Airolo viene revocato e riemesso a impulsi), e
    scrivere 0 inventa uno sgonfiamento mai avvenuto: si tiene l'ultimo
    valore osservato, marcando il campione con southHeld/northHeld.

    Tre limiti, perché non resti appesa una coda davvero finita:
    - se la revoca c'è, si scrive 0 senza discutere;
    - non si tiene oltre HOLD_WINDOW dall'ultima osservazione diretta;
    - non si tiene a partire da una coda vista una volta sola (un eco
      riemesso a coda già chiusa diventerebbe un plateau di 20 minuti).

    IN PROVA dal 01.08.2026 (opzione A): unica correzione attiva, niente
    riscritture retroattive dello storico.
    """
    for side in ("south", "north"):
        if state[side]["km"] is not None or state[side]["wait"] is not None:
            continue
        if side in revocations:
            continue

        km_key, delay_key = f"{side}QueueKm", f"{side}Delay"
        recent = history[-2:]
        if len(recent) < 2 or not all(s.get(km_key) for s in recent):
            continue

        observed = None
        for past in reversed(history):
            if not past.get(km_key):
                break
            if not past.get(f"{side}Held"):
                observed = past
                break
        if observed is None:
            continue
        seen_at = parse_time(observed.get("time", ""))
        if seen_at is None or now - seen_at > HOLD_WINDOW:
            continue

        state[side]["km"] = observed[km_key]
        state[side]["wait"] = observed[delay_key]
        state[side]["held"] = True
    return state


def update_alerts(events, revoked_ids, now):
    """Accumula gli avvisi ufficiali in data/alerts.json.

    Il feed non è un archivio: ritira i messaggi quando vuole — a volte per
    un solo giro di campionamento, a volte definitivamente. Qui ogni avviso
    viene tenuto per id: si aggiorna il contenuto a ogni riapparizione e si
    annotano `firstSeen` (quando l'abbiamo visto la prima volta) e `lastSeen`
    (l'ultimo giro in cui era pubblicato). Un avviso che sparisce per un giro
    non viene perso, e l'app può distinguere «non più pubblicato» da «mai
    esistito».

    `revokedAt` registra la revoca esplicita, l'unico modo in cui la fonte
    dichiara che un messaggio è chiuso.

    Si conservano 48 ore dall'ultima volta che l'avviso è stato visto.
    """
    stamp = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    alerts = []
    if ALERTS_FILE.exists():
        try:
            alerts = json.loads(ALERTS_FILE.read_text())
        except json.JSONDecodeError:
            alerts = []
    by_id = {a.get("id"): a for a in alerts if a.get("id")}

    diario = []

    for event in events:
        entry = by_id.get(event["id"])
        if entry is None:
            entry = {"firstSeen": stamp}
            by_id[event["id"]] = entry
            diario.append(("comparso", event, None))
        else:
            # Si registra solo se cambia qualcosa di sostanziale: senza questo
            # filtro il registro avrebbe una riga ogni 5 minuti per ogni
            # messaggio fermo, e il segnale sparirebbe nel rumore.
            prima = (entry.get("km"), entry.get("wait"), entry.get("versionTime"))
            dopo = (event.get("km"), event.get("wait"), event.get("versionTime"))
            if prima != dopo:
                diario.append(("aggiornato", event, prima))
        entry.update(event)
        entry["lastSeen"] = stamp
        entry.pop("revokedAt", None)   # ripubblicato: la revoca non vale più

    for record_id, revoca in revoked_ids.items():
        entry = by_id.get(record_id)
        if entry is None or "revokedAt" in entry:
            continue
        entry["revokedAt"] = revoca["at"]
        # Nel registro va il testo della REVOCA, non quello della coda: e'
        # quello che permette di verificare a posteriori che sia arrivata.
        diario.append(("revocato",
                       dict(entry, id=record_id, texts={"it": revoca["testo"]}),
                       None))

    cutoff = now - ALERTS_WINDOW
    kept = [
        a for a in by_id.values()
        if (parse_time(a.get("lastSeen", "")) or cutoff) > cutoff
    ]
    kept.sort(key=lambda a: a.get("lastSeen", ""), reverse=True)

    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERTS_FILE.write_text(json.dumps(kept, indent=1, ensure_ascii=False))
    scrivi_registro(diario, now)
    return kept


def scrivi_registro(diario, now):
    """Aggiunge gli eventi al registro e pota le righe piu vecchie di 14 giorni."""
    # Il file si crea SEMPRE, anche vuoto. Il 02.08.2026 l'uscita anticipata
    # ha fatto fallire "git add gotthard/data/feed-log.jsonl" con codice 128 su
    # un percorso inesistente, e con le impostazioni di GitHub Actions quello
    # abbatte l'intero run da tre ore: il collector e' rimasto fermo un'ora.
    # Un file vuoto costa nulla; un file assente costa il servizio.
    FEED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not diario and FEED_LOG_FILE.exists():
        return
    stamp = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    righe = []
    if FEED_LOG_FILE.exists():
        cutoff = (now - FEED_LOG_WINDOW).isoformat().replace("+00:00", "Z")
        for riga in FEED_LOG_FILE.read_text().splitlines():
            if not riga.strip():
                continue
            try:
                if json.loads(riga).get("seenAt", "") > cutoff:
                    righe.append(riga)
            except json.JSONDecodeError:
                continue   # una riga corrotta non deve far perdere il resto

    for tipo, evento, prima in diario:
        voce = {
            "seenAt": stamp,
            "evento": tipo,
            "id": evento.get("id"),
            "direction": evento.get("direction"),
            "km": evento.get("km"),
            "wait": evento.get("wait"),
            "versionTime": evento.get("versionTime"),
            # Testo italiano alla lettera: e' la prova, non va riassunto.
            "testo": (evento.get("texts") or {}).get("it"),
        }
        if prima is not None:
            voce["prima"] = {"km": prima[0], "wait": prima[1], "versionTime": prima[2]}
        righe.append(json.dumps(voce, ensure_ascii=False))

    FEED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEED_LOG_FILE.write_text("\n".join(righe) + "\n")


def hold_events(fresh, alerts, now):
    """Eventi da pubblicare in latest.json, tenuti attraverso i buchi.

    Il collector teneva gia lo STATO delle code (hold_through_gaps) ma
    scriveva gli eventi cosi come arrivavano: quando il feed ritirava i
    messaggi, latest.json usciva con le code valorizzate e `events` vuoto.
    Le app che ripiegano su questo file mostravano quindi schede piene e
    lista avvisi vuota — la stessa contraddizione corretta lato app in
    ADEV-565, mai applicata qui. Osservato il 02.08.2026 sulla 1.1.1.

    Si FONDE invece di sostituire: il feed a volte consegna una parte dei
    messaggi del corridoio e non le code, quindi "tieni solo se la lista e
    vuota" non basterebbe. Dall'archivio si riprendono gli avvisi non
    revocati e visti da meno di HOLD_WINDOW, saltando quelli gia presenti.
    """
    out = list(fresh)
    visti = {e.get("id") for e in out}
    cutoff = now - HOLD_WINDOW
    campi = ("id", "type", "direction", "versionTime", "km", "wait", "texts")

    for a in alerts:
        if a.get("id") in visti or a.get("revokedAt"):
            continue
        ultimo = parse_time(a.get("lastSeen", ""))
        if ultimo is None or ultimo <= cutoff:
            continue
        out.append({k: a[k] for k in campi if k in a})

    # stesso ordinamento di extract(): prima i messaggi con numeri
    out.sort(key=lambda e: e.get("versionTime") or "", reverse=True)
    out.sort(key=lambda e: not (e.get("km") is not None or e.get("wait") is not None))
    return out[:20]


def main():
    api_key = os.environ.get("OTD_API_KEY", "").strip()
    if not api_key:
        sys.exit("OTD_API_KEY mancante")

    state, events, revocations, revoked_ids, tunnel = extract(fetch_feed(api_key))
    now = datetime.now(timezone.utc).replace(microsecond=0)

    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            history = []

    cutoff = now - WINDOW
    history = [
        s for s in history
        if (parse_time(s.get("time", "")) or cutoff) > cutoff
    ]

    # Se il messaggio manca ma nessuno ne ha annunciato la revoca, la coda
    # c'è ancora: vale anche per notifiche e schede, che leggono lo stesso stato.
    hold_through_gaps(state, revocations, history, now)

    update_notifications(state, now)
    # Dopo le code, e da una rilettura fresca del file: la chiusura del tunnel
    # ha uno stato suo e non deve calpestare quello delle due direzioni.
    update_tunnel_notifications(tunnel, now)

    sample = {
        "time": now.isoformat().replace("+00:00", "Z"),
        "southDelay": delay_minutes(state["south"]),
        "northDelay": delay_minutes(state["north"]),
        "southQueueKm": state["south"]["km"],
        "northQueueKm": state["north"]["km"],
    }
    for side in ("south", "north"):
        if state[side].get("held"):
            sample[f"{side}Held"] = True

    history.append(sample)

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=1))

    # Ultimo stato completo per il fallback dell'app (schede + avvisi)
    # L'archivio si aggiorna PRIMA: serve a ricostruire gli avvisi tenuti.
    alerts = update_alerts(events, revoked_ids, now)
    latest_events = hold_events(events, alerts, now)

    latest = {
        "time": sample["time"],
        "south": state["south"],
        "north": state["north"],
        "events": latest_events,
    }

    (HISTORY_FILE.parent / "latest.json").write_text(
        json.dumps(latest, indent=1, ensure_ascii=False)
    )
    stato_tunnel = ("CHIUSO" + (f" verso {tunnel['direzione']}" if tunnel["direzione"] else "")
                    if tunnel["chiuso"] else ("revocato" if tunnel["revocato"] else "aperto"))
    print(f"campione salvato: {sample} (totale {len(history)}, eventi {len(events)}->{len(latest_events)}, archivio avvisi {len(alerts)}, revoche {sorted(revocations) or '-'}, tunnel {stato_tunnel})")


if __name__ == "__main__":
    main()
