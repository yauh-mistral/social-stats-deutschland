# social-stats-deutschland

Rohdaten aller 400 Landkreise und kreisfreien Städte Deutschlands —
**109 Variablen je Kreis** aus amtlichen Quellen (Stand: 02.–03.10.2026).

Das Projekt liefert eine vollständige, reproduzierbare Pipeline:
Quellabruf (GENESIS / Zensus / BfN / BKG) → Parsing → Merge → XLSX-Build.

## Ergebnis

- **Datensatz v3** — 109 Spalten × 400 Kreise, inkl. Registry
  (Bezeichnung, Einheit, Quelle, Erhebungsstand, Link, Anmerkung,
  Themenblock je Spalte). Wird per `merge.py` erzeugt
  (`data/merged_raw_v3.json`) und ist nicht selbst committet, sondern
  aus den committeten Daten reproduzierbar.
- **`dist/deutschland-rohdaten.xlsx`** — die fertige Mappe (2 Blätter:
  „Rohdaten“ + „Quellen & Variablen“), regenerierbar per `build_xlsx.py`
  (nicht committet, da Binärformat). Der committete Release-Build liegt
  als `data/deutschland-rohdaten.xlsx` und wird **automatisch per GitHub
  Actions** aktualisiert (`.github/workflows/build-xlsx.yml`): nach jedem
  Push auf `main` läuft die Pipeline (entpacken → mergen → bauen) und der
  Bot committet die XLSX, falls sich Inhalte geändert haben. Manuell geht
  es weiterhin per `python3 src/build_xlsx.py data/deutschland-rohdaten.xlsx`.

### Spaltenblöcke

| Block | Beispiele |
|---|---|
| Meta | `rs`, `name`, `type`, `bl`, `pop`, `ost` |
| Einkommen & Wohlstand | `verfeink_je_ew`, `kaufkraft_proxy`, `hh_veink` |
| Wohnen & Lebenshaltung | `bauendg`, `baugenehmigungen_hz`, `leerstandsquote` |
| Arbeit & Wege | `erwerbsquote`, `pendler`, `arbeitslose_prozent` |
| Gesundheit | `v_karzt`, `krankenhaeuser`, `betten`, `betten_100k` |
| Bildung & Betreuung | `schul`, `schulen_anzahl`, `schulen_100k` |
| Sicherheit | `crime_hz`, `verkehrsgetoetete` |
| Umwelt & Fläche | `fl_landw`, `flaeche_km2`, `wasserflaeche_prozent`, `erholungsflaeche_prozent`, `nsg_anzahl`, `nsg_ha`, `nsg_anteil_prozent` |
| Kultur, Sport & Gemeinschaft | `bibliotheken`, `schwimmbad_hz` |
| Demografie & Struktur | `bev_ausl`, `mig_eingewandert`, `mig_geschichte` |

## Pipeline

```
raw/ (Downloads, .gitignore'd)         data/ (committet)
-----------------------------------   ------------------------------------
fetch_genesis.py   -> raw/genesis/    parse_genesis.py  -> genesis_neu.json
fetch_zensus.py    -> raw/zensus/     parse_zensus.py   -> (mig-Spalten)
fetch_nsg.py       -> raw/nsg/        parse_nsg.py      -> nsg_je_kreis.json
fetch_vg250.py     -> raw/vg250/
                                      merge.py  -> merged_raw_v3.json
                                      build_xlsx.py -> dist/deutschland-rohdaten.xlsx
                                      export_parquet.py -> dist/*.parquet (R-Analyse)
```

Alles läuft mit Python 3 + NumPy + openpyxl
(`pip install numpy openpyxl`); nur der Parquet-Export benötigt
zusätzlich pyarrow (`pip install pyarrow`).

### Kompletter Rebuild

```bash
python3 src/unpack_base.py     # data/merged_raw_base.json entpacken (einmalig)
python3 src/fetch_genesis.py    # 4 GENESIS-CSVs (~1 MB)        [optional, data/ committet]
python3 src/parse_genesis.py    # Validierung: KH 1.841, Betten 472.851, ...
python3 src/parse_zensus.py    # mig-Spalten (aus data/mig_zensus.json; s. u.)
python3 src/merge.py            # 109 Spalten, Prüfzahlen-Assertions
python3 src/build_xlsx.py       # dist/deutschland-rohdaten.xlsx
python3 src/export_parquet.py   # dist/*.parquet (benötigt pyarrow)
```

Nur für einen NSG-Neuaufbau zusätzlich: `fetch_vg250.py` (BKG, ~30 MB),
`fetch_nsg.py` (BfN-WFS, ~106 MB), dann `parse_nsg.py` (s. u.). Der
Zensus-Abruf (`fetch_zensus.py`) ist derzeit nicht möglich (404, s. u.);
`parse_zensus.py --from-raw` rechnet die Werte, sobald die API wieder
liefert.

Da die Rohdaten groß sind, sind die Zwischenergebnisse in `data/`
committet — die XLSX lässt sich allein daraus rebuilden. Die v1-Basis
(870 KB JSON) liegt aus Platzgründen xz-komprimiert als
`data/merged_raw_base.json.xz.a85` vor; `src/unpack_base.py` stellt
die Originaldatei byte-identisch wieder her (nur Standardbibliothek).

## Quellen

| Daten | Quelle | Stand |
|---|---|---|
| 96 Grundspalten | Destatis/GENESIS, PKS, eigene Metadaten | 02.10.2026 |
| Krankenhäuser, Betten | [GENESIS 23111-01-05-4-B](https://www.regionalstatistik.de/genesisws/downloader/00/tables/23111-01-05-4-B_00.csv) | 31.12.2024 |
| Schulen | [GENESIS 21111-01-03-4-B](https://www.regionalstatistik.de/genesisws/downloader/00/tables/21111-01-03-4-B_00.csv) | Schuljahr 2023/24 |
| Kreisfläche, Wasser | [GENESIS 33111-01-02-4](https://www.regionalstatistik.de/genesisws/downloader/00/tables/33111-01-02-4_00.csv) | 31.12.2021 |
| Erholungsfläche | [GENESIS 33111-02-01-4](https://www.regionalstatistik.de/genesisws/downloader/00/tables/33111-02-01-4_00.csv) | 31.12.2021 |
| Migration | Zensus 2022, [Tabelle 1000A-1011](https://ergebnisse.zensus2022.de/) | 15.05.2022 |
| Naturschutzgebiete | [BfN-WFS schutzgebiet](https://geodienste.bfn.de/ogc/wfs/schutzgebiet) | 03.10.2026 |
| Kreisgrenzen | [BKG VG250](https://daten.gdz.bkg.bund.de/produkte/vg/vg250_ebenen_1231/aktuell/vg250_12-31.utm32s.shape.ebenen.zip) (EPSG:25832) | 31.12. |

## Methodik: NSG-Zuordnung (100-m-Raster)

Die 9.035 NSG des BfN-WFS (Attribut-Flächensumme 2.724.824 ha,
Polygonflächensumme 2.749.755 ha) werden den Kreisen räumlich zugeordnet:

- **Kreis-Raster:** Alle 400 VG250-Kreisgeometrien werden per Even-Odd-Scanline
  in ein Deutschland-Raster mit 100-m-Zellen gebrannt (1 Zelle = 1 ha;
  29 AGS liegen als Teilgeometrien in mehreren SHP-Records und werden je AGS
  zusammengefasst).
- **Ringe < 500 ha:** Ganzringzuordnung mit exakter Gauß'scher
  Dreiecksfläche an den Kreis mit der **Zellmehrheit** im Ring (>50 % der
  überdeckten Zellen Kreisgebiet); Ringe kleiner als eine Rasterzelle
  werden über die Schwerpunkt-Zelle zugeordnet. Liegt der Schwerpunkt
  außerhalb der Kreisflächen (Meer, Bodensee, Bundeswasserstraßen),
  bleibt der Ring unberücksichtigt.
- **Ringe ≥ 500 ha:** flächengenaue Zuordnung je Rasterzelle (Zellmitte →
  Kreis-Lookup, `np.bincount` × 1 ha).
- **Ergebnis:** 1.502.641 ha innerhalb der Kreisflächen zugewiesen;
  385 von 400 Kreisen haben mind. ein NSG. Meeres-/AWZ-Anteile
  (u. a. Sylter Außenriff, Doggerbank) bleiben korrekt unberücksichtigt.

**Unsicherheit:** Rasterauflösung 1 ha → geringe Randunschärfe an
Kreisgrenzen. Raster- vs. GENESIS-Kreisfläche: median 0,103 % / max 6,13 %
Abweichung (Watt-/Küstenbereiche). Wattenmeer gehört — konsistent mit der
GENESIS-Bodenfläche — zum Kreisgebiet (z. B. Nordfriesland groß).

`src/parse_nsg.py` ist eine getreue Rekonstruktion des validierten Laufs
und gegen die committeten Werte getestet: alle globalen Prüfgroßen stimmen
exakt, je Kreis reproduziert der Rebuild 290/400 Werte exakt (Gesamtsumme
+0,02 %, max. ~330 ha Abweichung durch Randkonventionen beim Zell-Fill).
Die committeten Werte bleiben verbindlich; `--write` überschreibt sie nur
nach Prüfung des Abgleichsberichts.

## Validierte Prüfzahlen

| Größe | Wert |
|---|---|
| Kreise / Spalten | 400 / 109 |
| Krankenhäuser (Summe) | 1.841 |
| Krankenhausbetten (Summe) | 472.851 |
| Schulen (Summe) | 30.604 |
| Kreisfläche (Summe) | 35.758,571 ha = 99,998 % des amtlichen Wertes |
| NSG zugewiesen | 1.502.641 ha von 2.749.755 ha Polygonfläche |
| Kreise mit NSG | 385 |
| Migration Gelsenkirchen | 25,4 % Eingewanderte / 32,9 % mit Einwanderungsgeschichte |
| Deutschland (Referenz) | 18,8 % Eingewanderte / 23,6 % mit Geschichte |

## Bekannte Einschränkungen

- **Zensus-API:** Der Tabellen-Endpunkt von ergebnisse.zensus2022.de
  antwortet derzeit mit 404 (Stand 03.10.2026; Basis-Endpunkte wie
  `helloworld/whoami` funktionieren). Das verifizierte Abruf-Rezept ist
  in `src/fetch_zensus.py` implementiert; die mig-Werte sind vollständig
  als `data/mig_zensus.json` committet. Sobald die API antwortet:
  `fetch_zensus.py` → `parse_zensus.py --from-raw`.
- **Alt-AGS:** Die GENESIS-Tabellen enthalten teils Alt-Regionalschlüssel
  (z. B. Eisenach `16056`) — der Parser filtert auf die 400 Ziel-AGS.
- **Berlin/Hamburg:** In den Flächentabellen als Sonderfälle
  (Hamburg = Land-Zeile `02`, Berlin = Summe der 12 Bezirke, 8-stellig).
- **`parse_nsg.py`** rekonstruiert den validierten Lauf vom 03.10.2026
  (getestet, s. Methodik); für einen Rebuild werden die 106 MB WFS-Rohdaten
  (`fetch_nsg.py`) und die BKG-VG250 (`fetch_vg250.py`) benötigt. Die
  committeten Werte stammen aus dem validierten Lauf und bleiben
  verbindlich. Die Zählweise `unassigned_bl` der committierten Datei ist
  nicht vollständig rekonstruierbar (Debug-Statistik des Originallaufs).

## Projektstruktur

```
├── AGENTS.md               # Agent-Anweisungen + KI-Disclosure (Stolperfallen, Konventionen)
├── README.md
├── src/                    # Pipeline-Skripte (keine externen Abhängigkeiten außer numpy/openpyxl)
│   ├── fetch_genesis.py / fetch_zensus.py / fetch_nsg.py / fetch_vg250.py
│   ├── parse_genesis.py / parse_zensus.py / parse_nsg.py
│   └── unpack_base.py / merge.py / build_xlsx.py / export_parquet.py
├── data/                   # committete Daten + Registry
│   ├── merged_raw_base.json.xz.a85  # v1-Basis, 96 Spalten (xz+Ascii85, entpacken per unpack_base.py)
│   ├── genesis_neu.json             # GENESIS-Spalten je AGS (10 Spalten inkl. mig)
│   ├── mig_zensus.json              # Zensus-Migrationswerte je AGS (1000A-1011)
│   ├── nsg_je_kreis.json            # NSG-Spalten je AGS + Validierungs-Metadaten
│   ├── registry_new.json            # Registry-Einträge der 13 neuen Spalten
│   └── deutschland-rohdaten.xlsx    # Release-Build (GitHub Actions hält ihn aktuell)
│       (merged_raw_base.json entpackt + merged_raw_v3.json + dist/* werden regeneriert)
├── raw/                    # Downloads (.gitignore'd)
└── dist/                   # generierte XLSX/Parquet (.gitignore'd)
```

## Automatischer XLSX-Build (GitHub Actions)

`.github/workflows/build-xlsx.yml` baut nach jedem Push auf `main`
(Pfade `data/**`, `src/**`, Workflow selbst) die `data/deutschland-rohdaten.xlsx`
aus den committeten Basisdateien und committet sie bei inhaltlicher
Änderung (`chore(data): … [skip ci]`, Bot-Identität). Benötigt nur
`openpyxl` — die Kernpipeline kommt ohne numpy aus. Auch manuell
startbar: *Actions → Build XLSX → Run workflow*.

## Join-Schlüssel

`rs` = 5-stelliger Regionalschlüssel (AGS), Gebietsstand 31.12.2024,
Eisenach seit 2021 Teil des Wartburgkreises.
