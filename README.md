# social-stats-deutschland

Rohdaten aller 400 Landkreise und kreisfreien Städte Deutschlands —
**109 Variablen je Kreis** aus amtlichen Quellen (Stand: 02.–03.10.2026).

Das Projekt liefert eine vollständige, reproduzierbare Pipeline:
Quellabruf (GENESIS / Zensus / BfN / BKG) → Parsing → Merge → XLSX-Build.

## Ergebnis

- **Datensatz v3** — 109 Spalten × 400 Kreise, inkl. Registry
  (Bezeichnung, Einheit, Quelle, Erhebungsstand, Link, Anmerkung,
  Themenblock je Spalte) — die Quelle der Wahrheit für die Herkunft
  jeder Spalte (s. „Quellen“). Wird per `merge.py` erzeugt
  (`data/merged_raw_v3.json`) und ist nicht selbst committet, sondern
  aus den committeten Daten reproduzierbar.
- **Release-Artefakte in `data/`** — `deutschland-rohdaten.xlsx`
  (2 Blätter: „Rohdaten“ + „Quellen & Variablen“),
  `deutschland-rohdaten.parquet` (400×109) und
  `deutschland-variablen.parquet` (Registry) werden **automatisch per
  GitHub Actions** aus den committeten Basisdateien gebaut
  (`.github/workflows/build-xlsx.yml`): bei jedem Push auf `main` läuft
  die Pipeline mit ihren Prüfzahlen-Assertions, liest die Parquets zur
  Verifikation zurück und der Bot committet bei inhaltlicher Änderung.
  Lokal geht es weiterhin manuell (s. „Kompletter Rebuild“); `dist/` bleibt
  das lokale Ausgabeverzeichnis (Default der Skripte) und ist gitignored.

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
raw/ (Downloads, .gitignore'd)         data/ (committete Basisdateien)
-----------------------------------   ------------------------------------
fetch_genesis.py   -> raw/genesis/    parse_genesis.py  -> genesis_neu.json
fetch_zensus.py    -> raw/zensus/     parse_zensus.py   -> (mig-Spalten)
fetch_nsg.py       -> raw/nsg/        parse_nsg.py      -> nsg_je_kreis.json
fetch_vg250.py     -> raw/vg250/
                                      merge.py  -> merged_raw_v3.json
                                        (Zwischenstand, gitignored)
                                      build_xlsx.py     -> dist/*.xlsx  (lokale Ausgabe)
                                      export_parquet.py -> dist/*.parquet (lokale Ausgabe)
                                      GitHub Action (Release):
                                        build_xlsx.py + export_parquet.py nach data/
                                        -> data/*.xlsx, data/*.parquet (committet)
```

Alles läuft mit Python 3 + NumPy + openpyxl
(`pip install numpy openpyxl`); nur der Parquet-Export benötigt
zusätzlich pyarrow (`pip install pyarrow`). In der GitHub-Action
sind beide installiert — Release-Builds brauchen lokal nichts.

### Kompletter Rebuild

```bash
python3 src/unpack_base.py     # data/merged_raw_base.json entpacken (einmalig)
python3 src/fetch_genesis.py    # 4 GENESIS-CSVs (~1 MB)        [optional, data/ committet]
python3 src/parse_genesis.py    # Validierung: KH 1.841, Betten 472.851, ...
python3 src/parse_zensus.py    # mig-Spalten (aus data/mig_zensus.json; s. u.)
python3 src/merge.py            # 109 Spalten, Prüfzahlen-Assertions
python3 src/build_xlsx.py       # dist/deutschland-rohdaten.xlsx (lokale Ausgabe)
python3 src/export_parquet.py   # dist/*.parquet (benötigt pyarrow; lokale Ausgabe)
# Release nach data/ (macht sonst die Action):
#   python3 src/build_xlsx.py data/deutschland-rohdaten.xlsx
#   python3 src/export_parquet.py data/deutschland-rohdaten.xlsx data
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

Die konkrete Herkunft **jeder einzelnen** Spalte — Tabelle, Erhebungsstand,
Link und Anmerkung — steht vollständig und verbindlich in der Registry
(Blatt „Quellen & Variablen“ der XLSX bzw.
`data/deutschland-variablen.parquet` — 109 Einträge, einer je Spalte). Diese Übersicht bleibt bewusst auf
Herausgeber-Ebene generisch; Datenabruf 02.–03.10.2026.

| Herausgeber | Spalten | Themen |
|---|---:|---|
| BBSR — Deutschlandatlas (inkl. regionaler Preisindex mit IW Köln) | 58 | Wohnen, Erwerbsleben, Pflege, Kinderbetreuung, Bildung, Sicherheit, Flächennutzung, Demografie, Infrastruktur, Soziales, Schulden |
| Destatis — GENESIS-Online/Regionalstatistik, Statistische Ämter | 20 | Bevölkerung, Beschäftigte, Krankenhäuser, Schulen, Fläche, Finanzen, Verkehrstote |
| BKA — Polizeiliche Kriminalstatistik | 13 | Kriminalität (Fallzahlen je 100.000) |
| Projekt — eigene Berechnungen und Metadaten | 7 | `bl`, `ost`, `type` sowie abgeleitete Raten (`kaufkraft_proxy`, `verkehrstote_hz`, `betten_100k`, `schulen_100k`) |
| Zensus 2022 (Destatis) | 3 | Migration, Wohnfläche |
| VGR der Länder (Statistikportal der Länder) | 3 | Einkommen, BIP, VGR-Kurzname |
| BfN — WFS Naturschutzgebiete (Kreiszuordnung gegen BKG-VG250) | 3 | Naturschutz |
| KBV — Bundesarztregister (Versorgungsatlas) | 1 | Ärzte |
| Die Bundeswahlleiterin | 1 | Wahlbeteiligung |

Die Downloads selbst machen die `fetch_*.py`-Skripte (URLs siehe dort);
die Kreisgrenzen der BKG VG250 fließen nur als Geometrie in die
NSG-Zuordnung ein, nicht als eigene Datenspalten.

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
│   ├── merged_raw_base.json.xz.a85  # v1-Basis: 96 Spalten je AGS inkl. Registry-Metadaten (eingefrorener Stand, entpacken per unpack_base.py)
│   ├── genesis_neu.json             # 8 GENESIS-Spalten + 2 abgeleitete + 2 mig-Spalten (per parse_zensus aus mig_zensus.json eingearbeitet)
│   ├── mig_zensus.json              # Zensus-Rohwerte je AGS (Tabelle 1000A-1011; committete Ersatzquelle, da die Zensus-API derzeit 404 liefert)
│   ├── nsg_je_kreis.json            # 3 NSG-Spalten je AGS (BfN-WFS + VG250-Raster) + Validierungs-Metadaten (meta-Block)
│   ├── registry_new.json            # Registry-Metadaten der 13 neuen Spalten (10 aus genesis_neu + 3 aus nsg_je_kreis)
│   ├── deutschland-rohdaten.xlsx    # Release-Build (GitHub Actions hält ihn aktuell)
│   ├── deutschland-rohdaten.parquet # Release (R-Analyse, 400 x 109)
│   └── deutschland-variablen.parquet # Release (Registry, 109 Eintraege)
│       (merged_raw_base.json entpackt + merged_raw_v3.json + dist/* werden regeneriert)
├── site/                   # Karten-Frontend (GitHub Pages, siehe unten)
│   ├── index.html / style.css / app.js
│   └── data/ (generiert: map_data.json + kreise.geo.json, siehe unten)
├── raw/                    # Downloads (.gitignore'd)
└── dist/                   # generierte XLSX/Parquet (.gitignore'd)
```

`_site/` (Pages-Build-Artefakt) wird in der CI erzeugt und nie committet.

### Warum eine Wertedatei je Quelle?

Die Spaltenzuwächse liegen bewusst **getrennt je Datenquelle** statt in
einer gemeinsamen Datei — GENESIS (jährliche Tabellen), Zensus 2022
(final) und BfN-WFS (Rebuild nur mit 106 MB Rohdaten) haben
unterschiedliche Aktualisierungszyklen. So bleibt jeder Teilrebuild
klein (z. B. nur `parse_genesis.py` anfassen, ohne NSG-Rohdaten), und
die Prüfzahlen liegen direkt bei den Daten (`checks` in
`genesis_neu.json`, `meta` in `nsg_je_kreis.json`). Konsolidiert wird
erst in `merge.py` — auf Metadatenebene bereits in `registry_new.json`,
das alle 13 neuen Spalten unabhängig von ihrer Herkunft vereint.

Arithmetik: 96 (Basis) + 10 (GENESIS/Zensus) + 3 (BfN) = 109 Spalten;
Registry: 96 in der Basis eingebettet + 13 in `registry_new.json` = 109.

## Automatischer Release-Build (GitHub Actions)

`.github/workflows/build-xlsx.yml` läuft **bei jedem Push auf `main`**
und baut aus den committeten Basisdateien die drei Release-Artefakte
`data/deutschland-rohdaten.xlsx`, `data/deutschland-rohdaten.parquet`,
`data/deutschland-variablen.parquet`:

1. Pipeline: `unpack_base.py` → `parse_zensus.py` → `merge.py` →
   `build_xlsx.py` — mit Assertions gegen amtliche Prüfzahlen
   (KH 1.841, Betten 472.851, NSG 1.502.641 ha, …).
2. Parquet-Export nach `data/` (`export_parquet.py … data`) mit
   Rücklese-Verifikation: 400×109, Registry 109, `rs` als String mit
   führenden Nullen.
3. Bei inhaltlicher Änderung committiert der Bot selbst
   (`chore(data): … [skip ci]`).

Benötigt nur `openpyxl` + `pyarrow` (in der Action installiert) —
die Kernpipeline kommt ohne numpy aus. Auch manuell startbar:
*Actions → Build XLSX + Parquet → Run workflow*.

## Interaktive Karte (GitHub Pages)

`site/` enthält eine Choroplethen-Karte aller 109 Variablen für die
400 Kreise (Leaflet via CDN, keine Build-Tools). Der Workflow
`.github/workflows/pages.yml` deployt sie bei jedem Push auf `main`,
der `data/`, `src/` oder `site/` berührt:

- **Daten**: Pipeline-Verifikation läuft mit (`merge.py`-Assertions),
  dann schreibt `src/build_map.py` `_site/data/map_data.json`
  (Werte + Registry-Metadaten inkl. Themenblock).
- **Geometrie**: `fetch_vg250.py` (67 MB, BKG) → `build_map.py` liest
  VG250_KRS, projiziert UTM 32N → WGS84, vereinfacht per
  Douglas-Peucker (~150 m, ~2 MB GeoJSON) und verifiziert den
  rs-Join (400 ↔ 400). Alles Standardbibliothek — kein pip, kein npm.
- **Bedienung**: Themenblock wählen → Variable wählen; Hover zeigt
  Kreis + Wert, Klick öffnet die Kreis-Detailansicht mit **fünf
  Spitzen- und fünf Schlussplätzen** über alle numerischen Variablen
  (keine vollständigen Ranglisten). Platz 1 = höchster Wert —
  bewusst ohne Bewertung als „gut“/„schlecht“; eine
  Polaritäts-Konfiguration je Variable wäre ein mögliches Upgrade.
- **Klassifizierung**: Quintile der 400 Kreise (5 Klassen) —
  Kreisverteilungen sind stark schief, Linear-Skalen würden
  visuell fast alles in eine Klasse legen.
- **Attribution**: Kreisgrenzen © GeoBasis-DE / BKG (GeoNutzV),
  sichtbar auf der Karte und im Footer.

**Einmalige Aktivierung** (nicht per API machbar): *Settings →
Pages → Source: „GitHub Actions“*. Danach:
`https://<owner>.github.io/social-stats-deutschland/`

## Join-Schlüssel

`rs` = 5-stelliger Regionalschlüssel (AGS), Gebietsstand 31.12.2024,
Eisenach seit 2021 Teil des Wartburgkreises.
