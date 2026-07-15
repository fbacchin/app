#!/usr/bin/env python3
"""
Rigenera i CSV pubblicati qui a partire dai file sorgente nella cartella Libor
su Google Drive, che restano la fonte di verità aggiornata dalla skill
`aggiorna-tassi`.

Non è una copia: applica tre trasformazioni.

1. ESTER e EURIBOR su Drive sono nel formato "largo" (date sulle colonne).
   Qui vengono trasposti nel formato riga-per-data usato da tutti gli altri.
2. I nomi con gli spazi ("LIBOR USD SOFR.csv") diventano trattini, perché
   negli URL gli spazi vanno percent-encoded e in Swift URL(string:) con uno
   spazio grezzo restituisce nil.
3. Bonifica: la virgola decimale diventa punto (14 valori del 16-17.11.2023
   la usano e farebbero fallire Double()), e "Week day" è ricalcolato dalla
   data, perché sui file Drive è spesso incoerente.

È idempotente: rilanciarlo senza nuovi dati non produce alcuna modifica.
Uso:  python3 sync-from-drive.py [--check]
      --check  non scrive nulla, riporta solo cosa cambierebbe (exit 1 se
               ci sono differenze)
"""

import csv
import io
import re
import sys
from datetime import datetime
from pathlib import Path

DRIVE = Path(
    "/Users/fabrizio/Library/CloudStorage/GoogleDrive-fabrizio.bacchin@cogipa.it"
    "/Il mio Drive/fabrizio.bacchin@wwconsultant.net/Libor"
)
REPO = Path(__file__).resolve().parent

COLUMNS = ["Date", "Week day", "ON", "1W", "1M", "2M", "3M", "6M", "12M"]
NUMERIC_WITH_COMMA = re.compile(r"^-?\d+,\d+$")

# (file su Drive, file qui, tipo). "wide" = date sulle colonne, da trasporre.
FILES = [
    ("ESTER.csv", "ESTER.csv", "wide", {"ON": "ON"}),
    ("EURIBOR.csv", "EURIBOR.csv", "wide",
     {"1w": "1W", "1m": "1M", "3m": "3M", "6m": "6M", "12m": "12M"}),
    ("LIBOR GBP.csv", "LIBOR-GBP.csv", "long", None),
    ("LIBOR USD SOFR.csv", "LIBOR-USD-SOFR.csv", "long", None),
    ("LIBOR USD.csv", "LIBOR-USD.csv", "long", None),
    ("SARON CHF.csv", "SARON-CHF.csv", "long", None),
    ("TONAR JPY.csv", "TONAR-JPY.csv", "long", None),
]


def clean_value(value):
    """Virgola decimale -> punto. Lascia intatto tutto il resto."""
    value = value.strip()
    return value.replace(",", ".") if NUMERIC_WITH_COMMA.match(value) else value


def render(rows):
    """Serializza le righe nel formato canonico: tutto quotato, newline \\n."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buffer.getvalue()


def from_wide(text, mapping):
    """Formato largo (date sulle colonne) -> righe per data, più recente in cima."""
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []

    dates = []
    for raw in rows[0][1:]:
        raw = raw.strip()
        if raw:
            dates.append(datetime.strptime(raw, "%d/%m/%Y"))

    data = {d: {} for d in dates}
    for row in rows[1:]:
        column = mapping.get(row[0].strip())
        if column is None:
            continue
        for index, value in enumerate(row[1:]):
            if index >= len(dates):
                break
            value = clean_value(value)
            if value:
                data[dates[index]][column] = value

    return [
        [d.strftime("%d.%m.%Y"), d.strftime("%A")]
        + [data[d].get(c, "") for c in COLUMNS[2:]]
        for d in sorted(data, reverse=True)
    ]


def from_long(text):
    """Formato riga-per-data: bonifica valori e ricalcola il giorno, ordine invariato."""
    rows = list(csv.reader(io.StringIO(text)))
    result = []
    for row in rows[1:]:
        if len(row) < 2 or not row[0].strip():
            continue
        try:
            date = datetime.strptime(row[0].strip(), "%d.%m.%Y")
        except ValueError:
            continue
        values = [clean_value(v) for v in row[2:]]
        values += [""] * (len(COLUMNS) - 2 - len(values))
        result.append([date.strftime("%d.%m.%Y"), date.strftime("%A")]
                      + values[: len(COLUMNS) - 2])
    return result


def main():
    check_only = "--check" in sys.argv
    if not DRIVE.is_dir():
        sys.exit(f"Cartella Drive non trovata: {DRIVE}")

    changed = []
    for source_name, dest_name, kind, mapping in FILES:
        source = DRIVE / source_name
        if not source.exists():
            sys.exit(f"Manca il file sorgente: {source}")

        text = source.read_text(encoding="utf-8")
        rows = from_wide(text, mapping) if kind == "wide" else from_long(text)
        if not rows:
            sys.exit(f"Nessun dato letto da {source_name}: interrotto per sicurezza")

        dest = REPO / dest_name
        new = render(rows)
        old = dest.read_text(encoding="utf-8") if dest.exists() else None

        if new == old:
            print(f"  = {dest_name:20} invariato ({len(rows)} date)")
            continue

        changed.append(dest_name)
        latest = rows[0][0]
        print(f"  → {dest_name:20} aggiornato ({len(rows)} date, ultima {latest})")
        if not check_only:
            dest.write_text(new, encoding="utf-8")

    if not changed:
        print("\nNessuna modifica: i file pubblicati sono già allineati al Drive.")
        return 0
    if check_only:
        print(f"\n{len(changed)} file da aggiornare: {', '.join(changed)}")
        return 1
    print(f"\n{len(changed)} file aggiornati. Ora fai commit e push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
