#!/usr/bin/env python3
"""
Incidentatlas – datascript.

Gebruik:
  python scripts/atlas.py valideer
      Controleert data/incidenten.csv op formaat en bewijsregels.

  python scripts/atlas.py verwerk [--voorstellen PAD_OF_URL] [--controleer-links]
      Neemt goedgekeurde voorstellen over in data/incidenten.csv.
      PAD_OF_URL is standaard data/voorstellen.csv; een Google Sheets
      CSV-exportlink werkt ook (dan wordt een verwerkingsverslag geschreven
      in plaats van de sheet aan te passen).

  python scripts/atlas.py links
      Controleert alle bronlinks en werkt 'laatst_gecontroleerd' bij.

Alleen de standaardbibliotheek van Python 3.9+ is nodig.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INCIDENTS = DATA / "incidenten.csv"
PROPOSALS = DATA / "voorstellen.csv"
CHANGES = DATA / "wijzigingen.csv"
RUNS = DATA / "runs.csv"

# ---------------------------------------------------------------- schema
COLUMNS = [
    "id", "datum", "datum_precisie", "titel", "samenvatting", "land", "regio", "lat", "lon",
    "categorie", "status", "toegeschreven_door", "datum_bevestigd", "actor", "oekraine_oorlog",
    "bron_1_url", "bron_1_uitgever", "bron_1_titel", "bron_1_niveau",
    "bron_2_url", "bron_2_uitgever", "bron_2_titel", "bron_2_niveau",
    "bron_3_url", "bron_3_uitgever", "bron_3_titel", "bron_3_niveau",
    "statusgeschiedenis", "toegevoegd_op", "laatst_gecontroleerd", "opmerking",
]
PROPOSAL_COLUMNS = [
    "voorstel_id", "run_datum", "soort", "incident_id",
    "datum", "datum_precisie", "titel", "samenvatting", "land", "regio", "lat", "lon",
    "categorie", "status", "toegeschreven_door", "datum_bevestigd", "actor", "oekraine_oorlog",
    "bron_url", "bron_uitgever", "bron_titel", "bron_niveau", "citaat", "zekerheid",
    "beoordeling", "beoordeeld_door", "opmerking_redactie", "verwerkt",
]
CHANGE_COLUMNS = ["datum", "run_datum", "soort", "incident_id", "titel", "omschrijving"]
RUN_COLUMNS = ["run_datum", "inbox", "bekeken", "relevant", "voorstellen", "goedgekeurd", "afgewezen"]

CATEGORIES = {
    "sabotage": "Sabotage & brandstichting",
    "luchtruim_drones": "Drones & luchtruim",
    "cyber": "Cyber",
    "moord_vergiftiging": "Moord & vergiftiging",
    "spionage": "Spionage",
    "desinformatie_verkiezingen": "Desinformatie & verkiezingen",
    "paramilitair": "Wagner / Africa Corps",
    "militair": "Militair",
    "energie_chantage": "Energie-chantage",
    "migratie": "Migratie als wapen",
}
STATUSES = {"bewezen", "past_in_profiel", "afgewezen"}
PRECISIONS = {"dag", "maand", "jaar"}
REGIONS = {"Europa", "Afrika", "Midden-Oosten", "Azië", "Noord-Amerika", "Latijns-Amerika",
           "Rusland & buurlanden", "Oekraïne"}
KINDS = {"nieuw", "extra_bron", "statuswijziging", "correctie"}

# ------------------------------------------------------------ bronniveaus
LEVEL_A = ("justice.gov", "gov.uk", "cisa.gov", "treasury.gov", "state.gov", "europa.eu", "nato.int",
           "un.org", "itlos.org", "echr.coe.int", "icc-cpi.int", "opcw.org", "icj-cij.org", "prokuratuur.ee",
           "rechtspraak.nl", "om.nl", "aivd.nl", "defensie.nl", "rijksoverheid.nl", "government.nl",
           "bundesregierung.de", "generalbundesanwalt.de", "verfassungsschutz.de", "gov.pl", "prokuratura",
           "vrm.lt", "valstybe.lt", "politsei.ee", "kapo.ee", "pst.no", "regjeringen.no", "sgdsn.gouv.fr",
           "gouv.fr", "vlada.cz", "mzv.cz", "osce.org", "bailii.org", "ncsc.gov", "fbi.gov", "ic3.gov")
LEVEL_B = ("reuters.com", "apnews.com", "afp.com", "bbc.", "nos.nl", "aljazeera.com", "euronews.com", "rferl.org",
           "nbcnews.com", "cbsnews.com", "abcnews.go.com", "pbs.org", "cnbc.com", "cnn.com", "nytimes.com",
           "washingtonpost.com", "theguardian.com", "ft.com", "lemonde.fr", "spiegel.de", "dw.com", "politico.eu",
           "kyivindependent.com", "themoscowtimes.com", "meduza.io", "lrt.lt", "err.ee", "lsm.lv", "polskieradio.pl",
           "radio.cz", "bta.bg", "aa.com.tr", "dutchnews.nl", "nltimes.nl", "stripes.com", "washingtontimes.com",
           "arabnews.com", "gulfnews.com", "thelocal.", "intellinews.com", "baltictimes.com", "sofiaglobe.com",
           "novayagazeta.eu", "globalnews.ca", "kpbs.org", "ajot.com", "heraldnet.com", "irishlegal.com",
           "pravda.com.ua", "eurointegration.com.ua", "1tv.ge", "civil.ge", "rudaw.net", "newarab.com",
           "arctictoday.com", "opb.org", "wsvn.com", "nrc.nl", "volkskrant.nl", "tagesschau.de", "yle.fi", "svt.se")
LEVEL_D = ("wikipedia.org", "globalsecurity.org", "devdiscourse.com", "yahoo.com", "feeds.ajc.com",
           "everycrsreport.com", "reliefweb.int", "staging", "casebook.icrc.org")

def source_level(url: str) -> str:
    """Schatting van het bronniveau op basis van het domein. De redactie mag dit altijd aanpassen."""
    host = re.sub(r"^https?://", "", url or "").split("/")[0].lower().replace("www.", "")
    if any(k in host for k in LEVEL_D):
        return "D"
    if any(k in host for k in LEVEL_A) or host.endswith(".gov") or ".gov." in host:
        return "A"
    if any(k in host for k in LEVEL_B):
        return "B"
    return "C"

# ------------------------------------------------------------- hulpjes
def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")

def today() -> str:
    return dt.date.today().isoformat()

def read_csv(path_or_url: str | Path, columns: list[str] | None = None) -> list[dict]:
    s = str(path_or_url)
    if s.startswith("http"):
        req = urllib.request.Request(s, headers={"User-Agent": "Incidentatlas/1.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    else:
        p = Path(s)
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if columns:
        for r in rows:
            for c in columns:
                r.setdefault(c, "")
            for k in list(r):
                if r[k] is None:
                    r[k] = ""
    return rows

def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: (r.get(c) or "") for c in columns})

def write_incidents(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["datum"], r["id"]), reverse=True)  # nieuwste eerst
    write_csv(INCIDENTS, rows, COLUMNS)

def append_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    existing = read_csv(path, columns)
    write_csv(path, existing + rows, columns)

DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

def iri_to_uri(url: str) -> str:
    """URL met letters als 'ț' of '–' omzetten naar iets wat urllib kan versturen."""
    p = urllib.parse.urlsplit(url)
    host = p.hostname.encode("idna").decode("ascii") if p.hostname else ""
    netloc = host + (f":{p.port}" if p.port else "")
    q = lambda s: urllib.parse.quote(s, safe="/%:@!$&'()*+,;=-._~?")
    return urllib.parse.urlunsplit((p.scheme, netloc, q(p.path), q(p.query), q(p.fragment)))

def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(iri_to_uri(url), headers={"User-Agent": "Mozilla/5.0 (Incidentatlas linkcheck)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(3_000_000).decode("utf-8", "ignore")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""

def norm(text: str) -> str:
    """Alleen de woorden, in volgorde: zonder HTML, entiteiten, hoofdletters, leestekens,
    aanhalingstekens en streepjes. Zo telt een ander streepje of aanhalingsteken niet als verschil."""
    text = re.sub(r"<(script|style)\b.*?</\1\s*>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKC", html.unescape(text)).casefold()
    words = re.findall(r"[^\W_]+", text)
    return " " + " ".join(words) + " "

# ------------------------------------------------------------ validatie
def validate_incident(r: dict, strict: bool = True) -> list[str]:
    """Geeft fouten terug. Met strict=False worden bronsterkte-regels als waarschuwing
    (prefix 'waarschuwing:') gemeld, voor bestaande data die nog een betere bron nodig heeft."""
    e = []
    warn = (lambda m: e.append(m)) if strict else (lambda m: e.append("waarschuwing: " + m))
    if not r["id"]:
        e.append("id ontbreekt")
    if not DATE_RE.match(r["datum"]):
        e.append(f"datum ongeldig: {r['datum']!r}")
    if r["datum_precisie"] not in PRECISIONS:
        e.append(f"datum_precisie moet dag/maand/jaar zijn: {r['datum_precisie']!r}")
    for k in ("titel", "samenvatting", "land"):
        if not r[k].strip():
            e.append(f"{k} ontbreekt")
    if r["regio"] not in REGIONS:
        e.append(f"onbekende regio: {r['regio']!r}")
    if r["categorie"] not in CATEGORIES:
        e.append(f"onbekende categorie: {r['categorie']!r}")
    if r["status"] not in STATUSES:
        e.append(f"onbekende status: {r['status']!r}")
    try:
        lat, lon = float(r["lat"]), float(r["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            e.append("coördinaten buiten bereik")
    except ValueError:
        e.append("lat/lon geen getal")
    levels = [r[f"bron_{i}_niveau"] for i in (1, 2, 3) if r[f"bron_{i}_url"]]
    if not levels:
        e.append("geen bron")
    if r["status"] == "bewezen":
        if not r["toegeschreven_door"].strip():
            e.append("bewezen zonder toeschrijver")
        if "A" not in levels and levels.count("B") < 2:
            warn("bewezen vereist een A-bron of twee B-bronnen")
    if r["status"] == "past_in_profiel" and not ({"A", "B"} & set(levels)):
        warn("past_in_profiel vereist minstens een A- of B-bron")
    if r["oekraine_oorlog"] not in ("ja", "nee"):
        e.append("oekraine_oorlog moet ja of nee zijn")
    return e

def cmd_validate(_args) -> int:
    rows = read_csv(INCIDENTS, COLUMNS)
    ids, bad, weak = set(), 0, []
    for r in rows:
        msgs = validate_incident(r, strict=False)
        if r["id"] in ids:
            msgs.append("dubbel id")
        ids.add(r["id"])
        errs = [m for m in msgs if not m.startswith("waarschuwing")]
        if errs:
            bad += 1
            print(f"  ✗ {r['id']}: " + "; ".join(errs))
        elif msgs:
            weak.append(r["id"])
    if weak:
        print(f"  ! {len(weak)} incidenten hebben een sterkere bron nodig (zie 'bron verbeteren' in opmerking).")
    print(f"{len(rows)} incidenten gecontroleerd, {bad} met fouten.")
    return 1 if bad else 0

# ------------------------------------------------------- voorstellen
def add_source(inc: dict, p: dict) -> str | None:
    urls = [inc[f"bron_{i}_url"] for i in (1, 2, 3)]
    if p["bron_url"] in urls:
        return None
    for i in (1, 2, 3):
        if not inc[f"bron_{i}_url"]:
            break
    else:
        # alle plekken vol: vervang de zwakste bron als de nieuwe sterker is
        order = "ABCD"
        weakest = max((1, 2, 3), key=lambda i: order.index(inc[f"bron_{i}_niveau"] or "D"))
        if order.index(p["bron_niveau"] or "D") >= order.index(inc[f"bron_{weakest}_niveau"] or "D"):
            return "al drie bronnen en de nieuwe is niet sterker"
        i = weakest
    inc[f"bron_{i}_url"] = p["bron_url"]
    inc[f"bron_{i}_uitgever"] = p["bron_uitgever"]
    inc[f"bron_{i}_titel"] = p["bron_titel"]
    inc[f"bron_{i}_niveau"] = p["bron_niveau"] or source_level(p["bron_url"])
    return None

def check_link_and_quote(p: dict) -> str | None:
    code, body = fetch(p["bron_url"])
    if code != 200:
        return f"bron geeft HTTP {code or 'geen antwoord'}"
    q = norm(p["citaat"])
    if q.strip() and q not in norm(body):
        return "citaat niet gevonden op de bronpagina"
    return None

def cmd_process(args) -> int:
    src = args.voorstellen or str(PROPOSALS)
    proposals = read_csv(src, PROPOSAL_COLUMNS)
    incidents = read_csv(INCIDENTS, COLUMNS)
    by_id = {r["id"]: r for r in incidents}
    changes, done, failed = [], 0, 0

    for p in proposals:
        if p["beoordeling"].strip().lower() != "goedgekeurd" or p["verwerkt"].strip():
            continue
        p["bron_niveau"] = (p["bron_niveau"] or source_level(p["bron_url"])).upper()
        kind = p["soort"].strip().lower()
        err = None
        if kind not in KINDS:
            err = f"onbekende soort: {kind!r}"
        elif not p["bron_url"].startswith("http"):
            err = "bron_url ontbreekt"
        elif args.controleer_links:
            err = check_link_and_quote(p)

        if not err and kind == "nieuw":
            iid = base = f"{p['datum']}-{slugify(p['titel'])[:40]}"
            n = 2
            while iid in by_id:
                iid, n = f"{base}-{n}", n + 1
            inc = {c: "" for c in COLUMNS}
            for c in COLUMNS:
                if c in p and p[c]:
                    inc[c] = p[c].strip()
            inc.update(id=iid, toegevoegd_op=today(), oekraine_oorlog=inc["oekraine_oorlog"] or "nee",
                       statusgeschiedenis=f"{p['datum_bevestigd'] or today()}:{inc['status']}")
            add_source(inc, p)
            errs = validate_incident(inc)
            if errs:
                err = "; ".join(errs)
            else:
                incidents.append(inc); by_id[iid] = inc
                changes.append(dict(datum=today(), run_datum=p["run_datum"], soort="nieuw", incident_id=iid, titel=inc["titel"],
                                    omschrijving=f"Opgenomen als {inc['status'].replace('_', ' ')} · bron {inc['bron_1_niveau']}"))
        elif not err:
            inc = by_id.get(p["incident_id"].strip())
            if not inc:
                err = f"incident_id niet gevonden: {p['incident_id']!r}"
            else:
                before = dict(inc)
                if kind in ("extra_bron", "statuswijziging"):
                    err = add_source(inc, p)
                if not err and kind == "statuswijziging":
                    new = p["status"].strip()
                    inc["status"] = new
                    if p["toegeschreven_door"]:
                        inc["toegeschreven_door"] = p["toegeschreven_door"].strip()
                    if p["datum_bevestigd"]:
                        inc["datum_bevestigd"] = p["datum_bevestigd"].strip()
                    inc["statusgeschiedenis"] += f";{p['datum_bevestigd'] or today()}:{new}"
                if not err and kind == "correctie":
                    for c in COLUMNS:
                        if c in p and p[c].strip() and c not in ("id", "statusgeschiedenis"):
                            inc[c] = p[c].strip()
                if not err:
                    errs = validate_incident(inc)
                    if errs:
                        inc.clear(); inc.update(before)
                        err = "; ".join(errs)
                    else:
                        inc["opmerking"] = re.sub(r"^bron verbeteren:[^.]*\.?\s*", "", inc["opmerking"])
                if not err:
                    label = {"extra_bron": "Bron toegevoegd", "statuswijziging": f"Status nu {inc['status'].replace('_', ' ')}",
                             "correctie": "Gecorrigeerd"}[kind]
                    changes.append(dict(datum=today(), run_datum=p["run_datum"], soort=kind, incident_id=inc["id"], titel=inc["titel"],
                                        omschrijving=f"{label} · {p['bron_uitgever']} (niveau {p['bron_niveau']})"))

        if err:
            failed += 1
            p["verwerkt"] = f"fout: {err}"
            print(f"  ✗ {p['voorstel_id'] or p['titel']}: {err}")
        else:
            done += 1
            p["verwerkt"] = f"ja {today()}"
            print(f"  ✓ {p['voorstel_id'] or p['titel']}")

    write_incidents(incidents)
    if changes:
        append_csv(CHANGES, changes, CHANGE_COLUMNS)

    # tellingen per run bijwerken
    runs = {r["run_datum"]: r for r in read_csv(RUNS, RUN_COLUMNS)}
    for p in proposals:
        rd = p["run_datum"]
        if not rd or rd not in runs:
            continue
        rr = runs[rd]
        rr["goedgekeurd"] = str(sum(1 for q in proposals if q["run_datum"] == rd and q["beoordeling"].lower() == "goedgekeurd"))
        rr["afgewezen"] = str(sum(1 for q in proposals if q["run_datum"] == rd and q["beoordeling"].lower() == "afgewezen"))
    if runs:
        write_csv(RUNS, sorted(runs.values(), key=lambda r: r["run_datum"], reverse=True), RUN_COLUMNS)

    if src.startswith("http"):
        report = DATA / f"verwerkingsverslag-{today()}.csv"
        write_csv(report, proposals, PROPOSAL_COLUMNS)
        print(f"Verslag geschreven naar {report.name}; zet de kolom 'verwerkt' daaruit terug in de sheet.")
    else:
        write_csv(Path(src), proposals, PROPOSAL_COLUMNS)
    print(f"{done} verwerkt, {failed} met fout.")
    return 1 if failed else 0

# ------------------------------------------------------------- links
def cmd_links(_args) -> int:
    rows = read_csv(INCIDENTS, COLUMNS)
    dead = 0
    for r in rows:
        ok = True
        for i in (1, 2, 3):
            u = r[f"bron_{i}_url"]
            if not u:
                continue
            code, _ = fetch(u, timeout=15)
            if code != 200:
                ok = False
                print(f"  ✗ {r['id']} bron {i}: HTTP {code or 'geen antwoord'}  {u}")
        if ok:
            r["laatst_gecontroleerd"] = today()
        else:
            dead += 1
    write_incidents(rows)
    print(f"{len(rows)} incidenten gecontroleerd, {dead} met een onbereikbare bron.")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description="Incidentatlas datascript")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("valideer").set_defaults(fn=cmd_validate)
    pr = sub.add_parser("verwerk")
    pr.add_argument("--voorstellen", help="pad of CSV-URL (standaard data/voorstellen.csv)")
    pr.add_argument("--controleer-links", action="store_true", help="link en citaat online controleren")
    pr.set_defaults(fn=cmd_process)
    sub.add_parser("links").set_defaults(fn=cmd_links)
    args = ap.parse_args()
    return args.fn(args)

if __name__ == "__main__":
    sys.exit(main())
