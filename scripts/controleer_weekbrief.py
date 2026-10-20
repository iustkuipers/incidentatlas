#!/usr/bin/env python3
"""
Controle na de wekelijkse brief (aangeroepen door run_weekbrief.ps1).

Gebruik:
  python scripts/controleer_weekbrief.py --backup MAP --log LOG.json

MAP bevat de kopieën van data/ van vóór de run. Gecontroleerd wordt:
  - voorstellen.csv: alleen rijen toegevoegd, elke nieuwe rij beoordeling=te_beoordelen
    (en beoordeeld_door en verwerkt leeg);
  - runs.csv: alleen rijen toegevoegd;
  - incidenten.csv en wijzigingen.csv: ongewijzigd.
Faalt een controle, dan wordt dat bestand teruggezet uit MAP. Het resultaat komt onder
"controle" in LOG.json. Exitcode 1 als er iets is teruggezet.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def rows_of(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))

def only_appended(old: Path, new: Path) -> tuple[list[str], list[dict]]:
    """Geeft (fouten, nieuwe rijen als dict)."""
    a, b = rows_of(old), rows_of(new)
    if not b:
        return ["bestand is leeg of ontbreekt"], []
    if a and a[0] != b[0]:
        return ["kolommen zijn gewijzigd"], []
    if len(b) < len(a):
        return [f"{len(a) - len(b)} rij(en) verwijderd"], []
    changed = [i for i in range(1, len(a)) if a[i] != b[i]]
    if changed:
        return [f"bestaande rij(en) gewijzigd: regel {', '.join(str(i + 1) for i in changed[:10])}"], []
    header = b[0]
    added = [dict(zip(header, r)) for r in b[len(a):]]
    bad_len = [i + len(a) + 1 for i, r in enumerate(b[len(a):]) if len(r) != len(header)]
    if bad_len:
        return [f"nieuwe rij(en) met verkeerd aantal kolommen: regel {', '.join(map(str, bad_len))}"], added
    return [], added

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True, type=Path)
    ap.add_argument("--log", required=True, type=Path)
    args = ap.parse_args()

    result = {"tijd": dt.datetime.now().isoformat(timespec="seconds"), "ok": True,
              "nieuwe_voorstellen": 0, "nieuwe_runs": 0, "fouten": [], "teruggezet": []}

    def restore(name: str, reasons: list[str]) -> None:
        result["ok"] = False
        result["fouten"] += [f"{name}: {r}" for r in reasons]
        shutil.copy2(args.backup / name, DATA / name)
        result["teruggezet"].append(name)

    # voorstellen.csv
    errs, added = only_appended(args.backup / "voorstellen.csv", DATA / "voorstellen.csv")
    for i, r in enumerate(added, 1):
        rid = r.get("voorstel_id") or f"nieuwe rij {i}"
        if r.get("beoordeling", "").strip() != "te_beoordelen":
            errs.append(f"{rid}: beoordeling is {r.get('beoordeling')!r}, verwacht 'te_beoordelen'")
        for col in ("beoordeeld_door", "verwerkt"):
            if r.get(col, "").strip():
                errs.append(f"{rid}: kolom {col} is ingevuld")
    if errs:
        restore("voorstellen.csv", errs)
    else:
        result["nieuwe_voorstellen"] = len(added)

    # runs.csv
    errs, added = only_appended(args.backup / "runs.csv", DATA / "runs.csv")
    if errs:
        restore("runs.csv", errs)
    else:
        result["nieuwe_runs"] = len(added)

    # bestanden die de brief nooit mag aanraken
    for name in ("incidenten.csv", "wijzigingen.csv"):
        if (args.backup / name).read_bytes() != (DATA / name).read_bytes():
            restore(name, ["bestand is gewijzigd, dat mag de brief niet"])

    # resultaat in de JSON-log zetten
    raw = args.log.read_text(encoding="utf-8-sig") if args.log.exists() else ""
    try:
        log = json.loads(raw)
        if not isinstance(log, dict):
            log = {"uitvoer": log}
    except json.JSONDecodeError:
        log = {"ruwe_uitvoer": raw}
    log["controle"] = result
    args.log.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    if result["ok"]:
        print(f"Controle ok: {result['nieuwe_voorstellen']} nieuwe voorstel(len), {result['nieuwe_runs']} run-regel(s).")
        return 0
    print("Controle MISLUKT, teruggezet: " + ", ".join(result["teruggezet"]))
    for f in result["fouten"]:
        print("  - " + f)
    return 1

if __name__ == "__main__":
    sys.exit(main())
