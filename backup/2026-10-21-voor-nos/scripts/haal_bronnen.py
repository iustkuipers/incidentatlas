#!/usr/bin/env python3
"""
Incidentatlas – bronnen ophalen vóór de wekelijkse brief.

Gebruik:
  python scripts/haal_bronnen.py [--dagen 8] [--datum JJJJ-MM-DD]
      Haalt alle bronnen met actief=ja uit data/bronnen.csv op:
        - met een feed in kolom 'rss' (of type 'rss'): de feed;
        - type 'pagina': de pagina, en daaruit de links met datum en titel;
        - type 'zoekopdracht': overgeslagen (dat doet Claude).
      Schrijft de berichten van de afgelopen N dagen naar logs/inbox-JJJJ-MM-DD.csv
      (titel, url, datum, bron, niveau) en per bron het resultaat naar
      logs/inbox-JJJJ-MM-DD-bronnen.csv.

  python scripts/haal_bronnen.py --zoek-rss
      Zoekt voor elke bron zonder feed of er een werkende RSS/Atom-feed is en zet die
      in de kolom 'rss' van data/bronnen.csv.

Alleen de standaardbibliotheek van Python 3.9+ is nodig.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import gzip
import html
import io
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "bronnen.csv"
LOGS = ROOT / "logs"
INBOX_COLUMNS = ["titel", "url", "datum", "bron", "niveau"]
STATUS_COLUMNS = ["bron", "type", "methode", "gelukt", "gevonden", "zonder_datum", "in_periode", "melding"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 Incidentatlas/1.0"

# ------------------------------------------------------------- ophalen
def decode(raw: bytes, charset: str | None) -> str:
    if raw[:2] == b"\x1f\x8b":  # sommige servers sturen gzip, ook ongevraagd
        raw = gzip.decompress(raw)
    return raw.decode(charset or "utf-8", "replace")

def fetch_curl(url: str, timeout: int) -> tuple[int, str, str]:
    """Terugval via curl.exe van Windows: die gebruikt de certificaatopslag van Windows en vult
    ontbrekende tussencertificaten aan, wat Python niet doet. De certificaatcontrole blijft aan."""
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return 0, "SSLCertVerificationError", url
    marker = "\n@@incidentatlas@@"
    try:
        p = subprocess.run([curl, "-sL", "--compressed", "--max-time", str(timeout), "-A", UA,
                            "-w", marker + "%{http_code} %{url_effective}", url],
                           capture_output=True, timeout=timeout + 10)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 0, type(e).__name__, url
    body, _, tail = p.stdout.rpartition(marker.encode())
    code, _, final = tail.decode(errors="replace").partition(" ")
    code = int(code) if code.isdigit() else 0
    return code, decode(body, None) if code == 200 else (f"curl {p.returncode}" if not code else ""), final or url

def iri_to_uri(url: str) -> str:
    """URL met letters als 'ț' of '–' omzetten naar iets wat urllib kan versturen."""
    p = urllib.parse.urlsplit(url)
    host = p.hostname.encode("idna").decode("ascii") if p.hostname else ""
    netloc = host + (f":{p.port}" if p.port else "")
    q = lambda s: urllib.parse.quote(s, safe="/%:@!$&'()*+,;=-._~?")
    return urllib.parse.urlunsplit((p.scheme, netloc, q(p.path), q(p.query), q(p.fragment)))

def fetch(url: str, timeout: int = 25) -> tuple[int, str, str]:
    """(HTTP-status, tekst, uiteindelijke URL). Status 0 bij geen antwoord."""
    url = iri_to_uri(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en,nl;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, decode(r.read(5_000_000), r.headers.get_content_charset()), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            return fetch_curl(url, timeout)
        return 0, type(e.reason).__name__, url
    except Exception as e:  # time-out, verbroken verbinding ...
        return 0, type(e).__name__, url

# --------------------------------------------------------------- datums
MONTHS = {}
for num, names in enumerate([
    "january jan januari janvier janv jaanuar sausio stycznia styczeń januar",
    "february feb februari februar février févr veebruar vasario lutego luty",
    "march mar maart märz mars märts kovo marca marzec",
    "april apr avril aprill balandžio kwietnia kwiecień",
    "may mei mai gegužės maja maj",
    "june jun juni juin juuni birželio czerwca czerwiec",
    "july jul juli juillet juuli liepos lipca lipiec",
    "august aug augustus août rugpjūčio sierpnia sierpień",
    "september sep sept septembre rugsėjo września wrzesień",
    "october oct oktober okt octobre oktoober spalio października październik",
    "november nov novembre lapkričio listopada listopad",
    "december dec dezember décembre déc detsember desember gruodžio grudnia grudzień",
], start=1):
    for n in names.split():
        MONTHS[n] = num
MONTH_RE = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
DATE_PATTERNS = [
    ("iso", re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")),
    ("dmy_word", re.compile(rf"(?<!\d)(\d{{1,2}})\.?\s+({MONTH_RE})\.?,?\s+(20\d\d)", re.I)),
    ("mdy_word", re.compile(rf"\b({MONTH_RE})\.?\s+(\d{{1,2}}),?\s+(20\d\d)", re.I)),
    ("num", re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](20\d\d)(?!\d)")),
    ("url", re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")),
    ("url", re.compile(r"/(20\d\d)(\d\d)(\d\d)[-_]")),
]

def safe_date(y, m, d) -> dt.date | None:
    try:
        return dt.date(int(y), int(m), int(d))
    except ValueError:
        return None

def dates_in(text: str, us: bool = False) -> list[tuple[int, dt.date]]:
    """Alle datums in de tekst, met hun positie."""
    found = []
    for kind, rx in DATE_PATTERNS:
        for m in rx.finditer(text):
            g = m.groups()
            if kind in ("iso", "url"):
                d = safe_date(*g)
            elif kind == "dmy_word":
                d = safe_date(g[2], MONTHS[g[1].lower()], g[0])
            elif kind == "mdy_word":
                d = safe_date(g[2], MONTHS[g[0].lower()], g[1])
            else:
                a, b, y = int(g[0]), int(g[1]), g[2]
                if a > 12 or (not us and b <= 12):
                    d = safe_date(y, b, a)
                else:
                    d = safe_date(y, a, b)
            if d:
                found.append((m.start(), d))
    return found

def parse_feed_date(s: str) -> dt.date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s).date()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.match(r"(20\d\d)-(\d\d)-(\d\d)", s)
    return safe_date(*m.groups()) if m else None

# ---------------------------------------------------------------- feeds
def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()

def parse_feed(text: str, base: str) -> list[dict] | None:
    """Items uit RSS 2.0, RSS 1.0 (RDF) of Atom; None als het geen feed is."""
    text = text.lstrip("﻿ \r\n\t")
    if not text.startswith("<"):
        return None
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        return None
    if local(root.tag) not in ("rss", "feed", "rdf"):
        return None
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        title = link = date = ""
        for c in el:
            name = local(c.tag)
            if name == "title":
                title = "".join(c.itertext()).strip()
            elif name == "link":
                href = c.get("href")
                if href and c.get("rel", "alternate") == "alternate":
                    link = href
                elif not href and (c.text or "").strip():
                    link = c.text.strip()
            elif name in ("pubdate", "date", "published", "updated", "issued") and not date:
                date = (c.text or "").strip()
            elif name == "guid" and not link and (c.text or "").startswith("http"):
                link = c.text.strip()
        if title and link:
            items.append({"titel": re.sub(r"\s+", " ", html.unescape(title)),
                          "url": urllib.parse.urljoin(base, link), "datum": parse_feed_date(date)})
    return items

def feed_ok(url: str) -> tuple[bool, str]:
    code, text, final = fetch(url, timeout=15)
    if code != 200:
        return False, f"HTTP {code or text}"
    items = parse_feed(text, final)
    if items is None:
        return False, "geen feed"
    if not items:
        return False, "lege feed"
    return True, f"{len(items)} items"

# --------------------------------------------------------------- pagina's
A_RE = re.compile(r"<a\b[^>]*?href\s*=\s*([\"'])(.*?)\1[^>]*>(.*?)</a\s*>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
TIME_RE = re.compile(r"<time\b[^>]*datetime\s*=\s*[\"']([^\"']+)[\"']", re.I)

def strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", s))).strip()

def same_site(a: str, b: str) -> bool:
    ha, hb = (urllib.parse.urlparse(x).hostname or "" for x in (a, b))
    base = lambda h: ".".join(h.split(".")[-2:])
    return base(ha) == base(hb)

def parse_page(text: str, base: str) -> tuple[list[dict], int]:
    """Links met een titel en een datum uit een nieuwspagina. Geeft (items, aantal_zonder_datum).
    De datum komt uit de URL, een <time>-element of tekst vlak bij de link."""
    text = re.sub(r"<(script|style|noscript)\b.*?</\1\s*>", " ", text, flags=re.S | re.I)
    us = (urllib.parse.urlparse(base).hostname or "").endswith(".gov")
    anchors = list(A_RE.finditer(text))
    items, seen, undated = [], set(), 0
    for i, m in enumerate(anchors):
        href = html.unescape(m.group(2).strip())
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        url = urllib.parse.urljoin(base, href).split("#")[0]
        title = strip(m.group(3)) or strip(re.search(r"title\s*=\s*[\"']([^\"']*)", m.group(0)).group(1)
                                           if re.search(r"title\s*=", m.group(0)) else "")
        if len(title) < 20 or len(title.split()) < 4 or url in seen or not same_site(url, base) or url.rstrip("/") == base.rstrip("/"):
            continue
        seen.add(url)
        # zoekgebied: tussen de vorige en de volgende link, maximaal 500 tekens elk kant op
        lo = max(anchors[i - 1].end() if i else 0, m.start() - 500)
        hi = min(anchors[i + 1].start() if i + 1 < len(anchors) else len(text), m.end() + 500)
        date = None
        u = dates_in(url, us)
        if u:
            date = u[0][1]
        else:
            seg = text[lo:hi]
            t = TIME_RE.search(seg)
            if t:
                date = parse_feed_date(t.group(1))
            if not date:
                near = dates_in(strip(seg), us) or dates_in(strip(m.group(3)), us)
                if near:
                    date = near[0][1]
        if date:
            # een hele nieuwskaart als link: datum vooraan weg, introtekst afkappen
            title = re.sub(r"^\d{1,2}[-./]\d{1,2}[-./]20\d\d\s+|^20\d\d-\d\d-\d\d\s+", "", title)
            if len(title) > 160:
                title = title[:160].rsplit(" ", 1)[0] + " …"
            items.append({"titel": title, "url": url, "datum": date})
        else:
            undated += 1
    return items, undated

def discover_feeds(page_url: str, text: str) -> list[str]:
    """Kandidaat-feeds: <link rel=alternate>, links met rss/feed erin, gangbare paden."""
    cands = []
    for m in re.finditer(r"<link\b[^>]*>", text, re.I):
        tag = m.group(0)
        if re.search(r"application/(rss|atom)\+xml", tag, re.I):
            h = re.search(r"href\s*=\s*[\"']([^\"']+)", tag)
            if h:
                cands.append(urllib.parse.urljoin(page_url, html.unescape(h.group(1))))
    for m in A_RE.finditer(text):
        href = html.unescape(m.group(2))
        if re.search(r"(rss|atom|feed)(\.xml|\.ashx|/|$|\?)", href, re.I) and not href.startswith("mailto:"):
            cands.append(urllib.parse.urljoin(page_url, href))
    p = urllib.parse.urlparse(page_url)
    root = f"{p.scheme}://{p.netloc}"
    path = p.path.rstrip("/")
    for suffix in ("/rss", "/feed", "/rss.xml", "/feed.xml", ".rss", "/atom.xml", "/index.xml"):
        if path:
            cands.append(root + path + suffix)
    for c in ("/rss", "/feed", "/rss.xml", "/feed.xml", "/atom.xml", "/news.xml", "/rss/news.xml"):
        cands.append(root + c)
    return list(dict.fromkeys(c for c in cands if c.startswith("http")))

# ------------------------------------------------------------ commando's
def read_sources() -> tuple[list[dict], list[str]]:
    text = SOURCES.read_text(encoding="utf-8-sig")
    rd = csv.DictReader(io.StringIO(text))
    rows = list(rd)
    return rows, list(rd.fieldnames or [])

def cmd_fetch(args) -> int:
    run = dt.date.fromisoformat(args.datum) if args.datum else dt.date.today()
    since = run - dt.timedelta(days=args.dagen)
    sources, _ = read_sources()
    inbox, status = [], []
    for s in sources:
        if s.get("actief", "").strip().lower() != "ja":
            continue
        name, kind = s["naam"], s["type"].strip().lower()
        feed = (s.get("rss") or "").strip() or (s["url_of_zoekterm"] if kind == "rss" else "")
        st = {"bron": name, "type": kind, "methode": "", "gelukt": "nee", "gevonden": 0, "zonder_datum": 0, "in_periode": 0, "melding": ""}
        if kind == "zoekopdracht" and not feed:
            st.update(methode="overgeslagen", gelukt="n.v.t.", melding="zoekopdracht: doet Claude")
            status.append(st)
            continue
        items: list[dict] = []
        if feed:
            st["methode"] = "rss"
            code, text, final = fetch(feed)
            parsed = parse_feed(text, final) if code == 200 else None
            if parsed is None:
                st["melding"] = f"feed: HTTP {code or text}" if code != 200 else "feed: geen geldige feed"
            else:
                items = parsed
                st["gelukt"] = "ja"
        if st["gelukt"] != "ja" and kind == "pagina":
            st["methode"] = "pagina" if not feed else "rss→pagina"
            code, text, final = fetch(s["url_of_zoekterm"])
            if code != 200:
                st["melding"] = "; ".join(x for x in (st["melding"], f"pagina: HTTP {code or text}") if x)
            else:
                items, st["zonder_datum"] = parse_page(text, final)
                st["gelukt"] = "ja"
                if not items:
                    st["melding"] = "; ".join(x for x in (st["melding"], "pagina geladen maar geen links met datum gevonden (mogelijk JavaScript)") if x)
        st["zonder_datum"] += sum(1 for it in items if not it["datum"])
        st["gevonden"] = len(items)
        recent = [it for it in items if it["datum"] and since <= it["datum"] <= run]
        st["in_periode"] = len(recent)
        for it in recent:
            inbox.append({"titel": it["titel"], "url": it["url"], "datum": it["datum"].isoformat(), "bron": name, "niveau": s.get("niveau", "")})
        status.append(st)
        print(f"  {'✓' if st['gelukt'] == 'ja' else '✗'} {name}: {st['methode']}, {st['in_periode']} in periode"
              + (f" ({st['melding']})" if st["melding"] else ""))

    # dubbele URL's (zelfde bericht via twee bronnen) één keer houden, nieuwste eerst
    uniq = {}
    for it in inbox:
        uniq.setdefault(it["url"], it)
    inbox = sorted(uniq.values(), key=lambda r: r["datum"], reverse=True)

    LOGS.mkdir(exist_ok=True)
    out = Path(args.uit) if args.uit else LOGS / f"inbox-{run.isoformat()}.csv"
    stat = out.with_name(out.stem + "-bronnen.csv")
    for path, rows, cols in ((out, inbox, INBOX_COLUMNS), (stat, status, STATUS_COLUMNS)):
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    ok = sum(1 for s in status if s["gelukt"] == "ja")
    tried = sum(1 for s in status if s["gelukt"] != "n.v.t.")
    print(f"{len(inbox)} berichten van {since} t/m {run} in {out.relative_to(ROOT)}; {ok} van {tried} bronnen opgehaald.")
    return 0

def cmd_discover(_args) -> int:
    sources, cols = read_sources()
    if "rss" not in cols:
        cols.append("rss")
    for s in sources:
        s.setdefault("rss", "")
        if s["type"].strip().lower() == "zoekopdracht" or s["rss"].strip():
            continue
        page = s["url_of_zoekterm"]
        code, text, final = fetch(page)
        cands = discover_feeds(final, text if code == 200 else "")
        found = ""
        for c in cands[:25]:
            ok, msg = feed_ok(c)
            if ok:
                found = c
                print(f"  ✓ {s['naam']}: {c} ({msg})")
                break
        if not found:
            print(f"  – {s['naam']}: geen werkende feed gevonden (pagina HTTP {code or text}, {len(cands)} kandidaten)")
        s["rss"] = found
    with SOURCES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(sources)
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description="Bronnen ophalen voor de wekelijkse brief")
    ap.add_argument("--dagen", type=int, default=8)
    ap.add_argument("--datum", help="rundatum (standaard vandaag)")
    ap.add_argument("--uit", help="pad van de inbox (standaard logs/inbox-JJJJ-MM-DD.csv)")
    ap.add_argument("--zoek-rss", action="store_true", help="zoek feeds en zet ze in data/bronnen.csv")
    args = ap.parse_args()
    return cmd_discover(args) if args.zoek_rss else cmd_fetch(args)

if __name__ == "__main__":
    sys.exit(main())
