#!/usr/bin/env python3
"""
Klaarzetten en controleren van de AI-runs (protocol 2.0; aangeroepen door run_weekbrief.ps1).

Gebruik:
  python scripts/controleer_weekbrief.py klaarzetten --uit LIJST.csv
      Schrijft alle berichten uit data/inbox.csv die nog niet in data/beoordelingen.csv
      staan naar LIJST.csv (url, titel, datum, feed). Print het aantal.

  python scripts/controleer_weekbrief.py zaken --uit ZAKEN.csv [--open] [--max 15]
      Schrijft de zaken (incidenten plus nog niet verwerkte nieuwe zaken uit de voorstellen)
      naar ZAKEN.csv, met id, fase, titel, land, categorie, laatste ontwikkeling. Met --open
      alleen signaal/beschuldigd/aangeklaagd, langst niet bijgewerkt eerst. Print het aantal.

  python scripts/controleer_weekbrief.py controleer --modus week|archief|verdieping|volglijst
         --backup MAP --log LOG.json [--lijst LIJST.csv] [--zaak ID] [--afgekeurd AFGEKEURD.csv]
      MAP bevat data/ van vóór de run. Daarna:
      - data/beoordelingen.csv en data/voorstellen.csv worden opnieuw opgebouwd als de versie van
        vóór de run plus de nieuwe regels die de controle doorstaan;
      - week/archief: elke beoordeling hoort bij de lijst (week) of op nos.nl/het register (archief), één per
        bericht, geldig besluit; bij nieuwe_zaak/ontwikkeling een geldige fase, categorie en een
        citaat dat echt op de pagina staat, en een bijbehorend voorstel;
      - verdieping/volglijst: alleen voorstellen (ontwikkelingen) bij bestaande zaken;
      - bronnen: nos.nl, en bij verdieping ook domeinen uit data/bronnenregister.csv met lijst
        'voorkeur' of 'vertrouwd';
      - een signaal alleen in de categorieën spionage/sabotage/cyber/desinformatie_verkiezingen,
        met doelwit in Europa of een NAVO-land en een datum vanaf 2014;
      - data/incidenten.csv, data/ontwikkelingen.csv en data/wijzigingen.csv moeten ongewijzigd zijn;
        data/inbox.csv mag alleen groeien;
      - week: één regel in data/runs.csv met de tellingen.
      Afgekeurde regels gaan met reden naar AFGEKEURD.csv; het resultaat staat onder "controle" in
      LOG.json. Exitcode 1 als er iets is afgekeurd, ontbreekt of is teruggezet.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import shutil
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas  # noqa: E402  (citaatcontrole, fasen en vaste lijsten)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BESLUITEN = {"niet_relevant", "achtergrond", "nieuwe_zaak", "ontwikkeling"}
FASEN = atlas.STATUSES
REVIEW_COLUMNS = ["url", "titel", "datum", "besluit", "reden", "categorie", "land", "status", "citaat", "run_datum", "incident_id"]
NATO_OUTSIDE_EUROPE = {"Verenigde Staten", "Canada", "Turkije"}
START_YEAR = 2014

def read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))

def read_dicts(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))) if path.exists() else []

def new_rows(old: list[list[str]], new: list[list[str]]) -> tuple[list[list[str]], int]:
    left = Counter(tuple(r) for r in old[1:])
    added = []
    for r in new[1:]:
        if left[tuple(r)] > 0:
            left[tuple(r)] -= 1
        elif any(c.strip() for c in r):
            added.append(r)
    return added, sum(left.values())

def rebuild(path: Path, backup: Path, rows: list[list[str]]) -> None:
    shutil.copy2(backup, path)
    if not rows:
        return
    text = backup.read_text(encoding="utf-8-sig")
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(rows)
    with path.open("a", encoding="utf-8", newline="") as f:
        f.write(("" if text.endswith(("\n", "\r")) or not text else "\r\n") + buf.getvalue())

def host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")

def on_nos(url: str) -> bool:
    h = host(url)
    return h == "nos.nl" or h.endswith(".nos.nl")

def register_domains() -> set[str]:
    return {r["domein"].lower().removeprefix("www.") for r in read_dicts(DATA / "bronnenregister.csv")
            if r.get("lijst") in ("voorkeur", "vertrouwd") and r.get("domein")}

def searchable(url: str) -> bool:
    """Archief: elk geopend artikel van nos.nl of een domein uit het register (behalve niet_gebruiken)."""
    h = host(url)
    return on_nos(url) or any(h == d or h.endswith("." + d) for d in
        {r["domein"].lower().removeprefix("www.") for r in read_dicts(DATA / "bronnenregister.csv")
         if r.get("domein") and r.get("lijst") != "niet_gebruiken"})

def allowed_source(url: str, modus: str, reg: set[str]) -> bool:
    """Bewijs komt alleen van nos.nl of van een domein uit het bronnenregister (voorkeur/vertrouwd)."""
    if on_nos(url):
        return True
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in reg)

def target_ok(land: str, regio: str) -> bool:
    return regio == "Europa" or land in NATO_OUTSIDE_EUROPE

def precise(v: str) -> bool:
    return bool(re.fullmatch(r"-?\d+\.\d{2,}", (v or "").strip()))

_quote_cache: dict[tuple[str, str], str | None] = {}
def quote_error(url: str, quote: str) -> str | None:
    key = (url, quote)
    if key not in _quote_cache:
        _quote_cache[key] = atlas.check_link_and_quote({"bron_url": url, "citaat": quote})
    return _quote_cache[key]

# ------------------------------------------------------------- klaarzetten
def cmd_prepare(args) -> int:
    done = {r["url"] for r in read_dicts(DATA / "beoordelingen.csv")}
    todo, seen = [], set()
    for r in read_dicts(DATA / "inbox.csv"):
        if r["url"] in done or r["url"] in seen:
            continue
        seen.add(r["url"])
        todo.append({k: r.get(k, "") for k in ("url", "titel", "datum", "feed")})
    args.uit.parent.mkdir(parents=True, exist_ok=True)
    with args.uit.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url", "titel", "datum", "feed"], lineterminator="\r\n")
        w.writeheader()
        w.writerows(todo)
    print(len(todo))
    return 0

def cmd_cases(args) -> int:
    """Overzicht van zaken voor de AI: bestaande incidenten plus open nieuwe zaken in voorstellen."""
    devs = read_dicts(DATA / "ontwikkelingen.csv")
    last = {}
    for d in devs:
        if d["datum"] > last.get(d["incident_id"], ""):
            last[d["incident_id"]] = d["datum"]
    rows = []
    for r in read_dicts(DATA / "incidenten.csv"):
        f = atlas.phase(r["status"])
        rows.append({"id": r["id"], "fase": f, "titel": r["titel"], "land": r["land"], "categorie": r["categorie"],
                     "datum": r["datum"], "laatste_ontwikkeling": last.get(r["id"], r["datum"])})
    for p in read_dicts(DATA / "voorstellen.csv"):
        if p["soort"] == "nieuw" and not p["verwerkt"].startswith("ja") and p["beoordeling"] != "afgewezen":
            rows.append({"id": f"voorstel:{p['voorstel_id']}", "fase": atlas.phase(p["status"]), "titel": p["titel"],
                         "land": p["land"], "categorie": p["categorie"], "datum": p["datum"], "laatste_ontwikkeling": p["datum"]})
    if args.open:
        rows = [r for r in rows if r["fase"] in ("signaal", "beschuldigd", "aangeklaagd")]
        rows.sort(key=lambda r: r["laatste_ontwikkeling"])
        rows = rows[: args.max]
    args.uit.parent.mkdir(parents=True, exist_ok=True)
    with args.uit.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "fase", "titel", "land", "categorie", "datum", "laatste_ontwikkeling"], lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows))
    return 0

# ------------------------------------------------------------- controleren
def same_place(a: tuple[str, str], b: tuple[str, str]) -> bool:
    try:
        return abs(float(a[0]) - float(b[0])) < 1e-4 and abs(float(a[1]) - float(b[1])) < 1e-4
    except ValueError:
        return False

def check_proposal_fields(d: dict, modus: str, reg: set[str], case_ids: set[str], places: dict | None = None) -> list[str]:
    e = []
    if d.get("beoordeling", "").strip() != "te_beoordelen":
        e.append(f"beoordeling is {d.get('beoordeling', '')!r}, verwacht 'te_beoordelen'")
    for col in ("beoordeeld_door", "verwerkt"):
        if d.get(col, "").strip():
            e.append(f"kolom {col} is ingevuld")
    kind = d.get("soort", "").strip()
    if kind not in ("nieuw", "ontwikkeling", "extra_bron"):
        e.append(f"soort moet nieuw, ontwikkeling of extra_bron zijn, niet {kind!r}")
    if modus in ("verdieping", "volglijst", "verrijken") and kind == "nieuw":
        e.append(f"bij {modus} alleen ontwikkelingen of extra bronnen bij bestaande zaken")
    if modus == "dossier" and kind == "nieuw" and not d.get("voorstel_id", "").startswith("dossier-"):
        e.append("voorstel_id van de nieuwe zaak moet met 'dossier-' beginnen")
    if kind != "nieuw" and d.get("incident_id", "").strip() not in case_ids:
        e.append(f"zaak {d.get('incident_id', '')!r} bestaat niet")
    # de plek van een zaak is die van het oorspronkelijke voorval; een ontwikkeling verandert hem niet
    place = (places or {}).get(d.get("incident_id", "").strip())
    if kind != "nieuw" and place and (d.get("lat", "").strip() or d.get("lon", "").strip()) and not same_place((d.get("lat", ""), d.get("lon", "")), place):
        e.append(f"coördinaten wijken af van de zaak ({place[0]}, {place[1]}): de plek blijft die van het oorspronkelijke voorval")
    fase = atlas.phase(d.get("status", ""))
    if fase not in FASEN:
        e.append(f"onbekende fase {d.get('status', '')!r}")
    if d.get("categorie", "").strip() not in atlas.CATEGORIES:
        e.append(f"onbekende categorie {d.get('categorie', '')!r}")
    if kind == "nieuw":
        if d.get("regio", "").strip() not in atlas.REGIONS:
            e.append(f"onbekende regio {d.get('regio', '')!r}")
        if not (precise(d.get("lat", "")) and precise(d.get("lon", ""))):
            e.append("coördinaten te grof: minstens 2 decimalen (liefst 4), zo exact mogelijk")
        if fase == "signaal":
            if d.get("categorie") not in atlas.SIGNAL_CATEGORIES:
                e.append(f"categorie {d.get('categorie')!r} kan niet als signaal beginnen, pas vanaf beschuldigd")
            if not target_ok(d.get("land", ""), d.get("regio", "")):
                e.append("signaal alleen bij een doelwit in Europa of een NAVO-land")
            if d.get("datum", "")[:4] < str(START_YEAR):
                e.append(f"signalen alleen vanaf {START_YEAR}")
    if not allowed_source(d.get("bron_url", ""), modus, reg):
        e.append("bron staat niet op nos.nl of in het bronnenregister (voorkeur/vertrouwd)")
    q = d.get("citaat", "").strip()
    if not q:
        e.append("citaat ontbreekt")
    elif len(q.split()) > 30:
        e.append("citaat is langer dan 30 woorden")
    elif not e:
        qe = quote_error(d["bron_url"], q)
        if qe:
            e.append(qe)
    return e

def cmd_check(args) -> int:
    modus = args.modus
    today = dt.date.today().isoformat()
    afgekeurd = args.afgekeurd or ROOT / "logs" / f"afgekeurd-{modus}-{today}.csv"
    result = {"tijd": dt.datetime.now().isoformat(timespec="seconds"), "modus": modus, "fouten": [], "teruggezet": []}
    rejected: list[dict] = []
    lijst = {r["url"]: r for r in read_dicts(args.lijst)} if args.lijst else {}
    reg = register_domains()

    # zaken waar een ontwikkeling bij mag horen: incidenten + open nieuwe zaken (ook uit deze run)
    case_ids = {r["id"] for r in read_dicts(args.backup / "incidenten.csv")}
    case_ids |= {f"voorstel:{p['voorstel_id']}" for p in read_dicts(args.backup / "voorstellen.csv")
                 if p["soort"] == "nieuw" and not p["verwerkt"].startswith("ja") and p["beoordeling"] != "afgewezen"}
    if modus == "verdieping" and args.zaak and args.zaak not in case_ids:
        result["fouten"].append(f"zaak {args.zaak} bestaat niet")

    # --- voorstellen eerst (nieuwe zaken uit deze run tellen dan mee als case_ids)
    name = "voorstellen.csv"
    old, new = read_rows(args.backup / name), read_rows(DATA / name)
    header = old[0] if old else atlas.PROPOSAL_COLUMNS
    added, missing = ([], 0) if (new and old and new[0] != old[0]) else new_rows(old, new)
    if new and old and new[0] != old[0]:
        result["fouten"].append(f"{name}: kolommen gewijzigd; alle wijzigingen teruggedraaid")
    if missing:
        result["fouten"].append(f"{name}: {missing} bestaande regel(s) gewijzigd of verwijderd; teruggezet")
        result["teruggezet"].append(name)
    ids_before = {r[0] for r in old[1:] if r}
    prop_header = header
    cand = [dict(zip(header, r)) for r in added]
    places = {r["id"]: (r["lat"], r["lon"]) for r in read_dicts(args.backup / "incidenten.csv")}
    for q in read_dicts(args.backup / "voorstellen.csv") + cand:
        if q.get("soort") == "nieuw":
            places[f"voorstel:{q.get('voorstel_id', '')}"] = (q.get("lat", ""), q.get("lon", ""))
    run_new = {f"voorstel:{d.get('voorstel_id', '')}" for d in cand if d.get("soort") == "nieuw"}
    if modus == "dossier" and len(run_new) > 1:
        result["fouten"].append(f"dossier maakt {len(run_new)} nieuwe zaken aan; er mag er maar één zijn")
    good_props, ids, prop_urls = [], set(), {}
    for r, d in zip(added, cand):
        e = []
        if len(r) != len(header):
            e.append(f"{len(r)} kolommen in plaats van {len(header)}")
        vid = d.get("voorstel_id", "").strip()
        if not vid or vid in ids_before or vid in ids:
            e.append("voorstel_id ontbreekt of bestaat al")
        if modus == "verdieping" and args.zaak and d.get("incident_id") != args.zaak:
            e.append(f"verdieping is voor zaak {args.zaak}, niet {d.get('incident_id')!r}")
        e += check_proposal_fields(d, modus, reg, case_ids | run_new, places)
        ids.add(vid)
        if e:
            rejected.append({"bestand": name, "afkeurreden": "; ".join(e), **d})
        else:
            good_props.append(r)
            prop_urls.setdefault(d["bron_url"], []).append(d)
    result["voorstellen"] = len(good_props)
    result["afgekeurd_voorstellen"] = len(added) - len(good_props)

    # --- beoordelingen (alleen week en archief)
    name = "beoordelingen.csv"
    old, new = read_rows(args.backup / name), read_rows(DATA / name)
    header = old[0] if old else REVIEW_COLUMNS
    good, counts = [], Counter()
    if modus in ("week", "archief"):
        added, missing = ([], 0) if (new and old and new[0] != old[0]) else new_rows(old, new)
        if new and old and new[0] != old[0]:
            result["fouten"].append(f"{name}: kolommen gewijzigd; alle wijzigingen teruggedraaid")
        if missing:
            result["fouten"].append(f"{name}: {missing} bestaande regel(s) gewijzigd of verwijderd; teruggezet")
            result["teruggezet"].append(name)
        done_before = {r[0] for r in old[1:] if r}
        seen = set()
        for i, r in enumerate(added):
            d = dict(zip(header, r))
            e = []
            if len(r) != len(header):
                e.append(f"{len(r)} kolommen in plaats van {len(header)}")
            url = d.get("url", "").strip()
            # titel en datum mag de AI leeg laten: hier invullen uit de lijst (week) zodat regels kort blijven
            if url in lijst and len(r) == len(header):
                for k in ("titel", "datum"):
                    if not d.get(k, "").strip():
                        d[k] = lijst[url].get(k, "")
                r = added[i] = [d.get(c, "") for c in header]
            if not url:
                e.append("url ontbreekt")
            elif url in done_before:
                e.append("bericht was al beoordeeld")
            elif url in seen:
                e.append("bericht twee keer beoordeeld in deze run")
            if modus == "archief":
                if not searchable(url):
                    e.append("url staat niet op nos.nl of in het bronnenregister")
                if d.get("run_datum", "").strip() != "archief":
                    e.append("run_datum moet 'archief' zijn")
            else:
                if url and url not in lijst and not (allowed_source(url, modus, reg) and d.get("besluit") in ("nieuwe_zaak", "ontwikkeling", "achtergrond")):
                    e.append("url staat niet in de lijst te beoordelen berichten (en is geen relevante treffer van een persbureau)")
                if d.get("run_datum", "").strip() != today:
                    e.append(f"run_datum moet {today} zijn")
            b = d.get("besluit", "").strip()
            if b not in BESLUITEN:
                e.append(f"onbekend besluit {b!r}")
            if not d.get("reden", "").strip():
                e.append("reden ontbreekt")
            if b in ("nieuwe_zaak", "ontwikkeling"):
                if d.get("categorie", "").strip() not in atlas.CATEGORIES:
                    e.append(f"onbekende categorie {d.get('categorie', '')!r}")
                if atlas.phase(d.get("status", "")) not in FASEN:
                    e.append(f"onbekende fase {d.get('status', '')!r}")
                if b == "ontwikkeling" and d.get("incident_id", "").strip() not in case_ids | run_new:
                    e.append(f"zaak {d.get('incident_id', '')!r} bestaat niet")
                ps = prop_urls.get(url, [])
                if not any((p["soort"] == "nieuw") == (b == "nieuwe_zaak") for p in ps):
                    e.append("geen (geldig) voorstel bij dit bericht")
                q = d.get("citaat", "").strip()
                if not q:
                    e.append("citaat ontbreekt")
                elif not e:
                    qe = quote_error(url, q)
                    if qe:
                        e.append(qe)
            seen.add(url)
            if e:
                rejected.append({"bestand": name, "afkeurreden": "; ".join(e), **d})
            else:
                good.append(r)
                counts[b] += 1
        if lijst:
            accepted = {dict(zip(header, r))["url"] for r in good}
            miss = [u for u in lijst if u not in accepted]
            result["te_beoordelen"] = len(lijst)
            result["zonder_geldige_beoordeling"] = len(miss)
            if miss:
                result["fouten"].append(f"{len(miss)} bericht(en) zonder geldige beoordeling; die komen de volgende run terug")
                result["ontbrekend"] = miss[:50]
        # voorstellen zonder geldige beoordeling vallen alsnog af
        ok_urls = {dict(zip(header, r))["url"] for r in good}
        keep = []
        for r in good_props:
            d = dict(zip(prop_header, r))
            if d["bron_url"] in ok_urls or d["soort"] == "extra_bron":
                keep.append(r)
            else:
                rejected.append({"bestand": "voorstellen.csv", "afkeurreden": "bijbehorende beoordeling ontbreekt of is afgekeurd", **d})
        result["afgekeurd_voorstellen"] += len(good_props) - len(keep)
        result["voorstellen"] = len(keep)
        good_props = keep
        rebuild(DATA / name, args.backup / name, good)
    elif read_rows(DATA / name) != old:
        rebuild(DATA / name, args.backup / name, [])
        result["fouten"].append(f"{name}: hoort bij {modus} niet te veranderen; teruggezet")
        result["teruggezet"].append(name)
    rebuild(DATA / "voorstellen.csv", args.backup / "voorstellen.csv", good_props)
    result["beoordeeld"] = dict(counts)

    # --- bestanden die de AI nooit mag aanraken
    oi, ni = read_rows(args.backup / "inbox.csv"), read_rows(DATA / "inbox.csv")
    if oi and ni[:len(oi)] != oi:
        result["fouten"].append("inbox.csv: bestaande regels zijn gewijzigd; niet teruggezet, controleer handmatig")
    for nm in ("incidenten.csv", "ontwikkelingen.csv", "wijzigingen.csv", "runs.csv", "bronnenregister.csv"):
        b, n = args.backup / nm, DATA / nm
        if b.exists() and n.exists() and b.read_bytes() != n.read_bytes():
            shutil.copy2(b, n)
            result["fouten"].append(f"{nm}: bestand was gewijzigd; teruggezet")
            result["teruggezet"].append(nm)

    # --- tellingen in runs.csv (alleen de wekelijkse zoekrun)
    if modus == "week":
        runs = DATA / "runs.csv"
        rr = read_rows(runs)
        cols = rr[0] if rr else atlas.RUN_COLUMNS
        row = {"run_datum": today, "inbox": str(len(lijst)), "bekeken": str(sum(counts.values())),
               "relevant": str(counts["nieuwe_zaak"] + counts["ontwikkeling"]), "voorstellen": str(result["voorstellen"])}
        buf = io.StringIO()
        csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n").writerow({c: row.get(c, "") for c in cols})
        text = runs.read_text(encoding="utf-8-sig") if runs.exists() else ",".join(cols) + "\r\n"
        with runs.open("w" if not runs.exists() else "a", encoding="utf-8", newline="") as f:
            if not runs.exists():
                f.write(text)
            f.write(("" if text.endswith(("\n", "\r")) else "\r\n") + buf.getvalue())

    # --- verslag
    if rejected:
        afgekeurd.parent.mkdir(parents=True, exist_ok=True)
        cols = ["bestand", "afkeurreden"] + [c for c in dict.fromkeys(k for r in rejected for k in r) if c not in ("bestand", "afkeurreden")]
        with afgekeurd.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rejected)
        result["afgekeurd_bestand"] = str(afgekeurd)
        result["afgekeurde_regels"] = [f"{r.get('voorstel_id') or r.get('url', '?')}: {r['afkeurreden']}" for r in rejected]
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

    c = result["beoordeeld"]
    if modus in ("week", "archief"):
        print(f"Controle ({modus}): {sum(c.values())} beoordelingen geaccepteerd "
              f"({c.get('niet_relevant', 0)} niet relevant, {c.get('achtergrond', 0)} achtergrond, "
              f"{c.get('nieuwe_zaak', 0)} nieuwe zaak, {c.get('ontwikkeling', 0)} ontwikkeling); "
              f"{result['voorstellen']} voorstel(len), {result['afgekeurd_voorstellen']} afgekeurd.")
    else:
        print(f"Controle ({modus}): {result['voorstellen']} voorstel(len) geaccepteerd, {result['afgekeurd_voorstellen']} afgekeurd.")
    for f in result["fouten"]:
        print("  - " + f)
    for r in result.get("afgekeurde_regels", [])[:20]:
        print("  - afgekeurd " + r)
    if rejected:
        print(f"  Afgekeurde regels staan in {afgekeurd}")
    return 0 if result["ok"] else 1

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("klaarzetten"); p.add_argument("--uit", required=True, type=Path); p.set_defaults(fn=cmd_prepare)
    z = sub.add_parser("zaken"); z.add_argument("--uit", required=True, type=Path); z.add_argument("--open", action="store_true")
    z.add_argument("--max", type=int, default=15); z.set_defaults(fn=cmd_cases)
    c = sub.add_parser("controleer")
    c.add_argument("--modus", required=True, choices=["week", "archief", "verdieping", "volglijst", "verrijken", "dossier"])
    c.add_argument("--backup", required=True, type=Path)
    c.add_argument("--log", required=True, type=Path)
    c.add_argument("--lijst", type=Path)
    c.add_argument("--zaak")
    c.add_argument("--afgekeurd", type=Path)
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args()
    return args.fn(args)

if __name__ == "__main__":
    sys.exit(main())
