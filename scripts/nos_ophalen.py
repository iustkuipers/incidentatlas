#!/usr/bin/env python3
"""
Incidentatlas – nieuws en officiële bronnen ophalen naar de inboxen (protocol 2.1, 5c en 5d).

Gebruik:
  python scripts/nos_ophalen.py
      Nieuws (elk uur via Taakplanner): de actieve bronnen in data/bronnen.csv. Per bron bepaalt
      `type` hoe:
        rss            feed, alle berichten (NOS)
        rss_filter     feed, alleen berichten waarvan de titel een trefwoord bevat (omroepen)
        pagina_filter  nieuwspagina: links met titel en datum, met trefwoordfilter
        zoekopdracht   overgeslagen (Claude zoekt zelf, bijvoorbeeld bij persbureaus)
      Nieuwe berichten gaan onderaan data/inbox.csv (url, titel, datum, feed, opgehaald_op).

  python scripts/nos_ophalen.py --officieel [--dagen 8]
      Officiële bronnen (wekelijks, voor volglijst en verrijken): alle domeinen in
      data/bronnenregister.csv met lijst 'voorkeur' en een feed of nieuwspagina. Berichten van de
      afgelopen N dagen met een trefwoord in de titel gaan onderaan data/inbox_officieel.csv
      (url, titel, datum, bron, domein, land, niveau, opgehaald_op).

Ontdubbelt op url; bestaande regels worden nooit gewijzigd. Per run één regel in logs/ophalen.log.
Alleen de standaardbibliotheek van Python 3.9+ is nodig.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from haal_bronnen import fetch, parse_feed, parse_page  # noqa: E402  (zelfde ophaal- en feedcode)

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "bronnen.csv"
REGISTER = ROOT / "data" / "bronnenregister.csv"
INBOX = ROOT / "data" / "inbox.csv"
INBOX_OFF = ROOT / "data" / "inbox_officieel.csv"
LOG = ROOT / "logs" / "ophalen.log"
COLUMNS = ["url", "titel", "datum", "feed", "opgehaald_op"]
OFF_COLUMNS = ["url", "titel", "datum", "bron", "domein", "land", "niveau", "opgehaald_op"]

# Trefwoorden (begin van een woord, hoofdletters maken niet uit) in de talen van de prioriteitslanden.
# Ruim gekozen: liever een bericht te veel voor Claude dan een signaal missen.
KEYWORDS = re.compile(r"\b(" + "|".join([
    # Rusland en diensten
    r"rus(land|sia|sisch|sland|sie|se\b|ia\b|ij|ko\b|ky|kij|ijos)", r"russ", r"ros(ja|ji|yj|yjsk|sij)", r"krievij", r"vene(maa|näe)", r"venä",
    r"rysk", r"ryssland", r"kreml", r"putin", r"poetin", r"moskv", r"moskou", r"moskau", r"moscow", r"moscou",
    r"gru\b", r"fsb\b", r"svr\b", r"wagner", r"africa corps", r"belarus", r"wit-rus",
    # sabotage, brand, explosies, infrastructuur
    r"sabota", r"sabotaż", r"sabotáž", r"sabotāž", r"dywersj", r"arson", r"brandstift", r"brandanschlag", r"brandsticht",
    r"mordbrand", r"brannstift", r"podpal", r"padegim", r"süüta", r"tuhopolt", r"incendi", r"explos", r"wybuch",
    r"undersea", r"onderzee", r"seekabel", r"kabelbr", r"pipeline", r"gps", r"jamming", r"stör", r"shadow fleet",
    r"schaduwvloot", r"schattenflotte", r"skuggflott",
    # spionage
    r"spy", r"spie", r"spion", r"espion", r"szpieg", r"šnip", r"spieg", r"vakoil", r"špion", r"inlichtingen", r"intelligence",
    # cyber
    r"hack", r"cyber", r"ddos", r"ransomware", r"datalek", r"phishing", r"kyber", r"küber",
    # drones en luchtruim
    r"drone", r"drohne", r"drön", r"dron", r"droon", r"droni", r"luchtruim", r"airspace", r"luftraum", r"ilmatila",
    # inmenging
    r"desinform", r"disinform", r"dezinform", r"propagand", r"troll", r"nepnieuws", r"fake news", r"deepfake",
    r"inmenging", r"interference", r"einmisch", r"beïnvloed", r"election", r"verkiezing", r"wahl", r"vaal", r"rinkim",
    r"vēlēšan", r"wybor", r"vaalit", r"valet", r"volby",
]) + r")", re.I)

def wanted(title: str) -> bool:
    return bool(KEYWORDS.search(title or ""))

def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))

def append(path: Path, cols: list[str], rows: list[dict]) -> None:
    if not path.exists():
        path.write_text(",".join(cols) + "\r\n", encoding="utf-8")
    if not rows:
        return
    text = path.read_text(encoding="utf-8-sig")
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=cols, lineterminator="\r\n", extrasaction="ignore").writerows(rows)
    with path.open("a", encoding="utf-8", newline="") as f:
        if text and not text.endswith(("\n", "\r")):
            f.write("\r\n")
        f.write(buf.getvalue())

def items_of(kind: str, url: str) -> tuple[list[dict] | None, str]:
    """Berichten van één bron: (items of None bij mislukken, melding)."""
    code, body, final = fetch(url)
    if code != 200:
        return None, f"HTTP {code or body}"
    if kind.startswith("pagina"):
        items, _ = parse_page(body, final)
        return items, ""
    items = parse_feed(body, final)
    return (items, "") if items is not None else (None, "geen geldige feed")

def log(line: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def run_news() -> int:
    now = dt.datetime.now().isoformat(timespec="seconds")
    seen = {r["url"] for r in read(INBOX)}
    new, report, failed = [], [], 0
    for s in read(SOURCES):
        if s.get("actief", "").strip().lower() != "ja":
            continue
        kind = s["type"].strip().lower()
        if kind == "zoekopdracht":
            continue
        url = (s.get("rss") or "").strip() or s["url_of_zoekterm"]
        items, msg = items_of(kind, url)
        if items is None:
            failed += 1
            report.append(f"{s['naam']}: mislukt ({msg})")
            continue
        n = 0
        for it in items:
            if it["url"] in seen or (kind.endswith("_filter") and not wanted(it["titel"])):
                continue
            seen.add(it["url"])
            new.append({"url": it["url"], "titel": it["titel"], "datum": it["datum"].isoformat() if it["datum"] else "",
                        "feed": s["naam"], "opgehaald_op": now})
            n += 1
        report.append(f"{s['naam']}: {n} nieuw")
    new.sort(key=lambda r: r["datum"])
    append(INBOX, COLUMNS, new)
    log(f"{now}  nieuws: {len(new)} nieuw, inbox nu {len(seen)}  |  " + "; ".join(report))
    return 1 if failed else 0

def run_official(days: int) -> int:
    now = dt.datetime.now().isoformat(timespec="seconds")
    since = dt.date.today() - dt.timedelta(days=days)
    seen = {r["url"] for r in read(INBOX_OFF)}
    new, ok, failed = [], 0, []
    for r in read(REGISTER):
        if r.get("lijst") != "voorkeur" or not (r.get("rss") or r.get("nieuwspagina")):
            continue
        kind, url = ("rss", r["rss"]) if r.get("rss") else ("pagina", r["nieuwspagina"])
        items, msg = items_of(kind, url)
        if items is None and kind == "rss" and r.get("nieuwspagina"):
            items, msg = items_of("pagina", r["nieuwspagina"])
        if items is None:
            failed.append(r["domein"])
            continue
        ok += 1
        for it in items:
            if it["url"] in seen or not it["datum"] or it["datum"] < since or not wanted(it["titel"]):
                continue
            seen.add(it["url"])
            new.append({"url": it["url"], "titel": it["titel"], "datum": it["datum"].isoformat(), "bron": r["instelling"],
                        "domein": r["domein"], "land": r["land"], "niveau": r["niveau"], "opgehaald_op": now})
    new.sort(key=lambda x: x["datum"])
    append(INBOX_OFF, OFF_COLUMNS, new)
    log(f"{now}  officieel: {len(new)} nieuw uit {ok} bronnen; {len(failed)} niet bereikbaar"
        + (f" ({', '.join(failed[:15])}{' …' if len(failed) > 15 else ''})" if failed else ""))
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--officieel", action="store_true")
    ap.add_argument("--dagen", type=int, default=8)
    a = ap.parse_args()
    return run_official(a.dagen) if a.officieel else run_news()

if __name__ == "__main__":
    sys.exit(main())
