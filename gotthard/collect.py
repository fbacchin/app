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
CORRIDOR = [
    "galleria del s. gottardo", "galleria del san gottardo",
    "gotthardtunnel", "gotthard tunnel",
    "göschenen", "goeschenen", "airolo", "wassen", "amsteg", "erstfeld",
    "quinto", "faido", "area di dosaggio",
]
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

HISTORY_FILE = Path(__file__).parent / "data" / "history.json"
WINDOW = timedelta(hours=48)


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
    request = urllib.request.Request(
        ENDPOINT,
        data=SOAP_BODY.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "SOAPAction": SOAP_ACTION,
            "Content-Type": "text/xml; charset=utf-8",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    # Il server comprime in gzip a prescindere dall'Accept-Encoding
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


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
        if not any(k in lower for k in CORRIDOR):
            continue

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
            if typename == "AbnormalTraffic" and age <= FRESHNESS:
                for d in ([direction] if direction else ["south", "north"]):
                    portal = SOUTH_PORTAL if d == "south" else NORTH_PORTAL
                    if any(k in lower for k in portal):
                        revocations.add(d)
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
    return state, events[:20], revocations


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


def hold_through_gaps(state, revocations, history, now):
    """Un messaggio assente non significa «coda finita».

    La fonte annuncia la fine con una **revoca esplicita** (prefisso
    «Revocato:»). Se il messaggio sparisce senza revoca è quasi sempre un buco
    del feed, e scrivere 0 inventa uno sgonfiamento che non è avvenuto: in quel
    caso si tiene l'ultimo valore osservato.

    Tre limiti, perché non resti appesa una coda che è davvero finita:

    - se la revoca c'è, si scrive 0 senza discutere;
    - non si tiene oltre CLEAR_CONFIRM dall'ultima osservazione diretta, così
      una revoca sfuggita costa venti minuti, non l'eternità;
    - non si tiene a partire da una coda vista **una volta sola**: il feed
      riemette a volte un ultimo messaggio di una coda già chiusa, e senza
      questo controllo quell'eco diventerebbe un plateau di venti minuti
      (stessa logica di drop_feed_echoes).
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
        if seen_at is None or now - seen_at > CLEAR_CONFIRM:
            continue

        state[side]["km"] = observed[km_key]
        state[side]["wait"] = observed[delay_key]
        state[side]["held"] = True
    return state


def drop_feed_echoes(history):
    """Toglie le code isolate, l'altra faccia del lampeggio del feed.

    Quando una coda finisce davvero, il messaggio ufficiale viene talvolta
    riemesso un'ultima volta a distanza di minuti: nello storico compare un
    picco largo **un solo campione**, con lo stesso identico chilometraggio
    dell'episodio appena concluso. Otto chilometri di auto non si formano e
    si dissolvono in cinque minuti.

    La soglia non è arbitraria: su 48h reali gli episodi veri vanno da 4 a
    215 campioni (10-1082 minuti), gli echi da 1 campione (0 minuti). Si
    scarta quindi solo l'episodio lungo un campione, isolato fra due assenze.

    L'**ultimo** campione dello storico è esente: una coda appena nata è
    indistinguibile da un eco finché non arriva il campione successivo, e
    fra i due è meno grave mostrare una coda in più per cinque minuti che
    nasconderne una vera a chi sta per partire.

    Va eseguita PRIMA di fill_feed_gaps: un eco lasciato al suo posto
    farebbe da àncora e la ricucitura estenderebbe all'indietro una coda
    che era già finita.
    """
    for side in ("south", "north"):
        delay_key, km_key = f"{side}Delay", f"{side}QueueKm"
        for i in range(1, len(history) - 1):
            if (history[i][km_key]
                    and not history[i - 1][km_key]
                    and not history[i + 1][km_key]):
                history[i][delay_key], history[i][km_key] = 0, None
    return history


def fill_feed_gaps(history):
    """Ricuce i buchi del feed nello storico.

    All'area di dosaggio di Airolo il messaggio ufficiale non resta pubblicato
    per tutta la durata della coda: viene revocato e riemesso a impulsi. Il
    campione grezzo registra allora 8 km, poi 0, poi di nuovo 8 km, e il
    grafico dell'app diventa un'onda quadra impossibile.

    Si riempiono SOLO i buchi **racchiusi fra due campioni con coda** distanti
    non più di CLEAR_CONFIRM: la ricomparsa della coda è la prova che non era
    mai finita. Una fine vera non ha nulla dopo di sé, quindi resta 0 — stessa
    soglia e stessa logica delle notifiche (vedi update_notifications).
    Si usa il minore dei due estremi: mai inventare una coda più lunga di
    quanto le autorità abbiano effettivamente pubblicato.

    L'operazione è idempotente: rigirarla sullo storico già ricucito non trova
    altri buchi, quindi ogni run ripara anche i campioni vecchi ancora in
    finestra senza accumulare effetti.
    """
    for side in ("south", "north"):
        delay_key, km_key = f"{side}Delay", f"{side}QueueKm"
        queued = [i for i, s in enumerate(history) if s.get(km_key)]
        for start, end in zip(queued, queued[1:]):
            if end - start < 2:
                continue
            t_start, t_end = parse_time(history[start]["time"]), parse_time(history[end]["time"])
            if not t_start or not t_end or t_end - t_start > CLEAR_CONFIRM:
                continue
            delay = min(history[start][delay_key] or 0, history[end][delay_key] or 0)
            km = min(history[start][km_key], history[end][km_key])
            for gap in history[start + 1:end]:
                gap[delay_key], gap[km_key] = delay, km
    return history


def main():
    api_key = os.environ.get("OTD_API_KEY", "").strip()
    if not api_key:
        sys.exit("OTD_API_KEY mancante")

    state, events, revocations = extract(fetch_feed(api_key))
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

    # Prima di ogni altra cosa: se il messaggio manca ma nessuno ne ha
    # annunciato la revoca, la coda c'è ancora. Vale anche per le notifiche e
    # per le schede dell'app, che leggono lo stesso stato.
    hold_through_gaps(state, revocations, history, now)

    update_notifications(state, now)

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
    drop_feed_echoes(history)
    fill_feed_gaps(history)

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=1))

    # Ultimo stato completo per il fallback dell'app (schede + avvisi)
    latest = {
        "time": sample["time"],
        "south": state["south"],
        "north": state["north"],
        "events": events,
    }
    (HISTORY_FILE.parent / "latest.json").write_text(
        json.dumps(latest, indent=1, ensure_ascii=False)
    )
    print(f"campione salvato: {sample} (totale {len(history)}, eventi {len(events)})")


if __name__ == "__main__":
    main()
