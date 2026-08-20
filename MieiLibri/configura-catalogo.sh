#!/bin/bash
# Scrive la chiave Google Books dentro Catalog.swift.
#
#   ./configura-catalogo.sh AIzaSy...
#
# Attenzione: questo repository e' pubblico. Non fare il commit della chiave;
# usala in locale, oppure conservala nel segreto GOOGLE_BOOKS_KEY su GitHub,
# che il workflow inietta da solo al momento della compilazione.

set -euo pipefail

CHIAVE="${1:-}"
if [ -z "$CHIAVE" ]; then
  echo "Uso: $0 <chiave-google-books>" >&2
  exit 1
fi

FILE="$(cd "$(dirname "$0")" && pwd)/MieiLibri/Services/Catalog.swift"
[ -f "$FILE" ] || { echo "File non trovato: $FILE" >&2; exit 1; }

python3 - "$FILE" "$CHIAVE" <<'PY'
import re, sys
percorso, chiave = sys.argv[1], sys.argv[2]
testo = open(percorso).read()
nuovo, n = re.subn(r'static let googleAPIKey = "[^"]*"',
                   f'static let googleAPIKey = "{chiave}"', testo)
if n != 1:
    sys.exit("Riga della chiave non trovata in Catalog.swift")
open(percorso, "w").write(nuovo)
print(f"Chiave scritta in {percorso}")
PY

echo "Ricompila l'app perche' abbia effetto."
