#!/usr/bin/env python3
"""
Controle na de wekelijkse brief (aangeroepen door run_weekbrief.ps1).

Gebruik:
  python scripts/controleer_weekbrief.py --backup MAP --log LOG.json [--afgekeurd AFGEKEURD.csv]

MAP bevat de kopieën van data/ van vóór de run.

voorstellen.csv en runs.csv worden opnieuw opgebouwd als: de versie van vóór de run plus de
nieuwe rijen die de controle doorstaan. Bestaande rijen blijven dus altijd zoals ze waren,
ook als de agent ze heeft gewijzigd of verwijderd. Afgekeurde nieuwe rijen gaan met de reden
naar AFGEKEURD.csv (standaard logs/afgekeurd-JJJJ-MM-DD.csv).
incidenten.csv en wijzigingen.csv moeten ongewijzigd zijn; anders worden ze teruggezet.

Het resultaat komt onder "controle" in LOG.json. Exitcode 1 als er iets is afgekeurd of teruggezet.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KINDS = {"nieuw", "extra_bron", "statuswijziging", "correctie"}

def read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))

def new_rows(old: list[list[str]], new: list[list[str]]) -> tuple[list[list[str]], int]:
    """Rijen in new die niet in old staan (rekening houdend met dubbele), en het aantal
    rijen uit old dat in new ontbreekt (gewijzigd of verwijderd)."""
    left = Counter(tuple(r) for r in old[1:])
    added = []
    for r in new[1:]:
        if left[tuple(r)] > 0:
            left[tuple(r)] -= 1
        elif any(c.strip() for c in r):
            added.append(r)
    return added, sum(left.values())

def rebuild(path: Path, backup: Path, rows: list[list[str]]) -> None:
    """Schrijf de backupversie terug en hang de goedgekeurde nieuwe rijen eraan."""
    shutil.copy2(backup, path)
    if not rows:
        return
    text = backup.read_text(encoding="utf-8-sig")
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(rows)
    sep = "" if text.endswith(("\n", "\r")) or not text else "\r\n"
    with path.open("a", encoding="utf-8", newline="") as f:
        f.write(sep + buf.getvalue())

def check_proposal(r: dict, seen_ids: set[str], incident_ids: set[str]) -> list[str]:
    e = []
    vid = r.get("voorstel_id", "").strip()
    if not vid:
        e.append("voorstel_id ontbreekt")
    elif vid in seen_ids:
        e.append(f"voorstel_id {vid} bestaat al")
    if r.get("beoordeling", "").strip() != "te_beoordelen":
        e.append(f"beoordeling is {r.get('beoordeling', '')!r}, verwacht 'te_beoordelen'")
    for col in ("beoordeeld_door", "verwerkt"):
        if r.get(col, "").strip():
            e.append(f"kolom {col} is ingevuld")
    kind = r.get("soort", "").strip()
    if kind not in KINDS:
        e.append(f"onbekende soort {kind!r}")
    elif kind != "nieuw" and r.get("incident_id", "").strip() not in incident_ids:
        e.append(f"incident_id {r.get('incident_id', '')!r} staat niet in incidenten.csv")
    if not r.get("bron_url", "").startswith("http"):
        e.append("bron_url ontbreekt")
    if not r.get("citaat", "").strip():
        e.append("citaat ontbreekt")
    return e

def process(name: str, backup_dir: Path, check, result: dict, rejected: list[dict]) -> None:
    old = read_rows(backup_dir / name)
    new = read_rows(DATA / name)
    header = old[0] if old else (new[0] if new else [])
    if new and old and new[0] != old[0]:
        result["fouten"].append(f"{name}: kolommen gewijzigd; alle wijzigingen teruggedraaid")
        rebuild(DATA / name, backup_dir / name, [])
        result["teruggezet"].append(name)
        return
    added, missing = new_rows(old, new)
    if missing:
        result["fouten"].append(f"{name}: {missing} bestaande rij(en) gewijzigd of verwijderd; teruggezet")
    good = []
    for r in added:
        if len(r) != len(header):
            reasons = [f"{len(r)} kolommen in plaats van {len(header)}"]
            d = dict(zip(header, r))
        else:
            d = dict(zip(header, r))
            reasons = check(d)
        if reasons:
            rejected.append({"bestand": name, "reden": "; ".join(reasons), **d})
        else:
            good.append(r)
    rebuild(DATA / name, backup_dir / name, good)
    result[f"nieuw_{name.split('.')[0]}"] = len(good)
    result[f"afgekeurd_{name.split('.')[0]}"] = len(added) - len(good)
    if missing:
        result["teruggezet"].append(name)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True, type=Path)
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--afgekeurd", type=Path)
    args = ap.parse_args()
    afgekeurd = args.afgekeurd or ROOT / "logs" / f"afgekeurd-{dt.date.today().isoformat()}.csv"

    result = {"tijd": dt.datetime.now().isoformat(timespec="seconds"), "fouten": [], "teruggezet": []}
    rejected: list[dict] = []

    old_props = read_rows(args.backup / "voorstellen.csv")
    seen = {r[0] for r in old_props[1:] if r}
    incident_ids = {r["id"] for r in csv.DictReader(io.StringIO(
        (args.backup / "incidenten.csv").read_text(encoding="utf-8-sig")))}

    def check_prop(d: dict) -> list[str]:
        errs = check_proposal(d, seen, incident_ids)
        seen.add(d.get("voorstel_id", "").strip())
        return errs

    def check_run(d: dict) -> list[str]:
        errs = []
        if not d.get("run_datum", "").strip():
            errs.append("run_datum ontbreekt")
        if "inbox" in d and not d["inbox"].strip().isdigit():
            errs.append(f"inbox moet een aantal zijn, niet {d['inbox']!r}")
        for col in ("goedgekeurd", "afgewezen"):
            if d.get(col, "").strip():
                errs.append(f"kolom {col} is ingevuld (dat doet verwerk)")
        return errs

    process("voorstellen.csv", args.backup, check_prop, result, rejected)
    process("runs.csv", args.backup, check_run, result, rejected)

    # bestanden die de brief nooit mag aanraken
    for name in ("incidenten.csv", "wijzigingen.csv"):
        if (args.backup / name).read_bytes() != (DATA / name).read_bytes():
            shutil.copy2(args.backup / name, DATA / name)
            result["fouten"].append(f"{name}: bestand was gewijzigd; teruggezet")
            result["teruggezet"].append(name)

    if rejected:
        afgekeurd.parent.mkdir(parents=True, exist_ok=True)
        cols = ["bestand", "reden"] + [c for c in dict.fromkeys(k for r in rejected for k in r) if c not in ("bestand", "reden")]
        with afgekeurd.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rejected)
        result["afgekeurd_bestand"] = str(afgekeurd)
        result["afgekeurde_rijen"] = [f"{r.get('voorstel_id') or r.get('run_datum') or '?'}: {r['reden']}" for r in rejected]
    result["ok"] = not result["fouten"] and not rejected

    raw = args.log.read_text(encoding="utf-8-sig") if args.log.exists() else ""
    try:
        log = json.loads(raw)
        if not isinstance(log, dict):
            log = {"uitvoer": log}
    except json.JSONDecodeError:
        log = {"ruwe_uitvoer": raw}
    log["controle"] = result
    args.log.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Controle: {result.get('nieuw_voorstellen', 0)} voorstel(len) toegevoegd, "
          f"{result.get('afgekeurd_voorstellen', 0)} afgekeurd; "
          f"{result.get('nieuw_runs', 0)} run-regel(s) toegevoegd, {result.get('afgekeurd_runs', 0)} afgekeurd.")
    for f in result["fouten"]:
        print("  - " + f)
    for r in result.get("afgekeurde_rijen", []):
        print("  - afgekeurd " + r)
    if rejected:
        print(f"  Afgekeurde rijen staan in {afgekeurd}")
    return 0 if result["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
