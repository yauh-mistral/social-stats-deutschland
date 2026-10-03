# -*- coding: utf-8 -*-
"""unpack_base.py — data/merged_raw_base.json aus der gepackten Fassung herstellen.

Die v1-Basis (96 Spalten x 400 Kreise, ~870 KB JSON) liegt als
data/merged_raw_base.json.xz.a85 im Repo (xz-komprimiert + Ascii85),
um die Datei groessenfreundlich im Git zu halten.

Aufruf:  python3 src/unpack_base.py
Ergebnis: data/merged_raw_base.json (byte-identisch zur Originaldatei)
"""
import base64
import lzma
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

SRC = os.path.join(DATA, "merged_raw_base.json.xz.a85")
DEST = os.path.join(DATA, "merged_raw_base.json")


def main():
    with open(SRC, encoding="ascii") as f:
        a85 = f.read()
    raw = lzma.decompress(base64.a85decode("".join(a85.split()).encode("ascii")))
    with open(DEST, "wb") as f:
        f.write(raw)
    print("OK:", DEST, len(raw), "Bytes")


if __name__ == "__main__":
    main()
