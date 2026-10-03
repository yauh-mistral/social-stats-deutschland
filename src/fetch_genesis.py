# -*- coding: utf-8 -*-
"""fetch_genesis.py — GENESIS-Regionalstatistik-Tabellen herunterladen.

Laedt die vier CSV-Tabellen (je ~45-440 KB, ISO-8859-1, ';') von
regionalstatistik.de nach raw/genesis/.

  23111-01-05-4-B  Krankenhaeuser + Betten (31.12.2024)
  21111-01-03-4-B  Schulen nach Schularten (Schuljahr 2023/24)
  33111-01-02-4    Bodenflaeche nach Art der Nutzung (31.12.2021)
  33111-02-01-4    Siedlungsflaeche/Erholungsflaeche (31.12.2021)

URL-Muster (verifiziert am 03.10.2026):
  https://www.regionalstatistik.de/genesisws/downloader/00/tables/{ID}_00.csv

Aufruf:  python3 src/fetch_genesis.py
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "raw", "genesis")

TABLES = [
    "23111-01-05-4-B",
    "21111-01-03-4-B",
    "33111-01-02-4",
    "33111-02-01-4",
]

BASE = "https://www.regionalstatistik.de/genesisws/downloader/00/tables/{}_00.csv"


def main():
    os.makedirs(OUT, exist_ok=True)
    for tid in TABLES:
        url = BASE.format(tid)
        dest = os.path.join(OUT, tid + ".csv")
        if os.path.exists(dest) and "--force" not in sys.argv:
            print("existiert:", dest)
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
        print("OK:", dest, os.path.getsize(dest), "Bytes")


if __name__ == "__main__":
    main()
