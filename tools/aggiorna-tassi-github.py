#!/usr/bin/env python3
"""
Aggiorna i CSV dei tassi direttamente su GitHub (fbacchin/app, cartella Euribor/).
Nessun file locale né Google Drive: GitHub è l'unica fonte di verità.

Uso:
    aggiorna-tassi-github.py --latest
        stampa l'ultima data pubblicata per ogni file (per sapere cosa scaricare)
    aggiorna-tassi-github.py --data nuovi.json [--check]
        aggiunge le date mancanti. Le righe già pubblicate non vengono riscritte.
    aggiorna-tassi-github.py --put-file LOCALE DEST_NEL_REPO
        crea/aggiorna un file qualsiasi nel repo (es. log/aggiornamento-tassi-….md)

Formato di nuovi.json (date dd.mm.yyyy, valori con il punto, solo colonne usate):
    {"ESTER.csv": {"12.11.2026": {"ON": "2.44300"}},
     "LIBOR-USD.csv": {"12.11.2026": {"1M": "3.95695", "3M": "4.15779",
                                       "6M": "4.32165", "12M": "4.53096"}}}
Nomi file ammessi: ESTER.csv EURIBOR.csv LIBOR-GBP.csv LIBOR-USD-SOFR.csv
                   LIBOR-USD.csv SARON-CHF.csv TONAR-JPY.csv

Token: variabile d'ambiente GITHUB_TOKEN (fine-grained, solo fbacchin/app,
permesso Contents Read+Write).

L'ultima riga stampata è `ESITO: …` da riportare nel riepilogo.
"""
import base64, csv, io, json, os, re, subprocess, sys, urllib.parse
from datetime import datetime

REPO = "https://api.github.com/repos/fbacchin/app/contents/"
BRANCH = "main"
COLUMNS = ["Date", "Week day", "ON", "1W", "1M", "2M", "3M", "6M", "12M"]
HEADER = '"' + '","'.join(COLUMNS) + '"'
FILES = ["ESTER.csv", "EURIBOR.csv", "LIBOR-GBP.csv", "LIBOR-USD-SOFR.csv",
         "LIBOR-USD.csv", "SARON-CHF.csv", "TONAR-JPY.csv"]
COMMA = re.compile(r"^-?\d+,\d+$")


class ApiError(RuntimeError):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}: {body[:160]}")
        self.code = code


def token():
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if not t:
        print("ESITO: FALLITO (variabile GITHUB_TOKEN mancante)")
        sys.exit(1)
    return t


def github(path, method="GET", payload=None):
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method,
           "-H", f"Authorization: Bearer {TOKEN}",
           "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28", "-w", "\n%{http_code}"]
    stdin = None
    if payload is not None:
        cmd += ["--data-binary", "@-"]
        stdin = json.dumps(payload).encode()
    cmd.append(REPO + urllib.parse.quote(path, safe="?=&/"))
    r = subprocess.run(cmd, input=stdin, capture_output=True)
    if r.returncode != 0:
        raise ApiError(0, r.stderr.decode(errors="replace"))
    body, _, status = r.stdout.decode().rpartition("\n")
    code = int(status)
    if code >= 400:
        raise ApiError(code, body)
    return json.loads(body)


def clean(v):
    v = str(v).strip()
    return v.replace(",", ".") if COMMA.match(v) else v


def render(date, values):
    row = [date.strftime("%d.%m.%Y"), date.strftime("%A")] + [
        values.get(c, "") for c in COLUMNS[2:]]
    b = io.StringIO()
    csv.writer(b, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
    return b.getvalue()


def read_published(text):
    pub, dates = [], set()
    for line in text.split("\n")[1:]:
        if not line.strip():
            continue
        raw = next(csv.reader(io.StringIO(line)), [""])[0].strip()
        try:
            d = datetime.strptime(raw, "%d.%m.%Y")
        except ValueError:
            continue
        pub.append((d, line))
        dates.add(d)
    return pub, dates


def merge(pub, new):
    ordered = sorted(new, key=lambda x: x[0], reverse=True)
    out, i = [], 0
    for d, line in pub:
        while i < len(ordered) and ordered[i][0] > d:
            out.append(ordered[i][1]); i += 1
        out.append(line)
    out.extend(l for _, l in ordered[i:])
    return out


def fetch(name):
    info = github(f"Euribor/{name}?ref={BRANCH}")
    return info, base64.b64decode(info["content"]).decode()


def cmd_latest():
    for name in FILES:
        _, text = fetch(name)
        pub, _ = read_published(text)
        print(f"{name:22} ultima data: {pub[0][0]:%d.%m.%Y}" if pub else f"{name:22} vuoto")


def process(name, data, check):
    new = {}
    for ds, vals in data.items():
        d = datetime.strptime(ds, "%d.%m.%Y")
        bad = [c for c in vals if c not in COLUMNS[2:]]
        if bad:
            raise RuntimeError(f"colonne non valide {bad}")
        new[d] = {c: clean(v) for c, v in vals.items() if clean(v)}
    for attempt in (1, 2):
        info, text = fetch(name)
        pub, existing = read_published(text)
        missing = sorted(set(new) - existing)
        if not missing:
            print(f"  = {name:20} nessuna data nuova")
            return 0
        lines = merge(pub, [(d, render(d, new[d])) for d in missing])
        out = HEADER + "\n" + "\n".join(lines) + "\n"
        label = ", ".join(d.strftime("%d.%m.%Y") for d in missing)
        if check:
            print(f"  + {name:20} pubblicherebbe {len(missing)} data/e: {label}")
            return len(missing)
        try:
            github(f"Euribor/{name}", "PUT", {
                "message": f"Aggiorna {name} al {missing[-1]:%d.%m.%Y}",
                "content": base64.b64encode(out.encode()).decode(),
                "sha": info["sha"], "branch": BRANCH})
            print(f"  + {name:20} pubblicate {len(missing)} data/e: {label}")
            return len(missing)
        except ApiError as e:
            if e.code in (409, 422) and attempt == 1:
                continue
            raise
    return 0


def cmd_data(path, check):
    payload = json.load(open(path, encoding="utf-8"))
    total, failed = 0, []
    for name, data in payload.items():
        try:
            if name not in FILES:
                raise RuntimeError("nome file non ammesso")
            total += process(name, data, check)
        except Exception as e:
            failed.append(name)
            print(f"  ! {name:20} ERRORE: {e}")
    print()
    if failed:
        print(f"ESITO: FALLITO ({', '.join(failed)}: vedi errori sopra)")
        return 1
    if total == 0:
        print("ESITO: OK (nessuna data nuova)")
    elif check:
        print(f"ESITO: OK ({total} data/e da pubblicare — solo anteprima)")
    else:
        print(f"ESITO: OK (pubblicate {total} data/e)")
    return 0


def cmd_put_file(local, dest):
    content = open(local, "rb").read()
    sha = None
    try:
        sha = github(f"{dest}?ref={BRANCH}")["sha"]
    except ApiError as e:
        if e.code != 404:
            raise
    payload = {"message": f"Aggiungi {dest}" if not sha else f"Aggiorna {dest}",
               "content": base64.b64encode(content).decode(), "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    github(dest, "PUT", payload)
    print(f"ESITO: OK (pubblicato {dest})")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    TOKEN = token()
    try:
        if "--latest" in a:
            cmd_latest(); sys.exit(0)
        if "--data" in a:
            sys.exit(cmd_data(a[a.index("--data") + 1], "--check" in a))
        if "--put-file" in a:
            i = a.index("--put-file")
            sys.exit(cmd_put_file(a[i + 1], a[i + 2]))
    except ApiError as e:
        print(f"ESITO: FALLITO ({e})"); sys.exit(1)
    print(__doc__); sys.exit(2)
