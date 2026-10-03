# -*- coding: utf-8 -*-
"""build_xlsx.py — deutschland-rohdaten.xlsx aus merged_raw_v3.json bauen.

openpyxl-Portierung der urspruenglichen solution.ts (ExcelJS-SDK):
  - Blatt 1 "Rohdaten": 109 Spalten x 400 Kreise, eingefrorene Kopfzeile,
    Zahlformate (EUR, Tsd, Ganzzahlen, Dezimalstellen)
  - Blatt 2 "Quellen & Variablen": Infoblock + Registry je Spalte
    (Quelle, Erhebungsstand, Link, Anmerkung)

Aufruf:  python3 src/build_xlsx.py  [ausgabe.xlsx]
Ausgabe: dist/deutschland-rohdaten.xlsx (Default)
"""
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")

BASE_FONT = "Arial"
BASE_SIZE = 11
LINK_COLOR = "FF2E7D6B"
EUR_FORMAT = '#,##0 "€";(#,##0 "€");-'  # currencyFormat("EUR", 0) des SDK

INT_COLS = ["pop", "verkehrsgetoetete", "ost", "krankenhaeuser", "betten",
            "schulen_anzahl", "nsg_anzahl"]
EUR_COLS = ["verfeink_je_ew", "kaufkraft_proxy", "ko_kasskred"]
TSD_COLS = ["hh_veink", "erw_bip"]
DEC1_COLS = ["betten_100k", "schulen_100k", "flaeche_km2", "wasserflaeche_prozent",
             "erholungsflaeche_prozent", "nsg_ha"]
DEC2_COLS = ["mig_eingewandert", "mig_geschichte", "nsg_anteil_prozent"]

INFO_ROWS = [
    ("Datensatz", "Deutschland im Überblick — Rohdaten aller 400 Landkreise und kreisfreien Städte"),
    ("Stand", "02.–03.10.2026 (Grunddaten 02.10.2026; Naturschutzgebiete am 03.10.2026 nachgeliefert)"),
    ("Gebietsstand", "31.12.2024; Eisenach seit 2021 Teil des Wartburgkreises (400 Kreise)"),
    ("Aufbau", "Blatt 'Rohdaten': ein Kreis je Zeile, jede Spalte ein konkreter Wert (keine Ränge). Dieses Blatt: eine Zeile je Spalte mit Quelle, Erhebungsstand und Link."),
    ("Join-Schlüssel", "Spalte 'rs' = 5-stelliger Regionalschlüssel (AGS), identisch zum Schlüssel in Karte, XLSX-Basis und Finder"),
    ("Konventionen", "HZ = Häufigkeitszahl je 100.000 Einwohner (eigene Berechnung aus Fallzahlen ÷ 'pop'). GENESIS '-' als 0 kodiert (exakt null oder Geheimhaltung). PKS = Hellfeld. 'kaufkraft_proxy' = verfeink_je_ew ÷ (preisindex_gesamt/100)."),
    ("Naturschutzgebiete", "Flächenanteile je Kreis aus BfN-WFS (9.035 Gebiete, 2,75 Mio ha gesamt) per 100-m-Raster den BKG-VG250-Kreisgrenzen zugeordnet; 1,50 Mio ha liegen innerhalb der Kreisflächen, Meeres-/AWZ-Anteile (u. a. Sylter Außenriff) bleiben unberücksichtigt; geringe Randunschärfe von ±1 ha an Kreisgrenzen."),
    ("Nicht enthalten (offen)", "Lebenserwartung je Kreis (RKI nur Quintils-Aggregate; je Kreis via INKAR-Registrierung), ÖPNV-/Erreichbarkeitsindikatoren (INKAR), Luft/Lärm (UBA unvollständig), Kino-/Gastronomiedichte"),
]


def style_header_row(ws, row_number):
    bold = Font(name=BASE_FONT, size=BASE_SIZE, bold=True)
    align = Alignment(vertical="center")
    for cell in ws[row_number]:
        if cell.value is not None:
            cell.font = bold
            cell.alignment = align


def main():
    with open(os.path.join(DATA, "merged_raw_v3.json"), encoding="utf-8") as f:
        raw = json.load(f)
    columns, rows = raw["columns"], raw["rows"]
    keys = [c["key"] for c in columns]
    assert len(columns) == 109 and len(rows) == 400

    wb = Workbook()

    # ==================== Blatt 1: Rohdaten ====================
    ws = wb.active
    ws.title = "Rohdaten"
    ws.freeze_panes = "C2"
    ws.sheet_view.showGridLines = False

    for i, c in enumerate(columns, start=1):
        ws.cell(row=1, column=i, value=c["key"])
    style_header_row(ws, 1)

    ws.column_dimensions["A"].width = 10   # rs
    ws.column_dimensions["B"].width = 26   # name
    for i in range(3, len(columns) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12.5

    for r, row in enumerate(rows, start=2):
        for i, k in enumerate(keys, start=1):
            v = row.get(k)
            if v is not None:
                ws.cell(row=r, column=i, value=v)

    fmt_map = {}
    for k in EUR_COLS:
        fmt_map[k] = EUR_FORMAT
    for k in TSD_COLS:
        fmt_map[k] = "0.00"
    for k in INT_COLS:
        fmt_map[k] = "0"
    for k in DEC1_COLS:
        fmt_map[k] = "0.0"
    for k in DEC2_COLS:
        fmt_map[k] = "0.00"

    for i, k in enumerate(keys, start=1):
        if k in fmt_map:
            letter = get_column_letter(i)
            for r in range(2, len(rows) + 2):
                ws.cell(row=r, column=i).number_format = fmt_map[k]

    # ==================== Blatt 2: Quellen & Variablen ====================
    meta = wb.create_sheet("Quellen & Variablen")
    meta.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFG", (22, 46, 16, 52, 13, 55, 52)):
        meta.column_dimensions[col].width = w

    bold = Font(name=BASE_FONT, size=BASE_SIZE, bold=True)
    link_font = Font(name=BASE_FONT, size=BASE_SIZE, color=LINK_COLOR[2:])
    for i, (k, v) in enumerate(INFO_ROWS, start=1):
        meta.cell(row=i, column=1, value=k).font = bold
        meta.cell(row=i, column=2, value=v)

    header_row_idx = len(INFO_ROWS) + 2
    headers = ["Spalte", "Bezeichnung", "Einheit", "Quelle", "Erhebungsstand",
               "Link", "Anmerkung"]
    for i, h in enumerate(headers, start=1):
        meta.cell(row=header_row_idx, column=i, value=h)
    style_header_row(meta, header_row_idx)

    for i, c in enumerate(columns):
        r = header_row_idx + 1 + i
        meta.cell(row=r, column=1, value=c["key"])
        meta.cell(row=r, column=2, value=c["label"])
        meta.cell(row=r, column=3, value=c["einheit"])
        meta.cell(row=r, column=4, value=c["quelle"])
        meta.cell(row=r, column=5, value=c["jahr"])
        if c.get("link"):
            cell = meta.cell(row=r, column=6, value=c["link"])
            cell.hyperlink = c["link"]
            cell.font = link_font
        else:
            meta.cell(row=r, column=6, value="—")
        meta.cell(row=r, column=7, value=c.get("anmerkung") or "")

    os.makedirs(DIST, exist_ok=True)
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        DIST, "deutschland-rohdaten.xlsx")
    wb.save(out_path)
    print("OK:", out_path)
    print("Blatt 1:", ws.max_row, "x", ws.max_column, "| Blatt 2:", meta.max_row, "x", meta.max_column)


if __name__ == "__main__":
    main()
