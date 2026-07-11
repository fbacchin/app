# Gottardo Live — Raccoglitore storico

Raccoglie ogni ~10 minuti lo stato delle code al tunnel del San Gottardo
dall'API ufficiale di opentransportdata.swiss (DATEX II, dati USTRA/VMZ-CH)
e mantiene una finestra mobile di 48 ore in `data/history.json`.

L'app iOS **Gottardo Live** lo scarica da:

```
https://raw.githubusercontent.com/fbacchin/app/main/gotthard/data/history.json
```

per riempire il grafico delle ultime 24 ore anche quando è rimasta chiusa.

## Componenti

- `collect.py` — interroga l'API Traffic Situations, estrae code/attese ai
  portali (filtro corridoio Erstfeld↔Faido, direzioni, anti-zombie) e accoda
  un campione al JSON.
- `.github/workflows/gotthard-collect.yml` (alla radice del repo) — cron ogni
  10 minuti + avvio manuale. Richiede il secret `OTD_API_KEY` (chiave
  opentransportdata.swiss, gratuita).

## Note

- Il cron `*/10` è best-effort: GitHub può ritardare le esecuzioni di qualche
  minuto nelle ore di punta. Per il grafico è più che sufficiente.
- Quando il messaggio ufficiale riporta solo i km di coda senza tempo
  d'attesa, il ritardo è stimato a ~10 min/km (dosaggio del Gottardo).
- Test locale: `OTD_API_KEY=... python3 collect.py`
