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

## Phase 0.10: User-defined equations (done 2026-11-06)
- [x] Type any equation (safe AST parser: arithmetic + whitelisted math functions only),
      parameters detected automatically, starting values, constraints; 68 tests

## Phase 0.11: Standard curves + colors (done 2026-11-06)
- [x] Interpolate unknowns from any fitted curve (rows with blank X): linear, 4PL, custom; no extrapolation
- [x] Per-series color pickers in the Format panel (by series name, saved with the graph)
- [x] 72 tests

## Phase 0.12: Outliers + AUC (done 2026-11-06)
- [x] Grubbs' outlier test (iterative, two-sided) per group; outliers circled on the graph
- [x] Area under the curve for XY data (trapezoid on mean Y, baseline, exact split at crossings)
- [x] 75 tests

## Phase 0.13: Multiple variables + diagnostics (done 2026-11-06)
- [x] Correlation matrix (Pearson/Spearman, pairwise deletion, CIs) with heatmap
- [x] ROC curve (AUC = Mann-Whitney, Hanley-McNeil SE, cutoff table, Youden best cutoff)
- [x] Bland-Altman (bias, limits of agreement with CIs, proportional-bias check)
- [x] 79 tests

## Phase 0.14: Transform & normalize (done 2026-11-06)
- [x] Transform dialog → new analysis: normalize 0–100% (min/max or chosen values), % of first row,
      log10, ln, reciprocal, square root, Y×K+C; X transforms for XY tables

## Phase 0.15: Multiple t tests (done 2026-11-06)
- [x] One t test per row name (Welch/unpaired/Mann-Whitney), Benjamini-Hochberg FDR, volcano plot; 81 tests

## Phase 0.16: Multiple & logistic regression (done 2026-11-06)
- [x] Multiple linear regression (coefficients, CIs, VIF, R²/adjusted, F test, actual-vs-predicted plot)
- [x] Logistic regression (IRLS, odds ratios, LR test, McFadden/Tjur R², AUC, separation check, ROC plot)
- [x] Cross-checked vs statsmodels; 85 tests

## Phase 0.17: Export sizes (done 2026-11-06)
- [x] Journal export presets (single/1.5/double column, slide, square) and 150/300/600 DPI PNG

## Phase 0.18: PCA, TIFF, UI test (done 2026-11-06)
- [x] PCA (standardized or raw), eigenvalues, loadings, Kaiser rule, biplot and scree plot
- [x] TIFF export (LZW) and DPI metadata in PNG/TIFF (adds Pillow)
- [x] Automatic UI smoke test: every example renders without JS errors (skips without Playwright)
- [x] 89 tests

## Phase 0.19: Column statistics + axis/legend (done 2026-11-06)
- [x] "Describe each column": quartiles ((n+1)p), CV, geometric mean/SD factor, skewness, kurtosis,
      Shapiro-Wilk + D'Agostino-Pearson, one-sample t and Wilcoxon vs a hypothetical value
- [x] Format: Y tick interval, hide legend; 91 tests

## Phase 0.20: Two-way repeated measures (done 2026-11-06)
- [x] Mixed (split-plot) ANOVA: rows repeated on the same subjects, columns = groups; Geisser-Greenhouse;
      Type III for unequal groups; simple-effect comparisons per row; subject trajectories on the graph
- [x] Verified vs pingouin (balanced, interaction) and statsmodels Type III (unequal groups); 94 tests

## Phase 0.21: Figure layouts (done 2026-11-06)
- [x] "Figure layout" type: pick analyses, 1–3 columns, panel letters; each panel uses its own graph settings
- [x] Composite PNG/TIFF export at journal width and chosen DPI (canvas compositing in the browser)

## Phase 0.22: "Help me choose" guide (done 2026-11-06)
- [x] Plain-language question flow → recommended analysis with reason → creates it pre-configured
- [x] Browser test walks every branch (22+ recommendations) and runs each with example data; 95 tests

## Phase 0.23: Text for your paper (done 2026-11-06)
- [x] Methods + results sentences (APA-style statistics) for every analysis type, with Copy button
- [x] UI test checks every example produces text without undefined/NaN gaps

## Phase 0.24: Spreadsheet-style editing (done 2026-11-06)
- [x] Block selection (drag, Shift+click, Shift+arrows, row numbers), copy/cut as TSV, Delete clears, undoable
- [x] Right-click row number: insert row above/below, delete row(s); 96 tests

## Phase 0.25: Polish pack (done 2026-11-06)
- [x] Dark mode (saved in projects/.prefs.json via /api/prefs), duplicate analysis, drag-to-reorder sidebar

## Phase 0.26: Compare curves (done 2026-11-06)
- [x] XY "each Y column = its own curve": separate fits for every model (incl. linear, custom)
- [x] Compare a parameter (e.g. LogIC50, slope) or whole curves via shared-parameter global fit + extra-SS F test
- [x] Linear slope comparison verified = ANCOVA interaction (statsmodels); 100 tests

## Phase 0.27: Prism file import (done 2026-11-06)
- [x] Open .pzfx (Prism XML) files: column, XY (replicates / multiple data sets), grouped, survival,
      contingency, multiple-variable tables → matching analyses; excluded values dropped with a note;
      SD/SEM summary formats import the means with a note. Not yet verified on a real Prism file.

## Phase 0.28: Exclude values (done 2026-11-06)
- [x] Right-click a cell/block → Exclude/Include; blue italics; left out of analyses, graphs and layouts;
      stays aligned on row insert/delete and column removal; undoable

## Phase 0.29: Summary data (done 2026-11-06)
- [x] "Compare groups (mean, SD, n)": exact Welch/unpaired t, one-way/Welch ANOVA + Tukey/Games-Howell
      from summary statistics (SD or SEM input); bar/mean graph; verified vs scipy from_stats; 106 tests

## Phase 0.30: Full graph styling + editable SVG (done 2026-11-06)
- [x] Format panel in sections: text (font, sizes, color), colors, points (shape, size, opacity, outline),
      lines & error bars (thickness, cap width), bars (fill opacity, outline, hatch patterns), axes (thickness,
      tick direction/length, gridlines), background (white/transparent), legend position, export
- [x] One style pass (applyStyle/styledReact in app.js) applies these to every graph type
- [x] SVG export keeps text and shapes editable (Illustrator/Inkscape/PowerPoint); figure layouts export as one
      combined editable SVG with panel letters as text; 107 tests (tests/test_ui_style.py)

## Phase 0.31: Frequency distributions + Q-Q plots (done 2026-11-06)
- [x] Compare groups → "Distribution" mode: histogram on shared bins (automatic Freedman-Diaconis width rounded to
      1/2/2.5/5×10^k, or your own width and start), count / percent / fraction, cumulative; frequency polygon;
      normal curve overlay; overlapping / side-by-side / stacked columns
- [x] Normal Q-Q plot (R qqnorm plotting positions) + Shapiro-Wilk and D'Agostino per column; guide entry; 111 tests

## Phase 0.32: ROUT outliers (done 2026-11-06)
- [x] ROUT (Motulsky & Brown 2006): Lorentzian robust fit with RSDR scale, FDR outlier test (Q), refit without outliers
      (backend/app/outliers.py); FDR rule matches the dr4pl R implementation and Benjamini-Hochberg step-up
- [x] Compare groups: identify outliers with ROUT (default, finds several) or Grubbs; choose Q
- [x] XY fits (linear, all nonlinear models, custom equations): "Remove outliers before fitting"; red crosses on the
      graph, removed-points table, paper text; 118 tests
- [x] Violin plots (with inner box, mean line and points) for Compare groups

## Phase 0.33: Graph extras (done 2026-11-06)
- [x] Horizontal (sideways) graphs for Compare groups, summary data, grouped and contingency graphs (flipLayout in app.js)
- [x] Stacked bars (grouped means; contingency tables)
- [x] Edit on the graph: click titles, axis titles, legend entries to retype; drag legend; edits saved per graph
      (g.axisText, g.legendNames, g.legendXY) with "Reset graph edits"
- [x] Free text labels (g.notes, paper coordinates, draggable, size); 119 tests
- [x] Y axis break (breakYAxis: two stacked y axes, adjustable lower height), minor ticks, X label angle, X tick interval (XY)

## Phase 0.34: Cox regression (done 2026-11-06)
- [x] Multiple variables → Cox proportional hazards (Efron ties): hazard ratios + CIs, LR / Wald / score tests,
      Harrell's C, forest plot; matches lifelines (incl. tied times); guide branch; 122 tests

## Phase 0.35: Nested t test / nested ANOVA (done 2026-11-06)
- [x] New "Nested" type: one row per subject (group name + replicates); REML mixed model (random subject),
      Wald F with containment df, Tukey for 3+ groups, variance components + ICC, subjects-within-groups F test
- [x] Balanced data = ANOVA/t test on subject means (tested); unbalanced REML matches statsmodels MixedLM
- [x] Graph: replicates (small), subject means, group mean ± SD; guide entry; example; 125 tests

## Phase 0.36: Multiple comparison choices (done 2026-11-06)
- [x] One-way ANOVA (raw and summary data): compare every pair or each group vs control (first column);
      Tukey, Dunnett, Holm-Šídák, Šídák, Bonferroni, Fisher's LSD; Kruskal-Wallis: Dunn's all pairs or vs control
- [x] Dunnett = scipy.stats.dunnett (seeded integration); corrections match statsmodels multipletests; 132 tests

## Phase 0.37: Two-way ANOVA comparison choices (done 2026-11-06)
- [x] Compare columns within each row (default), rows within each column, column means or row means (main effects,
      unweighted marginal means); Šídák for 2 levels, Tukey for 3+; brackets for within-row/column families
- [x] 2-level main-effect comparison reproduces the Type III F test (balanced and unbalanced); 136 tests

## Phase 0.38: Survival extras (done 2026-11-06)
- [x] Gehan-Breslow-Wilcoxon test (matches lifelines weightings="wilcoxon"), log-rank test for trend (3+ groups),
      number-at-risk table under the Kaplan-Meier graph; 138 tests

## Phase 0.39: Contingency extras (done 2026-11-07)
- [x] Chi-square test for trend (Cochran-Armitage, k×2 ordered rows), McNemar's test (exact + corrected chi-square,
      matched odds ratio), chi-square goodness of fit (+ exact binomial for 2 categories), observed vs expected graph
- [x] Verified vs statsmodels/scipy; guide branch; 3 new examples; 141 tests

## Phase 0.40: Deming regression (done 2026-11-07)
- [x] Method comparison: Deming regression with error SD ratio, jackknife SE/CI, tests of slope = 1 and intercept = 0,
      identity line on graph; equals orthogonal regression (ratio 1) and scipy.odr (other ratios); 144 tests

## Phase 0.41: Three-way ANOVA (done 2026-11-07)
- [x] New "Three factors" type (long format: 3 label columns + value; grid supports several text columns via
      isTextCol); Type III SS matching statsmodels (balanced and unbalanced); grouped bar graph; 147 tests

## Phase 0.42: More normality and two-group tests (done 2026-11-07)
- [x] Column statistics: Anderson-Darling (D'Agostino-Stephens P) and Kolmogorov-Smirnov/Lilliefors (Dallal-Wilkinson P),
      both matching statsmodels; Kolmogorov-Smirnov two-sample test; ratio paired t test (geometric mean ratio + CI); 150 tests

## Phase 0.43: Residuals + runs test (done 2026-11-07)
- [x] Linear and nonlinear fits return residuals; exact runs test (one-tailed, replicates averaged per X);
      "Residual plot" option in Format; 154 tests

## Phase 0.44: Fit weighting (done 2026-11-07)
- [x] Nonlinear fits: weight by 1/Y, 1/Y² (Y of the fitted curve, iteratively reweighted), 1/X, 1/X²; weighted
      SS/R²/Sy.x; model comparison uses the same weights; 156 tests

## Phase 0.45: Dunnett's T3 (done 2026-11-07)
- [x] Welch's ANOVA: Games-Howell or Dunnett's T3 (studentized maximum modulus by numerical integration; checked
      against the Šídák limit and simulation), all pairs or vs control; 159 tests

## Phase 0.46: More transforms (done 2026-11-07)
- [x] Subtract first row (baseline), subtract first data column, percent of column total, Z scores, transpose
      (column / multiple-variable tables); 160 tests

## Phase 0.47: More Prism import (done 2026-11-07)
- [x] .pzfx nested tables → Nested analysis (subcolumn = subject); column tables entered as mean/SD/N or mean/SEM/N →
      summary-data analysis (exact tests). Synthetic-file tests only; 161 tests

## Phase 0.48: Three-way comparisons (done 2026-11-07)
- [x] Compare one factor's levels within each combination of the other two (Šídák for 2 levels, Tukey for 3+),
      pooled error; table and paper text; 162 tests

## Phase 0.49: PDF export (done 2026-11-07)
- [x] PDF button: graph or figure layout as a PDF page at the chosen print size and DPI (Pillow, high-resolution
      image; SVG remains the vector/editable option); 163 tests

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
