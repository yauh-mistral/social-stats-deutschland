# -*- coding: utf-8 -*-
"""fetch_zensus.py — Zensus 2022 REST: Tabelle 1000A-1011 je Landkreis.

Laedt die Ergebnistabelle 1000A-1011 (Wohnbevoelkerung nach
Einwanderungsgeschichte, Stichtag 15.05.2022) je Landkreis ueber die
REST-API von ergebnisse.zensus2022.de nach raw/zensus/:
  - raw/zensus/str1011.json   (Tabellenstruktur / initialState)
  - raw/zensus/mig_data.json  (JSON-stat-Wuerfel)

VERIFIZIERTES REZEPT (02.10.2026, als der Endpunkt noch antwortete):

  1. GET  {B}/tables/1000A-1011/structure
     -> initialState mit tableStructure, contentBlocks, Variablen v1..v9
  2. POST {B}/tables/1000A-1011/data
     Body: {"initialState": <tiefe Kopie des initialState>}
     WICHTIG: initialState verpackt GENAU EINMAL in {"initialState": ...}
     - nicht in ein weiteres Objekt schachteln.
     initialState.tableStructure setzen:
       filter  : [s1 (blockType STATISTIC)]
       colTitle: [c1 (blockType CONTENT)]           -> absolute Zahlen:
                  initialState.contentBlocks.c1.functions = ['ID0004']
       rowTitle: [v6 (VARIABLE, GEOLK4 = Kreise) mit Kind v9 (WDGAT2)]
     Antwort: JSON-stat-Wuerfel
       DS_002: [content, WDGAT1, GEOLK4]  mit WDGAT1-Kategorien
               WANDERUNG-X-S2 (ohne) / WANDERUNG-EINS-S2 / EINGEWANDERTE /
               NACHKOMMEN
       DS_004: [content, WDGAT2, GEOLK4]  mit WDGAT2-Kategorien
               %TOTAL% / WANDERUNG-X-S1 / WANDERUNG-BEID-S1 / WANDERUNG-EINS-S1
     Der GEOLK4-Kategorie-Index enthaelt DIE AGS der 400 Kreise direkt
     ('05513' ...), die Bevoelkerungszahl steht in %TOTAL%.
     Umlaute/Sonderzeichen in Kategorien sind als Paragraph-Ersatz (Paragraph
     -> "S") kodiert; nicht auf die exakten Strings verlassen, sondern die
     Kategorien der Wuerfel-Dimension auslesen.

BEKANNTES PROBLEM (Stand 03.10.2026): der Tabellen-Endpunkt antwortet mit
404 ("nicht verfuegbar"), Basis-Endpunkte wie {B}/helloworld/whoami
funktionieren. Die mig-Werte liegen daher vollstaendig als
data/mig_zensus.json committet vor; parse_zensus.py liest standardmaessig
diese Datei und greift nur mit --from-raw auf raw/zensus/mig_data.json
zurueck, sobald der Endpunkt wieder liefert.

Aufruf:  python3 src/fetch_zensus.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "raw", "zensus")

BASE = "https://ergebnisse.zensus2022.de/proxy/api/rest"
TABLE = "1000A-1011"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get_structure():
    req = urllib.request.Request(BASE + "/tables/%s/structure" % TABLE,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def build_initial_state(stru):
    """initialState fuer den Datenabruf (s. Modul-Docstring)."""
    ist = json.loads(json.dumps(stru["initialState"]))  # tiefe Kopie
    ist["tableStructure"] = {
        "filter": [{"blockCode": "s1", "blockType": "STATISTIC",
                    "childBlocks": [], "possibleBlocks": []}],
        "colTitle": [{"blockCode": "c1", "blockType": "CONTENT",
                      "childBlocks": [], "possibleBlocks": []}],
        "rowTitle": [
            {"blockCode": "v6", "blockType": "VARIABLE",
             "childBlocks": [{"blockCode": "v9", "blockType": "VARIABLE",
                              "childBlocks": [], "possibleBlocks": []}],
             "possibleBlocks": []}],
    }
    ist["contentBlocks"]["c1"]["functions"] = ["ID0004"]  # absolute Zahlen
    return ist


def post_data(ist):
    body = json.dumps({"initialState": ist}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/tables/%s/data" % TABLE, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": UA},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def main():
    os.makedirs(OUT, exist_ok=True)

    print("GET Struktur", BASE + "/tables/%s/structure" % TABLE, "...")
    try:
        stru = get_structure()
    except urllib.error.HTTPError as e:
        sys.exit(
            "FEHLER: Struktur-Endpunkt antwortet mit HTTP %d.\n"
            "Die Zensus-API ist derzeit nicht verfuegbar (Stand 03.10.2026\n"
            "liefert der Tabellen-Endpunkt 404). Die mig-Werte sind als\n"
            "data/mig_zensus.json committet; parse_zensus.py faellt darauf\n"
            "zurueck. --from-raw nutzen, sobald die API wieder antwortet.\n"
            "Details: %s" % (e.code, e.read().decode("utf-8")[:500]))
    with open(os.path.join(OUT, "str1011.json"), "w", encoding="utf-8") as f:
        json.dump(stru, f, ensure_ascii=False)
    print("OK:", os.path.join(OUT, "str1011.json"))

    ist = build_initial_state(stru)
    print("POST Daten ... (initialState einmal in {\"initialState\": ...} verpackt)")
    try:
        resp = post_data(ist)
    except urllib.error.HTTPError as e:
        sys.exit(
            "FEHLER: Daten-Endpunkt antwortet mit HTTP %d — %s"
            % (e.code, e.read().decode("utf-8")[:500]))
    with open(os.path.join(OUT, "mig_data.json"), "w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False)
    print("OK:", os.path.join(OUT, "mig_data.json"))

    codes = [c["code"] for c in resp.get("data", [])]
    print("Wuerfel:", codes)
    print("Weiter: python3 src/parse_zensus.py --from-raw")


if __name__ == "__main__":
    main()
