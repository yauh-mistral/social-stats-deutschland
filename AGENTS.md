# AGENTS.md

Anweisungen für Coding-Agents (und menschliche Mitwirkende), die dieses
Repository bearbeiten. Das README beschreibt **Was** das Projekt tut und
wie die Datenmethode funktioniert — hier steht **Wie man sicher damit
arbeitet**. Bei Widerspruch gilt: README für Methodik, diese Datei für
Arbeitsweise und Constraints.

## Entstehung des Projekts (KI-Disclosure)

Dieses Projekt wurde überwiegend agentisch mit **Mistral Vibe**
(KI-Coding-Agent, Modell GLM von Z.ai, betrieben von Mistral AI)
entwickelt. Commits stammen teils vom Agent-Account `mistral-vibe`
(Pull Requests mit `Co-Authored-by`-Hinweis), teils vom Repository-Owner
`yauh`. Roh- und Berechnungswerte sind **nicht** frei generiert: Jede
Datenspalte wurde gegen amtliche Prüfzahlen der Quellen validiert
(aktuelle Sollwerte in der Kette unten und im README). Die NSG-Zuordnung
ist eine eigene Berechnung (100-m-Raster) und als solche inklusive ihrer
Restunsicherheit dokumentiert (README „Methodik").

Diese Datei folgt dem De-facto-Standard `AGENTS.md` (agents.md), den
agentische Coding-Tools (Codex, Claude Code, Cursor u. a.) automatisch
lesen. Agent-Runtimes ohne Auto-Discovery: diese Datei aktiv in den
Kontext laden, bevor Skripte geändert werden.

## Grundregel: Verify before commit

1. `data/*.json` sind **generierte Artefakte** — niemals manuell editieren,
   immer über die Pipeline-Skripte regenerieren.
2. Vor jedem Commit, der Daten oder Parsing betrifft, muss diese Kette
   ohne Fehler durchlaufen ( Assertions sind Teil der Skripte):

   ```bash
   python3 src/unpack_base.py      # data/merged_raw_base.json entpacken
   python3 src/parse_genesis.py   # KH 1841, Betten 472851, Schulen 30604, Flaeche 35758571 ha
   python3 src/parse_zensus.py    # Gelsenkirchen 25.4/32.9
   python3 src/merge.py           # 109 Spalten, alle Pruefzahlen
   python3 src/build_xlsx.py      # dist/deutschland-rohdaten.xlsx
   ```

3. Commit erst, wenn alle Pruefzahlen grün sind. Prüfzahlen in
   `merge.py` sind absichtlich hart codiert — sie sind der Datenvertrag,
   kein frei editierbarer Code.

## Bekannte Stolperfallen (nicht im README)

- **GENESIS-CSVs:** Latin-1-kodiert, Semikolon-getrennt. Fehlwerte `'x'`,
  `'-'`, `'.'` sind als 0 zu werten. Die Kopfzeilen variieren zwischen
  Tabellen und Ständen — Spalten immer über die Header-Zeilen suchen,
  nie über feste Indizes.
- **Alt-Regionalschlüssel:** GENESIS-Tabellen enthalten teils Alt-AGS
  (z. B. Eisenach `16056`). Parser müssen auf die 400 Ziel-AGS
  (Gebietsstand 31.12.2024) filtern.
- **Flächentabelle 33111-01-02-4:** Hamburg nur als Land-Zeile `02`,
  Berlin nur als 12 Bezirke (8-stellige Schlüssel, `11001001`–`11012012`)
  — beide Sonderfälle werden in `parse_genesis.py` aufgelöst.
- **BfN-WFS:** lehnt Default-User-Agents mit 403 ab — Browser-UA
  setzen (steht in `fetch_nsg.py`).
- **Zensus-API:** Tabellen-Endpunkt antwortet derzeit 404 (Stand
  03.10.2026). `parse_zensus.py` liest deshalb standardmäßig die
  committete `data/mig_zensus.json`. `--from-raw` erst verwenden, wenn
  `fetch_zensus.py` wieder liefert — und danach die Gelsenkirchen- und
  DE-Referenzwerte prüfen (Assertions im Skript).
- **Shapefile-Parsing:** Punkte liegen interleaved vor —
  `x = pts[2*s:2*e:2]`, `y = pts[2*s+1:2*e:2]` (Stride 2). Der
  klassische Bug `pts[2*s:2*e]` mischt x- und y-Koordinaten.
- **`parse_nsg.py`:** Die committeten Werte in `data/nsg_je_kreis.json`
  sind verbindlich. Ein Rebuild (nur mit den 106 MB Rohdaten aus
  `fetch_nsg.py`) reproduziert sie rasterungsbedingt nicht byte-genau
  (290/400 Kreise exakt, Gesamtsumme +0,02 %, max. ~330 ha je Kreis).
  `--write` (Überschreiben der committeten Datei) nur nach Prüfung des
  Abgleichsberichts laufen lassen.
- **`nsg_anteil_prozent`** wird gegen die *Raster*-Kreisfläche gerechnet
  (verbindlich; weicht in 3 Grenzfällen um 0,01 pp von der GENESIS-Fläche
  ab). In `merge.py` bewusst mit ±0,02-pp-Toleranz abgesichert.
- **Sandbox-Umgebungen:** numpy/openpyxl sind ggf. nur über das
  gebündelte data-analysis-Library aktivierbar; **pyarrow ist dort
  nicht enthalten** — `export_parquet.py` nur in eigener Umgebung mit
  `pip install pyarrow` ausführen.

## Konventionen

- Python ≥ 3.9; außer der Standardbibliothek nur **numpy** und
  **openpyxl** (Ausnahme: **pyarrow** für den Parquet-Export). Keine
  neuen Abhängigkeiten ohne Not.
- Docstrings/Kommentare auf Deutsch, in Code ASCII (ae/oe/ue statt
  Umlaute), Dateien UTF-8 mit Coding-Deklaration.
- Commit-Messages als Conventional Commits (`feat:`, `fix:`, `docs:`,
  `data:` — `data:` für neu generierte Datenstände).
- `raw/` (Downloads) und `dist/` (Build-Artefakte) sind gitignored;
  `data/` ist committet und zugleich Quelle der Wahrheit für den XLSX-Build.
- Der Join-Schlüssel ist immer `rs`, 5-stellig, als **String**
  (führende Nullen!).

## Typische Aufgaben

**Neue Spalte ergänzen:**
1. fetch-/parse-Skript unter `src/` schreiben, Ausgabe als
   `data/*.json` (je AGS → Wert), mit amtlicher Prüfzahl als Assertion.
2. Registry-Eintrag in `data/registry_new.json` ergänzen
   (label, einheit, quelle, jahr, link, anmerkung).
3. In `src/merge.py` thematisch einsortieren (`insert_after`) und
   Soll-Summen/Assertions ergänzen.
4. Kette (s. o.) durchlaufen lassen, README-Spaltenübersicht und
   ggf. `build_xlsx.py` (Zahlformate, INT/DEC-Spalten) aktualisieren.

**Vollständigen Rebuild fahren:** Reihenfolge im README unter
„Kompletter Rebuild". `fetch_genesis.py`/`fetch_zensus.py` sind optional,
solange die committeten `data/`-Dateien aktuell sind; `fetch_nsg.py`
+ `fetch_vg250.py` werden nur für einen NSG-Rebuild (`parse_nsg.py`)
benötigt.

## Nicht tun

- Keine neuen Datenquellen einbauen, ohne eine amtliche Prüfzahl zur
  Validierung zu haben.
- Keine Format-/Layout-Änderungen an `build_xlsx.py` ohne Abgleich
  gegen die bestehende Mappe — Zahlformate und Blattaufbau sind Teil
  des Datenvertrags (R-Auswertungen hängen an Spaltennamen und Typen).
- Keine Prüfzahlen „korrigieren", wenn eine Assertion fehlschlägt —
  erst die Ursache in den Quelldaten finden.
- `data/merged_raw_base.json` (entpackt) nicht committen; die
  xz+Ascii85-Fassung ist die committete Form.
