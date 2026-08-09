#!/usr/bin/env python3
"""Raccoglitore per Valichi Live (nome di lavoro).

Campiona i tempi d'attesa ai valichi di frontiera europei elencati in
catalog.json, li normalizza in uno schema comune e mantiene:

  data/latest.json       — ultimo stato per valico e direzione
  data/history.json      — finestra mobile di 48 ore per i grafici
  data/push-state.json   — fase notifiche per valico/direzione
  data/sources-log.jsonl — registro di salute fonti + finestre di testo
                           estratte (il materiale per tarare i parser)

Fonti della prima versione (nessuna chiave necessaria):
  hak         — HAK, frontiere esterne della Croazia (ME/BA/RS)
  police_hu   — polizia ungherese, frontiere HU–RS e HU–UA
  granica_pl  — granica.gov.pl, frontiere PL–UA
  gotthard    — riuso di ../gotthard/data/latest.json (zero rete, zero quota)

Le pagine di HAK/police.hu/granica sono HTML senza contratto: qui non si
fa parsing della STRUTTURA ma del TESTO — si spiana la pagina, si cerca il
nome del valico (da catalog.json, senza accenti) e si leggono le durate
nella finestra di testo che segue. Regge ai restyling finché la pagina
resta "nome + attesa", che è la sua ragione d'essere. Ogni run scrive le
finestre estratte in sources-log.jsonl: se un parser sbaglia, lì c'è il
testo vero su cui correggerlo.

Una fonte che fallisce NON ferma le altre: lo stato di salute finisce in
latest.json e l'ultimo valore noto viene tenuto (marcato "held") fino a
HOLD_WINDOW — per una pagina di stato un fetch fallito è un buco, non
un'attesa finita. Oltre la finestra il valore torna null (ignoto), MAI 0:
ai confini "nessuna coda" è un'informazione, non un default.

Notifiche push (opzionali): con B4A_VALICHI_APP_ID e B4A_VALICHI_MASTER_KEY
nell'ambiente, invia su canali per valico (valico-<id con - al posto di .>)
con la stessa logica a fasi collaudata dal collector del Gottardo.

Test locale senza rete:  python3 collect.py --prova   (fixture in prove/)
"""

import gzip
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).parent
CATALOG_FILE = BASE / "catalog.json"
DATA_DIR = BASE / "data"
LATEST_FILE = DATA_DIR / "latest.json"
HISTORY_FILE = DATA_DIR / "history.json"
PUSH_STATE_FILE = DATA_DIR / "push-state.json"
SOURCES_LOG_FILE = DATA_DIR / "sources-log.jsonl"
PROVE_DIR = BASE / "prove"

WINDOW = timedelta(hours=48)          # storico per i grafici, come Gottardo
SOURCES_LOG_WINDOW = timedelta(days=14)

# Un fetch fallito o un valico assente dalla pagina non azzerano niente:
# si tiene l'ultimo valore osservato, marcato held, fino a questo tetto.
# 90 minuti e non 60 come al Gottardo: qui le fonti si aggiornano più
# lentamente (granica dichiara 8 aggiornamenti al giorno) e un'attesa di
# frontiera non si dissolve in un quarto d'ora.
HOLD_WINDOW = timedelta(minutes=90)

# Quanto testo leggere dopo il nome del valico. Deve contenere le voci di
# entrambe le direzioni e di più categorie di veicoli, non il valico dopo:
# sulle pagine reali le schede sono compatte, 320 caratteri spianati bastano
# e raddoppiarli farebbe rubare i numeri al valico successivo in lista.
WINDOW_CHARS = 320

# --- soglie notifiche ---
# Più alte del Gottardo: mezz'ora a una frontiera esterna è ordinaria
# amministrazione, due ore è la notizia. CLEAR_CONFIRM regge su due
# campioni consecutivi (cadenza 10 minuti).
NOTIFY_START = 30
NOTIFY_HEAVY = 120
NOTIFY_CLEAR = 15
CLEAR_CONFIRM = timedelta(minutes=20)
PUSH_COOLDOWN = timedelta(minutes=60)
PUSH_APP_ID = os.environ.get("B4A_VALICHI_APP_ID", "")
PUSH_MASTER_KEY = os.environ.get("B4A_VALICHI_MASTER_KEY", "")

# Un User-Agent da browser, non "Python-urllib": i portali governativi
# spesso filtrano i client non dichiarati, e a noi serve la stessa pagina
# che vede un utente.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 "
              "ValichiLive-collector/0.1 (+https://github.com/fbacchin/app)")

# Gli URL per fonte. Si provano TUTTI e vince quello da cui si estraggono
# più attese (collaudo del 09.08.2026: m.hak.hr/stanje.asp rispondeva per
# primo con una pagina sostanziosa — ma era la pagina AVVISI, prosa su
# lavori e telecamere senza un solo tempo d'attesa, e "il primo URL che
# risponde" l'aveva fatta vincere).
SOURCE_URLS = {
    "hak": [
        "https://www.hak.hr/info/granicni-prijelazi/",
        "https://m.hak.hr/stanje.asp?id=2",
    ],
    "police_hu": [
        "https://www.police.hu/hu/hirek-es-informaciok/hatarinfo",
    ],
    "granica_pl": [
        "https://granica.gov.pl/index_wait.php?p=u&v=pl&k=w",
        "https://granica.gov.pl/wczasy.php?v=pl",
    ],
}
SOURCE_LANG = {"hak": "hr", "police_hu": "hu", "granica_pl": "pl"}

# --- vocabolario multilingue, tutto in forma GIÀ SPIANATA (minuscole,
# senza accenti: "óra"→"ora", "zadržavanja"→"zadrzavanja") ---

# Le frasi con cui le fonti dicono "nessuna attesa". Vanno cercate PRIMA
# dei numeri: "brak kolejki" non contiene cifre e senza questa lista il
# valico risulterebbe ignoto invece che libero.
ZERO_PHRASES = [
    "nema zadrzavanja", "nema cekanja", "bez zadrzavanja", "nema guzve",   # hr
    "nincs varakozas", "nincs torlodas", "nincs varakozasi ido",           # hu
    "brak kolejki", "brak oczekiwania", "bez oczekiwania", "brak kolejek", # pl
    "no waiting", "no delay", "no queue",                                  # en
    "nessuna attesa", "nessuna coda",                                      # it
]

# Direzioni come le chiama ciascuna fonte (prefissi, dopo spiana()):
# "kilep" prende kilépő/kilépés, "belep" belépő/belépés.
EXIT_WORDS = ["izlaz", "kilep", "wyjazd", "exit", "uscita"]
ENTRY_WORDS = ["ulaz", "belep", "wjazd", "entry", "ingresso"]

# Categorie di veicoli: si isola il segmento delle auto quando il testo
# distingue auto/camion/bus, perché l'app parla ai viaggiatori, non agli
# spedizionieri. I prefissi coprono le declinazioni.
CAR_WORDS = ["osobna", "osobni", "szemely", "osobowe", "osobowy",
             "samochody osobowe", "cars", "autovetture"]
OTHER_VEHICLE_WORDS = ["teretna", "teretni", "kamion", "autobus",
                       "teherg", "tehergepkocsi", "busz",
                       "ciezarowe", "ciezarowy", "autokar",
                       "trucks", "buses", "lorries"]

# Durate: ore e minuti in hr/hu/pl/en/it. Dopo spiana() l'ungherese "óra"
# coincide con l'italiano "ora" e va benissimo così. Il croato usa
# sat/sata/sati, il polacco godz(iny).
HOURS_RE = r"(\d+(?:[.,]\d+)?)\s*(?:h\b|hr\b|sat[ai]?\b|ora\b|ore\b|godz\w*|hour\w*)"
MINUTES_RE = r"(\d+)\s*(?:min\w*|perc\b|')"


def spiana(text):
    """Minuscole, senza accenti, spazi compressi: la forma unica su cui
    lavorano ricerca dei nomi e vocabolario, così "Karasovići", "KARASOVIĆI"
    e "karasovici" sono la stessa stringa."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


class _Spogliatore(HTMLParser):
    """Butta i tag e tiene il testo. script/style vanno saltati per intero:
    il loro contenuto non è prosa e inquina le finestre."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pezzi = []
        self._salta = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._salta += 1
        elif tag in ("br", "p", "div", "tr", "td", "th", "li", "h1", "h2",
                     "h3", "h4", "table", "section", "article"):
            self.pezzi.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._salta:
            self._salta -= 1

    def handle_data(self, data):
        if not self._salta:
            self.pezzi.append(data)


def html_in_testo(html):
    parser = _Spogliatore()
    try:
        parser.feed(html)
    except Exception:
        # Un HTML malformato non deve costare il giro: si ripiega su una
        # rimozione grezza dei tag.
        return re.sub(r"<[^>]+>", " ", html)
    return " ".join(parser.pezzi)


def parse_wait(text):
    """Minuti d'attesa da un frammento di testo, o None se non ne parla.

    0 esce SOLO da una frase esplicita di "nessuna attesa" o da uno 0
    scritto: ai confini l'assenza di numeri è ignoranza, non scorrevolezza.
    Ore e minuti si sommano ("1 ora 30 min" → 90). Le ore decimali esistono
    ("1,5 h") e valgono 90.
    """
    if any(z in text for z in ZERO_PHRASES):
        return 0
    minutes = None
    m = re.search(HOURS_RE, text)
    if m:
        minutes = round(float(m.group(1).replace(",", ".")) * 60)
        # I minuti dopo le ore, separati anche da punteggiatura: il polacco
        # scrive "1 godz. 15 min" e senza il punto ammesso i 15 si perdevano.
        resto = text[m.end():m.end() + 20]
        m2 = re.match(r"[\s.,;:–—-]*" + MINUTES_RE, resto)
        if m2:
            minutes += int(m2.group(1))
    else:
        m = re.search(MINUTES_RE, text)
        if m:
            minutes = int(m.group(1))
    # Oltre le 24 ore per le auto non è un'attesa, è un numero letto male
    # (l'etichetta sbagliata del Gottardo insegna): meglio ignoto che assurdo.
    if minutes is not None and minutes > 1440:
        return None
    return minutes


def _posizioni(testo, words):
    """Le posizioni di tutte le occorrenze di tutte le parole, ordinate."""
    out = []
    for w in words:
        for m in re.finditer(re.escape(w), testo):
            out.append(m.start())
    return sorted(out)


def attesa_nel_segmento(seg):
    """L'attesa delle AUTO in un segmento di testo: se il segmento nomina una
    categoria auto si legge da lì, e ci si ferma comunque alla prima categoria
    non-auto. L'app parla ai viaggiatori: i tempi dei camion — spesso di ore
    superiori — non devono vincere sulle auto per la regola del massimo."""
    cars = _posizioni(seg, CAR_WORDS)
    start = cars[0] if cars else 0
    others = [p for p in _posizioni(seg, OTHER_VEHICLE_WORDS) if p > start]
    end = others[0] if others else len(seg)
    return parse_wait(seg[start:end])


def parse_directions(window):
    """{exit: min|None, entry: min|None} da una finestra di testo spianata.

    Le pagine reali hanno due impaginazioni e vanno rette entrambe:
      - per categoria (HAK, police.hu): "auto: uscita X, entrata Y. camion:
        uscita Z" — il marcatore di direzione che segue una voce camion/bus
        appartiene ai camion e va saltato, altrimenti Z ruba il posto a X;
      - per direzione (granica): "uscita – auto X, camion Z; entrata – auto Y"
        — lì il segmento di direzione nomina a sua volta le auto, e si legge
        dal marcatore auto alla prima altra categoria.
    La regola: un marcatore preceduto da una categoria non-auto si salta solo
    se il suo segmento non nomina le auto.

    Se la finestra non nomina direzioni ma un'attesa c'è, si attribuisce
    all'uscita: è il dato che le pagine danno per primo e quello che serve a
    chi sta partendo. Scelta annotata nel README, da verificare sul registro
    delle finestre.
    """
    marks = []
    for direction, words in (("exit", EXIT_WORDS), ("entry", ENTRY_WORDS)):
        for w in words:
            for m in re.finditer(re.escape(w), window):
                marks.append((m.start(), direction))
    marks.sort()

    veicoli = sorted(
        [(p, "car") for p in _posizioni(window, CAR_WORDS)]
        + [(p, "other") for p in _posizioni(window, OTHER_VEHICLE_WORDS)])

    out = {"exit": None, "entry": None}
    if not marks:
        wait = attesa_nel_segmento(window)
        if wait is not None:
            out["exit"] = wait
        return out

    for i, (pos, direction) in enumerate(marks):
        fine = marks[i + 1][0] if i + 1 < len(marks) else len(window)
        seg = window[pos:fine]
        prima = [kind for p, kind in veicoli if p < pos]
        if prima and prima[-1] == "other" and not _posizioni(seg, CAR_WORDS):
            continue
        wait = attesa_nel_segmento(seg)
        if wait is not None and (out[direction] is None or wait > out[direction]):
            out[direction] = wait
    return out


def estrai_valichi(page_text, crossings):
    """Per ogni valico attivo della fonte: la finestra di testo della
    migliore occorrenza dei matchNames e le direzioni lette.
    Ritorna (campioni, finestre).

    La finestra si chiude alla prima comparsa del nome di un ALTRO valico:
    su una pagina-elenco le schede sono contigue, e senza questo taglio i
    numeri del valico successivo entrerebbero nella finestra vincendo per la
    regola del massimo. I nomi del valico stesso (es. "Bijača" dentro la
    scheda di Nova Sela) non chiudono niente.
    """
    piatto = spiana(page_text)
    occorrenze = {}
    tutte = []
    for crossing in crossings:
        pos_list = []
        for name in crossing.get("matchNames", []):
            for m in re.finditer(re.escape(name), piatto):
                tutte.append((m.start(), crossing["id"]))
                pos_list.append(m.start())
        if pos_list:
            # Un tetto alle occorrenze: su una pagina patologica un nome
            # citato cento volte non deve far esplodere il giro.
            occorrenze[crossing["id"]] = sorted(pos_list)[:20]
    tutte.sort()

    campioni = {}
    finestre = {}
    for cid, posizioni in occorrenze.items():
        # Si prova OGNI occorrenza del nome e vince quella da cui si leggono
        # più valori; a parità la prima. Il collaudo del 09.08.2026 ha
        # mostrato perché la prima da sola non basta: su police.hu il primo
        # "roszke" era un titolo di cronaca in tedesco a inizio pagina, e la
        # riga con i dati veniva molto dopo.
        migliore = None
        for pos in posizioni:
            fine = pos + WINDOW_CHARS
            for p, altro in tutte:
                if p > pos and altro != cid:
                    fine = min(fine, p)
                    break
            window = piatto[pos:fine]
            letto = parse_directions(window)
            punteggio = sum(1 for v in letto.values() if v is not None)
            if migliore is None or (punteggio, -pos) > migliore[0]:
                migliore = ((punteggio, -pos), window, letto)
        finestre[cid] = migliore[1]
        campioni[cid] = migliore[2]
    return campioni, finestre


def scarica(urls, lang):
    """La prima pagina sostanziosa fra gli URL della fonte.

    Ritorna (testo, url, note). Un tentativo per URL con un solo retry sui
    5xx: le fonti sono siti pubblici sotto carico nei giorni di esodo, ma
    qui — a differenza del feed svizzero — c'è quasi sempre un URL gemello
    da provare subito dopo.
    """
    ultimo_errore = "nessun URL"
    for url in urls:
        request = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{lang},en;q=0.7",
            "Accept-Encoding": "gzip",
        })
        for tentativo in range(2):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read()
                if data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                for enc in ("utf-8", "iso-8859-2", "windows-1250"):
                    try:
                        testo = data.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    testo = data.decode("utf-8", "replace")
                if len(testo) > 500:
                    return testo, url, None
                ultimo_errore = f"{url}: risposta corta ({len(testo)} caratteri)"
                break
            except urllib.error.HTTPError as exc:
                ultimo_errore = f"{url}: HTTP {exc.code}"
                if exc.code < 500 or tentativo == 1:
                    break
                time.sleep(15)
            except Exception as exc:
                ultimo_errore = f"{url}: {exc}"
                break
    return None, None, ultimo_errore


# --- adapter per fonte -------------------------------------------------
# Ogni adapter riceve i valichi attivi della propria fonte e ritorna
# (campioni {id: {exit/entry/…: minuti|None}}, salute {…}, finestre {id: testo}).

def fonte_pagina(source, crossings):
    """Adapter comune alle fonti "pagina di stato": HAK, police.hu, granica.

    Si provano tutti gli URL della fonte e vince quello da cui si LEGGONO
    più attese — non il primo che risponde: una pagina può essere
    raggiungibile, sostanziosa e comunque sbagliata (la pagina avvisi di
    HAK, 09.08.2026). Se nessun URL produce numeri si tiene comunque il
    migliore per nomi trovati, così le finestre nel registro mostrano su
    cosa stiamo inciampando.
    """
    migliore = None   # ((attese, trovati), campioni, url, finestre, testo)
    errori = []
    for url in SOURCE_URLS[source]:
        html, _, errore = scarica([url], SOURCE_LANG[source])
        if html is None:
            errori.append(errore)
            continue
        testo = html_in_testo(html)
        campioni, finestre = estrai_valichi(testo, crossings)
        attese = sum(1 for c in campioni.values()
                     for v in c.values() if v is not None)
        chiave = (attese, len(campioni))
        if migliore is None or chiave > migliore[0]:
            migliore = (chiave, campioni, url, finestre, testo)
        if attese >= 2 * len(crossings):
            break   # entrambe le direzioni di tutti: non si può fare meglio

    if migliore is None:
        return {}, {"ok": False, "error": " | ".join(errori) or "nessun URL"}, {}

    (attese, _), campioni, url, finestre, testo = migliore
    salute = {"ok": True, "url": url, "found": len(campioni),
              "of": len(crossings), "waits": attese}
    if not campioni:
        # Pagina raggiunta ma nessun valico riconosciuto: quasi certamente è
        # cambiato il formato. Si conserva l'inizio del testo spianato come
        # reperto, senza committare l'HTML intero (peserebbe a ogni giro).
        salute["ok"] = False
        salute["error"] = "nessun valico riconosciuto nella pagina"
        salute["excerpt"] = spiana(testo)[:400]
    return campioni, salute, finestre


def fonte_gotthard(crossings):
    """Il Gottardo dalla copia già raccolta dal collector gemello: un file
    nel repo, niente rete, niente quota API consumata due volte."""
    latest = BASE.parent / "gotthard" / "data" / "latest.json"
    try:
        dati = json.loads(latest.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {}, {"ok": False, "error": f"gotthard/data/latest.json: {exc}"}, {}
    campioni = {}
    for crossing in crossings:
        campioni[crossing["id"]] = {
            "south": (dati.get("south") or {}).get("wait"),
            "north": (dati.get("north") or {}).get("wait"),
        }
    quando = dati.get("time", "")
    return campioni, {"ok": True, "sampled": quando}, {}


FONTI = {
    "hak": lambda c: fonte_pagina("hak", c),
    "police_hu": lambda c: fonte_pagina("police_hu", c),
    "granica_pl": lambda c: fonte_pagina("granica_pl", c),
    "gotthard": fonte_gotthard,
}


# --- push --------------------------------------------------------------

def send_push(channel, alert):
    if not PUSH_APP_ID or not PUSH_MASTER_KEY:
        return False
    request = urllib.request.Request(
        "https://parseapi.back4app.com/push",
        data=json.dumps({
            "where": {"channels": channel, "deviceType": "ios"},
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
            print(f"push {channel} ({response.status}): {alert}")
            return response.status < 300
    except Exception as exc:  # la notifica non deve mai rompere il campionamento
        print(f"push fallito su {channel}: {exc}")
        return False


def canale_di(crossing_id):
    return "valico-" + crossing_id.replace(".", "-")


def parse_time(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def stampa_ora(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def update_notifications(stato_valichi, per_id, now):
    """Stessa macchina a fasi del Gottardo (clear → queued → heavy → clear),
    una per valico+direzione, con chiave "id.direzione" in push-state.json.
    La fine è confermata nel tempo (CLEAR_CONFIRM) perché anche qui un buco
    di fonte non va scambiato per frontiera tornata libera."""
    try:
        push_state = json.loads(PUSH_STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        push_state = {}

    for crossing_id, stato in stato_valichi.items():
        crossing = per_id[crossing_id]
        labels = crossing.get("directions", {})
        for direction, valori in stato["directions"].items():
            wait = valori.get("wait")
            if wait is None:
                continue   # ignoto: nessuna decisione, la fase resta com'è
            chiave = f"{crossing_id}.{direction}"
            entry = push_state.get(chiave, {})
            phase = entry.get("phase", "clear")
            last_sent = parse_time(entry.get("lastSent") or "")
            clear_since = parse_time(entry.get("clearSince") or "")
            cooling = last_sent is not None and now - last_sent < PUSH_COOLDOWN

            if phase in ("queued", "heavy"):
                clear_since = None if wait >= NOTIFY_CLEAR else (clear_since or now)
            else:
                clear_since = None

            etichetta = labels.get(direction, direction)
            nome = crossing["name"]
            message = None
            new_phase = phase
            if phase == "clear" and wait >= NOTIFY_START:
                message = f"🚦 {nome} ({etichetta}): ~{wait} min wait"
                new_phase = "queued"
            elif phase == "queued" and wait >= NOTIFY_HEAVY:
                message = f"⚠️ {nome} ({etichetta}): heavy — ~{wait} min wait"
                new_phase = "heavy"
            elif (phase in ("queued", "heavy") and clear_since is not None
                  and now - clear_since >= CLEAR_CONFIRM):
                message = f"✅ {nome} ({etichetta}): waiting time back to normal"
                new_phase = "clear"

            if message and not cooling and send_push(canale_di(crossing_id), message):
                phase = new_phase
                last_sent = now
                if new_phase == "clear":
                    clear_since = None

            nuovo = {"phase": phase}
            if last_sent is not None:
                nuovo["lastSent"] = stampa_ora(last_sent)
            if clear_since is not None:
                nuovo["clearSince"] = stampa_ora(clear_since)
            push_state[chiave] = nuovo

    PUSH_STATE_FILE.write_text(json.dumps(push_state, indent=1, sort_keys=True))


# --- registro fonti ----------------------------------------------------

def scrivi_registro(salute_fonti, finestre, now):
    """Una riga per giro con la salute delle fonti; le finestre di testo solo
    quando cambiano rispetto all'ultima registrata, altrimenti il registro
    sarebbe rumore puro. Il file esiste SEMPRE, anche vuoto: un percorso
    mancante nel git add del workflow abbatte il run (successo al Gottardo
    il 02.08.2026)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    righe = []
    ultime_finestre = {}
    if SOURCES_LOG_FILE.exists():
        cutoff = stampa_ora(now - SOURCES_LOG_WINDOW)
        for riga in SOURCES_LOG_FILE.read_text().splitlines():
            if not riga.strip():
                continue
            try:
                voce = json.loads(riga)
            except json.JSONDecodeError:
                continue   # una riga corrotta non deve far perdere il resto
            if voce.get("at", "") > cutoff:
                righe.append(riga)
                for k, v in (voce.get("windows") or {}).items():
                    ultime_finestre[k] = v

    # 400 caratteri, non di meno: al collaudo del 09.08.2026 le finestre da
    # 220 mozzavano proprio il pezzo che serviva a capire il formato vero.
    nuove = {k: v[:400] for k, v in finestre.items()
             if ultime_finestre.get(k) != v[:400]}
    voce = {"at": stampa_ora(now), "sources": salute_fonti}
    if nuove:
        voce["windows"] = nuove
    righe.append(json.dumps(voce, ensure_ascii=False))
    SOURCES_LOG_FILE.write_text("\n".join(righe) + "\n")


# --- prova offline -----------------------------------------------------

def prova():
    """Fa girare la catena di estrazione sulle fixture in prove/ e verifica
    i valori attesi. Niente rete: è il collaudo del PARSER, non delle fonti
    (quelle si collaudano al primo run del workflow, sul registro)."""
    catalogo = json.loads(CATALOG_FILE.read_text())
    attivi = [c for c in catalogo["crossings"] if c.get("status") == "active"]
    per_fonte = {}
    for c in attivi:
        per_fonte.setdefault(c["source"], []).append(c)

    attese = {
        "hak": {
            "hr-me.karasovici": {"exit": 90, "entry": 0},
            "hr-me.vitaljina": {"exit": None, "entry": None},
            "hr-ba.nova-sela": {"exit": 20, "entry": 20},
            "hr-ba.stara-gradiska": {"exit": 0, "entry": 30},
            "hr-rs.bajakovo": {"exit": 180, "entry": 45},
            "hr-rs.tovarnik": {"exit": 150, "entry": 0},
        },
        "police_hu": {
            "hu-rs.roszke": {"exit": 120, "entry": 30},
            "hu-rs.tompa": {"exit": 0, "entry": 0},
            "hu-ua.zahony": {"exit": 60, "entry": 90},
            "hu-ua.beregsurany": {"exit": 30, "entry": 0},
        },
        "granica_pl": {
            "pl-ua.medyka": {"exit": 75, "entry": 0},
            "pl-ua.korczowa": {"exit": 0, "entry": 120},
            "pl-ua.dorohusk": {"exit": 45, "entry": None},
            "pl-ua.hrebenne": {"exit": 0, "entry": 0},
        },
    }

    errori = 0
    for source, expected in attese.items():
        fixture = PROVE_DIR / f"{source}.html"
        campioni, _ = estrai_valichi(html_in_testo(fixture.read_text()),
                                     per_fonte[source])
        for crossing_id, atteso in expected.items():
            avuto = campioni.get(crossing_id, {"exit": None, "entry": None})
            esito = "ok" if avuto == atteso else "SBAGLIATO"
            if esito != "ok":
                errori += 1
            print(f"  {source:>10}  {crossing_id:<22} atteso {atteso}  letto {avuto}  {esito}")

    fixture = PROVE_DIR / "gotthard.latest.json"
    dati = json.loads(fixture.read_text())
    print(f"  {'gotthard':>10}  ch.gottardo            south={dati['south']['wait']} north={dati['north']['wait']}  ok")

    if errori:
        sys.exit(f"{errori} estrazioni sbagliate")
    print("tutte le estrazioni tornano")


# --- giro completo -----------------------------------------------------

def main():
    if "--prova" in sys.argv:
        prova()
        return

    catalogo = json.loads(CATALOG_FILE.read_text())
    attivi = [c for c in catalogo["crossings"] if c.get("status") == "active"]
    per_id = {c["id"]: c for c in attivi}
    per_fonte = {}
    for c in attivi:
        per_fonte.setdefault(c["source"], []).append(c)

    now = datetime.now(timezone.utc).replace(microsecond=0)

    campioni = {}
    salute_fonti = {}
    finestre = {}
    for source, crossings in per_fonte.items():
        try:
            estratti, salute, finestre_fonte = FONTI[source](crossings)
        except Exception as exc:
            # Qualunque cosa succeda a una fonte, le altre committano lo
            # stesso: l'app di un utente dei Balcani non deve restare al buio
            # perché una pagina polacca ha cambiato faccia.
            estratti, salute, finestre_fonte = {}, {"ok": False, "error": repr(exc)}, {}
        campioni.update(estratti)
        salute_fonti[source] = salute
        finestre.update(finestre_fonte)

    # Stato precedente: serve alla tenuta (held) per i valichi senza campione.
    try:
        precedente = json.loads(LATEST_FILE.read_text()).get("crossings", {})
    except (FileNotFoundError, json.JSONDecodeError):
        precedente = {}

    stato_valichi = {}
    for crossing in attivi:
        cid = crossing["id"]
        direzioni_catalogo = list(crossing.get("directions", {"exit": "", "entry": ""}))
        nuovo = {"updated": stampa_ora(now), "directions": {}}
        letto = campioni.get(cid)

        if letto is not None and any(v is not None for v in letto.values()):
            for d in direzioni_catalogo:
                nuovo["directions"][d] = {"wait": letto.get(d)}
        else:
            # Niente campione: si riporta l'ultimo stato entro HOLD_WINDOW,
            # marcato held e con l'updated ORIGINALE (i valori tenuti non
            # riarmano il timer — lezione del Gottardo). Oltre la finestra
            # le attese diventano null: ignote, non zero.
            vecchio = precedente.get(cid)
            visto = parse_time((vecchio or {}).get("updated") or "")
            if vecchio and visto is not None and now - visto <= HOLD_WINDOW:
                nuovo = dict(vecchio)
                nuovo["held"] = True
            else:
                for d in direzioni_catalogo:
                    nuovo["directions"][d] = {"wait": None}
        stato_valichi[cid] = nuovo

    # --- storico compatto: un campione per giro, solo i valori noti ---
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            history = []
    cutoff = now - WINDOW
    history = [s for s in history
               if (parse_time(s.get("time", "")) or cutoff) > cutoff]

    sample = {"time": stampa_ora(now), "w": {}}
    tenuti = []
    for cid, stato in stato_valichi.items():
        if stato.get("held"):
            tenuti.append(cid)
        for d, valori in stato["directions"].items():
            if valori.get("wait") is not None:
                sample["w"][f"{cid}.{d}"] = valori["wait"]
    if tenuti:
        sample["held"] = sorted(tenuti)
    history.append(sample)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=1))

    update_notifications(stato_valichi, per_id, now)

    latest = {
        "time": sample["time"],
        "catalogVersion": catalogo.get("version"),
        "crossings": stato_valichi,
        "sources": salute_fonti,
    }
    LATEST_FILE.write_text(json.dumps(latest, indent=1, ensure_ascii=False))

    scrivi_registro(salute_fonti, finestre, now)

    ok = sum(1 for s in salute_fonti.values() if s.get("ok"))
    noti = len(sample["w"])
    print(f"campione salvato: {noti} attese note su {len(attivi)} valichi, "
          f"fonti ok {ok}/{len(salute_fonti)}, tenuti {sorted(tenuti) or '-'} "
          f"(storico {len(history)})")


if __name__ == "__main__":
    main()
