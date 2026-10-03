# -*- coding: utf-8 -*-
"""fetch_nsg.py — BfN-WFS Naturschutzgebiete herunterladen (19 Chunks a 500).

Laedt die NSG-Geometrien (GML, EPSG:25832, nur posList) vom BfN-WFS in
19 Chunks zu je 500 Gebieten nach raw/nsg/chunk_000..018.xml
(ca. 106 MB gesamt, 9.035 Features).

Wichtig: Der WFS lehnt Default-User-Agents mit 403 ab — Browser-UA setzen!

URL-Muster (verifiziert am 03.10.2026):
  https://geodienste.bfn.de/ogc/wfs/schutzgebiet?service=WFS&version=2.0.0&request=GetFeature&typenames=schutzgebiet:Naturschutzgebiete&count=500&startindex={N}

Aufruf:  python3 src/fetch_nsg.py   [--force]
"""
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "raw", "nsg")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BASE = ("https://geodienste.bfn.de/ogc/wfs/schutzgebiet"
        "?service=WFS&version=2.0.0&request=GetFeature"
        "&typenames=schutzgebiet:Naturschutzgebiete"
        "&count=500&startindex={idx}")

N_CHUNKS = 19  # 9.035 Features -> Startindex 0..9000


def main():
    os.makedirs(OUT, exist_ok=True)
    for i in range(N_CHUNKS):
        idx = i * 500
        dest = os.path.join(OUT, "chunk_%03d.xml" % i)
        if os.path.exists(dest) and "--force" not in sys.argv:
            print("existiert:", dest)
            continue
        url = BASE.format(idx=idx)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=240) as r, open(dest, "wb") as f:
                    f.write(r.read())
                break
            except Exception as e:  # noqa: BLE001
                print("Chunk %d fehlgeschlagen (%s), Versuch %d" % (i, e, attempt + 1))
                time.sleep(5)
        else:
            sys.exit("Abbruch: Chunk %d endgueltig fehlgeschlagen" % i)
        print("OK:", dest, os.path.getsize(dest), "Bytes")
    print("Fertig: %d Chunks in %s" % (N_CHUNKS, OUT))


if __name__ == "__main__":
    main()
