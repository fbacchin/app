# Percorsi del Gottardo (ADEV-773)

Codice di una prova di osservazione dei tempi di percorrenza sull'asse del San Gottardo (A2), via galleria e via passo, in entrambi i sensi di marcia.

Qui c'è solo il codice; il flusso di GitHub Actions che lo esegue ogni 15 minuti è `.github/workflows/gotthard-percorsi.yml` alla radice del repository. I dati raccolti non sono pubblici: vanno nel repository privato `fbacchin/gottardo-percorsi-privati`, clonato in `privati/` durante il flusso.

Fonti: Apple Maps, TomTom, Google (galleria e passo, più le tratte separate dell'A2) e i contatori ASTRA di opentransportdata (solo le tratte separate). Fino al 19.10.2026 il codice stava nel repository `fbacchin/gottardo-percorsi`.

- `giro.py` — un giro di misure
- `fonti.py` — chiamate alle fonti
- `archivio.py` — file CSV e quote
- `pagina.py` — mappe e pagine
- `prova_percorsi.py` — banco di prova (`python3 prova_percorsi.py`, con il privato clonato in `privati/` per i campioni)
- `sito/` — Worker Cloudflare della pagina percorsi.bacchin.app (`npx wrangler@4.151.0 deploy` da `sito/`)
