#!/usr/bin/env python3
"""
Incidentatlas – lokaal beheerscherm voor het beoordelen van voorstellen.

Gebruik:
  python scripts/beheer.py [--poort 8100]
      Start een server op http://127.0.0.1:8100 (alleen bereikbaar vanaf deze computer).
      De eerste keer maak je in het scherm een account aan; naam en wachtwoord-hash staan
      daarna in beheer-account.json in de projectmap (staat in .gitignore).

Wat het scherm doet:
  - voorstellen uit data/voorstellen.csv tonen, met de bijbehorende beoordeling (reden,
    citaat) uit data/beoordelingen.csv;
  - velden aanpassen, goedkeuren of afwijzen; beoordeeld_door wordt je accountnaam;
  - 'Verwerken' draait scripts/atlas.py verwerk --controleer-links en daarna valideer.
  Opslaan is geblokkeerd zolang de wekelijkse brief draait (logs/brief.lock).

Alleen de standaardbibliotheek van Python 3.9+ is nodig.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import http.server
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROPOSALS = DATA / "voorstellen.csv"
REVIEWS = DATA / "beoordelingen.csv"
ACCOUNT = ROOT / "beheer-account.json"
LOCK = ROOT / "logs" / "brief.lock"
PAGE = Path(__file__).resolve().parent / "beheer.html"

# velden die je in het scherm mag aanpassen; de rest (id's, verwerkt) blijft van het systeem
EDITABLE = ["soort", "incident_id", "datum", "datum_precisie", "titel", "samenvatting", "land", "regio", "lat", "lon",
            "categorie", "status", "toegeschreven_door", "datum_bevestigd", "actor", "oekraine_oorlog",
            "bron_url", "bron_uitgever", "bron_titel", "bron_niveau", "citaat", "zekerheid", "opmerking_redactie"]
CHOICES = {"status": ["signaal", "beschuldigd", "aangeklaagd", "bewezen", "ontkracht"], "categorie": list(atlas.CATEGORIES), "regio": sorted(atlas.REGIONS),
           "datum_precisie": ["dag", "maand", "jaar"], "zekerheid": ["hoog", "middel", "laag"], "oekraine_oorlog": ["ja", "nee"],
           "bron_niveau": ["A", "B", "C", "D"], "soort": sorted(atlas.KINDS)}
SESSIONS: dict[str, str] = {}

def brief_busy() -> bool:
    """De brief draait als logs/brief.lock bestaat en jonger is dan 3 uur (ouder = vastgelopen run)."""
    try:
        return (time.time() - LOCK.stat().st_mtime) < 3 * 3600
    except OSError:
        return False
WRITE = threading.Lock()

# ------------------------------------------------------------ account
def hash_pw(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 300_000).hex()

def load_account() -> dict | None:
    try:
        return json.loads(ACCOUNT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

# ------------------------------------------------------------ data
def read(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    rd = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    rows = [{k: (v or "") for k, v in r.items() if k is not None} for r in rd]
    return list(rd.fieldnames or []), rows

def write_atomic(path: Path, cols: list[str], rows: list[dict]) -> None:
    """Schrijf via een tijdelijk bestand. OneDrive vergrendelt een bestand soms even tijdens het
    synchroniseren; dan een paar keer opnieuw proberen en als laatste direct overschrijven."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    text = buf.getvalue()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.25 * (attempt + 1))
    path.write_text(text, encoding="utf-8", newline="")  # kan nog steeds PermissionError geven (bijv. Excel)
    tmp.unlink(missing_ok=True)

def timeline_for(case: str, rows: list[dict], devs: list[dict]) -> list[dict]:
    """Tijdlijn van een zaak: verwerkte ontwikkelingen plus open voorstellen voor die zaak."""
    items = [dict(d, _bron="verwerkt") for d in devs if d.get("incident_id") == case]
    keys = {case}
    if case.startswith("voorstel:"):
        parent = next((r for r in rows if r.get("voorstel_id") == case.split(":", 1)[1]), None)
        if parent:
            items.append({"datum": parent.get("datum", ""), "fase": atlas.phase(parent.get("status", "")), "fasewissel": "ja",
                          "wat": parent.get("samenvatting", ""), "wie": parent.get("toegeschreven_door", ""),
                          "bron_url": parent.get("bron_url", ""), "bron_uitgever": parent.get("bron_uitgever", ""),
                          "_bron": "voorstel", "_id": parent.get("voorstel_id", "")})
    for r in rows:
        if r.get("incident_id") in keys and r.get("soort") == "ontwikkeling" and not r.get("verwerkt", "").startswith("ja"):
            items.append({"datum": r.get("datum", ""), "fase": atlas.phase(r.get("status", "")), "wat": r.get("samenvatting", ""),
                          "wie": r.get("toegeschreven_door", ""), "bron_url": r.get("bron_url", ""), "bron_uitgever": r.get("bron_uitgever", ""),
                          "_bron": "voorstel", "_id": r.get("voorstel_id", "")})
    return sorted(items, key=lambda x: x.get("datum", ""))

def cases_payload(rows: list[dict], incidents: list[dict], devs: list[dict]) -> list[dict]:
    last = {}
    for d in devs:
        last[d["incident_id"]] = max(last.get(d["incident_id"], ""), d.get("datum", ""))
    out = []
    for r in incidents:
        out.append({"id": r["id"], "titel": r["titel"], "fase": atlas.phase(r["status"]), "land": r["land"], "categorie": r["categorie"],
                    "datum": r["datum"], "laatste": last.get(r["id"], r["datum"]), "verwerkt": True, "controle": r.get("controle", "")})
    for r in rows:
        if r.get("soort") == "nieuw" and not r.get("verwerkt", "").startswith("ja") and r.get("beoordeling") != "afgewezen":
            out.append({"id": f"voorstel:{r['voorstel_id']}", "titel": r["titel"], "fase": atlas.phase(r["status"]), "land": r["land"],
                        "categorie": r["categorie"], "datum": r["datum"], "laatste": r["datum"], "verwerkt": False})
    _, status = read(DATA / "dossierstatus.csv")
    status = {s["incident_id"]: s for s in status}
    for c in out:
        c["tijdlijn"] = timeline_for(c["id"], rows, devs)
        c["laatste"] = max([c["laatste"]] + [x.get("datum", "") for x in c["tijdlijn"]])
        s = status.get(c["id"], {})
        c.update({k: s.get(k, "") for k in ("wachtrij", "bronnen_voldoende", "bronniveaus", "laatst_gezocht", "laatst_gezocht_door", "laatste_uitkomst")})
    return sorted(out, key=lambda c: c["laatste"], reverse=True)

def proposals_payload() -> dict:
    _, rows = read(PROPOSALS)
    _, reviews = read(REVIEWS)
    by_url = {r["url"]: r for r in reviews}
    _, incidents = read(DATA / "incidenten.csv")
    _, devs = read(DATA / "ontwikkelingen.csv")
    titles = {r["id"]: r["titel"] for r in incidents}
    titles.update({f"voorstel:{r['voorstel_id']}": r["titel"] for r in rows if r.get("soort") == "nieuw"})
    extra: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("incident_id", "").startswith("voorstel:") and r.get("soort") == "extra_bron":
            extra.setdefault(r["incident_id"].split(":", 1)[1], []).append(r)
    main = [r for r in rows if not (r.get("incident_id", "").startswith("voorstel:") and r.get("soort") == "extra_bron")]
    for r in main:
        r["status"] = atlas.phase(r.get("status", ""))
        r["_extra"] = extra.get(r.get("voorstel_id", ""), [])
        rv = by_url.get(r.get("bron_url", ""))
        r["_reden"] = rv.get("reden", "") if rv else ""
        r["_incident_titel"] = titles.get(r.get("incident_id", ""), "")
        case = r["incident_id"] if r.get("soort") != "nieuw" else f"voorstel:{r['voorstel_id']}"
        r["_zaak"] = case
        r["_tijdlijn"] = timeline_for(case, rows, devs) if case else []
    return {"voorstellen": main, "zaken": cases_payload(rows, incidents, devs), "keuzes": CHOICES,
            "categorieen": atlas.CATEGORIES, "bewerkbaar": EDITABLE, "brief_bezig": brief_busy(),
            "verdieping_bezig": verdieping_status()}

def verdieping_status() -> dict:
    """Welke verdieping loopt er (logs/verdieping.lock met zaak-id), en de laatste uitkomst."""
    lock = ROOT / "logs" / "verdieping.lock"
    try:
        zaak = lock.read_text(encoding="utf-8").strip()
        if time.time() - lock.stat().st_mtime < 3600:
            return {"zaak": zaak}
    except OSError:
        pass
    return {}

def start_verdieping(zaak: str) -> tuple[int, dict]:
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,120}", zaak):
        return 400, {"fout": "ongeldig zaak-id"}  # komt in een PowerShell-opdracht: alleen veilige tekens
    if brief_busy() or verdieping_status():
        return 409, {"fout": "Er loopt al een run; probeer het straks opnieuw."}
    _, rows = read(PROPOSALS)
    _, incidents = read(DATA / "incidenten.csv")
    ok = zaak in {r["id"] for r in incidents} or zaak in {f"voorstel:{r['voorstel_id']}" for r in rows if r.get("soort") == "nieuw"}
    if not ok:
        return 404, {"fout": "zaak niet gevonden"}
    lock = ROOT / "logs" / "verdieping.lock"
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(zaak, encoding="utf-8")
    script = (f"try {{ & '{ROOT / 'run_weekbrief.ps1'}' -Modus verdieping -Zaak '{zaak}' }} "
              f"finally {{ Remove-Item -LiteralPath '{lock}' -ErrorAction SilentlyContinue }}")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                     cwd=ROOT, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 200, {"ok": True, "zaak": zaak}

def validate(changes: dict) -> list[str]:
    e = []
    for k, v in changes.items():
        if k not in EDITABLE and k != "beoordeling":
            e.append(f"veld {k} mag niet worden aangepast")
        elif k in CHOICES and v and v not in CHOICES[k]:
            e.append(f"ongeldige waarde voor {k}: {v}")
    if changes.get("datum") and not atlas.DATE_RE.match(changes["datum"]):
        e.append("datum moet JJJJ, JJJJ-MM of JJJJ-MM-DD zijn")
    for k in ("lat", "lon"):
        if changes.get(k):
            try:
                float(changes[k])
            except ValueError:
                e.append(f"{k} moet een getal zijn")
    if changes.get("beoordeling") not in (None, "te_beoordelen", "goedgekeurd", "afgewezen"):
        e.append("ongeldige beoordeling")
    return e

def update_proposal(vid: str, changes: dict, user: str) -> tuple[int, dict]:
    if brief_busy():
        return 409, {"fout": "De wekelijkse brief draait nu; probeer het straks opnieuw."}
    errs = validate(changes)
    if errs:
        return 400, {"fout": "; ".join(errs)}
    with WRITE:
        cols, rows = read(PROPOSALS)
        row = next((r for r in rows if r.get("voorstel_id") == vid), None)
        if not row:
            return 404, {"fout": "voorstel niet gevonden"}
        if row.get("verwerkt", "").startswith("ja"):
            return 409, {"fout": "dit voorstel is al verwerkt"}
        for k, v in changes.items():
            row[k] = str(v).strip()
        if row.get("verwerkt", "").startswith("fout") and changes:
            row["verwerkt"] = ""  # na aanpassing opnieuw laten verwerken
            for e in rows:
                if e.get("incident_id") == f"voorstel:{vid}" and e.get("verwerkt", "").startswith("fout"):
                    e["verwerkt"] = ""
        if "beoordeling" in changes:
            row["beoordeeld_door"] = user if changes["beoordeling"] != "te_beoordelen" else ""
        try:
            write_atomic(PROPOSALS, cols, rows)
        except PermissionError:
            return 423, {"fout": "voorstellen.csv is geopend in een ander programma (bijv. Excel); sluit het en probeer opnieuw."}
    return 200, {"ok": True, "voorstel": row}

def add_source(vid: str, b: dict, user: str) -> tuple[int, dict]:
    """Extra bron bij een voorstel: eigen regel met incident_id 'voorstel:<id>', meteen goedgekeurd.
    Link en citaat worden direct gecontroleerd."""
    if brief_busy():
        return 409, {"fout": "De wekelijkse brief draait nu; probeer het straks opnieuw."}
    src = {k: str(b.get(k, "")).strip() for k in ("bron_url", "bron_uitgever", "bron_titel", "bron_niveau", "citaat")}
    if not src["bron_url"].startswith("http"):
        return 400, {"fout": "vul een geldige URL in"}
    if src["bron_niveau"] not in ("A", "B", "C", "D"):
        return 400, {"fout": "kies een bronniveau"}
    if not src["citaat"] or not src["bron_uitgever"]:
        return 400, {"fout": "uitgever en citaat zijn nodig"}
    err = atlas.check_link_and_quote(src)
    if err:
        return 400, {"fout": f"{err}. Neem een zin letterlijk van de pagina over."}
    with WRITE:
        cols, rows = read(PROPOSALS)
        parent = next((r for r in rows if r.get("voorstel_id") == vid), None)
        if not parent or parent.get("incident_id", "").startswith("voorstel:"):
            return 404, {"fout": "voorstel niet gevonden"}
        if parent.get("verwerkt", "").startswith("ja"):
            return 409, {"fout": "dit voorstel is al verwerkt"}
        n = 1 + sum(1 for r in rows if r.get("incident_id") == f"voorstel:{vid}")
        new = {c: "" for c in cols}
        new.update(src, voorstel_id=f"{vid}-bron{n}", run_datum=parent.get("run_datum", ""), soort="extra_bron",
                   incident_id=f"voorstel:{vid}", titel=parent.get("titel", ""), status=parent.get("status", ""),
                   categorie=parent.get("categorie", ""), beoordeling="goedgekeurd", beoordeeld_door=user,
                   opmerking_redactie="extra bron toegevoegd in het beheerscherm")
        rows.append(new)
        if parent.get("verwerkt", "").startswith("fout"):
            parent["verwerkt"] = ""
        try:
            write_atomic(PROPOSALS, cols, rows)
        except PermissionError:
            return 423, {"fout": "voorstellen.csv is geopend in een ander programma; sluit het en probeer opnieuw."}
    return 200, {"ok": True}

def remove_source(sid: str) -> tuple[int, dict]:
    if brief_busy():
        return 409, {"fout": "De wekelijkse brief draait nu; probeer het straks opnieuw."}
    with WRITE:
        cols, rows = read(PROPOSALS)
        row = next((r for r in rows if r.get("voorstel_id") == sid and r.get("incident_id", "").startswith("voorstel:")), None)
        if not row:
            return 404, {"fout": "bron niet gevonden"}
        if row.get("verwerkt", "").startswith("ja"):
            return 409, {"fout": "deze bron is al verwerkt"}
        rows.remove(row)
        try:
            write_atomic(PROPOSALS, cols, rows)
        except PermissionError:
            return 423, {"fout": "voorstellen.csv is geopend in een ander programma; sluit het en probeer opnieuw."}
    return 200, {"ok": True}

def run_atlas_case(cmd: str, case: str, user: str) -> tuple[int, dict]:
    """Zaak nagekeken of van de kaart halen; loopt via atlas.py zoals elke wijziging in incidenten.csv."""
    if not re.fullmatch(r"[0-9]{4}[A-Za-z0-9-]{0,120}", case):
        return 400, {"fout": "ongeldige zaak"}
    if brief_busy():
        return 409, {"fout": "De wekelijkse brief draait nu; probeer het straks opnieuw."}
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with WRITE:
        p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "atlas.py"), cmd, "--id", case, "--door", user],
                           capture_output=True, text=True, encoding="utf-8", cwd=ROOT, env=env, timeout=120)
    if p.returncode:
        return 400, {"fout": (p.stdout + p.stderr).strip() or "mislukt"}
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "dossiers.py"), "bijwerken"],
                   capture_output=True, cwd=ROOT, env=env, timeout=120)
    return 200, {"ok": True, "melding": p.stdout.strip()}

def run_process() -> dict:
    if brief_busy():
        return {"fout": "De wekelijkse brief draait nu; probeer het straks opnieuw."}
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = []
    with WRITE:
        for args in (["verwerk", "--controleer-links"], ["valideer"]):
            p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "atlas.py"), *args],
                               capture_output=True, text=True, encoding="utf-8", cwd=ROOT, env=env, timeout=600)
            out.append({"stap": args[0], "code": p.returncode, "uitvoer": (p.stdout + p.stderr).strip().splitlines()})
    return {"ok": True, "stappen": out}

# ------------------------------------------------------------ http
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "IncidentatlasBeheer/1.0"

    def log_message(self, fmt, *a):  # stil, behalve fouten
        pass

    def _send(self, code: int, body, ctype="application/json; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _user(self) -> str | None:
        m = re.search(r"(?:^|;\s*)beheer=([A-Za-z0-9_-]+)", self.headers.get("Cookie", ""))
        return SESSIONS.get(m.group(1)) if m else None

    def _same_origin(self) -> bool:
        # verzoeken die iets wijzigen moeten van deze pagina zelf komen
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        return self.headers.get("X-Beheer") == "1" and (not origin or origin == f"http://{host}")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            acc = load_account()
            return self._send(200, {"account": bool(acc), "ingelogd": self._user(), "naam": acc and acc.get("naam")})
        if self.path == "/api/voorstellen":
            if not self._user():
                return self._send(401, {"fout": "niet ingelogd"})
            return self._send(200, proposals_payload())
        self._send(404, {"fout": "niet gevonden"})

    def do_POST(self):
        if not self._same_origin():
            return self._send(403, {"fout": "geweigerd"})
        b = self._body()
        if self.path == "/api/account":
            if load_account():
                return self._send(409, {"fout": "er is al een account"})
            naam, pw = str(b.get("naam", "")).strip(), str(b.get("wachtwoord", ""))
            if not naam or len(pw) < 8:
                return self._send(400, {"fout": "naam en een wachtwoord van minstens 8 tekens zijn nodig"})
            salt = secrets.token_bytes(16)
            ACCOUNT.write_text(json.dumps({"naam": naam, "salt": salt.hex(), "hash": hash_pw(pw, salt)}), encoding="utf-8")
            return self._login(naam)
        if self.path == "/api/login":
            acc = load_account()
            if not acc:
                return self._send(400, {"fout": "maak eerst een account"})
            ok = str(b.get("naam", "")).strip() == acc["naam"] and hmac.compare_digest(
                hash_pw(str(b.get("wachtwoord", "")), bytes.fromhex(acc["salt"])), acc["hash"])
            return self._login(acc["naam"]) if ok else self._send(401, {"fout": "naam of wachtwoord klopt niet"})
        if self.path == "/api/logout":
            m = re.search(r"beheer=([A-Za-z0-9_-]+)", self.headers.get("Cookie", ""))
            if m:
                SESSIONS.pop(m.group(1), None)
            return self._send(200, {"ok": True}, headers={"Set-Cookie": "beheer=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"})
        user = self._user()
        if not user:
            return self._send(401, {"fout": "niet ingelogd"})
        if self.path == "/api/voorstel":
            code, res = update_proposal(str(b.get("voorstel_id", "")), b.get("wijzigingen") or {}, user)
            return self._send(code, res)
        if self.path == "/api/bron":
            code, res = add_source(str(b.get("voorstel_id", "")), b, user)
            return self._send(code, res)
        if self.path == "/api/bron/verwijder":
            code, res = remove_source(str(b.get("bron_id", "")))
            return self._send(code, res)
        if self.path == "/api/verdiep":
            code, res = start_verdieping(str(b.get("zaak", "")).strip())
            return self._send(code, res)
        if self.path == "/api/verwerk":
            return self._send(200, run_process())
        if self.path in ("/api/zaak/nagekeken", "/api/zaak/verwijder"):
            code, res = run_atlas_case("nagekeken" if self.path.endswith("nagekeken") else "verwijder", str(b.get("zaak", "")).strip(), user)
            return self._send(code, res)
        self._send(404, {"fout": "niet gevonden"})

    def _login(self, naam: str):
        tok = secrets.token_urlsafe(32)
        SESSIONS[tok] = naam
        return self._send(200, {"ok": True, "naam": naam},
                          headers={"Set-Cookie": f"beheer={tok}; Path=/; HttpOnly; SameSite=Strict"})

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poort", type=int, default=8100)
    ap.add_argument("--geen-browser", action="store_true")
    a = ap.parse_args()
    # Op Windows laat SO_REUSEADDR een tweede server op dezelfde poort toe; dan blijft een oude
    # versie verzoeken beantwoorden. Daarom uit: een bezette poort geeft een duidelijke fout.
    http.server.ThreadingHTTPServer.allow_reuse_address = False
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.poort), Handler)
    except OSError:
        print(f"Poort {a.poort} is al in gebruik: draait het beheerscherm al? Sluit dat venster eerst, of gebruik --poort.")
        return 1
    url = f"http://127.0.0.1:{a.poort}/"
    print(f"Beheerscherm draait op {url}  (stoppen: Ctrl+C)")
    if not a.geen_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
