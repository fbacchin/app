# Configurazione di gottardo-percorsi (ADEV-773). Specifica: Doc/ADEV-773/spec.md nel progetto Gotthard.
from zoneinfo import ZoneInfo

ZURIGO = ZoneInfo("Europe/Zurich")

# Punti dove la rampa d'uscita dell'A2 incontra la strada locale (OpenStreetMap, 15.10.2026).
# Il passo è un punto sulla strada 2 al valico, non l'Ospizio (che sta su un piazzale a lato).
PUNTI = {
    "Erstfeld": (46.83446, 8.63694),
    "Amsteg":   (46.77208, 8.66830),
    "Faido":    (46.46584, 8.82325),
    "Biasca":   (46.35530, 8.96100),   # strada locale a est dello svincolo: sulla rampa Apple lo agganciava alla carreggiata verso sud (Biasca→Faido 52,8 km)
    "Passo":    (46.55880, 8.56210),
    # Göschenen–Airolo aggiunta il 16.10 (richiesta dell'utente). Punti provati con Apple e TomTom: Erstfeld↔Göschenen torna uguale nei due sensi.
    "Göschenen": (46.67062, 8.59251),  # strada 2 (Umfahrungsstrasse) appena a sud della rotonda dello svincolo
    "Airolo":    (46.52917, 8.60837),  # Via San Gottardo (strada 2) in paese. Vicino alla rotonda dello svincolo TomTom partiva male: Airolo→Faido 30 km, Airolo→Göschenen sul passo
}
VALICO = "Passo"   # punto obbligato del percorso «passo»

# (nome = intestazione CSV, origine, destinazione, percorso). NS = nord→sud, SN = sud→nord.
MISURE = [   # prima i percorsi col tunnel, poi quelli sul passo (richiesta dell'utente)
    ("NS Erstfeld-Biasca tunnel", "Erstfeld", "Biasca", "tunnel"),
    ("SN Biasca-Erstfeld tunnel", "Biasca", "Erstfeld", "tunnel"),
    ("NS Amsteg-Faido tunnel",    "Amsteg", "Faido", "tunnel"),
    ("SN Faido-Amsteg tunnel",    "Faido", "Amsteg", "tunnel"),
    ("NS Erstfeld-Biasca passo",  "Erstfeld", "Biasca", "passo"),
    ("SN Biasca-Erstfeld passo",  "Biasca", "Erstfeld", "passo"),
    ("NS Amsteg-Faido passo",     "Amsteg", "Faido", "passo"),
    ("SN Faido-Amsteg passo",     "Faido", "Amsteg", "passo"),
    # In coda e non in mezzo: le colonne dei CSV già scritti restano al loro posto.
    ("NS Göschenen-Airolo tunnel", "Göschenen", "Airolo", "tunnel"),
    ("SN Airolo-Göschenen tunnel", "Airolo", "Göschenen", "tunnel"),
    ("NS Göschenen-Airolo passo",  "Göschenen", "Airolo", "passo"),
    ("SN Airolo-Göschenen passo",  "Airolo", "Göschenen", "passo"),
    # Tratte separate (16.10, richiesta dell'utente): una sola strada, l'A2.
    ("NS Erstfeld-Amsteg",  "Erstfeld", "Amsteg", "diretto"),  ("SN Amsteg-Erstfeld",  "Amsteg", "Erstfeld", "diretto"),
    ("NS Amsteg-Göschenen", "Amsteg", "Göschenen", "diretto"), ("SN Göschenen-Amsteg", "Göschenen", "Amsteg", "diretto"),
    ("NS Airolo-Faido",     "Airolo", "Faido", "diretto"),     ("SN Faido-Airolo",     "Faido", "Airolo", "diretto"),
    ("NS Faido-Biasca",     "Faido", "Biasca", "diretto"),     ("SN Biasca-Faido",     "Biasca", "Faido", "diretto"),
    # Passo verso nord con la CUPRA (19.10, richiesta dell'utente): calcolate, nessuna richiesta in più.
    ("SN Biasca-Erstfeld passo CUPRA", "Biasca", "Erstfeld", "cupra"),
    ("SN Faido-Amsteg passo CUPRA",    "Faido", "Amsteg", "cupra"),
]

# CUPRA: la corsia d'emergenza dell'A2 verso nord, da Varenzo all'uscita di Airolo, aperta per chi va ai passi quando c'è
# coda al portale sud (USTRA, astra.admin.ch/it/a2-cupra-it). Per le fonti è la stessa carreggiata dell'A2, quindi danno
# al passo la velocità della coda. Passo con la CUPRA = passo misurato meno il ritardo della fonte su Faido→Airolo.
# Vale solo se la corsia è aperta: l'USTRA non pubblica quando lo è.
CUPRA = {"SN Biasca-Erstfeld passo CUPRA": "SN Biasca-Erstfeld passo", "SN Faido-Amsteg passo CUPRA": "SN Faido-Amsteg passo"}
TRATTO_CUPRA = "SN Faido-Airolo"

# Misure che una fonte non fa. Google resta a 8 chiamate l'ora (decisione dell'utente, 16.10):
# Amsteg–Faido e Göschenen–Airolo, niente Erstfeld–Biasca né tratte separate. Faido→Airolo verso nord sì:
# viene dal primo tratto del passo Faido→Amsteg, chiesto con Airolo come tappa (19.10), senza chiamate in più.
NON_MISURATE = {"google": {m[0] for m in MISURE if "Erstfeld-Biasca" in m[0] or "Biasca-Erstfeld" in m[0]
                           or (m[3] == "diretto" and m[0] != TRATTO_CUPRA)}}

# Contatori ASTRA (opentransportdata «Road traffic – traffic counters», 19.10, richiesta dell'utente): solo le tratte
# separate dell'A2. Velocità delle auto in un punto, ultimo minuto: il tempo di una tratta è la lunghezza di riferimento
# divisa tra le sue stazioni, ognuna percorsa alla velocità che misura. Nessun «senza traffico»: la fonte non lo dà.
NON_MISURATE["astra"] = {m[0] for m in MISURE if m[3] != "diretto"}
STAZIONI_ASTRA = {   # tratta (nomi da nord a sud) → stazioni sull'A2 lungo la tratta; posizioni dall'elenco ASTRA del 15.10
    "Erstfeld-Amsteg": ["CH:0195"],                  # 46.79, 8.67
    "Amsteg-Göschenen": ["CH:0528", "CH:0529"],      # Gurtnellen 46.73, 8.63 · Wassen 46.69, 8.60
    "Airolo-Faido": ["CH:0293"],                     # Quinto 46.51, 8.71 (nel tratto della CUPRA)
    "Faido-Biasca": ["CH:0204", "CH:0166"],          # Lavorgo 46.43, 8.85 · Biasca 46.35, 8.96
}
# Corsie (record) per senso ASTRA, dall'elenco delle stazioni. CH:0529.01 non ha senso: è una rampa, non si usa.
CORSIE_ASTRA = {
    "CH:0195": {"negative": ["01", "02"], "positive": ["03", "04"]},
    "CH:0528": {"negative": ["01", "02"], "positive": ["03", "04"]},
    "CH:0529": {"negative": ["02", "03"], "positive": ["04", "05"]},
    "CH:0293": {"negative": ["01", "02"], "positive": ["03", "04"]},
    "CH:0204": {"negative": ["01", "02"], "positive": ["03", "04", "05"]},
    "CH:0166": {"negative": ["01", "02"], "positive": ["03", "04"]},
}
SENSO_ASTRA = {"positive": "SN", "negative": "NS"}   # vedi la nota in fondo al file su come è stato stabilito

def misure(fonte):
    return [m for m in MISURE if m[0] not in NON_MISURATE.get(fonte, ())]

def chiamate(fonte):
    """Le misure che chiedono qualcosa alla fonte: le CUPRA si calcolano, e Google ricava le tratte dal passo."""
    return [m for m in misure(fonte) if m[3] != "cupra" and not (fonte == "google" and m[3] == "diretto")]

# Fonti i cui dati possono stare nel repository pubblico. Vuoto: Apple vieta di pubblicare i suoi dati,
# le condizioni di TomTom non sono verificate (Doc/ADEV-773/preliminari.md).
PUBBLICHE = set()
ORARIE = {"google"}                                   # le altre girano ogni 15 minuti

# Soglie dell'app (HistoryChartView.livello): < 1 verde, < 10 giallo, < 40 arancione, oltre rosso.
# Nelle mappe il verde arriva a 2 minuti: 1-2 minuti di scarto sono arrotondamento, non coda (richiesta dell'utente, 15.10).
SOGLIE = ((3, "🟢"), (10, "🟡"), (40, "🟠"))
COLORI = {"🟢": "#2fb350", "🟡": "#ffcc00", "🟠": "#ff6f00", "🔴": "#c62828", "⚪": "#d5d8dc"}

# Tetti sotto le quote gratuite: (periodo, limite).
TETTI = {"tomtom": ("giorno", 2000), "google": ("mese", 4800)}


# Distanza di riferimento per misura (metri), fissata dal primo giro riuscito e controllata a mano.
# Vuota = nessun controllo. Oltre TOLLERANZA la fonte ha calcolato un'altra strada.
RIFERIMENTI_M = {   # Apple Maps, giro del 15.10.2026 17:30 (Google entro il 5 %), approvate dall'utente
    "NS Erstfeld-Biasca tunnel": 75400, "SN Biasca-Erstfeld tunnel": 76000,
    "NS Amsteg-Faido tunnel": 50000,    "SN Faido-Amsteg tunnel": 49800,
    "NS Erstfeld-Biasca passo": 90000,  "SN Biasca-Erstfeld passo": 90600,
    "NS Amsteg-Faido passo": 64600,     "SN Faido-Amsteg passo": 64400,
    # Göschenen–Airolo e tratte separate: Apple, 16.10 sera, punto di Airolo in paese. TomTom entro il 3 %, tranne Erstfeld–Amsteg (0,8 km in meno).
    # Faido→Airolo: le due fonti insieme ora 19,0 ora 20,7 km (due accessi al paese): riferimento a metà.
    "NS Göschenen-Airolo tunnel": 21000, "SN Airolo-Göschenen tunnel": 22250,
    "NS Göschenen-Airolo passo": 31750,  "SN Airolo-Göschenen passo": 31850,
    "NS Erstfeld-Amsteg": 8960,   "SN Amsteg-Erstfeld": 8870,   "NS Amsteg-Göschenen": 13900, "SN Göschenen-Amsteg": 13710,
    "NS Airolo-Faido": 21050,     "SN Faido-Airolo": 19850,     "NS Faido-Biasca": 17930,     "SN Biasca-Faido": 18540,
}
TOLLERANZA = 0.05
TOLLERANZA_MIN_M = 1000   # sulle tratte corte il 5 % è meno della differenza tra le fonti (Erstfeld–Amsteg: Apple 9,0 km, TomTom 8,2)

# Senso dei contatori ASTRA, stabilito il 19.10.2026 16:25-16:40 con 5 letture (un minuto ciascuna), durante una coda
# verso nord ad Airolo (Apple: +10 min su Faido→Airolo):
# - salite verso sud (Wassen, Gurtnellen): mezzi pesanti più lenti in «negative» (58 e 70 km/h contro 82 e 79);
# - salita verso nord (Biaschina, CH:0204): mezzi pesanti più lenti in «positive» (72 contro 87), e «positive» ha la terza corsia;
# - a nord della galleria il flusso «positive» è il doppio e più (coda verso nord smaltita dalla galleria piena).
# Quindi positive = verso nord (SN), negative = verso sud (NS).
