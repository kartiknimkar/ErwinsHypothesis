# Erwin's Hypothesis

A local statistics and scientific graphing application: data tables,
statistical analyses, curve fitting and publication-quality graphs, with a
clean, modern interface. Everything runs on your own computer.

**Status:** early preview. Available today:

- **Compare groups:** t tests (unpaired, Welch, paired), Mann-Whitney, one-way ANOVA + Tukey,
  Welch's ANOVA + Games-Howell, Kruskal-Wallis + Dunn's, normality tests; for the same subjects
  measured repeatedly: paired t, Wilcoxon, repeated-measures ANOVA, Friedman
- **Grouped (two factors):** two-way ANOVA with multiple comparisons
- **XY:** linear regression & correlation; curve fitting: dose-response (IC50/EC50),
  standard-slope dose-response, Michaelis-Menten, exponential growth/decay (one & two phase),
  one-phase association, Gaussian, Boltzmann; compare two models (F test / AICc)
- **Survival:** Kaplan-Meier curves, log-rank test, hazard ratio, median survival
- **Contingency tables:** Fisher's exact, chi-square, odds ratio, relative risk

Data can be typed, pasted from Excel, or imported from .xlsx / .csv files.

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

## Run it on Windows

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

## Run it on a Mac

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

## For developers
```
backend/app/stats.py     Statistics engine
backend/app/storage.py   Saving (always inside the app folder)
backend/app/main.py      Local server
backend/app/static/      User interface
backend/tests/           Tests: cd backend && python -m pytest -q
```
