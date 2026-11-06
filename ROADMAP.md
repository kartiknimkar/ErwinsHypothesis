# Roadmap

Each item is built, tested, committed, and checked off in `HANDOFF.md`.

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
