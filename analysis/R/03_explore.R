# 03_explore.R — Explorative Begutachtung: Verteilungen, Korrelationsstruktur
# der Indikatoren und Profil-Scores, PCA zur Validierung der Dimensionen.
# Muss nach 01_load_prepare.R laufen.
#
# Aufruf: source("analysis/R/01_load_prepare.R");
#         source("analysis/R/03_explore.R")

require(dplyr)
require(tidyr)
require(ggplot2)

OUT_DIR <- "dist/analysis"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

all_ind <- unique(unlist(lapply(DIMENSIONS, names)))
z_vars  <- paste0("z_", all_ind)
dim_vars <- paste0("dim_", names(DIMENSIONS))

# ---- 1. Korrelationsstruktur der (orientierten) Indikatoren --------------
cor_mat <- cor(kreise[, z_vars], method = "spearman",
               use = "pairwise.complete.obs")

# Indikatorenpaare mit |rho| >= 0.8: Redundanzwarnung
high <- which(abs(cor_mat) >= 0.8 & upper.tri(cor_mat), arr.ind = TRUE)
cat("===== Stark korrelierte Indikatorenpaare (|rho| >= 0.8) =====\n")
if (nrow(high) > 0) {
  pairs_df <- data.frame(
    a = z_vars[high[, "row"]],
    b = z_vars[high[, "col"]],
    rho = cor_mat[high]
  ) %>% arrange(desc(abs(rho)))
  print(pairs_df, row.names = FALSE)
} else {
  cat("Keine — Indikatorenauswahl ist faktisch unkorreliert genug.\n")
}

# ---- 2. PCA: Ist "Lebensqualitaet" hier ein Faktor? -----------------------
pca <- prcomp(kreise[, z_vars], center = FALSE, scale. = FALSE)
var_expl <- pca$sdev^2 / sum(pca$sdev^2)
cat("\n===== PCA auf den z-Indikatoren (Varianzanteil) =====\n")
print(round(head(var_expl, 5), 3))
cat("Cum. Varianz der ersten 3 Komponenten:",
    round(sum(var_expl[1:3]), 3), "\n")

# Ladungen der ersten beiden Komponenten je Dimensionsscore
pca_scores <- prcomp(kreise[, dim_vars], center = TRUE, scale. = FALSE)
load12 <- data.frame(
  dimension = names(DIMENSIONS),
  PC1 = pca_scores$rotation[, 1],
  PC2 = pca_scores$rotation[, 2]
)
cat("\n===== PCA (Dimensionsscores): Ladungen PC1/PC2 =====\n")
print(load12, row.names = FALSE, digits = 3)

# ---- 3. Heatmap der Dimensionsscores (Top-Kreise je Profil) ----------------
top_kreise <- unique(unlist(lapply(names(PROFILES), function(p) {
  kreise$rs[order(-kreise[[paste0("score_", p)]])][1:10]
})))
heat <- kreise %>%
  filter(rs %in% top_kreise) %>%
  select(rs, name, all_of(dim_vars)) %>%
  pivot_longer(all_of(dim_vars), names_to = "dimension",
                values_to = "score") %>%
  mutate(dimension = sub("^dim_", "", dimension))

p <- ggplot(heat, aes(x = dimension, y = reorder(name, -score),
                      fill = score)) +
  geom_tile() +
  scale_fill_gradient2(low = "#b2182b", mid = "white", high = "#2166ac") +
  labs(title = "Dimensionsscores der Top-10-Kreise je Profil",
       x = "Dimension", y = "", fill = "z-Score") +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))
ggsave(file.path(OUT_DIR, "heatmap_top_kreise.png"), p,
       width = 10, height = 8, dpi = 150)

# ---- 4. Scatter: zwei Profile gegenueberstellen ----------------------------
# Zeigt, welche Kreise fuer unterschiedliche Zielgruppen unterschiedlich
# gut abschneiden (z. B. urban vs. natur).
if (all(c("score_urban", "score_natur") %in% names(kreise))) {
  p2 <- ggplot(kreise, aes(x = score_urban, y = score_natur,
                          label = name)) +
    geom_point(aes(color = factor(ost)), size = 2, alpha = 0.8) +
    geom_hline(yintercept = 0, linetype = "dashed", alpha = 0.4) +
    geom_vline(xintercept = 0, linetype = "dashed", alpha = 0.4) +
    ggrepel::geom_text_repel(
      data = kreise %>% filter(
        rank_urban <= 10 | rank_natur <= 10),
      max.overlaps = 20, size = 3) +
    scale_color_manual(values = c(`0` = "#2166ac", `1` = "#b2182b"),
                       name = "Ost") +
    labs(title = "Urbanes Profil vs. Natur-Profil",
         x = "Score urban", y = "Score natur") +
    theme_minimal()
  ggsave(file.path(OUT_DIR, "scatter_urban_natur.png"), p2,
         width = 8, height = 6, dpi = 150)
}

message("03_explore: Grafiken und Statistiken unter ", OUT_DIR, ".")
