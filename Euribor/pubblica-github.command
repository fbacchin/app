#!/bin/zsh
# Pubblica su GitHub le date nuove dei tassi.
#
# Serve da ponte per la sessione programmata di Claude: la sua sandbox vede
# solo la cartella Libor, non il clone git. Questo file va quindi ESEGUITO
# FUORI dal sandbox (con `open` o doppio clic: Terminal lo esegue come
# utente pieno) e scrive l'esito in pubblica-github.log accanto a sé, dove
# la sessione può rileggerlo.
#
# La copia di riferimento è versionata nella repo (Euribor/). Non modificare
# questa al volo: correggere quella e ricopiarla qui.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HERE/pubblica-github.log"
REPO="/Users/fabrizio/Xcode/=NewApps/app"

{
  echo "== $(date '+%Y-%m-%d %H:%M:%S') =="
  if ! cd "$REPO"; then
      echo "ERRORE: repo non trovata in $REPO"
      echo "ESITO: FALLITO"
      exit 0
  fi
  git pull --rebase --quiet origin main || echo "AVVISO: pull non riuscito, continuo con la copia locale"
  python3 Euribor/sync-from-drive.py
  if git diff --quiet -- Euribor; then
      echo "ESITO: OK (nessuna modifica da pubblicare)"
  else
      git add Euribor
      git commit -m "Aggiorna i tassi al $(date +%d.%m.%Y)"
      if git push origin main; then
          echo "ESITO: OK (pubblicato)"
      else
          echo "ESITO: FALLITO (push non riuscito: i dati restano solo in locale)"
      fi
  fi
} > "$LOG" 2>&1
exit 0
