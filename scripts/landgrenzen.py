"""Maakt data/landgrenzen.geojson: landsgrenzen voor de kaart (klikken, oplichten, inzoomen).

Bron: Natural Earth 1:50m Admin 0 Countries (publiek domein). Per land blijven drie velden over:
  en  Engelse naam zoals de site die al gebruikt (data/landen.csv, kolom land_en)
  nl  Nederlandse naam (Natural Earth NAME_NL)
  a3  ISO-code (ADM0_A3)
De lijnen worden vereenvoudigd (Douglas-Peucker) en afgerond, zodat het bestand klein blijft.

Gebruik: python scripts/landgrenzen.py   (alleen nodig als de grenzen opnieuw moeten worden gemaakt)
"""
import json
import pathlib
import urllib.request

BRON = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
DOEL = pathlib.Path(__file__).resolve().parent.parent / "data" / "landgrenzen.geojson"
TOLERANTIE = 0.03  # graden, ongeveer 3 km
DECIMALEN = 2

# Natural Earth-naam -> naam die de site gebruikt (gelijk aan het oude kaartbestand)
ALIAS = {
    "United States of America": "United States", "South Korea": "Korea", "North Korea": "Dem. Rep. Korea",
    "Czechia": "Czech Rep.", "North Macedonia": "Macedonia", "eSwatini": "Swaziland", "Laos": "Lao PDR",
    "Republic of the Congo": "Congo", "Cabo Verde": "Cape Verde", "Faeroe Is.": "Faeroe Is.",
    "Åland": "Aland", "São Tomé and Principe": "São Tomé and Principe", "Côte d'Ivoire": "Côte d'Ivoire",
}
NL_FIX = {"Korea": "Zuid-Korea", "Dem. Rep. Korea": "Noord-Korea"}


def perp(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def dp(pts, tol):
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0, None
        for k in range(i + 1, j):
            d = perp(pts[k], pts[i], pts[j])
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(pts, keep) if k]


def ring(r):
    r = dp(r, TOLERANTIE)
    out = []
    for x, y in r:
        q = [round(x, DECIMALEN), round(y, DECIMALEN)]
        if not out or out[-1] != q:
            out.append(q)
    return out if len(out) >= 4 else None


def polygon(poly):
    rings = [ring(r) for r in poly]
    if not rings[0]:
        return None
    return [rings[0]] + [r for r in rings[1:] if r]


def main():
    with urllib.request.urlopen(BRON, timeout=60) as f:
        g = json.load(f)
    feats = []
    for f in g["features"]:
        P = f["properties"]
        if P["ADM0_A3"] == "ATA":
            continue
        name = P["NAME"]
        en = ALIAS.get(name, name)
        geom = f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        polys = [p for p in (polygon(p) for p in polys) if p]
        if not polys:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"en": en, "nl": NL_FIX.get(en, P.get("NAME_NL") or name), "a3": P["ADM0_A3"]},
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
        })
    DOEL.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False,
                               separators=(",", ":")), encoding="utf-8")
    print(f"{len(feats)} landen, {DOEL.stat().st_size // 1024} kB -> {DOEL}")


if __name__ == "__main__":
    main()
