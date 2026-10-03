# 01_load_prepare.R — Daten laden, Profil-Konfiguration einlesen,
# robuste Standardisierung je Indikator (Winsorisierung + z-Score).
#
# Voraussetzung: data/deutschland-rohdaten.parquet existiert
# (siehe src/export_parquet.py bzw. GitHub Action).
#
# Aufruf: source("analysis/R/01_load_prepare.R")  — aus dem Repo-Wurzelverzeichnis

require(arrow)
require(dplyr)

# ---- Konfiguration (Indikatoren, Richtungen, Profile) --------------------
source("analysis/R/profiles_config.R")

# Vereinigung der Dimensionen aus beiden Frameworks (Namen kollidieren nicht)
ALL_DIMENSIONS <- c(DIMENSIONS, OECD_DIMENSIONS)

PARQUET_RAW <- "data/deutschland-rohdaten.parquet"

# ---- Laden und Validieren -------------------------------------------------
kreise_raw <- read_parquet(PARQUET_RAW)
stopifnot(nrow(kreise_raw) == 400)

# Alle konfigurierten Indikatoren muessen existieren
all_ind <- unique(unlist(lapply(ALL_DIMENSIONS, names)))
missing <- setdiff(all_ind, names(kreise_raw))
if (length(missing) > 0) {
  stop("Fehlende Indikatoren im Datensatz: ", paste(missing, collapse = ", "))
}

# ---- Hilfsfunktionen ------------------------------------------------------

#' Winsorisieren: Extremwerte auf die p- bzw. (1-p)-Quantile kappen
winsorize <- function(x, p = 0.01) {
  q <- quantile(x, c(p, 1 - p), na.rm = TRUE)
  pmin(pmax(x, q[1]), q[2])
}

#' Robuster z-Score (Median/MAD), skaliert auf SD-aehnliche Streuung
robust_z <- function(x) {
  med <- median(x, na.rm = TRUE)
  mad <- mad(x, na.rm = TRUE)
  if (mad == 0) mad <- sd(x, na.rm = TRUE)
  if (is.na(mad) || mad == 0) return(rep(0, length(x)))
  (x - med) / (mad * 1.4826)
}

# ---- Standardisierung -----------------------------------------------------
# Je Indikator: winsorisieren -> Richtung anwenden -> robuster z-Score.
# "hoeher = besser" ist danach einheitlich fuer alle standardisierten Spalten.
z_cols <- lapply(all_ind, function(v) {
  direction <- unique(
    vapply(ALL_DIMENSIONS, function(d) if (v %in% names(d)) d[[v]], numeric(1))
  )
  stopifnot(length(direction) == 1)
  raw <- as.numeric(kreise_raw[[v]])
  raw <- winsorize(raw)
  z <- robust_z(raw)
  z * direction
})
names(z_cols) <- all_ind

kreise <- kreise_raw %>%
  as.data.frame() %>%
  cbind(do.call(data.frame, lapply(z_cols, function(z) data.frame(z = z))))

# sprechende Namen: z_<indikator>
zdf <- do.call(data.frame, lapply(z_cols, function(z) data.frame(x = z)))
names(zdf) <- paste0("z_", all_ind)
kreise <- cbind(as.data.frame(kreise_raw), zdf)

# ---- Dimensionsscores ----------------------------------------------------
# Gleichgewichtetes Mittel der z-Scores je Dimension (na.rm: robust gegen
# einzelne fehlende Indikatoren; vollstaendige Daten hier ohnehin gegeben).
for (dim in names(ALL_DIMENSIONS)) {
  z_vars <- paste0("z_", names(ALL_DIMENSIONS[[dim]]))
  kreise[[paste0("dim_", dim)]] <- rowMeans(kreise[, z_vars], na.rm = TRUE)
}

message("01_load_prepare: ", nrow(kreise), " Kreise, ",
        length(all_ind), " Indikatoren, ", length(ALL_DIMENSIONS),
        " Dimensionsscores, ", length(PROFILES), " Profile konfiguriert.")
