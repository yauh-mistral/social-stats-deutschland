# 02_rankings.R — Profil-Scores, Rankings und Kreuz-Vergleich der Profile.
# Muss nach 01_load_prepare.R laufen.
#
# Aufruf: source("analysis/R/01_load_prepare.R");
#         source("analysis/R/02_rankings.R")

require(dplyr)
require(readr)
require(tidyr)

OUT_DIR <- "dist/analysis"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

# ---- Profil-Score je Kreis ------------------------------------------------
# Score = gewichteter Mittelwert der Dimensionsscores (Gewichte aus
# profiles_config.R; Gewichte werden vor Mittelung auf Summe 1 normiert).
for (p in names(PROFILES)) {
  w <- PROFILES[[p]]$weights
  w <- w[w > 0]
  stopifnot(all(names(w) %in% names(DIMENSIONS)))
  w_norm <- w / sum(w)
  score <- rep(NA_real_, nrow(kreise))
  for (d in names(w_norm)) {
    score <- score + w_norm[[d]] * kreise[[paste0("dim_", d)]]
  }
  kreise[[paste0("score_", p)]] <- score
  kreise[[paste0("rank_", p)]]  <- rank(-score, ties.method = "min")
}

score_cols <- paste0("score_", names(PROFILES))
rank_cols  <- paste0("rank_", names(PROFILES))

# ---- Top-10 je Profil (Konsole + CSV) --------------------------------------
top_cols <- c("rank", "name", "bl", "type", "ost", "pop", "rs", score_cols)
for (p in names(PROFILES)) {
  cat("\n=====", PROFILES[[p]]$label, "— Top 10 =====\n")
  top <- kreise %>%
    select(rs, name, bl, type, ost, pop, score = !!paste0("score_", p)) %>%
    arrange(desc(score)) %>%
    head(10) %>%
    mutate(rank = row_number())
  print(as.data.frame(top), row.names = FALSE, digits = 3)
  write_csv(top, file.path(OUT_DIR, paste0("top10_", p, ".csv")))
}

# ---- Gesamt-Tabelle aller Profil-Rankings ---------------------------------
rankings <- kreise %>%
  select(rs, name, bl, type, ost, pop, all_of(rank_cols), all_of(score_cols)) %>%
  arrange(score_familie)
write_csv(rankings, file.path(OUT_DIR, "profile_rankings.csv"))

# ---- Kreuz-Vergleich: Profil-Allianzen ------------------------------------
# Spearman-Rangkorrelation zwischen den Profil-Scores zeigt, welche Profile
# aehnliche Kreise praemieren — und welche bewusst gegenlaeufig sind.
cor_mat <- cor(kreise[, score_cols], method = "spearman",
               use = "pairwise.complete.obs")
cat("\n===== Spearman-Rangkorrelation der Profil-Scores =====\n")
print(round(cor_mat, 2))

# Stabilitaet: Ranguebereinstimmung Top-50 je Profelpaar
top_sets <- lapply(names(PROFILES), function(p) {
  kreise$rs[order(-kreise[[paste0("score_", p)]])][1:50]
})
names(top_sets) <- names(PROFILES)
overlap <- outer(names(top_sets), names(top_sets), Vectorize(function(a, b) {
  length(intersect(top_sets[[a]], top_sets[[b]]))
}))
dimnames(overlap) <- list(names(top_sets), names(top_sets))
cat("\n===== Top-50-Uebereinstimmung je Profilepaar (Anzahl Kreise) =====\n")
print(overlap)

message("02_rankings: Ergebnisse unter ", OUT_DIR,
        " (profile_rankings.csv, top10_<profil>.csv).")
