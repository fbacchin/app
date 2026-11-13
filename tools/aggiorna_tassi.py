#!/usr/bin/env python3
"""
Aggiorna i CSV dei tassi in Euribor/ leggendo global-rates.com.
Pensato per GitHub Actions: lavora sul repo già clonato (cartella corrente),
aggiunge solo le date mancanti, non riscrive mai le righe esistenti,
scrive il riepilogo in log/aggiornamento-tassi-YYYY-MM-DD.md.
Esce con codice 1 se qualche file fallisce (così GitHub segnala l'errore).

Solo libreria standard. Uso:  python3 tools/aggiorna_tassi.py [--dry-run]
"""
import csv, io, re, sys, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.global-rates.com/en/interest-rates/"
COLUMNS = ["Date", "Week day", "ON", "1W", "1M", "2M", "3M", "6M", "12M"]
HEADER = '"' + '","'.join(COLUMNS) + '"'
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# file, pagina, tipo, decimali
SOURCES = [
    ("ESTER.csv", "ester/", "single:ON", 5),
    ("EURIBOR.csv", "euribor/", "euribor", 3),
    ("LIBOR-GBP.csv", "sonia/", "single:ON", 5),
    ("LIBOR-USD-SOFR.csv", "sofr/", "single:ON", 5),
    ("LIBOR-USD.csv", "cme-term-sofr/", "cme", 5),
    ("SARON-CHF.csv", "saron/", "single:ON", 6),
    ("TONAR-JPY.csv", "tonar/", "single:ON", 5),
]
DATE = r"(\d{2})-(\d{2})-(\d{4})"
NUM = r"(-?\d+(?:\.\d+)?)"


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip(): self.out.append(data.strip())


def page_lines(html):
    p = Text(); p.feed(html); return p.out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return page_lines(r.read().decode("utf-8", "replace"))


def to_date(m):
    return datetime(int(m[2]), int(m[0]), int(m[1]))  # mm-dd-yyyy


def check(v):
    if not -3 <= float(v) <= 20:
        raise ValueError(f"valore implausibile {v}")


def parse_single(lines, column):
    """Tabella 'Latest ... rates': coppie data / valore, fino a 'Rate on 1st day'."""
    out, seen = {}, False
    for i, l in enumerate(lines):
        if re.search(r"(?i)^latest .* rates$", l): seen = True; continue
        if seen and re.search(r"(?i)1st day", l): break
        m = re.fullmatch(DATE, l)
        if seen and m and i + 1 < len(lines):
            v = re.fullmatch(NUM + r"\s*%", lines[i + 1])
            if v: out[to_date(m.groups())] = {column: v.group(1)}
    return out


def parse_matrix(lines, header, label, cols):
    """Intestazione con N date, poi una riga per scadenza con N valori ciascuna."""
    start = next((i for i, l in enumerate(lines) if re.fullmatch(header, l, re.I)), None)
    if start is None: return {}
    i = start + 1; dates = []
    while i < len(lines) and (m := re.fullmatch(DATE, lines[i])):
        dates.append(to_date(m.groups())); i += 1
    out = {d: {} for d in dates}
    while i < len(lines):
        k = re.fullmatch(label, lines[i], re.I)
        if k:
            col = cols[k.group(1).lower()]; i += 1
            for d in dates:
                v = re.fullmatch(NUM + r"\s*%", lines[i]) if i < len(lines) else None
                if not v: break
                out[d][col] = v.group(1); i += 1
        else:
            i += 1
    return {d: v for d, v in out.items() if len(v) == len(cols)}


def parse_euribor(lines):
    return parse_matrix(lines, r"Current Euribor interest rates",
                        r"Euribor (1 week|1 month|3 months|6 months|12 months)",
                        {"1 week": "1W", "1 month": "1M", "3 months": "3M",
                         "6 months": "6M", "12 months": "12M"})


def parse_cme(lines):
    return parse_matrix(lines, r"Latest CME Term SOFR rates",
                        r"CME Term SOFR (1 month|3 months|6 months|12 months)",
                        {"1 month": "1M", "3 months": "3M", "6 months": "6M", "12 months": "12M"})


def parse(kind, lines):
    if kind.startswith("single:"): return parse_single(lines, kind.split(":")[1])
    return {"euribor": parse_euribor, "cme": parse_cme}[kind](lines)


def render(date, values, dec):
    row = [date.strftime("%d.%m.%Y"), date.strftime("%A")] + [
        f"{float(values[c]):.{dec}f}" if c in values else "" for c in COLUMNS[2:]]
    b = io.StringIO()
    csv.writer(b, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
    return b.getvalue()


def read_published(text):
    pub, dates = [], set()
    for line in text.split("\n")[1:]:
        if not line.strip(): continue
        raw = next(csv.reader(io.StringIO(line)), [""])[0].strip()
        try: d = datetime.strptime(raw, "%d.%m.%Y")
        except ValueError: continue
        pub.append((d, line)); dates.add(d)
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


def main():
    dry = "--dry-run" in sys.argv
    folder = Path("Euribor")
    now = datetime.now(timezone.utc)
    report, failed = [], []
    for name, page, kind, dec in SOURCES:
        try:
            data = parse(kind, fetch(BASE + page))
            if not data: raise RuntimeError("nessun dato letto dalla pagina (struttura cambiata o sito che blocca)")
            for vals in data.values():
                for v in vals.values(): check(v)
            path = folder / name
            text = path.read_text(encoding="utf-8")
            pub, existing = read_published(text)
            if not pub: raise RuntimeError("file di destinazione vuoto o illeggibile")
            missing = sorted(set(data) - existing)
            if missing:
                lines = merge(pub, [(d, render(d, data[d], dec)) for d in missing])
                if not dry:
                    path.write_text(HEADER + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
                rng = f"{missing[0]:%d.%m.%Y}" + (f" – {missing[-1]:%d.%m.%Y}" if len(missing) > 1 else "")
                report.append((name, len(missing), rng, ""))
            else:
                report.append((name, 0, "—", f"già aggiornato (ultima data {pub[0][0]:%d.%m.%Y})"))
            print(f"{name}: {report[-1][1]} nuove righe {report[-1][2]}")
        except Exception as e:
            failed.append(name); report.append((name, 0, "—", f"ERRORE: {e}"))
            print(f"{name}: ERRORE {e}")
    if not dry:
        status = "FALLITO" if len(failed) == len(SOURCES) else ("PARZIALE" if failed else "SUCCESSO")
        log = [f"# Aggiornamento tassi — {now:%d/%m/%Y}", "",
               f"**Esecuzione:** {now:%d/%m/%Y %H:%M} UTC (GitHub Actions)",
               f"**Stato complessivo: {status}**", "",
               "| File | Nuove righe | Date aggiunte | Note |", "|---|---|---|---|"]
        log += [f"| {n} | {c} | {r} | {note} |" for n, c, r, note in report]
        Path("log").mkdir(exist_ok=True)
        Path(f"log/aggiornamento-tassi-{now:%Y-%m-%d}.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
