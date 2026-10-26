#!/usr/bin/env python3
"""
Incidentatlas – wachtrijen en status per dossier (protocol 2.1, 5d–5f en 5k).

Gebruik:
  python scripts/dossiers.py bijwerken
      Berekent per dossier de wachtrij (verrijken / volglijst / afgerond / slapend), of de bronnen
      voldoende zijn en de datum van de laatste ontwikkeling, en schrijft data/dossierstatus.csv.
      Eerder vastgelegde zoekdata blijven behouden.

  python scripts/dossiers.py wachtrij --soort volglijst|verrijken --uit LIJST.csv [--max 15]
      Werkt eerst bij en zet dan de dossiers van die wachtrij klaar, het langst niet gezocht eerst.
      Print het aantal.

  python scripts/dossiers.py gezocht --lijst LIJST.csv --door volglijst|verrijken|verdieping|dossier --prefix PREFIX
      Na een run: zet voor elk dossier in LIJST.csv `laatst_gezocht` op vandaag en `laatste_uitkomst`
      op het aantal geaccepteerde voorstellen van deze run (voorstel_id begint met PREFIX).

Een dossier is een zaak in data/incidenten.csv of een nieuwe zaak in data/voorstellen.csv die nog
op goedkeuring wacht (id `voorstel:<voorstel_id>`).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATUS_FILE = DATA / "dossierstatus.csv"
COLUMNS = ["incident_id", "titel", "fase", "wachtrij", "bronnen_voldoende", "bronniveaus",
           "laatst_bijgewerkt", "laatst_gezocht", "laatst_gezocht_door", "laatste_uitkomst"]
OPEN = {"signaal", "beschuldigd", "aangeklaagd"}
SLAPEND_NA = 365   # dagen zonder ontwikkeling
SLAPEND_CHECK = 90  # slapende dossiers één keer per kwartaal nog nalopen

def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [{k: (v or "") for k, v in r.items() if k} for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))]

def write(path: Path, rows: list[dict], cols: list[str]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)

def as_date(s: str) -> dt.date | None:
    s = (s or "").strip()
    for n, fmt in ((10, "%Y-%m-%d"), (7, "%Y-%m"), (4, "%Y")):
        try:
            return dt.datetime.strptime(s[:n], fmt).date()
        except ValueError:
            continue
    return None

def sufficient(fase: str, levels: list[str]) -> bool:
    """De bronnenregel (protocol 4): bewezen één A of twee B; de andere fasen één A of B."""
    if fase == "bewezen":
        return "A" in levels or levels.count("B") >= 2
    return "A" in levels or "B" in levels

def dossiers() -> list[dict]:
    incidents = read(DATA / "incidenten.csv")
    devs = read(DATA / "ontwikkelingen.csv")
    props = read(DATA / "voorstellen.csv")
    out = []
    for r in incidents:
        last = max([r["datum"]] + [d["datum"] for d in devs if d["incident_id"] == r["id"]])
        levels = [r[f"bron_{i}_niveau"] for i in (1, 2, 3) if r[f"bron_{i}_url"]]
        out.append({"incident_id": r["id"], "titel": r["titel"], "fase": atlas.phase(r["status"]), "land": r["land"],
                    "categorie": r["categorie"], "datum": r["datum"], "levels": levels, "laatst_bijgewerkt": last})
    for p in props:
        if p["soort"] != "nieuw" or p["verwerkt"].startswith("ja") or p["beoordeling"] == "afgewezen":
            continue
        key = f"voorstel:{p['voorstel_id']}"
        kids = [q for q in props if q["incident_id"] == key and q["beoordeling"] != "afgewezen"]
        fase = atlas.phase(p["status"])
        for q in sorted(kids, key=lambda q: q["datum"]):
            f = atlas.phase(q["status"])
            if f == "ontkracht" or (f in atlas.PHASE_RANK and fase in atlas.PHASE_RANK and atlas.PHASE_RANK[f] > atlas.PHASE_RANK[fase]):
                fase = f
        out.append({"incident_id": key, "titel": p["titel"], "fase": fase, "land": p["land"], "categorie": p["categorie"],
                    "datum": p["datum"], "levels": [p["bron_niveau"]] + [q["bron_niveau"] for q in kids],
                    "laatst_bijgewerkt": max([p["datum"]] + [q["datum"] for q in kids])})
    return out

def queue_of(d: dict, searched: str, today: dt.date) -> str:
    ok = sufficient(d["fase"], d["levels"])
    if not ok:
        return "verrijken"
    if d["fase"] not in OPEN:
        return "afgerond"
    last = as_date(d["laatst_bijgewerkt"])
    if last and (today - last).days > SLAPEND_NA:
        return "slapend"
    return "volglijst"

def cmd_update(_args=None) -> list[dict]:
    today = dt.date.today()
    old = {r["incident_id"]: r for r in read(STATUS_FILE)}
    rows = []
    for d in dossiers():
        o = old.get(d["incident_id"], {})
        rows.append({"incident_id": d["incident_id"], "titel": d["titel"], "fase": d["fase"],
                     "wachtrij": queue_of(d, o.get("laatst_gezocht", ""), today),
                     "bronnen_voldoende": "ja" if sufficient(d["fase"], d["levels"]) else "nee",
                     "bronniveaus": "+".join(d["levels"]), "laatst_bijgewerkt": d["laatst_bijgewerkt"],
                     "laatst_gezocht": o.get("laatst_gezocht", ""), "laatst_gezocht_door": o.get("laatst_gezocht_door", ""),
                     "laatste_uitkomst": o.get("laatste_uitkomst", ""),
                     "_d": d})
    write(STATUS_FILE, rows, COLUMNS)
    if _args is not None:
        from collections import Counter
        c = Counter(r["wachtrij"] for r in rows)
        print(f"{len(rows)} dossiers: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    return rows

def cmd_queue(args) -> int:
    today = dt.date.today()
    rows = cmd_update()
    if args.soort == "volglijst":
        sel = [r for r in rows if r["wachtrij"] == "volglijst"]
        # slapende dossiers één keer per kwartaal meenemen
        for r in rows:
            g = as_date(r["laatst_gezocht"])
            if r["wachtrij"] == "slapend" and (not g or (today - g).days >= SLAPEND_CHECK):
                sel.append(r)
    else:
        sel = [r for r in rows if r["wachtrij"] == "verrijken"]
    sel.sort(key=lambda r: (r["laatst_gezocht"] or "0000", r["laatst_bijgewerkt"]))
    sel = sel[: args.max]
    args.uit.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "fase", "titel", "land", "categorie", "datum", "laatste_ontwikkeling", "laatst_gezocht", "bronniveaus", "wachtrij"]
    write(args.uit, [{"id": r["incident_id"], "fase": r["fase"], "titel": r["titel"], "land": r["_d"]["land"],
                      "categorie": r["_d"]["categorie"], "datum": r["_d"]["datum"], "laatste_ontwikkeling": r["laatst_bijgewerkt"],
                      "laatst_gezocht": r["laatst_gezocht"], "bronniveaus": r["bronniveaus"], "wachtrij": r["wachtrij"]} for r in sel], cols)
    print(len(sel))
    return 0

def cmd_searched(args) -> int:
    today = dt.date.today().isoformat()
    ids = [r["id"] for r in read(args.lijst)] if args.lijst else []
    props = read(DATA / "voorstellen.csv")
    rows = {r["incident_id"]: r for r in read(STATUS_FILE)}
    for i in ids:
        n = sum(1 for p in props if p["incident_id"] == i and p["voorstel_id"].startswith(args.prefix))
        r = rows.setdefault(i, {"incident_id": i})
        r.update(laatst_gezocht=today, laatst_gezocht_door=args.door,
                 laatste_uitkomst="niets nieuws" if not n else f"{n} voorstel{'len' if n > 1 else ''}")
    write(STATUS_FILE, list(rows.values()), COLUMNS)
    cmd_update()
    print(f"{len(ids)} dossier(s) als nagezocht vastgelegd")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bijwerken").set_defaults(fn=lambda a: (cmd_update(a), 0)[1])
    q = sub.add_parser("wachtrij"); q.add_argument("--soort", required=True, choices=["volglijst", "verrijken"])
    q.add_argument("--uit", required=True, type=Path); q.add_argument("--max", type=int, default=15); q.set_defaults(fn=cmd_queue)
    g = sub.add_parser("gezocht"); g.add_argument("--lijst", type=Path); g.add_argument("--door", required=True)
    g.add_argument("--prefix", required=True); g.set_defaults(fn=cmd_searched)
    args = ap.parse_args()
    return args.fn(args)

if __name__ == "__main__":
    sys.exit(main())
