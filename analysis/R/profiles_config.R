# profiles_config.R — Indikatoren, Richtungen und Profil-Gewichte
# Konfiguration fuer die Lebensqualitaets-Profile.
# Alle Variablen muessen in data/deutschland-rohdaten.parquet existieren.
# Richtung: +1 = hoeher ist besser, -1 = hoeher ist schlechter.

# ---------------------------------------------------------------------------
# Dimensionen mit Indikatoren (Richtung je Indikator)
# Bereits normierte Groessen (HZ je 100.000 EW, Prozent, Indizes) verwenden,
# damit grosse und kleine Kreise vergleichbar sind.
# ---------------------------------------------------------------------------
DIMENSIONS <- list(
  einkommen = c(
    verfeink_je_ew       = 1,    # verfuegbares Einkommen je EW (EUR)
    kaufkraft_proxy      = 1,    # preisbereinigte Kaufkraft (EUR)
    preisindex_wohnraum  = -1    # regionale Wohnraumkosten (Index, DE=100)
  ),
  wohnen = c(
    wohnflaeche_je_bewohner = 1, # m2 je Bewohner
    wohn_leer               = -1 # Leerstandsquote (%)
  ),
  arbeit = c(
    alq        = -1,              # Arbeitslosenquote (%)
    erw_wachs  = 1                # Erwerbstaetigenentwicklung (% p.a.)
  ),
  gesundheit = c(
    aerz            = 1,          # Aerzte je 100.000 EW
    betten_100k     = 1,          # Krankenhausbetten je 100.000 EW
    verkehrstote_hz = -1          # Verkehrstote je 100.000 EW
  ),
  kinder = c(
    v_karzt    = 1,               # Kinderaerzte je 100.000 U15
    kbetr_ue3  = 1,               # Betreuungsquote 3-<6 Jahre (%)
    kbetr_ue6  = 1                # Betreuungsquote 6-<11 Jahre (%)
  ),
  bildung = c(
    bquali_oabschl = -1,          # Beschaeftigte OHNE Berufs-/akad. Abschluss (%)
    schulen_100k   = 1            # Schulen je 100.000 EW
  ),
  sicherheit = c(
    strafen_gesamt_hz = -1,       # Straftaten gesamt je 100.000 EW
    gewalt_hz         = -1,       # Gewaltdelikte je 100.000 EW
    einbr             = -1        # Wohnungseinbruch je 100.000 EW
  ),
  umwelt = c(
    erholungsflaeche_prozent = 1, # Erholungsflaeche (% Kreisflaeche)
    nsg_anteil_prozent       = 1, # Naturschutzgebiete (% Kreisflaeche)
    fl_wald                  = 1  # Waldanteil (%)
  ),
  gemeinschaft = c(
    mitgl_sportv             = 1, # Sportvereinsmitglieder je 100 EW
    wahlbeteiligung_btw2025  = 1   # Wahlbeteiligung BTW 2025 (%)
  )
)

# ---------------------------------------------------------------------------
# OECD Regional Well-Being (9 Dimensionen) — Nachbau mit vorhandenen Daten.
# Blaupause: OECD Regional Well-Being / Better Life Index (11 Dimensionen;
# 'Life Satisfaction' und 'Work-Life-Balance' sind ohne Umfragedaten nicht
# abbildbar und entfallen; 'Health'/'Environment' laufen ueber Versorgungs-
# bzw. Landnutzungs-Proxies — das ist ausdrücklich schwächer als die
# OECD-Originale (Lebenserwartung, PM2.5) und als solches zu deklarieren.
# ---------------------------------------------------------------------------
OECD_DIMENSIONS <- list(
  income = c(
    verfeink_je_ew = 1,
    hh_veink       = 1,
    kaufkraft_proxy = 1
  ),
  jobs = c(
    alq        = -1,
    erw_wachs  = 1
  ),
  housing = c(
    wohnflaeche_je_bewohner = 1,
    preisindex_wohnraum     = -1,
    wohn_leer               = -1
  ),
  health = c(
    aerz        = 1,
    betten_100k = 1
  ),
  education = c(
    bquali_mabschl = 1,
    bquali_oabschl = -1,
    schule_oabschl = -1
  ),
  environment = c(
    erholungsflaeche_prozent = 1,
    fl_wald                  = 1,
    nsg_anteil_prozent       = 1
  ),
  safety = c(
    gewalt_hz = -1,
    einbr     = -1
  ),
  social_connections = c(
    mitgl_sportv            = 1,
    wahlbeteiligung_btw2025 = 1
  ),
  civic_engagement = c(
    wahlbeteiligung_btw2025 = 1
  )
)

# OECD-Profile: 9 Dimensionen gleichgewichtet (OECD published bewusst keinen
# Gesamtscore; hier fuer die Rangfolge dennoch gleichgewichtet aggregiert).
PROFILES$oecd <- list(
  label = "OECD Regional Well-Being (Nachbau, 9 Dimensionen gleichgewichtet)",
  weights = c(
    income            = 1,
    jobs              = 1,
    housing           = 1,
    health            = 1,
    education         = 1,
    environment       = 1,
    safety            = 1,
    social_connections = 1,
    civic_engagement   = 1
  )
)

# ---------------------------------------------------------------------------
# Profile: Gewichte je Dimension (0 = Dimension entfaellt im Profil).
# Die Gewichte sind begruendete Setzungen und bewusst editierbar —
# Sensitivitaet bitte immer mitlenken (siehe 02_rankings.R).
# ---------------------------------------------------------------------------
PROFILES <- list(
  familie = list(
    label = "Beste Lebensqualitaet fuer Familien",
    weights = c(
      einkommen   = 1.0,
      wohnen      = 1.5,   # Wohnflaeche, Kosten, Leerstand
      arbeit      = 1.0,
      gesundheit  = 1.0,
      kinder      = 2.0,   # Kita-Betreuung, Kinderaerzte: Kern des Profils
      bildung     = 1.5,
      sicherheit  = 1.5,
      umwelt      = 0.75,
      gemeinschaft = 0.75
    )
  ),
  rentner = list(
    label = "Beste Lebensqualitaet fuer Rentner:innen",
    weights = c(
      einkommen   = 1.0,
      wohnen      = 1.0,
      arbeit      = 0.25,  # irrelevant, aber nicht ganz 0 (Erwerbsumfeld)
      gesundheit  = 2.0,   # Aerztedichte, Krankenhausversorgung: Kern
      kinder      = 0,
      bildung     = 0.25,
      sicherheit  = 1.25,
      umwelt      = 1.0,
      gemeinschaft = 1.25  # Vereinsleben, soziale Teilhabe
    )
  ),
  urban = list(
    label = "Beste Lebensqualitaet fuer urbane Karriere-Menschen",
    weights = c(
      einkommen   = 1.5,
      wohnen      = 1.0,
      arbeit      = 1.5,   # Arbeitsmarkt-Dynamik
      gesundheit  = 1.0,
      kinder      = 0.5,
      bildung     = 1.0,
      sicherheit  = 0.75,
      umwelt      = 0.5,
      gemeinschaft = 1.0
    )
  ),
  natur = list(
    label = "Beste Lebensqualitaet fuer Natur- und Ruhe suchende",
    weights = c(
      einkommen   = 0.75,
      wohnen      = 1.25,
      arbeit      = 0.5,
      gesundheit  = 0.75,
      kinder      = 0.5,
      bildung     = 0.5,
      sicherheit  = 1.0,
      umwelt      = 2.0,   # Erholung, NSG, Wald: Kern des Profils
      gemeinschaft = 1.5
    )
  ),
  urban_kompakt = list(
    label = "Beste Lebensqualitaet fuer Bestandswohner in kompakten Staedten (Versorgung + Gruen)",
    weights = c(
      einkommen   = 0.5,   # niedrige Wohnkosten wirken teilweise dem Einkommen entgegen
      wohnen      = 1.0,
      arbeit      = 0.25,  # Arbeitsmarkt schwaecher gewichtet
      gesundheit  = 1.5,   # Aerzte/KH-Betten je EW: Staerken kompakter Staedte
      kinder      = 0.5,
      bildung     = 0.5,
      sicherheit  = 0.25,  # Kriminalitaet bewusst nieder-gewichtet
      umwelt      = 1.5,   # Erholungsflaeche/NSG: Gruen in der Stadt
      gemeinschaft = 0.5
    )
  )
)
