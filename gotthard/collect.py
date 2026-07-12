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
        if lower.startswith(("revocato", "aufgehoben", "révoqué")):
            continue
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
    return state, events[:20]


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
        entry = push_state.get(direction, {"phase": "clear", "lastSent": None})
        phase = entry.get("phase", "clear")
        last_sent = parse_time(entry.get("lastSent") or "")
        cooling = last_sent is not None and now - last_sent < PUSH_COOLDOWN

        km_part = f"{km:g} km queue · " if km else "queue · "
        message = None
        new_phase = phase
        if phase == "clear" and wait >= NOTIFY_START:
            message = f"🚦 {labels[direction]}: {km_part}~{wait} min wait"
            new_phase = "queued"
        elif phase == "queued" and wait >= NOTIFY_HEAVY:
            message = f"⚠️ {labels[direction]}: heavy queue — {km_part}~{wait} min wait"
            new_phase = "heavy"
        elif phase in ("queued", "heavy") and wait < NOTIFY_CLEAR:
            message = f"✅ {labels[direction]}: queue cleared"
            new_phase = "clear"

        if message and not cooling and send_push(message):
            entry = {"phase": new_phase,
                     "lastSent": now.isoformat().replace("+00:00", "Z")}
        push_state[direction] = entry

    state_file.write_text(json.dumps(push_state, indent=1))


def main():
    api_key = os.environ.get("OTD_API_KEY", "").strip()
    if not api_key:
        sys.exit("OTD_API_KEY mancante")

    state, events = extract(fetch_feed(api_key))
    now = datetime.now(timezone.utc).replace(microsecond=0)

    update_notifications(state, now)

    sample = {
        "time": now.isoformat().replace("+00:00", "Z"),
        "southDelay": delay_minutes(state["south"]),
        "northDelay": delay_minutes(state["north"]),
        "southQueueKm": state["south"]["km"],
        "northQueueKm": state["north"]["km"],
    }

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
    history.append(sample)

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
