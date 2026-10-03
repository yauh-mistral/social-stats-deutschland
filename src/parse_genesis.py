# -*- coding: utf-8 -*-
"""parse_genesis.py — GENESIS-Tabellen auswerten -> data/genesis_neu.json (8 Spalten).

Quellen (raw/genesis/, ISO-8859-1, Semikolon-getrennt):
  23111-01-05-4-B  Krankenhaeuser + Betten          (31.12.2024)
  21111-01-03-4-B  Schulen nach Schularten           (Schuljahr 2023/24, Jahr 2023)
  33111-01-02-4    Bodenflaeche nach Nutzung          (31.12.2021)
  33111-02-01-4    Siedlungsflaeche/Erholungsflaeche  (31.12.2021)

Sonderfaelle:
  - Die Tabellen enthalten auch Alt-AGS (z. B. Eisenach 16056) -> Filter
    auf die 400 Ziel-AGS aus merged_raw_base.json.
  - Hamburg: in den Flaechentabellen als Land-Zeile '02' statt '02000'.
  - Berlin: in den Flaechentabellen als 12 Bezirke ('11001001'..'11012012',
    8-stellig) statt '11000' -> Summe der Bezirke.
  - 'x', '-', '.' werden als 0 gewertet (exakt null oder Geheimhaltung).

mig_eingewandert / mig_geschichte stammen aus dem Zensus (parse_zensus.py)
und bleiben hier unveraendert; sie werden aus der bestehenden
genesis_neu.json uebernommen, falls vorhanden.

Validierung: KH-Summe 1.841, Betten 472.851, Schulen 30.604,
Flaeche 35.758.571 ha (99,998 % des amtlichen Wertes).

Aufruf:  python3 src/parse_genesis.py [--check]
  --check  nur gegen die committete genesis_neu.json abgleichen
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw", "genesis")

KH_FILE = "23111-01-05-4-B.csv"
SCHULEN_FILE = "21111-01-03-4-B.csv"
BODEN_FILE = "33111-01-02-4.csv"
ERHOLUNG_FILE = "33111-02-01-4.csv"

SCHULART_AUSSER = {"Vorschulbereich", "Insgesamt"}
BERLIN_BEZIRKE = ["11001001", "11002002", "11003003", "11004004", "11005005",
                  "11006006", "11007007", "11008008", "11009009", "11010010",
                  "11011011", "11012012"]


def read_rows(filename):
    """CSV latin-1, ';' -> Liste der Feldlisten."""
    path = os.path.join(RAW, filename)
    with open(path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\n").rstrip(";")
            if not line:
                continue
            yield line.split(";")


def val(s):
    """Zahlenwert; 'x'/'-'/'.' = 0 (exakt null oder Geheimhaltung)."""
    s = s.strip()
    if s in ("x", "-", ".", ""):
        return 0
    return float(s.replace(",", "."))


def main():
    with open(os.path.join(DATA, "merged_raw_base.json"), encoding="utf-8") as f:
        base = json.load(f)
    targets = [str(r["rs"]) for r in base["rows"]]
    target_set = set(targets)

    kh = {}
    betten = {}
    schulen = {}
    flaeche_ha = {}
    wasser_ha = {}
    erholung_ha = {}
    # Sondersummen Berlin (Bezirke) / Hamburg (Land-Zeile)
    berlin = {"flaeche": 0.0, "wasser": 0.0, "erholung": 0.0}
    hamburg = {}

    for row in read_rows(KH_FILE):
        if row[0].strip() != "31.12.2024":
            continue
        ags = row[1].strip()
        if ags in target_set:
            kh[ags] = int(val(row[3]))
            betten[ags] = int(val(row[4]))

    for row in read_rows(SCHULEN_FILE):
        if row[0].strip() != "2023":
            continue
        ags = row[1].strip()
        schulart = row[3].strip()
        if ags in target_set and schulart not in SCHULART_AUSSER:
            schulen[ags] = schulen.get(ags, 0) + int(val(row[4]))

    for row in read_rows(BODEN_FILE):
        if row[0].strip() != "31.12.2021":
            continue
        ags = row[1].strip()
        gesamt = val(row[3])       # Bodenflaeche Insgesamt
        wasser = val(row[14])      # Gewaesser Insgesamt
        if ags in target_set:
            flaeche_ha[ags] = gesamt
            wasser_ha[ags] = wasser
        elif ags == "02":           # Hamburg als Land-Zeile
            hamburg = {"flaeche": gesamt, "wasser": wasser}
        elif ags in BERLIN_BEZIRKE:  # Berlin = Summe der 12 Bezirke
            berlin["flaeche"] += gesamt
            berlin["wasser"] += wasser

    for row in read_rows(ERHOLUNG_FILE):
        if row[0].strip() != "31.12.2021":
            continue
        ags = row[1].strip()
        erholung = val(row[13])    # Sport-, Freizeit- und Erholungsflaeche Insgesamt
        if ags in target_set:
            erholung_ha[ags] = erholung
        elif ags == "02":
            hamburg["erholung"] = erholung
        elif ags in BERLIN_BEZIRKE:
            berlin["erholung"] += erholung

    # Sonderfaelle einsetzen
    if "02000" in target_set and "02000" not in flaeche_ha:
        flaeche_ha["02000"] = hamburg["flaeche"]
        wasser_ha["02000"] = hamburg["wasser"]
        erholung_ha["02000"] = hamburg["erholung"]
    if "11000" in target_set and "11000" not in flaeche_ha:
        flaeche_ha["11000"] = berlin["flaeche"]
        wasser_ha["11000"] = berlin["wasser"]
        erholung_ha["11000"] = berlin["erholung"]

    # --- Zielgroessen je Kreis ---
    out = {
        "krankenhaeuser": kh,
        "betten": betten,
        "schulen_anzahl": schulen,
        "flaeche_km2": {},
        "wasserflaeche_prozent": {},
        "erholungsflaeche_prozent": {},
    }
    for ags in targets:
        out["flaeche_km2"][ags] = round(flaeche_ha[ags] / 100, 2)
        out["wasserflaeche_prozent"][ags] = round(wasser_ha[ags] / flaeche_ha[ags] * 100, 1)
        out["erholungsflaeche_prozent"][ags] = round(erholung_ha[ags] / flaeche_ha[ags] * 100, 1)

    # Abgeleitete 100k-Raten + mig aus Zensus dazunehmen
    pop = {str(r["rs"]): r["pop"] for r in base["rows"]}
    out["betten_100k"] = {a: round(betten[a] / pop[a] * 100000, 1) for a in targets}
    out["schulen_100k"] = {a: round(schulen[a] / pop[a] * 100000, 1) for a in targets}

    # mig-Spalten: aus bestehender genesis_neu.json uebernehmen (Zensus-Pipeline)
    old_path = os.path.join(DATA, "genesis_neu.json")
    if os.path.exists(old_path):
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f)
        for k in ("mig_eingewandert", "mig_geschichte"):
            if k in old:
                out[k] = old[k]

    # --- Validierung ---
    s_kh = sum(kh[a] for a in targets)
    s_be = sum(betten[a] for a in targets)
    s_sc = sum(schulen[a] for a in targets)
    s_fl = round(sum(flaeche_ha[a] for a in targets))
    print("KH:", s_kh, "(Soll 1841) | Betten:", s_be, "(Soll 472851)")
    print("Schulen:", s_sc, "(Soll 30604) | Flaeche ha:", s_fl, "(Soll 35758571)")
    print("Gelsenkirchen 05513: KH", kh["05513"], "| Betten", betten["05513"],
          "| Schulen", schulen["05513"], "| km2", out["flaeche_km2"]["05513"],
          "| Wasser %", out["wasserflaeche_prozent"]["05513"],
          "| Erholung %", out["erholungsflaeche_prozent"]["05513"])
    assert s_kh == 1841, s_kh
    assert s_be == 472851, s_be
    assert s_sc == 30604, s_sc
    assert s_fl == 35758571, s_fl

    if "--check" in sys.argv:
        # gegen die committete Datei abgleichen
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f)
        errs = []
        for k, m in out.items():
            if k not in old:
                errs.append((k, "fehlt in committeter Datei"))
                continue
            for a in targets:
                if abs(float(m[a]) - float(old[k][a])) > 1e-9:
                    errs.append((k, a, m[a], old[k][a]))
        print("Abgleich committete genesis_neu.json: Fehler:", len(errs))
        if errs:
            for e in errs[:10]:
                print("  ", e)
            sys.exit(1)
        print("OK — Neuparsing identisch zur committeten Datei.")
        return

    with open(old_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("OK:", old_path, "| Spalten:", len(out))


if __name__ == "__main__":
    main()
