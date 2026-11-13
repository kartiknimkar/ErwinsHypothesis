# Erwin's Hypothesis

A local statistics and scientific graphing application: data tables,
statistical analyses, curve fitting and publication-quality graphs, with a
clean, modern interface. Everything runs on your own computer.

**Status:** preview (not yet checked against Prism on real lab data). Available today:

**Analyses**
- **Compare groups:** unpaired / Welch / paired / ratio paired t tests, Mann-Whitney and Wilcoxon (with Hodges-Lehmann
  estimates), Kolmogorov-Smirnov; one-way ANOVA with Tukey, Dunnett (vs control), Holm-Šídák, Šídák, Bonferroni or
  Fisher's LSD, test for linear trend; Welch's ANOVA with Games-Howell or Dunnett's T3; Kruskal-Wallis + Dunn's;
  repeated-measures ANOVA (Geisser-Greenhouse), Friedman; effect sizes (Cohen's d, Hedges' g, η², ω²)
- **Describe and check data:** column statistics, one-sample tests, normality (Shapiro-Wilk, D'Agostino, Anderson-Darling,
  Kolmogorov-Smirnov), frequency distributions and Q-Q plots, ROUT and Grubbs outliers
- **Summary data:** compare groups from mean, SD (or SEM) and n
- **Two and three factors:** two-way ANOVA (ordinary, repeated on one or both factors) with comparisons within rows,
  within columns, main effects or every cell; three-way ANOVA with simple-effect comparisons; multiple t tests with
  FDR (Benjamini-Hochberg or two-stage BKY), Holm-Šídák or Bonferroni, volcano plot
- **Nested data:** nested t test / nested one-way ANOVA (mixed-effects model) for replicates within subjects
- **XY:** linear regression (also through the origin, prediction bands), 11 curve models + your own equations,
  constraints, weighting (1/Y, 1/Y², 1/X, 1/X²), model comparison (F test / AICc), compare curves (shared-parameter
  global fits), standard curves (X from Y and Y from X), runs test, residual plots, ROUT outlier removal, area under curve
- **Survival:** Kaplan-Meier, log-rank, Gehan-Breslow-Wilcoxon, trend test, pairwise comparisons, hazard ratio,
  number-at-risk table; Cox proportional hazards regression with forest plot
- **Counts:** Fisher's exact, chi-square, chi-square for trend, McNemar (paired), goodness of fit, odds ratio, relative risk
- **Multiple variables:** correlation matrix, multiple linear regression (VIF, standardized β), logistic regression
  (odds ratios, ROC, Hosmer-Lemeshow, classification table), PCA
- **Method comparison & diagnostics:** ROC curves, Bland-Altman (difference, % difference, ratio), Deming regression
- **Planning:** power and sample size (t tests, ANOVA, proportions)

**Graphs**
- Dots, bars, box and violin plots, horizontal or stacked bars, broken Y axes, significance brackets, error bars
  (both ways or above only), survival curves (survival or death), histograms, Q-Q, forest, volcano and more
- Full styling: fonts, sizes, colors, point shape/opacity/outline, line and error-bar thickness, bar opacity and hatch
  patterns, axes, ticks, gridlines, legend position, transparent background; edit titles and legend text right on the graph
- Click any data point or legend entry to change just that series (color, symbol, size, line style, thickness, bar
  pattern, hide); Prism-style offset axes or a box; bold/italic titles; μ α Δ ± ° buttons; `cm^{2}` and `CO_{2}` for
  superscripts and subscripts in any label
- **Draw on the graph:** text, arrows, lines, boxes, circles and labelled significance brackets; drag, resize, recolor,
  nudge with the arrow keys, duplicate (Ctrl+D), delete, undo
- The graph on screen is drawn at its export size, so the file looks exactly like what you see; built-in and your own
  saved looks ("Save look as…") apply to any graph
- Export PNG, TIFF, PDF or **fully editable SVG** at journal sizes and 150–600 DPI: no clipping masks, every point, bar,
  error bar, line and label is its own object in named groups ("Control – points", "Y axis…", "Legend: …"), ready for
  Illustrator, Inkscape, Affinity or PowerPoint (Convert to Shape); multi-panel figure layouts (A, B, C…)

**Working with data and results**
- Type or paste from Excel; import .xlsx / .csv or GraphPad Prism projects (.pzfx); sort rows, fill series, exclude values,
  transforms (normalize, log, baseline, percent of total, Z scores, transpose, row statistics); large tables stay fast
- **Help me choose** recommends and sets up the right analysis; **Text for your paper** writes methods and results sentences
- Undo/redo for data, options and formatting; automatic saving and backups (restore earlier versions)
- **Report** (one HTML file with every analysis) and **All to Excel** (one workbook); press **?** for quick help

Data can be typed, pasted from Excel, or imported from .xlsx / .csv files, or from GraphPad Prism
projects (.pzfx). Not sure which test to use?
Click **Help me choose**: a few plain-language questions recommend and set up the right analysis.
Every result also has **Text for your paper**: a methods sentence and a results sentence in standard reporting style.

See `ROADMAP.md` for what's coming.

## Everything stays in one folder

```
ErwinsHypothesis\
  run.bat / run.sh   start the app
  projects\          your projects (saved automatically)
  exports\           graphs you export (PNG / SVG)
  runtime\           Python + libraries, created on first run
  backend\           the app itself
```

Nothing is installed elsewhere on your computer. If you already have
Python 3.10 or newer, the app uses it (about 270 MB in total). Otherwise it
downloads a private copy of Python into `runtime\` (about 410 MB). To remove
the app completely, delete the folder.

## Easiest: download the ready-made app (nothing to install)

On the GitHub page, open **Releases** (right-hand side) and download:
- **ErwinsHypothesis-Windows.zip** for Windows, or
- **ErwinsHypothesis-Mac-AppleSilicon.zip** for Macs with M1/M2/M3/M4 chips.

Unzip it on your own disk (e.g. Documents) and double-click **ErwinsHypothesis**. Python and
all libraries are built in, and it works offline. The app isn't code-signed, so the first time
Windows says "Windows protected your PC": click **More info → Run anyway** (on Mac: System
Settings → Privacy & Security → **Open Anyway**). Projects and exports are saved in folders
next to the app.

## Run it from source on Windows

Put the app on your computer's own disk (e.g. `Documents`), **not a network
drive**: on a network drive setup takes much longer and the app starts slowly.

1. Install Git from https://git-scm.com (default options), then in Command Prompt:
   ```
   cd %USERPROFILE%\Documents
   git clone https://github.com/kartiknimkar/ErwinsHypothesis.git
   ```
   (Or click **Code → Download ZIP** on GitHub and unzip it, but then you won't
   get automatic updates.)
2. Double-click **`run.bat`** in the new folder. If Windows shows "Windows protected your PC",
   click **More info → Run anyway** (this happens for any script downloaded
   from the internet).
3. The first run needs internet and takes a minute or two. Your browser then
   opens the app. Keep the black window open while you work; close it to quit.

## Run it from source on a Mac

```bash
git clone https://github.com/kartiknimkar/ErwinsHypothesis.git
cd ErwinsHypothesis
./run.sh
```

## Updating

If you installed with `git clone`, the app updates itself every time you start
it (when online). Your `projects`, `exports` and `runtime` folders are never
touched by updates. With a ZIP download, download the new ZIP and copy your
`projects` folder across.

## Options

- Always use a private Python copy: run `set EH_PRIVATE_PYTHON=1` (Windows) or
  `export EH_PRIVATE_PYTHON=1` (Mac) before the launcher.
- Different port: `EH_PORT=9000`.

## Making a new release (for maintainers)

Downloads are built automatically by GitHub Actions (`.github/workflows/build.yml`):
on GitHub, go to **Releases → Draft a new release**, choose a new tag such as `v0.2.0`,
and click **Publish release**. The Windows and Mac zips are attached to the release
about 15 minutes later. To build without a
release, use **Actions → Build app → Run workflow**. Local build:
`pip install -r packaging/requirements-build.txt && pyinstaller packaging/ErwinsHypothesis.spec --noconfirm`.

## For developers
```
backend/app/stats.py     Statistics engine
backend/app/storage.py   Saving (always inside the app folder)
backend/app/main.py      Local server
backend/app/static/      User interface
backend/tests/           Tests: cd backend && python -m pytest -q
```
