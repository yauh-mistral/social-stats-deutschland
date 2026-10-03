# run_all.R — Kompletter Analyselauf: Daten vorbereiten, Rankings bauen,
# explorative Statistiken und Grafiken erzeugen.
#
# Aufruf aus dem Repo-Wurzelverzeichnis:
#   Rscript analysis/R/run_all.R

t0 <- Sys.time()

source("analysis/R/01_load_prepare.R")
source("analysis/R/02_rankings.R")
source("analysis/R/03_explore.R")

message("run_all: fertig in ", round(as.numeric(difftime(Sys.time(), t0,
          units = "secs")), 1), " s.")
