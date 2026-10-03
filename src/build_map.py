# -*- coding: utf-8 -*-
"""build_map.py — Kartendaten + vereinfachte Kreisgeometrie fuer GitHub Pages.

Liest data/merged_raw_v3.json (109 Spalten x 400 Kreise inkl. Registry)
und raw/vg250/.../VG250_KRS.shp (BKG, EPSG:25832) und schreibt:

  _site/data/map_data.json    — Spalten-Metadaten + Werte je Kreis
  _site/data/kreise.geo.json  — Kreisgrenzen, vereinfacht (WGS84)

Verarbeitung der Geometrie (nur Standardbibliothek):
  1. SHP-Polygone + DBF-AGS je Record lesen (Multipart je AGS sammeln)
  2. Ringe anhand der Vorzeichen-Shoelace-Flaeche in Aussen-/Lochringe
     trennen, Lochringe ihrem tragenden Aussenring zuordnen
  3. UTM 32N (EPSG:25832) -> WGS84 projizieren (Inverse
     Transversal-Mercator-Formeln, WGS84-Ellipsoid)
  4. Douglas-Peucker-Vereinfachung (EPSILON Grad, ~100 m)
  5. GeoJSON (Polygon/MultiPolygon je AGS, 5-stellig als String)

Verifikation:
  - Join: Menge der GeoJSON-AGS == Menge der rs aus merged_raw_v3
    (beides 400, 5-stellig, fuehrende Nullen)
  - Geometrie-Flaeche (Shoelace, UTM-Meter) je AGS gegen GENESIS
    flaeche_km2: Median-Abweichung wird berichtet (nur Warnung)

Aufruf:  python3 src/build_map.py
Voraussetzung: fetch_vg250.py + Pipeline (merge.py) gelaufen.

Attribution (GeoNutzV): "© GeoBasis-DE / BKG" — auf der Karte sichtbar.
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw")
SITE_DATA = os.path.join(ROOT, "_site", "data")

SHP = os.path.join(RAW, "vg250", "vg250_ebenen_1231", "VG250_KRS.shp")
DBF = os.path.join(RAW, "vg250", "vg250_ebenen_1231", "VG250_KRS.dbf")
V3 = os.path.join(DATA, "merged_raw_v3.json")

EPSILON = 0.0015          # Douglas-Peucker-Toleranz in Grad (~150 m)
MIN_RING_PTS = 4        # Ringe mit weniger Punkten fallen weg

# UTM Zone 32N / WGS84
K0 = 0.9996
A = 6378137.0
F = 1.0 / 298.257223563
E2 = F * (2.0 - F)
EP2 = E2 / (1.0 - E2)
LON0 = math.radians(9.0)
M0 = 0.0  # Meridionalbogen am Breitengrad des Ursprungs (hier 0 Grad)


def read_dbf_ags(path):
    """DBF -> AGS-Liste je Record (geloeschte Zeilen ueberspringen)."""
    with open(path, "rb") as f:
        dbf = f.read()
    hlen = struct.unpack("<H", dbf[8:10])[0]
    rlen = struct.unpack("<H", dbf[10:12])[0]
    fields = []
    off = 32
    while dbf[off] != 0x0D:
        fd = dbf[off:off + 32]
        fields.append((fd[:11].split(b"\x00")[0].decode("latin1"), fd[16]))
        off += 32
    offs = {}
    c = 1
    for name, ln in fields:
        offs[name] = (c, ln)
        c += ln
    ags_off, ags_len = offs["AGS"]
    out = []
    n = (len(dbf) - hlen) // rlen
    for i in range(n):
        r = dbf[hlen + i * rlen: hlen + (i + 1) * rlen]
        if r[0:1] == b"*":
            continue
        out.append(r[ags_off:ags_off + ags_len].decode("latin1").strip())
    return out


def read_shp_rings_by_ags(shp_path, ags_list):
    """SHP -> {ags: [ring, ...]}, ring = [(x, y), ...] (UTM-Meter).

    VG250-Konvention wie parse_nsg.py: Punktpuffer als Folge (x, y) je
    Record; Teile (parts) starten an Punktindex s und enden bei e.
    """
    with open(shp_path, "rb") as f:
        shp = f.read()
    rings = {}
    rec = 0
    pos = 100
    while pos + 8 <= len(shp):
        clen = struct.unpack(">i", shp[pos + 4:pos + 8])[0] * 2
        body = shp[pos + 8:pos + 8 + clen]
        pos += 8 + clen
        if not body:
            continue
        stype = struct.unpack("<i", body[0:4])[0]
        if stype not in (5, 15, 25):  # Polygon (M/Z-Varianten)
            rec += 1
            continue
        nparts = struct.unpack("<i", body[36:40])[0]
        npts = struct.unpack("<i", body[40:44])[0]
        # Punktkoordinaten: x0, y0, x1, y1, ... je Punkt zwei f8
        xs = struct.unpack_from("<%dd" % npts, body, 44 + 4 * nparts)
        # Achtung: x und y liegen verschachtelt (x0,y0,x1,y1,...)
        flat = struct.unpack_from("<%dd" % (2 * npts), body, 44 + 4 * nparts)
        parts = struct.unpack_from("<%di" % nparts, body, 44)
        bounds = [0] + list(parts) + [npts]
        for s, e in zip(bounds[:-1], bounds[1:]):
            if e - s < 3:
                continue
            ring = [(flat[2 * i], flat[2 * i + 1]) for i in range(s, e)]
            rings.setdefault(ags_list[rec], []).append(ring)
        rec += 1
    assert rec == len(ags_list), (rec, len(ags_list))
    return rings


def signed_area(ring):
    """Shoelace-Vorzeichenflaeche (mathematisch positiv = gegen UZS)."""
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def point_in_ring(pt, ring):
    """Even-Odd-Test: Liegt pt im Ring?"""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def utm32_to_wgs84(x, y):
    """EPSG:25832 -> (lon, lat) in Grad (inverse Transversal Mercator)."""
    m = y / K0
    mu = (m + M0) / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    t1 = math.tan(phi1) ** 2
    c1 = EP2 * math.cos(phi1) ** 2
    dd = ((x - 500000.0) / K0) / n1   # False Easting Zone 32 abziehen
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        dd ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * EP2) * dd ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * EP2 - 3 * c1 ** 2)
        * dd ** 6 / 720)
    lon = LON0 + (dd - (1 + 2 * t1 + c1) * dd ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * EP2
                     + 24 * t1 ** 2) * dd ** 5 / 120) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def perp_dist(pt, a, b):
    """Abstand Punkt -> Strecke (a, b)."""
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def douglas_peucker(ring, eps):
    """Iteratives DP; ring geschlossen -> offen schneiden (Endpunkt doppelt)."""
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        dmax, idx = 0.0, -1
        for i in range(s + 1, e):
            d = perp_dist(pts[i], pts[s], pts[e])
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    out = [p for p, k in zip(pts, keep) if k]
    out.append(out[0])  # wieder schliessen
    return out


def build_geometry():
    ags_list = read_dbf_ags(DBF)
    rings_by_ags = read_shp_rings_by_ags(SHP, ags_list)
    print("SHP: %d AGS, %d Ringe" % (len(rings_by_ags),
                                     sum(len(v) for v in rings_by_ags.values())))
    verts_in = sum(len(r) for v in rings_by_ags.values() for r in v)

    feats = []
    verts_out = 0
    dropped_rings = 0
    areas_km2 = {}
    for ags, rings in sorted(rings_by_ags.items()):
        # ESRI-Konvention: Aussenring im Uhrzeigersinn (negative Flaeche,
        # y nach oben) — LoicherINGE gegen den Uhrzeigersinn (positiv).
        outers = [r for r in rings if signed_area(r) < 0] or rings
        holes = [r for r in rings if r not in outers]
        polygons = [[o] for o in outers]
        for h in holes:
            host = None
            for cand in polygons:
                if point_in_ring(h[0], cand[0]):
                    host = cand
                    break
            if host is not None:
                host.append(h)
            else:
                polygons.append([h])
                dropped_rings += 0  # Lochnung ohne Trager: als eigener Ring
        area = sum(abs(signed_area(r)) for r in rings) / 1e6
        areas_km2[ags] = area

        polys_out = []
        for poly in polygons:
            simp = []
            for ring in poly:
                sr = douglas_peucker(
                    [utm32_to_wgs84(x, y) for x, y in ring], EPSILON)
                # auf 5 Dezimalstellen (~1 m) runden, Ring geschlossen halten
                sr = [(round(lon, 5), round(lat, 5)) for lon, lat in sr]
                sr[-1] = sr[0]
                if len(sr) >= MIN_RING_PTS:
                    simp.append(sr)
                else:
                    dropped_rings += 1
            if simp:
                polys_out.append(simp)
                verts_out += sum(len(r) for r in simp)
        if not polys_out:
            continue
        geom_type = "Polygon" if len(polys_out) == 1 else "MultiPolygon"
        coords = polys_out[0] if geom_type == "Polygon" else \
            [p for p in polys_out]
        feats.append({
            "type": "Feature",
            "properties": {"rs": ags},
            "geometry": {"type": geom_type, "coordinates": coords},
        })
    print("Vereinfachung: %d -> %d Punkte (%.1f%% behalten), %d Ringe weg"
          % (verts_in, verts_out, 100.0 * verts_out / max(verts_in, 1),
             dropped_rings))
    return {"type": "FeatureCollection", "features": feats}, areas_km2


def main():
    with open(V3, encoding="utf-8") as f:
        raw = json.load(f)
    columns, rows = raw["columns"], raw["rows"]
    assert len(columns) == 109 and len(rows) == 400

    fc, areas_km2 = build_geometry()
    rs_data = {str(r["rs"]).zfill(5) for r in rows}
    rs_geom = {f["properties"]["rs"].zfill(5) for f in fc["features"]}
    missing = rs_data - rs_geom
    extra = rs_geom - rs_data
    assert not missing, "Kreise ohne Geometrie: %s" % sorted(missing)
    assert not extra, "Geometrie ohne Daten: %s" % sorted(extra)
    for f in fc["features"]:
        f["properties"]["rs"] = f["properties"]["rs"].zfill(5)

    # Flaechen-Abgleich gegen GENESIS flaeche_km2 (Bericht, keine Assertion)
    fl = {str(r["rs"]).zfill(5): r.get("flaeche_km2") for r in rows}
    devs = []
    for rs, a in areas_km2.items():
        if fl.get(rs):
            devs.append(abs(a - fl[rs]) / fl[rs])
    devs.sort()
    med = devs[len(devs) // 2] if devs else 0.0
    print("Flaechenabgleich vs. GENESIS: Median-Abweichung %.2f%% (n=%d)"
          % (100 * med, len(devs)))

    os.makedirs(SITE_DATA, exist_ok=True)
    geo_path = os.path.join(SITE_DATA, "kreise.geo.json")
    data_path = os.path.join(SITE_DATA, "map_data.json")
    with open(geo_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"columns": columns, "rows": rows}, f, ensure_ascii=False,
                  separators=(",", ":"))
    print("OK: %s (%d B)" % (geo_path, os.path.getsize(geo_path)))
    print("OK: %s (%d B)" % (data_path, os.path.getsize(data_path)))
    b = fc["features"][0]["geometry"]
    print("Beispiel-Ring (erste 3 Punkte): %s"
          % str(b["coordinates"][0][:3])[:120])


if __name__ == "__main__":
    main()
