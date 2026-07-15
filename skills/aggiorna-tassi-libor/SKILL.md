---
name: aggiorna-tassi-libor
description: Aggiorna i file CSV dei tassi di interesse (Libor e Euribor) da martedì a sabato alle 13:00, li pubblica su GitHub e salva un riepilogo nella cartella outputs.
---

Esegui l'aggiornamento automatico dei file CSV dei tassi di interesse usando la skill `aggiorna-tassi`.

Passi da seguire:
1. Invoca la skill `aggiorna-tassi` (chiamando lo strumento Skill con `skill: "aggiorna-tassi"`). La skill fa due cose:
   - scarica i dati più recenti da global-rates.com tramite browser Chrome e aggiorna i 7 file CSV nella cartella Libor (ESTER, EURIBOR, LIBOR GBP, LIBOR USD SOFR, LIBOR USD, SARON CHF, TONAR JPY), aggiungendo solo le date mancanti senza modificare i dati esistenti;
   - pubblica le stesse date nuove sui CSV della repo GitHub `fbacchin/app` (cartella `Euribor/`), da cui le app le leggono, e fa commit e push.
2. Al termine, salva un file di riepilogo in formato Markdown nella cartella outputs dell'utente con il nome `aggiornamento-tassi-YYYY-MM-DD.md` (usa la data del giorno in cui viene eseguito il task). Il riepilogo deve contenere:
   - Data e ora dell'esecuzione
   - Per ciascuno dei 7 file: nome del file, numero di nuove righe aggiunte, intervallo di date aggiunte (da-a), eventuali errori o avvisi
   - **Esito della pubblicazione su GitHub**: se il push è riuscito o no
   - Stato complessivo (successo / parziale / fallito)
3. Condividi il file di riepilogo con l'utente usando `mcp__cowork__present_files`.

Se la skill `aggiorna-tassi` non è disponibile o fallisce, salva comunque un file di riepilogo che documenti il problema riscontrato.

Note importanti:
- Ogni esecuzione del task parte senza memoria delle esecuzioni precedenti — non assumere nulla sullo stato dei file, lascia che la skill rilevi automaticamente le date mancanti.
- **Se i dati su Drive sono aggiornati ma il push su GitHub fallisce, lo stato complessivo è "parziale", non "successo"**: le app continuerebbero a vedere i dati vecchi. Dillo esplicitamente nel riepilogo.
- Usa l'italiano nel file di riepilogo.
