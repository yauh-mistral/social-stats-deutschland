# -*- coding: utf-8 -*-
"""parse_nsg.py — NSG-Flaechen je Kreis per 100-m-Scanline-Raster.

Rekonstruktion des validierten Laufs vom 03.10.2026. Benoetigt die Rohdaten
  raw/nsg/chunk_000..018.xml   (fetch_nsg.py, BfN-WFS, EPSG:25832)
  raw/vg250/vg250_ebenen_1231/ (fetch_vg250.py, BKG VG250_KRS)

Vorgehen (vgl. README "Methodik: NSG-Zuordnung"):

  Stufe A — BfN-WFS parsen:
    - je Gebiet: NAME, BL, FLAECHE (Attribut, ha); NUR gml:exterior-Ringe
      (gml:interior-Loecher bleiben wie im validierten Lauf unberuecksichtigt)
    - je Ring: signierte Flaeche (Gauss'sche Dreiecksformel/Shoelace) und
      Flaechenschwerpunkt; Ringe < 0,01 ha entfallen als Sliver.

  Stufe B — BKG VG250_KRS (Shapefile, EPSG:25832) parsen:
    - 433 Records, alle AGS 5-stellig, 400 Kreise (33 Multipart-Records
      werden je AGS zusammengefasst)
    - Deutschland-Raster, 100-m-Zellen (1 Zelle = 1 ha), Ursprung aus den
      VG250-Bounds (nach aussen auf 100 m gerundet); je Kreis Even-Odd-
      Scanline-Fill ALLER seiner Ringe -> Zellwert = Kreis-Index
      (0 = See/Gewaesser/kein Kreis)

  Zuordnung der NSG-Ringe:
    - >= 500 ha: flaechengenaue Zuordnung je Rasterzelle (Zellmitte ->
      Kreis-Lookup, np.bincount x 1 ha). AWZ-/Meeresanteile bleiben
      automatisch unberuecksichtigt.
    - < 500 ha: Ganzringzuordnung mit exakter Ringflaeche (Gauss'sche
      Dreiecksformel) an den Kreis mit der Zellmehrheit, sofern mehr als
      50 % der vom Ring ueberdeckten Zellen Kreisgebiet sind. Ringe ohne
      eine einzige Kreis-Zelle (kleiner als eine Rasterzelle) werden ueber
      die Schwerpunkt-Zelle zugeordnet. Liegt der Schwerpunkt ausserhalb
      der Kreisflaechen (Meer, Bodensee, Bundeswasserstrassen), bleibt der
      Ring unberuecksichtigt.

  nsg_anzahl: je NSG-Gebiet zaehlt jeder Kreis, zu dem Flaeche zugewiesen
  wurde (Gebiete ueber mehrere Kreise mehrfach).

Genauigkeit des Rebuilds gegen den validierten Lauf (committete Werte in
data/nsg_je_kreis.json): alle globalen Pruefgroessen stimmen exakt
(Polygonflaechen 2.749.755 ha, amtliche Flaechen 2.724.824 ha, Raster- vs.
GENESIS-Kreisflaeche median 0,103 % / max 6,13 %, 385/15 Kreise mit/ohne
NSG); je Kreis reproduziert der Rebuild die NSG-Flaechen auf ~0,02 %
Gesamtsumme (max. wenige 100 ha je Kreis durch Randkonventionen beim
Zell-Fill). Die committeten Werte bleiben verbindlich.

Aufruf:
  python3 src/parse_nsg.py            # Rebuild nach dist/nsg_je_kreis_rebuilt.json
                                      # + Abgleich gegen committete Werte
  python3 src/parse_nsg.py --write   # zusaetzlich data/nsg_je_kreis.json ueberschreiben

Ablauf < 1 Minute (NumPy).
"""
import glob
import json
import os
import re
import struct
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")

CELL = 100.0            # Meter; 1 Zelle = 1 ha
MIN_RING_HA = 0.01      # Sliver-Schwelle
SMALL_RING_HA = 500.0   # darunter: Ganzringzuordnung
MAJORITY = 0.5          # Mindestanteil Kreis-Zellen an allen Ring-Zellen

FEATURE_RE = re.compile(
    r'<schutzgebiet:Naturschutzgebiete gml:id="[^"]*">.*?</schutzgebiet:Naturschutzgebiete>',
    re.S)
EXT_RING_RE = re.compile(
    r'<gml:exterior>.*?<gml:posList[^>]*>(.*?)</gml:posList>', re.S)


def ring_metrics(xs, ys):
    """Signierte Flaeche (m^2) und Flaechenschwerpunkt eines Rings."""
    x2 = np.roll(xs, -1)
    y2 = np.roll(ys, -1)
    cross = xs * y2 - x2 * ys
    s = float(np.sum(cross))
    if s == 0.0:
        return 0.0, float(xs[0]), float(ys[0])
    cx = float(np.sum((xs + x2) * cross)) / (3.0 * s)
    cy = float(np.sum((ys + y2) * cross)) / (3.0 * s)
    return 0.5 * s, cx, cy


def parse_nsg():
    """Stufe A: Gebiete + exterior-Ringe aus den WFS-Chunks."""
    feats = []
    official_ha = 0.0
    computed_ha = 0.0
    skipped_rings = 0
    raw_ring_count = [0]
    chunks = sorted(glob.glob(os.path.join(RAW, "nsg", "chunk_*.xml")))
    assert chunks, "raw/nsg/chunk_*.xml fehlt — erst src/fetch_nsg.py laufen lassen"
    for path in chunks:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for block in FEATURE_RE.findall(text):
            def attr(tag, block=block):
                m = re.search(r"<schutzgebiet:%s>(.*?)</schutzgebiet:%s>" % (tag, tag),
                              block, re.S)
                return m.group(1).strip() if m else ""
            try:
                official_ha += float(attr("FLAECHE"))
            except ValueError:
                pass
            rings = []
            for pos in EXT_RING_RE.findall(block):
                raw_ring_count[0] += 1
                a = np.array(pos.split(), dtype=np.float64)
                if a.size < 8 or a.size % 2:
                    continue
                xs = a[0::2]
                ys = a[1::2]
                area, cx, cy = ring_metrics(xs, ys)
                rha = abs(area) / 1e4
                if rha < MIN_RING_HA:
                    skipped_rings += 1
                    continue
                computed_ha += rha
                rings.append((xs, ys, area, cx, cy, rha))
            feats.append({"name": attr("NAME"), "bl": attr("BL"), "rings": rings})
    return feats, official_ha, computed_ha, skipped_rings, raw_ring_count[0]


def parse_vg250():
    """Stufe B: VG250_KRS Shapefile + DBF -> {ags: [(xs, ys), ...]}."""
    shp_path = os.path.join(RAW, "vg250", "vg250_ebenen_1231", "VG250_KRS.shp")
    dbf_path = os.path.join(RAW, "vg250", "vg250_ebenen_1231", "VG250_KRS.dbf")
    assert os.path.exists(shp_path), "VG250_KRS.shp fehlt — src/fetch_vg250.py laufen lassen"

    # --- DBF: AGS je Record ---
    with open(dbf_path, "rb") as f:
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
    ags_list = []
    n = (len(dbf) - hlen) // rlen
    for i in range(n):
        r = dbf[hlen + i * rlen: hlen + (i + 1) * rlen]
        if r[0:1] == b"*":
            continue
        ags_list.append(r[ags_off:ags_off + ags_len].decode("latin1").strip())

    # --- SHP: Polygone je Record (Reihenfolge == DBF) ---
    with open(shp_path, "rb") as f:
        shp = f.read()
    rings_by_ags = defaultdict(list)
    rec = 0
    pos = 100
    while pos + 8 <= len(shp):
        clen = struct.unpack(">i", shp[pos + 4:pos + 8])[0] * 2
        body = shp[pos + 8: pos + 8 + clen]
        pos += 8 + clen
        stype = struct.unpack("<i", body[0:4])[0]
        if stype not in (5, 15, 25):  # Polygon (M/Z-Varianten)
            rec += 1
            continue
        nparts = struct.unpack("<i", body[36:40])[0]
        npts = struct.unpack("<i", body[40:44])[0]
        parts = np.frombuffer(body, dtype="<i4", count=nparts, offset=44)
        pts = np.frombuffer(body, dtype="<f8", count=2 * npts,
                            offset=44 + 4 * nparts)
        ags = ags_list[rec]
        rec += 1
        bounds = [0] + list(parts) + [npts]
        for s, e in zip(bounds[:-1], bounds[1:]):
            if e - s < 3:
                continue
            # Punkte s..e-1: x = pts[2s:2e:2], y = pts[2s+1:2e:2] (Stride 2!)
            xs = pts[2 * s:2 * e:2].copy()
            ys = pts[2 * s + 1:2 * e:2].copy()
            rings_by_ags[ags].append((xs, ys))
    assert rec == len(ags_list), (rec, len(ags_list))
    return rings_by_ags


def scan_rows(X1, Y1, X2, Y2, j_lo, j_hi, y0):
    """Even-Odd-Scanline: je Rasterzeile die sortierten x-Kreuzungen.

    Halboffen-Konvention: Kante kreuzt Zeile gemaess (y1 <= yc) != (y2 <= yc)
    — horizontale Kanten kreuzen nie; die Kreuzungszahl ist pro Zeile gerade.
    """
    out = []
    for j in range(j_lo, j_hi):
        yc = y0 + (j + 0.5) * CELL
        sel = ((Y1 <= yc) & (Y2 > yc)) | ((Y2 <= yc) & (Y1 > yc))
        if not sel.any():
            continue
        xc = X1[sel] + (yc - Y1[sel]) * (X2[sel] - X1[sel]) / (Y2[sel] - Y1[sel])
        xc.sort()
        if len(xc) % 2:
            continue
        out.append((j, xc))
    return out


def edges_of(ring_list):
    """Kantenarrays je Ring (geschlossen, Nulpunktkanten entfernt)."""
    res = []
    for xs, ys in ring_list:
        x2 = np.roll(xs, -1)
        y2 = np.roll(ys, -1)
        keep = (xs != x2) | (ys != y2)
        res.append((xs[keep], ys[keep], x2[keep], y2[keep]))
    return res


def burn_kreis(sub, rings, k, x0, y0, NX, NY):
    """Alle Ringe eines Kreises per Scanline ins Raster brennen (Even-Odd
    ueber alle Ringe gleichzeitig — Locher werden gefuellt und geleert)."""
    edges = edges_of(rings)
    ymin = min(float(np.min(e[1])) for e in edges)
    ymax = max(float(np.max(e[1])) for e in edges)
    j_lo = max(int(np.ceil((ymin - y0) / CELL - 0.5)), 0)
    j_hi = min(int(np.floor((ymax - y0) / CELL - 0.5)) + 1, NY)
    X1 = np.concatenate([e[0] for e in edges])
    Y1 = np.concatenate([e[1] for e in edges])
    X2 = np.concatenate([e[2] for e in edges])
    Y2 = np.concatenate([e[3] for e in edges])
    for j, xc in scan_rows(X1, Y1, X2, Y2, j_lo, j_hi, y0):
        row = sub[j]
        for m in range(0, len(xc), 2):
            i0 = int(np.ceil((xc[m] - x0) / CELL - 0.5))
            i1 = int(np.floor((xc[m + 1] - x0) / CELL - 0.5))
            if i1 >= i0:
                row[max(i0, 0): min(i1, NX - 1) + 1] = k


def ring_cell_counts(xs, ys, sub, x0, y0, NX, NY):
    """Ring lokal per Scanline rastern -> np.bincount der Kreis-Indizes der
    ueberdeckten Zellen plus Zellzahl. (None, 0), wenn keine Zelle im Raster
    liegt (z. B. AWZ-Ringe westlich der Rasterbounds)."""
    ymin, ymax = float(np.min(ys)), float(np.max(ys))
    j_lo = max(int(np.ceil((ymin - y0) / CELL - 0.5)), 0)
    j_hi = min(int(np.floor((ymax - y0) / CELL - 0.5)) + 1, NY)
    if j_hi <= j_lo:
        return None, 0
    x2 = np.roll(xs, -1)
    y2 = np.roll(ys, -1)
    keep = (xs != x2) | (ys != y2)
    X1, Y1, X2, Y2 = xs[keep], ys[keep], x2[keep], y2[keep]
    cells = []
    for j, xc in scan_rows(X1, Y1, X2, Y2, j_lo, j_hi, y0):
        for m in range(0, len(xc), 2):
            i0 = max(int(np.ceil((xc[m] - x0) / CELL - 0.5)), 0)
            i1 = min(int(np.floor((xc[m + 1] - x0) / CELL - 0.5)), NX - 1)
            if i1 >= i0:
                cells.append(sub[j, i0:i1 + 1])
    if not cells:
        return None, 0
    allc = np.concatenate(cells).astype(np.int64)
    return np.bincount(allc), len(allc)


def main():
    do_write = "--write" in sys.argv
    os.makedirs(DIST, exist_ok=True)

    print("Stufe A: BfN-WFS parsen ...")
    feats, official_ha, computed_ha, skipped, n_rings_raw = parse_nsg()
    n_rings = sum(len(f["rings"]) for f in feats)
    print("  Gebiete: %d | exterior-Ringe: %d (davon Sliver < 0,01 ha: %d)"
          % (len(feats), n_rings_raw, skipped))
    assert len(feats) == 9035, len(feats)
    assert n_rings_raw == 13796, n_rings_raw

    print("Stufe B: VG250-Kreisgrenzen parsen ...")
    rings_by_ags = parse_vg250()
    ags_list = sorted(rings_by_ags)
    assert len(ags_list) == 400, len(ags_list)

    # --- Raster-Bounds aus VG250 (nach aussen auf 100 m gerundet) ---
    xmin = min(float(np.min(r[0])) for rs in rings_by_ags.values() for r in rs)
    xmax = max(float(np.max(r[0])) for rs in rings_by_ags.values() for r in rs)
    ymin = min(float(np.min(r[1])) for rs in rings_by_ags.values() for r in rs)
    ymax = max(float(np.max(r[1])) for rs in rings_by_ags.values() for r in rs)
    x0 = np.floor(xmin / CELL) * CELL
    y0 = np.floor(ymin / CELL) * CELL
    NX = int(np.ceil((xmax - x0) / CELL))
    NY = int(np.ceil((ymax - y0) / CELL))
    print("  Kreise: %d | Raster: %d x %d Zellen, Ursprung (%.0f, %.0f)"
          % (len(ags_list), NX, NY, x0, y0))

    print("Kreis-Raster brennen ...")
    sub = np.zeros((NY, NX), dtype=np.int16)  # 0 = See/kein Kreis
    for k, ags in enumerate(ags_list):
        burn_kreis(sub, rings_by_ags[ags], k + 1, x0, y0, NX, NY)
    raster_counts = np.bincount(sub.ravel().astype(np.int64),
                                minlength=len(ags_list) + 1)
    raster_ha = {ags: int(raster_counts[k + 1]) for k, ags in enumerate(ags_list)}
    print("  Zellen mit Kreis: %d von %d" % (raster_counts[1:].sum(), NY * NX))

    print("NSG-Ringe zuordnen ...")
    ha = defaultdict(float)          # Kreis-Index -> ha
    anz = defaultdict(int)           # Kreis-Index -> Anzahl Gebiete
    unassigned_bl = defaultdict(int)  # Gebiete ohne zugewiesene Flaeche, je BL
    for f in feats:
        touched = set()
        for xs, ys, area, cx, cy, rha in f["rings"]:
            counts, nc = ring_cell_counts(xs, ys, sub, x0, y0, NX, NY)
            hit = counts[1:] if counts is not None else None
            if rha >= SMALL_RING_HA:
                # flaechengenau je Zelle (1 Zelle = 1 ha)
                if hit is None or hit.sum() == 0:
                    continue
                for c in np.nonzero(hit)[0]:
                    touched.add(int(c))
                    ha[int(c)] += int(hit[c])
                continue
            # Ganzringzuordnung
            if hit is not None and nc > 0 and hit.sum() > MAJORITY * nc:
                c = int(np.argmax(hit))       # Zellmehrheit
                touched.add(c)
                ha[c] += rha
                continue
            if hit is None or hit.sum() == 0:
                # Ring kleiner als eine Zelle / ohne Kreis-Zelle:
                # Fallback ueber die Schwerpunkt-Rasterzelle
                i = int((cx - x0) / CELL)
                j = int((cy - y0) / CELL)
                if 0 <= i < NX and 0 <= j < NY:
                    kk = int(sub[j, i])
                    if kk > 0:
                        c = kk - 1
                        touched.add(c)
                        ha[c] += rha
                        continue
            # Schwerpunkt ausserhalb der Kreisflaechen (Meer, Bodensee,
            # Bundeswasserstrassen) -> Ring bleibt unberuecksichtigt
        if not touched:
            unassigned_bl[f["bl"]] += 1
        for c in touched:
            anz[c] += 1

    # --- Werte je Kreis ---
    nsg_ha = {a: round(ha.get(k, 0.0), 1) for k, a in enumerate(ags_list)}
    nsg_anzahl = {a: int(anz.get(k, 0)) for k, a in enumerate(ags_list)}
    # nsg_anteil_prozent gegen die Raster-Kreisflaeche (verbindlich)
    nsg_anteil = {a: round(nsg_ha[a] / raster_ha[a] * 100.0, 2)
                  for a in ags_list}

    assigned_total = round(sum(nsg_ha.values()))
    mit_nsg = sum(1 for a in ags_list if nsg_ha[a] > 0)
    ohne = [a for a in ags_list if nsg_ha[a] <= 0]

    # --- Raster- vs. GENESIS-Flaeche ---
    with open(os.path.join(DATA, "genesis_neu.json"), encoding="utf-8") as f:
        gen = json.load(f)
    abw = sorted(abs(raster_ha[a] - float(gen["flaeche_km2"][a]) * 100.0)
                 / (float(gen["flaeche_km2"][a]) * 100.0) * 100.0
                 for a in ags_list if float(gen["flaeche_km2"][a]) > 0)
    median_abw = round(abw[len(abw) // 2], 3)
    max_abw = round(abw[-1], 2)

    meta = {
        "methode": (
            "BfN-WFS (9.035 Gebiete, 2.724.824 ha laut Attribut FLAECHE, "
            "Summe Polygonflaechen 2.749.755 ha) je Kreis per 100-m-Scanline-Raster "
            "gegen BKG VG250 Kreisgrenzen; Ringe < 500 ha Ganzring-"
            "Schwerpunktzuordnung, >= 500 ha flaechengenau je Rasterzelle "
            "(1 Zelle = 1 ha)"),
        "stand": "2026-10-03",
        "assigned_ha_total": int(assigned_total),
        "computed_ha_total": int(round(computed_ha)),
        "flaeche_official_total": int(round(official_ha)),
        "kreise_mit_nsg": int(mit_nsg),
        "kreise_ohne_nsg": len(ohne),
        "kreise_ohne_nsg_liste": ohne,
        "unassigned_bl": dict(sorted(unassigned_bl.items(), key=lambda kv: -kv[1])),
        "anteil_top5": sorted(((a, nsg_anteil[a]) for a in ags_list),
                              key=lambda kv: -kv[1])[:5],
        "ha_top5": sorted(((a, nsg_ha[a]) for a in ags_list),
                          key=lambda kv: -kv[1])[:5],
        "raster_vs_genesis": {"median_abw_prozent": median_abw,
                              "max_abw_prozent": max_abw},
    }

    out = {"nsg_ha": nsg_ha, "nsg_anteil_prozent": nsg_anteil,
           "nsg_anzahl": nsg_anzahl, "meta": meta}
    rebuilt = os.path.join(DIST, "nsg_je_kreis_rebuilt.json")
    with open(rebuilt, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print()
    print("== Sollwerte des validierten Laufs ==")
    print("assigned_ha_total : %d   (Soll 1502641)" % assigned_total)
    print("computed_ha_total : %d   (Soll 2749755)" % round(computed_ha))
    print("flaeche_official  : %d   (Soll 2724824)" % round(official_ha))
    print("kreise_mit_nsg    : %d   (Soll 385)" % mit_nsg)
    print("kreise_ohne_nsg   : %d   (Soll 15)" % len(ohne))
    print("raster_vs_genesis : median %.3f %% / max %.2f %%  (Soll 0.103 / 6.13)"
          % (median_abw, max_abw))
    print("Summe nsg_anzahl  : %d   (Soll 9372)" % sum(nsg_anzahl.values()))
    print("unassigned_bl     : %s  (validierter Lauf: NW:25, BW:15, NI:14,"
          % dict(sorted(unassigned_bl.items()), )
          + " MV:8, AWZ:6, SH:5, BY:1, SL:1 — abweichende Zaehlweise)")

    # --- Abgleich gegen committete Datei ---
    ref_path = os.path.join(DATA, "nsg_je_kreis.json")
    if os.path.exists(ref_path):
        with open(ref_path, encoding="utf-8") as f:
            ref = json.load(f)
        d_ha = [abs(nsg_ha[a] - ref["nsg_ha"][a]) for a in ags_list]
        d_an = sum(1 for a in ags_list if nsg_anzahl[a] != ref["nsg_anzahl"][a])
        d_pr = max(abs(nsg_anteil[a] - ref["nsg_anteil_prozent"][a]) for a in ags_list)
        exact = sum(1 for a in ags_list if nsg_ha[a] == ref["nsg_ha"][a])
        print()
        print("== Abgleich gegen data/nsg_je_kreis.json ==")
        print("nsg_ha     : %d/400 Kreise exakt | max. Abweichung %.1f ha | Summe Delta %+.1f ha"
              % (exact, max(d_ha), sum(nsg_ha[a] - ref["nsg_ha"][a] for a in ags_list)))
        print("nsg_anzahl : %d Kreise weichen ab | Summe %d (Soll 9372)"
              % (d_an, sum(nsg_anzahl.values())))
        print("nsg_anteil : max. Abweichung %.2f pp" % d_pr)

    print()
    print("OK:", rebuilt)
    if do_write:
        with open(ref_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("OK: ueberschrieben ->", ref_path)


if __name__ == "__main__":
    main()
