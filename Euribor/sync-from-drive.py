#!/usr/bin/env python3
"""
Aggiunge ai CSV pubblicati qui le sole date nuove presenti nei file sorgente
della cartella Libor su Google Drive.

Le righe già presenti non vengono mai rilette, riconvertite o riscritte: restano
byte per byte quelle che sono. Solo le date nuove vengono convertite e inserite.
Questo è voluto: lo storico pubblicato qui è già stato bonificato, mentre quello
su Drive contiene ancora giorni della settimana incoerenti e valori con la
virgola decimale, che non devono tornare indietro.

Alle sole righe nuove si applicano tre trasformazioni:

1. ESTER ed EURIBOR su Drive sono nel formato "largo" (date sulle colonne): la
   data nuova diventa una riga.
2. La virgola decimale diventa punto (in Swift Double() fallirebbe).
3. "Week day" è calcolato dalla data.

I nomi con gli spazi ("LIBOR USD SOFR.csv") qui hanno i trattini, perché negli
URL gli spazi vanno percent-encoded e in Swift URL(string:) con uno spazio
grezzo restituisce nil.

Uso:
    python3 sync-from-drive.py             aggiunge le date nuove
    python3 sync-from-drive.py --check     dice cosa aggiungerebbe, non scrive
    python3 sync-from-drive.py --rebuild   rigenera tutto da Drive da zero.

--rebuild serve solo per riparare, non per l'uso quotidiano: usalo se hai
corretto un valore storico su Drive, perché la modalità normale guarda solo le
date mancanti e non se ne accorgerebbe. Attenzione: riscrive lo storico e nel
farlo elimina le righe con date duplicate (ce ne sono in SARON-CHF, LIBOR-GBP,
LIBOR-USD e LIBOR-USD-SOFR). Controlla sempre il git diff prima di committare.
"""

import csv
import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path

def find_drive_folder():
    """La cartella Libor sul Drive montato. Ricavata a runtime: questa repo è
    pubblica e il percorso completo conterrebbe indirizzi email."""
    override = os.environ.get("LIBOR_DIR")
    if override:
        return Path(override)
    matches = sorted(
        Path.home().glob("Library/CloudStorage/GoogleDrive-*/*/*/Libor")
    )
    return matches[0] if matches else None


DRIVE = find_drive_folder()
REPO = Path(__file__).resolve().parent

COLUMNS = ["Date", "Week day", "ON", "1W", "1M", "2M", "3M", "6M", "12M"]
HEADER = '"' + '","'.join(COLUMNS) + '"'
NUMERIC_WITH_COMMA = re.compile(r"^-?\d+,\d+$")

# (file su Drive, file qui, mappa dei tenori se è nel formato largo)
FILES = [
    ("ESTER.csv", "ESTER.csv", {"ON": "ON"}),
    ("EURIBOR.csv", "EURIBOR.csv",
     {"1w": "1W", "1m": "1M", "3m": "3M", "6m": "6M", "12m": "12M"}),
    ("LIBOR GBP.csv", "LIBOR-GBP.csv", None),
    ("LIBOR USD SOFR.csv", "LIBOR-USD-SOFR.csv", None),
    ("LIBOR USD.csv", "LIBOR-USD.csv", None),
    ("SARON CHF.csv", "SARON-CHF.csv", None),
    ("TONAR JPY.csv", "TONAR-JPY.csv", None),
]


def clean(value):
    """Virgola decimale -> punto. Lascia intatto tutto il resto."""
    value = value.strip()
    return value.replace(",", ".") if NUMERIC_WITH_COMMA.match(value) else value


def render(date, values):
    """Costruisce la riga a 9 campi, tutti quotati. values: {colonna: valore}."""
    row = [date.strftime("%d.%m.%Y"), date.strftime("%A")] + [
        values.get(column, "") for column in COLUMNS[2:]
    ]
    buffer = io.StringIO()
    csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
    return buffer.getvalue()


def read_source(path, mapping):
    """Legge un file su Drive -> {data: {colonna: valore}}, valori già bonificati."""
    rows = [
        r for r in csv.reader(io.StringIO(path.read_text(encoding="utf-8")))
        if any(c.strip() for c in r)
    ]
    if not rows:
        return {}

    data = {}
    if mapping is not None:  # formato largo: le date sono le colonne
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
                if clean(value):
                    data[dates[index]][column] = clean(value)
    else:  # già una riga per data
        header = [c.strip() for c in rows[0]]
        for row in rows[1:]:
            if len(row) < 2 or not row[0].strip():
                continue
            try:
                date = datetime.strptime(row[0].strip(), "%d.%m.%Y")
            except ValueError:
                continue
            if date in data:  # date ripetute nei file storici: tiene la prima
                continue
            values = {}
            for index, column in enumerate(header):
                if index >= 2 and index < len(row) and column in COLUMNS:
                    if clean(row[index]):
                        values[column] = clean(row[index])
            data[date] = values
    return data


def read_published(path):
    """Righe già pubblicate, verbatim -> (lista di (data, riga), insieme di date)."""
    if not path.exists():
        return [], set()
    published = []
    dates = set()
    for line in path.read_text(encoding="utf-8").split("\n")[1:]:
        if not line.strip():
            continue
        raw = next(csv.reader(io.StringIO(line)), [""])[0].strip()
        try:
            date = datetime.strptime(raw, "%d.%m.%Y")
        except ValueError:
            continue
        published.append((date, line))
        dates.add(date)
    return published, dates


def merge(published, new_rows):
    """Inserisce le righe nuove al posto giusto senza riordinare né toccare le altre."""
    ordered = sorted(new_rows, key=lambda item: item[0], reverse=True)
    result = []
    index = 0
    for date, line in published:
        while index < len(ordered) and ordered[index][0] > date:
            result.append(ordered[index][1])
            index += 1
        result.append(line)
    result.extend(line for _, line in ordered[index:])
    return result


def main():
    check_only = "--check" in sys.argv
    rebuild = "--rebuild" in sys.argv
    if DRIVE is None or not DRIVE.is_dir():
        sys.exit("Cartella Libor non trovata sul Drive montato. "
                 "Indica il percorso con la variabile LIBOR_DIR.")

    changed = []
    for source_name, dest_name, mapping in FILES:
        source = DRIVE / source_name
        if not source.exists():
            sys.exit(f"Manca il file sorgente: {source}")
        dest = REPO / dest_name

        data = read_source(source, mapping)
        if not data:
            sys.exit(f"Nessun dato letto da {source_name}: interrotto per sicurezza")

        if rebuild:
            lines = [render(d, data[d]) for d in sorted(data, reverse=True)]
            note = f"rigenerato ({len(lines)} date)"
        else:
            published, existing = read_published(dest)
            missing = sorted(set(data) - existing)
            if not missing:
                print(f"  = {dest_name:20} nessuna data nuova")
                continue
            lines = merge(published, [(d, render(d, data[d])) for d in missing])
            note = (f"{len(missing)} data/e aggiunta/e: "
                    + ", ".join(d.strftime("%d.%m.%Y") for d in missing[-3:]))

        text = HEADER + "\n" + "\n".join(lines) + "\n"
        if dest.exists() and text == dest.read_text(encoding="utf-8"):
            print(f"  = {dest_name:20} invariato")
            continue

        changed.append(dest_name)
        print(f"  + {dest_name:20} {note}")
        if not check_only:
            dest.write_text(text, encoding="utf-8")

    if not changed:
        print("\nNiente da fare: i file pubblicati sono già aggiornati.")
        return 0
    if check_only:
        print(f"\n{len(changed)} file da aggiornare: {', '.join(changed)}")
        return 1
    print(f"\n{len(changed)} file aggiornati. Ora fai commit e push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
