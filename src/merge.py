# -*- coding: utf-8 -*-
"""merge.py — merged_raw_v3.json erzeugen (109 Spalten × 400 Kreise).

Vereinigt die v1-Basis (96 Spalten, data/merged_raw_base.json) mit:
  - data/genesis_neu.json   (10 Spalten aus GENESIS / Zensus 2022)
  - data/nsg_je_kreis.json  (3 Spalten aus BfN-WFS + VG250-Rasterzuordnung)

Die 13 neuen Spalten werden thematisch einsortiert:
  nach v_karzt   (Gesundheit):  krankenhaeuser, betten, betten_100k
  nach schul     (Bildung):     schulen_anzahl, schulen_100k
  nach fl_landw  (Umwelt):      flaeche_km2, wasserflaeche_prozent,
                                erholungsflaeche_prozent, nsg_anzahl,
                                nsg_ha, nsg_anteil_prozent
  nach bev_ausl  (Demografie):  mig_eingewandert, mig_geschichte

Abgeleitete Größen (100k-Raten, Prozentanteile) werden hier neu berechnet
und müssen exakt den Werten aus genesis_neu.json entsprechen (Assertion).

Aufruf:  python3 src/merge.py   (aus dem Repo-Wurzelverzeichnis)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    base = load("merged_raw_base.json")
    genesis = load("genesis_neu.json")
    nsg = load("nsg_je_kreis.json")
    reg_new = load("registry_new.json")

    rows = base["rows"]
    assert len(rows) == 400, len(rows)

    # --- Werte je Kreis zusammensetzen und abgeleitete Groessen pruefen ---
    new_vals = {}  # rs -> {key: value} fuer alle 13 neuen Spalten
    for r in rows:
        rs = str(r["rs"])
        pop = float(r["pop"])
        kh = int(genesis["krankenhaeuser"][rs])
        betten = int(genesis["betten"][rs])
        schulen = int(genesis["schulen_anzahl"][rs])
        flaeche_km2 = genesis["flaeche_km2"][rs]
        nsg_ha = float(nsg["nsg_ha"][rs])
        nsg_anz = int(nsg["nsg_anzahl"][rs])

        v = {
            "krankenhaeuser": kh,
            "betten": betten,
            "betten_100k": round(betten / pop * 100000, 1),
            "schulen_anzahl": schulen,
            "schulen_100k": round(schulen / pop * 100000, 1),
            "flaeche_km2": flaeche_km2,
            "nsg_anzahl": nsg_anz,
            "nsg_ha": nsg_ha,
            # nsg_anteil_prozent: verbindlicher Wert aus parse_nsg.py
            # (dort gegen die Raster-Kreisflaeche gerechnet; weicht in 3
            # Grenzfaellen um 0,01 pp von der GENESIS-Flaeche ab)
            "nsg_anteil_prozent": float(nsg["nsg_anteil_prozent"][rs]),
            "mig_eingewandert": genesis["mig_eingewandert"][rs],
            "mig_geschichte": genesis["mig_geschichte"][rs],
            "wasserflaeche_prozent": genesis["wasserflaeche_prozent"][rs],
            "erholungsflaeche_prozent": genesis["erholungsflaeche_prozent"][rs],
        }

        # --- Validierung: abgeleitete Groessen == Quelldaten ---
        assert v["betten_100k"] == genesis["betten_100k"][rs], (rs, "betten_100k")
        assert v["schulen_100k"] == genesis["schulen_100k"][rs], (rs, "schulen_100k")
        # Plausibilitaet: Nachberechnung gegen die GENESIS-Flaeche (Tol. 0,02 pp)
        assert abs(v["nsg_anteil_prozent"]
                   - round(nsg_ha / (flaeche_km2 * 100) * 100, 2)) <= 0.02, (rs, "nsg_anteil")
        new_vals[rs] = v

    # --- Spaltenliste thematisch einsortieren ---
    insert_after = [
        ("v_karzt", ["krankenhaeuser", "betten", "betten_100k"]),
        ("schul", ["schulen_anzahl", "schulen_100k"]),
        ("fl_landw", ["flaeche_km2", "wasserflaeche_prozent", "erholungsflaeche_prozent",
                      "nsg_anzahl", "nsg_ha", "nsg_anteil_prozent"]),
        ("bev_ausl", ["mig_eingewandert", "mig_geschichte"]),
    ]
    base_keys = [c["key"] for c in base["columns"]]
    columns = []
    for c in base["columns"]:
        columns.append(dict(c))
        for anchor, keys in insert_after:
            if c["key"] == anchor:
                for k in keys:
                    reg = reg_new[k]
                    columns.append({
                        "key": k,
                        "label": reg["label"],
                        "einheit": reg["einheit"],
                        "quelle": reg["quelle"],
                        "jahr": reg["jahr"],
                        "link": reg["link"],
                        "anmerkung": reg["anmerkung"],
                        "block": c["block"],
                    })
    assert len(columns) == 109, len(columns)

    # --- Zeilen anreichern ---
    for r in rows:
        rs = str(r["rs"])
        r.update(new_vals[rs])

    out = {"columns": columns, "rows": rows}
    # falls die Basis weitere Metadaten-Schluessel traegt, uebernehmen
    for k, v in base.items():
        if k not in ("columns", "rows"):
            out.setdefault(k, v)

    path = os.path.join(DATA, "merged_raw_v3.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    # --- Pruefzahlen ---
    keys = [c["key"] for c in columns]
    assert keys[base_keys.index("v_karzt") + 1] == "krankenhaeuser"
    assert keys.index("mig_geschichte") == keys.index("bev_ausl") + 2
    s_kh = sum(v["krankenhaeuser"] for v in new_vals.values())
    s_be = sum(v["betten"] for v in new_vals.values())
    s_sc = sum(v["schulen_anzahl"] for v in new_vals.values())
    s_fl = round(sum(v["flaeche_km2"] for v in new_vals.values()))
    s_nsgha = round(sum(v["nsg_ha"] for v in new_vals.values()))
    n_mit = sum(1 for v in new_vals.values() if v["nsg_ha"] > 0)
    print("OK:", path)
    print("Spalten:", len(columns), "| Zeilen:", len(rows))
    print("KH-Summe:", s_kh, "(Soll 1841) | Betten:", s_be, "(Soll 472851)")
    print("Schulen:", s_sc, "(Soll 30604) | Flaeche km2:", s_fl, "(Soll 357586)")
    print("NSG ha gesamt:", s_nsgha, "(Soll 1502641) | Kreise mit NSG:", n_mit, "(Soll 385)")
    print("Gelsenkirchen 05513:", new_vals["05513"]["mig_eingewandert"],
          new_vals["05513"]["mig_geschichte"], "(Soll 25.4 / 32.9)")
    assert s_kh == 1841 and s_be == 472851 and s_sc == 30604
    assert s_fl == 357586 and s_nsgha == 1502641 and n_mit == 385


if __name__ == "__main__":
    main()
