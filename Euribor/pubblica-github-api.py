#!/usr/bin/env python3
"""
Pubblica su GitHub le date nuove dei tassi, via API — senza clone locale.

Pensato per la sessione programmata di Claude: la sua sandbox vede solo questa
cartella (Libor) ma ha la rete. Legge i CSV sorgente qui accanto, scarica lo
stato pubblicato dall'API di GitHub, calcola le sole date mancanti e carica i
file aggiornati (un commit per file). Le righe già pubblicate non vengono mai
riscritte: stessa semantica di sync-from-drive.py nella repo, di cui questo
script è la variante per il sandbox — se si cambia la logica in uno, allineare
anche l'altro.

Autenticazione: variabile d'ambiente GITHUB_TOKEN, oppure file `.github-token`
in questa cartella (token fine-grained limitato alla repo fbacchin/app, con il
solo permesso Contents Read+Write).

Uso:
    python3 pubblica-github-api.py            pubblica le date nuove
    python3 pubblica-github-api.py --check    mostra cosa farebbe, non scrive

L'ultima riga stampata è sempre `ESITO: …` — è quella da riportare nel
riepilogo.
"""

import base64
import csv
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.github.com/repos/fbacchin/app/contents/Euribor/"
BRANCH = "main"

COLUMNS = ["Date", "Week day", "ON", "1W", "1M", "2M", "3M", "6M", "12M"]
HEADER = '"' + '","'.join(COLUMNS) + '"'
NUMERIC_WITH_COMMA = re.compile(r"^-?\d+,\d+$")

# (file sorgente qui, file pubblicato, mappa dei tenori se è nel formato largo)
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


def load_token():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    token_file = HERE / ".github-token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    print("ESITO: FALLITO (token mancante: crea il file .github-token in questa "
          "cartella, oppure esporta GITHUB_TOKEN)")
    sys.exit(1)


TOKEN = load_token()


class ApiError(RuntimeError):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}: {body[:160]}")
        self.code = code


def github(path, method="GET", payload=None):
    # curl invece di urllib: usa i certificati di sistema di macOS, mentre
    # il python3 di serie spesso non ha le CA configurate e fallisce l'SSL.
    command = ["curl", "-sS", "--max-time", "60", "-X", method,
               "-H", f"Authorization: Bearer {TOKEN}",
               "-H", "Accept: application/vnd.github+json",
               "-H", "X-GitHub-Api-Version: 2022-11-28",
               "-w", "\n%{http_code}"]
    stdin = None
    if payload is not None:
        command += ["--data-binary", "@-"]
        stdin = json.dumps(payload).encode()
    # quote() non deve toccare la query string (?ref=main)
    command.append(API + urllib.parse.quote(path, safe="?=&"))
    result = subprocess.run(command, input=stdin, capture_output=True)
    if result.returncode != 0:
        raise ApiError(0, result.stderr.decode(errors="replace"))
    body, _, status = result.stdout.decode().rpartition("\n")
    code = int(status)
    if code >= 400:
        raise ApiError(code, body)
    return json.loads(body)


def clean(value):
    """Virgola decimale -> punto. Lascia intatto tutto il resto."""
    value = value.strip()
    return value.replace(",", ".") if NUMERIC_WITH_COMMA.match(value) else value


def render(date, values):
    """La riga a 9 campi, tutti quotati. values: {colonna: valore}."""
    row = [date.strftime("%d.%m.%Y"), date.strftime("%A")] + [
        values.get(column, "") for column in COLUMNS[2:]
    ]
    buffer = io.StringIO()
    csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
    return buffer.getvalue()


def read_source(path, mapping):
    """Legge un CSV sorgente -> {data: {colonna: valore}}, valori bonificati."""
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
            if date in data:  # date ripetute: tiene la prima
                continue
            values = {}
            for index, column in enumerate(header):
                if 2 <= index < len(row) and column in COLUMNS:
                    if clean(row[index]):
                        values[column] = clean(row[index])
            data[date] = values
    return data


def read_published(text):
    """Righe pubblicate, verbatim -> (lista di (data, riga), insieme di date)."""
    published = []
    dates = set()
    for line in text.split("\n")[1:]:
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
    """Inserisce le righe nuove al posto giusto senza toccare le esistenti."""
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


def publish(name, text, sha, message):
    github(name, method="PUT", payload={
        "message": message,
        "content": base64.b64encode(text.encode()).decode(),
        "sha": sha,
        "branch": BRANCH,
    })


def process(source_name, dest_name, mapping, check_only):
    """Ritorna il numero di date pubblicate per questo file."""
    source = HERE / source_name
    if not source.exists():
        raise RuntimeError(f"manca il file sorgente {source_name}")
    data = read_source(source, mapping)
    if not data:
        raise RuntimeError(f"nessun dato leggibile in {source_name}")

    # fino a 2 tentativi: se un altro commit arriva fra GET e PUT (l'API
    # risponde 409/422 sulla sha), ricarica e riprova una volta
    for attempt in (1, 2):
        info = github(f"{dest_name}?ref={BRANCH}")
        text = base64.b64decode(info["content"]).decode()
        published, existing = read_published(text)
        missing = sorted(set(data) - existing)
        if not missing:
            print(f"  = {dest_name:20} nessuna data nuova")
            return 0

        lines = merge(published, [(d, render(d, data[d])) for d in missing])
        new_text = HEADER + "\n" + "\n".join(lines) + "\n"
        label = ", ".join(d.strftime("%d.%m.%Y") for d in missing[-3:])
        if check_only:
            print(f"  + {dest_name:20} pubblicherebbe {len(missing)} data/e: {label}")
            return len(missing)
        try:
            publish(dest_name, new_text, info["sha"],
                    f"Aggiorna {dest_name} al {missing[-1]:%d.%m.%Y}")
            print(f"  + {dest_name:20} pubblicate {len(missing)} data/e: {label}")
            return len(missing)
        except ApiError as error:
            if error.code in (409, 422) and attempt == 1:
                continue  # sha cambiata nel frattempo: ricarica e riprova
            raise
    return 0


def main():
    check_only = "--check" in sys.argv
    total = 0
    failed = []
    for source_name, dest_name, mapping in FILES:
        try:
            total += process(source_name, dest_name, mapping, check_only)
        except Exception as error:  # un file non deve bloccare gli altri
            failed.append(dest_name)
            print(f"  ! {dest_name:20} ERRORE: {error}")

    print()
    if failed:
        print(f"ESITO: FALLITO ({', '.join(failed)}: vedi errori sopra)")
        return 1
    if total == 0:
        print("ESITO: OK (nessuna data nuova)")
    elif check_only:
        print(f"ESITO: OK ({total} data/e da pubblicare — solo anteprima)")
    else:
        print(f"ESITO: OK (pubblicate {total} data/e)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
