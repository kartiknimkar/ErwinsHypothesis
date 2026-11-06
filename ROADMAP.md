# Roadmap

Each item is built, tested, committed, and checked off in `HANDOFF.md`.

## Phase 0.5: Simple preview version (done 2026-11-06)
- [x] Stats engine: unpaired / Welch / paired t test, Mann-Whitney, linear regression (+95% band)
- [x] Tests against hand-computed and published (Anscombe) reference values
- [x] Local server serving the interface (fully offline; Plotly served from the installed package)
- [x] Interface: analysis list, editable grid (paste from Excel), plain-language results,
      dot/bar plots with significance bracket, regression plot, PNG/SVG export
- [x] Autosave in browser + Save/Open project file (`.ehp`, JSON)
- [x] `./run.sh` one-command launcher for macOS

## Phase 0.6: More modules + compact interface (done 2026-11-06)
- [x] Compare groups: 2 groups (t tests, Mann-Whitney) or 3+ (one-way ANOVA+Tukey, Welch+Games-Howell,
      Kruskal-Wallis+Dunn), Shapiro-Wilk normality, Brown-Forsythe/F variance warnings
- [x] XY: linear regression + Pearson/Spearman; nonlinear fits (dose-response IC50/EC50,
      Michaelis-Menten, exponential decay/growth, one-phase association) with replicate Y columns
- [x] Survival: Kaplan-Meier (log-log CI), log-rank (k groups), Mantel-Haenszel hazard ratio, medians
- [x] Contingency: chi-square, Fisher's exact, odds ratio, relative risk, risk difference
- [x] UI: compact layout, typed sidebar, add/remove columns, undo/redo, Format panel (palettes,
      point/font size, axis ranges, log axes, box plots, error-bar types, bracket stacking), Copy results
- [x] Tests cross-check vs statsmodels, pingouin, scikit-posthocs, lifelines (35 tests)

## Phase 0.7: Two-way & repeated measures (done 2026-11-06)
- [x] Grouped analysis: two-way ANOVA (Type III SS, unequal n), % variation, within-row comparisons
      (Šídák for 2 columns, Tukey for 3+), cell means, grouped bar / dot / interaction plots
- [x] Compare groups "same subjects" design: paired t, Wilcoxon signed-rank, RM one-way ANOVA
      (Geisser-Greenhouse) + Tukey, Friedman + Dunn's; before-after (connected) plot
- [x] Cross-checked vs statsmodels (Type III) and pingouin (RM ANOVA, epsilon); 41 tests

## Phase 0.8: Import + curve models (done 2026-11-06)
- [x] Import data from Excel (.xlsx, sheet picker) and CSV/TSV/TXT (header row detection,
      European decimals); adds openpyxl (pure-Python wheel)
- [x] New models: dose-response standard slope (3-param), two-phase decay, Gaussian, Boltzmann
- [x] Model comparison: extra sum-of-squares F test (nested pairs) + AICc; dashed second curve
- [x] 49 tests

## Phase 0.9: Constraints + Excel export (done 2026-11-06)
- [x] Curve fits: hold any parameter fixed (e.g. Bottom = 0, Top = 100); df/AICc use free params only
- [x] Export results + data to .xlsx in the exports folder (numbers stored as numbers)
- [x] 51 tests

## Phase 0: Foundations
- [x] Repo layout, roadmap, handoff protocol
- [ ] Backend: FastAPI app, health endpoint, test setup (pytest)
- [ ] Frontend: Vite + React + TypeScript shell with sidebar layout
- [ ] One-command launch script for macOS (`./run.sh`)

## Phase 1: Data & projects
- [ ] Data table types: XY, Column, Grouped (replicates, error values)
- [ ] Spreadsheet-style data grid (paste from Excel, keyboard navigation)
- [ ] Import CSV / Excel; export CSV
- [ ] Project file (`.ehp`, a zip of JSON + data): save, open, autosave
- [ ] Project navigator: Data tables → Analyses → Graphs, linked and auto-updating

## Phase 2: Core analyses (order to be confirmed with user)
- [ ] Descriptive statistics, normality tests (Shapiro-Wilk, D'Agostino)
- [ ] t-tests: unpaired, Welch, paired; Mann-Whitney, Wilcoxon
- [ ] One-way ANOVA (+ Tukey, Dunnett, Šídák, Bonferroni), Kruskal-Wallis + Dunn
- [ ] Two-way ANOVA (+ multiple comparisons), repeated measures
- [ ] Correlation (Pearson, Spearman), simple linear regression
- [ ] Nonlinear regression: dose-response (3/4-parameter logistic, IC50/EC50),
      exponential, Michaelis-Menten, user-defined equations; CIs, model comparison
- [ ] Survival: Kaplan-Meier, log-rank, hazard ratios
- [ ] Contingency tables: chi-square, Fisher's exact

## Phase 3: Graphs
- [ ] Column/scatter/bar with error bars, XY with fitted curves, survival curves
- [ ] Significance annotations (asterisks, brackets) from analysis results
- [ ] Full styling editor (axes, ticks, log scales, fonts, colors, legends)
- [ ] Export PNG / SVG / PDF / TIFF at publication DPI

## Phase 4: Polish & packaging
- [ ] Layouts (multiple graphs per page)
- [ ] Undo/redo everywhere
- [ ] Mac app bundle (.dmg)
- [ ] Results reports and analysis checklists
