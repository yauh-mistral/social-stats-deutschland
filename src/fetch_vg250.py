# -*- coding: utf-8 -*-
"""fetch_vg250.py — BKG-Verwaltungsgrenzen (VG250) herunterladen.

Laedt die BKG-Verwaltungsgrenzen 1:250.000 (Ebenen, Stand 31.12.) als
Shape-Zip nach raw/vg250.zip und entpackt sie nach raw/vg250/.
Wichtig fuer parse_nsg.py: VG250_KRS.shp (Kreisgrenzen, EPSG:25832).

URL (verifiziert am 03.10.2026 — Achtung, Pfadbestandteil "12-31", nicht "31-12"):
  https://daten.gdz.bkg.bund.de/produkte/vg/vg250_ebenen_1231/aktuell/vg250_12-31.utm32s.shape.ebenen.zip

Aufruf:  python3 src/fetch_vg250.py
"""
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "raw")
ZIP_PATH = os.path.join(RAW, "vg250.zip")

URL = ("https://daten.gdz.bkg.bund.de/produkte/vg/vg250_ebenen_1231/aktuell/"
       "vg250_12-31.utm32s.shape.ebenen.zip")


def main():
    os.makedirs(RAW, exist_ok=True)
    if os.path.exists(ZIP_PATH) and "--force" not in sys.argv:
        print("existiert:", ZIP_PATH)
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=240) as r, open(ZIP_PATH, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        print("OK:", ZIP_PATH, os.path.getsize(ZIP_PATH), "Bytes")

    out_dir = os.path.join(RAW, "vg250")
    if os.path.exists(out_dir):
        print("bereits entpackt:", out_dir)
        return
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(out_dir)
    print("entpackt nach:", out_dir)


if __name__ == "__main__":
    main()
