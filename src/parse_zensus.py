# -*- coding: utf-8 -*-
"""parse_zensus.py — Zensus-2022-Migrationsspalten in genesis_neu.json einarbeiten.

Die Werte (mig_eingewandert, mig_geschichte, je AGS, Prozent der
Bevoelkerung, Stichtag 15.05.2022) stammen aus der Ergebnistabelle
1000A-1011 des Zensus 2022 (Wohnbevoelkerung nach Einwanderung) und sind
als data/mig_zensus.json committet — der Tabellen-Endpunkt von
ergebnisse.zensus2022.de antwortet derzeit nicht (404, Stand 03.10.2026),
daher ist der Datenweg hier bewusst ueber die committete Datei gelegt.

Sobald fetch_zensus.py wieder liefert (Rezept siehe dort), koennen die
Werte aus dem Rohdaten-Wuerfel neu gerechnet werden:

    python3 src/parse_zensus.py --from-raw    # raw/zensus/mig_data.json

Umrechnung aus dem Wuerfel (JSON-stat, Reihenfolge: Geo am schnellsten):
    mig_eingewandert = EINGEWANDERTE / %TOTAL% * 100   (1 Dezimalstelle)
    mig_geschichte   = (100 - WANDERUNG-X / %TOTAL% * 100) — "mit
    Einwanderungsgeschichte" (ein- oder beidseitig)

Validierung: Gelsenkirchen (05513) 25,4 / 32,9;
            Deutschland-Referenz 18,8 / 23,6.

Aufruf:  python3 src/parse_zensus.py [--from-raw | --selftest]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
RAW_Z = os.path.join(ROOT, "raw", "zensus")

MIG_KEYS = ("mig_eingewandert", "mig_geschichte")


def aus_wuerfel(d):
    """JSON-stat-Wuerfel (fetch_zensus.py) -> {mig_eingewandert, mig_geschichte}.

    DS_004: [content, WDGAT2, GEOLK4] mit %TOTAL%, WANDERUNG-X (ohne),
            WANDERUNG-BEID, WANDERUNG-EINS; content-Index 1 = absolute Zahl.
    DS_002: [content, WDGAT1, GEOLK4] mit EINGEWANDERTE.
    """
    def cube(name):
        for c in d["data"]:
            if c["code"] == name:
                return c
        raise KeyError(name)

    def var_index(c, var_prefix):
        for k in c["dimension"]:
            if k.startswith(var_prefix):
                return c["dimension"][k]["category"]["index"]
        raise KeyError(var_prefix)

    w2 = cube("DS_004")
    w1 = cube("DS_002")
    idx2 = var_index(w2, "WDGAT")
    idx1 = var_index(w1, "WDGAT")
    geo2 = var_index(w2, "GEO")
    geo1 = var_index(w1, "GEO")
    n_geo = len(geo2)
    n_content2 = len(w2["dimension"]["content"]["category"]["index"])
    n_content1 = len(w1["dimension"]["content"]["category"]["index"])

    def anzahl_index(content_idx):
        """Content mit ID-Funktion = absolute Zahl (sonst Anteil)."""
        for code, i in content_idx.items():
            if "ID" in code and i > 0:
                return i
        return 1

    anzahl2 = anzahl_index(w2["dimension"]["content"]["category"]["index"])
    anzahl1 = anzahl_index(w1["dimension"]["content"]["category"]["index"])
    vals2 = w2["value"]
    vals1 = w1["value"]

    # Kategorie-Codes robust suchen (Sonderzeichen der API variieren):
    def find_key(idx, marker, alt_markers):
        for code in idx:
            if all(m in code for m in marker) or any(m in code for m in alt_markers):
                return code, idx[code]
        raise KeyError(marker)

    tot2, _ = find_key(idx2, ("%TOTAL%",), [])
    ohne, _ = find_key(idx2, ("WANDERUNG", "X"), [])
    eing, _ = find_key(idx1, ("EINGEWANDERTE",), [])

    eingewandert, geschichte = {}, {}
    for ags, gi in geo2.items():
        insg = vals2[(idx2[tot2] * n_content2 + anzahl2) * n_geo + gi]
        assert insg > 0, ags
        eingewandert[ags] = round(
            vals1[(idx1[eing] * n_content1 + anzahl1) * n_geo + gi] / insg * 100, 1)
        ohne_v = vals2[(idx2[ohne] * n_content2 + anzahl2) * n_geo + gi]
        geschichte[ags] = round(100 - ohne_v / insg * 100, 1)
    return {"mig_eingewandert": eingewandert, "mig_geschichte": geschichte}


def selftest():
    """Synthetischer Mini-Wuerfel (2 Kreise) prueft die Index-Arithmetik.

    Dimensionsreihenfolge der API: [Var, content, Geo] — Geo variiert am
    schnellsten, value-Index = (vi * n_content + ci) * n_geo + gi.
    """
    d = {"data": [
        {"code": "DS_004", "id": ["WDGAT2", "content", "GEOLK4"],
         "size": [3, 2, 2], "value": [], "dimension": {
             "content": {"category": {"index": {"Anteil PO0006": 0, "Anzahl ID0006": 1}}},
             "WDGAT2": {"category": {"index": {
                 "%TOTAL%": 0, "WANDERUNG-X-S1": 1, "WANDERUNG-BEID-S1": 2}}},
             "GEOLK4": {"category": {"index": {"05513": 0, "11000": 1}}}}},
        {"code": "DS_002", "id": ["WDGAT1", "content", "GEOLK4"],
         "size": [2, 2, 2], "value": [], "dimension": {
             "content": {"category": {"index": {"Anteil PO0004": 0, "Anzahl ID0004": 1}}},
             "WDGAT1": {"category": {"index": {
                 "WANDERUNG-X-S2": 0, "EINGEWANDERTE": 1}}},
             "GEOLK4": {"category": {"index": {"05513": 0, "11000": 1}}}}}]}

    def fill(cube, f):
        c = next(x for x in d["data"] if x["code"] == cube)
        n_var, n_content, n_geo = c["size"]
        c["value"] = [f(vi, ci, gi) for vi in range(n_var)
                      for ci in range(n_content) for gi in range(n_geo)]

    # Gelsenkirchen-artig: 1000 Einw., 250 Eingewanderte, 670 ohne Geschichte
    # (ci=0 = Anteile als Dummy, ci=1 = absolute Zahlen)
    fill("DS_004", lambda vi, ci, gi:
         ([1000, 670, 320][vi] if ci else 0) if gi == 0
         else ([500, 400, 100][vi] if ci else 0))
    fill("DS_002", lambda vi, ci, gi:
         ([670, 250][vi] if ci else 0) if gi == 0
         else ([400, 50][vi] if ci else 0))
    res = aus_wuerfel(d)
    assert res["mig_eingewandert"]["05513"] == 25.0, res
    assert res["mig_geschichte"]["05513"] == 33.0, res
    assert res["mig_eingewandert"]["11000"] == 10.0, res
    assert res["mig_geschichte"]["11000"] == 20.0, res
    print("selftest OK: Wuerfel-Arithmetik stimmt (2/2 Kreise)")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    from_raw = "--from-raw" in sys.argv

    if from_raw:
        raw_path = os.path.join(RAW_Z, "mig_data.json")
        with open(raw_path, encoding="utf-8") as f:
            mig = aus_wuerfel(json.load(f))
        with open(os.path.join(DATA, "mig_zensus.json"), "w", encoding="utf-8") as f:
            json.dump(mig, f, ensure_ascii=False, indent=1)
        print("OK: aus Wuerfel berechnet ->", os.path.join(DATA, "mig_zensus.json"))
    else:
        with open(os.path.join(DATA, "mig_zensus.json"), encoding="utf-8") as f:
            mig = json.load(f)

    with open(os.path.join(DATA, "genesis_neu.json"), encoding="utf-8") as f:
        gen = json.load(f)

    base_path = os.path.join(DATA, "merged_raw_base.json")
    if not os.path.exists(base_path):
        raise SystemExit("data/merged_raw_base.json fehlt — erst src/unpack_base.py laufen lassen")
    with open(base_path, encoding="utf-8") as f:
        ags_list = [str(r["rs"]) for r in json.load(f)["rows"]]

    for k in MIG_KEYS:
        assert k in mig, k
        vals = mig[k]
        missing = [a for a in ags_list if a not in vals]
        assert not missing, "fehlende AGS in %s: %s" % (k, missing[:5])
        gen[k] = {a: vals[a] for a in ags_list}

    # --- Pruefzahlen ---
    ge = gen["mig_eingewandert"]["05513"], gen["mig_geschichte"]["05513"]
    assert ge == (25.4, 32.9), ge
    checks = {
        "mig_Gelsenkirchen_eingewandert": gen["mig_eingewandert"]["05513"],
        "mig_Gelsenkirchen_geschichte": gen["mig_geschichte"]["05513"],
        "mig_DE_eingewandert": 18.8,
        "mig_DE_ohne": 76.3,
    }
    gen.setdefault("checks", {}).update(checks)

    path = os.path.join(DATA, "genesis_neu.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(gen, f, ensure_ascii=False, indent=1)
    print("OK:", path, "| Spalten:", len([k for k in gen if not k.startswith("checks")]))
    print("Gelsenkirchen:", ge, "(Soll 25.4 / 32.9)")


if __name__ == "__main__":
    main()
