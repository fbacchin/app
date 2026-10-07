# Avviso una tantum a tutti (07.10.2026): webcam ferme alla fonte. Uso: avviso.py conta | invia
# Stessi filtri per lingua del collector (per_lingua in collect.py). File temporaneo, da cancellare dopo l'invio.
import json, os, sys, urllib.parse, urllib.request
H = {"X-Parse-Application-Id": os.environ["B4A_APP_ID"], "X-Parse-Master-Key": os.environ["B4A_MASTER_KEY"], "Content-Type": "application/json"}
BASE = {"channels": "global", "deviceType": "ios"}
TESTI = {
    "it": "📷 Webcam ferme: dal 6 ottobre la fonte invia sempre la stessa immagine. Code, attese e avvisi funzionano normalmente.",
    "de": "📷 Webcams stehen still: Seit dem 6. Oktober liefert die Quelle immer dasselbe Bild. Stau, Wartezeiten und Meldungen funktionieren normal.",
    "fr": "📷 Webcams figées : depuis le 6 octobre, la source envoie toujours la même image. Bouchons, temps d'attente et alertes fonctionnent normalement.",
    "en": "📷 Webcams frozen: since 6 October the source has been sending the same image. Queues, waiting times and alerts work normally.",
}
def per_lingua(lingua):
    if lingua == "en":
        cond = {"$or": [{"localeIdentifier": {"$exists": False}}, {"localeIdentifier": {"$regex": "^(?!it|de|fr)"}}]}
    else:
        cond = {"localeIdentifier": {"$regex": f"^{lingua}"}}
    return {**BASE, "$and": [cond]}
def conta(where):
    q = urllib.parse.urlencode({"where": json.dumps(where), "count": 1, "limit": 0})
    r = urllib.request.Request("https://parseapi.back4app.com/classes/_Installation?" + q, headers=H)
    return json.loads(urllib.request.urlopen(r, timeout=30).read())["count"]
totale = conta(BASE); somma = 0
for l in TESTI:
    n = conta(per_lingua(l)); somma += n; print(f"destinatari {l}: {n}")
print(f"totale: {totale} | somma per lingua: {somma}")
assert somma == totale, "le lingue non coprono tutti: non invio"
if sys.argv[1] == "invia":
    for l, testo in TESTI.items():
        r = urllib.request.Request("https://parseapi.back4app.com/push", headers=H,
            data=json.dumps({"where": per_lingua(l), "data": {"alert": testo, "sound": "default"}}).encode())
        try:
            with urllib.request.urlopen(r, timeout=30) as risposta: print(f"push {l}: {risposta.status} {risposta.read().decode()[:60]}")
        except urllib.error.HTTPError as e: print(f"push {l} FALLITA: {e.code}")
