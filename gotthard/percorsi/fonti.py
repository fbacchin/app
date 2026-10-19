# Chiamate alle fonti. Mai un URL o una risposta grezza nei messaggi: contengono chiavi.
import base64, json, time, urllib.error, urllib.request
from config import (CORSIE_ASTRA, CUPRA, PUNTI, RIFERIMENTI_M, SENSO_ASTRA, STAZIONI_ASTRA, TRATTO_CUPRA, VALICO,
                    chiamate, misure)
from archivio import risultato

def http(metodo, url, intestazioni=None, corpo=None):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dati, method=metodo, headers=dict(intestazioni or {}))
    if dati:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            testo = r.read()
            return r.status, (json.loads(testo) if testo else None)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except Exception:
        return 0, None

def pem(testo):
    """La casella dei segreti può perdere gli a capo del .p8: si ricostruisce il PEM dal corpo."""
    corpo = "".join(testo.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").split())
    righe = [corpo[i:i + 64] for i in range(0, len(corpo), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(righe) + "\n-----END PRIVATE KEY-----\n"

def token_apple(key_id, team_id, chiave, chiama=http):
    """JWT ES256 firmato con la chiave Maps, scambiato con un token d'accesso (30 min)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    adesso = int(time.time())
    testa = b64(json.dumps({"alg": "ES256", "kid": key_id, "typ": "JWT"}).encode())
    carico = b64(json.dumps({"iss": team_id, "iat": adesso, "exp": adesso + 1800}).encode())
    privata = serialization.load_pem_private_key(pem(chiave).encode(), password=None)
    r, s = utils.decode_dss_signature(privata.sign(f"{testa}.{carico}".encode(), ec.ECDSA(hashes.SHA256())))
    jwt = f"{testa}.{carico}.{b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
    codice, d = chiama("GET", "https://maps-api.apple.com/v1/token", {"Authorization": "Bearer " + jwt})
    return d.get("accessToken") if codice == 200 and isinstance(d, dict) else None

def unisci(nome, a, b):
    """Passo = salita al valico + discesa. Se una tratta manca, manca la misura: mai un tempo a metà."""
    for tratta in (a, b):
        if tratta["esito"] != "ok":
            return {**tratta, "misura": nome}
    return risultato(nome, a["con_traffico_s"] + b["con_traffico_s"], a["senza_traffico_s"] + b["senza_traffico_s"],
                     a["distanza_m"] + b["distanza_m"])

def componi(nome, origine, destinazione, percorso, tratte):
    if percorso != "passo":
        return {**tratte[(origine, destinazione)], "misura": nome}
    return unisci(nome, tratte[(origine, VALICO)], tratte[(VALICO, destinazione)])

def richieste_apple():
    """(origine, destinazioni) per le misure di Apple. Le tratte che toccano il valico vanno in richieste a sé:
    col passo chiuso Apple potrebbe rifiutare l'intera richiesta, e si perderebbero anche le misure della galleria."""
    tunnel, salite, discese = {}, set(), []
    for _, o, d, percorso in chiamate("apple"):
        if percorso != "passo":
            tunnel.setdefault(o, []).append(d)
        else:
            salite.add(o)
            discese.append(d)
    return ([(o, sorted(set(ds))) for o, ds in sorted(tunnel.items())] + [(o, [VALICO]) for o in sorted(salite)]
            + [(VALICO, sorted(set(discese)))])

def _vicino(a, b):
    return abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01

def apple(token, chiama=http):
    tratte = {}
    for o, destinazioni in richieste_apple():
        q = "origin=%s,%s&destinations=%s&transportType=Automobile" % (*PUNTI[o], "|".join("%s,%s" % PUNTI[d] for d in destinazioni))
        codice, r = chiama("GET", "https://maps-api.apple.com/v1/etas?" + q, {"Authorization": "Bearer " + token})
        for d in destinazioni:
            if codice != 200 or not isinstance(r, dict):
                tratte[(o, d)] = risultato("", esito=f"errore {codice}")
                continue
            # Abbinamento per coordinate, non per posizione: una destinazione irraggiungibile può mancare.
            e = next((e for e in r.get("etas", []) if _vicino((e["destination"]["latitude"], e["destination"]["longitude"]), PUNTI[d])), None)
            tratte[(o, d)] = (risultato("", e["expectedTravelTimeSeconds"], e["staticTravelTimeSeconds"], e["distanceMeters"])
                              if e else risultato("", esito="percorso non trovato"))
    return [componi(nome, o, d, p, tratte) for nome, o, d, p in chiamate("apple")]

def _luogo(tappe):
    return ":".join("%s,%s" % PUNTI[t] for t in tappe)

def da_tomtom(nome, codice, r):
    if codice == 200 and isinstance(r, dict) and r.get("routes"):
        s = r["routes"][0]["summary"]
        return risultato(nome, s["travelTimeInSeconds"], s["noTrafficTravelTimeInSeconds"], s["lengthInMeters"])
    if codice == 400 and "NO_ROUTE_FOUND" in json.dumps(r or {}):
        return risultato(nome, esito="percorso non trovato")
    return risultato(nome, esito=f"errore {codice}")

def tomtom(chiave, chiama=http, attesa=time.sleep):
    """Una richiesta per misura; il passo con il punto del valico come tappa.
    Il piano gratuito rifiuta con 429 le richieste troppo ravvicinate (15.10.2026: le ultime 3 di 8):
    si lascia una pausa tra le richieste e dopo un 429 si riprova, al massimo due volte."""
    out = []
    for nome, o, d, percorso in chiamate("tomtom"):
        tappe = [o, VALICO, d] if percorso == "passo" else [o, d]
        for tentativo in range(3):
            attesa(0.3 if tentativo == 0 else 1.5)
            codice, r = chiama("GET", f"https://api.tomtom.com/routing/1/calculateRoute/{_luogo(tappe)}/json"
                                      f"?traffic=true&computeTravelTimeFor=all&travelMode=car&key={chiave}")
            if codice != 429:
                break
        out.append(da_tomtom(nome, codice, r))
    return out

def _punto(n):
    return {"location": {"latLng": {"latitude": PUNTI[n][0], "longitude": PUNTI[n][1]}}}

def _secondi(x):
    return int(x.rstrip("s"))

def da_google(nome, codice, r, tratto=None):
    """Con `tratto` (nome) si aggiunge il risultato del primo tratto, fino alla tappa: [passo, tratto]."""
    if codice != 200:
        rs = [risultato(nome, esito=f"errore {codice}")]
    elif not isinstance(r, dict) or not r.get("routes"):
        rs = [risultato(nome, esito="percorso non trovato")]
    else:
        x = r["routes"][0]
        rs = [risultato(nome, _secondi(x["duration"]), _secondi(x["staticDuration"]), x["distanceMeters"])]
        if tratto:
            g = (x.get("legs") or [{}])[0]
            return rs + [risultato(tratto, _secondi(g["duration"]), _secondi(g["staticDuration"]), g["distanceMeters"])
                         if {"duration", "staticDuration", "distanceMeters"} <= g.keys() else risultato(tratto, esito="manca il tratto")]
    return rs + ([{**rs[0], "misura": tratto}] if tratto else [])

CAMPI_GOOGLE = "routes.duration,routes.staticDuration,routes.distanceMeters,routes.legs.duration,routes.legs.staticDuration,routes.legs.distanceMeters"

def google(chiave, chiama=http):
    """Chiave nell'intestazione, mai nell'URL. Il passo con il punto del valico come tappa obbligata (via).
    Il passo verso nord che ha la CUPRA si chiede con una sosta ad Airolo: il primo tratto (legs[0]) è Faido→Airolo,
    con i suoi tempi, e serve al calcolo con la CUPRA. La sosta divide il percorso in tratti, il valico «via» no."""
    out = []
    for nome, o, d, percorso in chiamate("google"):
        corpo = {"origin": _punto(o), "destination": _punto(d), "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE"}
        tratto = TRATTO_CUPRA if nome in CUPRA.values() and o == "Faido" else None   # da Biasca il primo tratto non sarebbe Faido→Airolo
        if percorso == "passo":
            corpo["intermediates"] = ([_punto("Airolo")] if tratto else []) + [{**_punto(VALICO), "via": True}]
        codice, r = chiama("POST", "https://routes.googleapis.com/directions/v2:computeRoutes",
                           {"X-Goog-Api-Key": chiave, "X-Goog-FieldMask": CAMPI_GOOGLE}, corpo)
        out += da_google(nome, codice, r, tratto)
    return out

# --- Contatori ASTRA (opentransportdata, «Road traffic – traffic counters»), 19.10 ---------------------------------
# SOAP pullMeasuredData con il filtro per stazione, come nell'esempio del cookbook (rt-road-traffic-counters).
# Risposta DATEX II (gzip): per ogni corsia, ultimo minuto, indice 11/12 = flusso/velocità delle auto, 21/22 = pesanti.

def _richiesta_astra(stazioni):
    filtro = "".join(f'<siteRequestReference targetClass="MeasurementSiteRecord" id="{s}\\.[0-9]*" version="0"/>' for s in stazioni)
    return ('<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:tdpplv1="http://datex2.eu/wsdl/TDP/Soap_Datex2/Pull/v1" xmlns:dx223="http://datex2.eu/schema/2/2_0"><SOAP-ENV:Body>'
            '<d2LogicalModel modelBaseVersion="2" xmlns:D2LogicalModel="http://datex2.eu/schema/2/2_0" xmlns="http://datex2.eu/schema/2/2_0">'
            '<exchange><supplierIdentification><country>ch</country><nationalIdentifier>gottardo-percorsi</nationalIdentifier></supplierIdentification></exchange>'
            '<payloadPublication xsi:type="GenericPublication" lang="en"><publicationTime>2026-10-19T00:00:00</publicationTime>'
            '<publicationCreator><country>ch</country><nationalIdentifier>gottardo-percorsi</nationalIdentifier></publicationCreator>'
            '<genericPublicationName>MeasuredDataFilter</genericPublicationName><genericPublicationExtension><measuredDataFilter>'
            '<measurementSiteTableReference targetClass="MeasurementSiteTable" id="OTD:TrafficData" version="0"></measurementSiteTableReference>'
            f'{filtro}</measuredDataFilter></genericPublicationExtension></payloadPublication></d2LogicalModel></SOAP-ENV:Body></SOAP-ENV:Envelope>')

def http_soap(corpo, chiave):
    """(codice, byte della risposta, già decompressi). Mai la chiave nei messaggi."""
    import gzip
    req = urllib.request.Request("https://api.opentransportdata.swiss/TDP/Soap_Datex2/Pull", data=corpo.encode(), method="POST", headers={
        "Authorization": "Bearer " + chiave, "Content-Type": "text/xml", "User-Agent": "gottardo-percorsi",
        "SOAPAction": "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullMeasuredData"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            codice, dati = r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""
    return codice, gzip.decompress(dati) if dati[:2] == b"\x1f\x8b" else dati

def letture_astra(xml):
    """{record: (ora UTC, auto/h, km/h auto, pesanti/h, km/h pesanti)}; un valore che manca è None."""
    import xml.etree.ElementTree as ET
    nome = lambda e: e.tag.split("}")[-1]
    out = {}
    for sm in ET.fromstring(xml).iter():
        if nome(sm) != "siteMeasurements":
            continue
        rid = next((e.get("id") for e in sm if nome(e) == "measurementSiteReference"), None)
        ora = next((e.text for e in sm if nome(e) == "measurementTimeDefault"), None)
        v = {}
        for mv in sm:
            if nome(mv) == "measuredValue":
                for e in mv.iter():
                    if nome(e) in ("vehicleFlowRate", "speed") and e.text:
                        v[mv.get("index")] = float(e.text)
        if rid:
            out[rid] = (ora, v.get("11"), v.get("12"), v.get("21"), v.get("22"))
    return out

def velocita_astra(letture, stazione, senso_astra):
    """Velocità media delle auto di una stazione in un senso, pesata sul flusso di ogni corsia; None senza auto in quel minuto."""
    somma = peso = 0.0
    for c in CORSIE_ASTRA[stazione][senso_astra]:
        _, flusso, kmh, _, _ = letture.get(f"{stazione}.{c}", (None,) * 5)
        if flusso and kmh:
            somma += flusso * kmh
            peso += flusso
    return somma / peso if peso else None

def astra(chiave, chiama=http_soap, letture_out=None):
    """Una richiesta per tutte le stazioni. letture_out (lista) riceve le letture grezze per corsia, da archiviare."""
    stazioni = sorted({s for ss in STAZIONI_ASTRA.values() for s in ss})
    codice, xml = chiama(_richiesta_astra(stazioni), chiave)
    nomi = misure("astra")
    if codice != 200 or not xml:
        return [risultato(n, esito=f"errore {codice}") for n, *_ in nomi]
    letture = letture_astra(xml)
    if letture_out is not None:
        letture_out += [[rid, *("" if x is None else x for x in v)] for rid, v in sorted(letture.items())]
    senso_di = {s: a for a, s in SENSO_ASTRA.items()}            # "SN" → "positive"
    out = []
    for nome, o, d, _ in nomi:
        senso = nome.split()[0]
        tratta = f"{o}-{d}" if senso == "NS" else f"{d}-{o}"
        lunghezza = RIFERIMENTI_M[nome]
        velocita = [velocita_astra(letture, s, senso_di[senso]) for s in STAZIONI_ASTRA[tratta]]
        if any(v is None for v in velocita):
            out.append(risultato(nome, esito="nessun veicolo misurato"))
            continue
        secondi = sum(lunghezza / len(velocita) / (v / 3.6) for v in velocita)
        out.append(risultato(nome, round(secondi), None, lunghezza))
    return out
