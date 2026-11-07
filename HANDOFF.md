# HANDOFF — read this first in every new session

This file is the single source of truth for project progress.
Every session starts by reading it and ends by updating it (then committing).

## Project
**Erwin's Hypothesis**: a local, desktop statistics & scientific graphing app
(functional alternative to GraphPad Prism, with a cleaner modern interface).

- Owner: kartiknimkar
- Repo: https://github.com/kartiknimkar/ErwinsHypothesis
- Target platform: macOS (Apple Silicon and Intel)

## Session protocol
1. Read `HANDOFF.md`, then `ROADMAP.md`.
2. Work in small chunks. After each chunk: run the tests, commit, update this file, push.
3. If the user says **"stop now"**: finish the current file, commit, update
   "Current state" and "Next step" below, push.
4. Never leave uncommitted work at the end of a turn.
5. Keep everything user-friendly: plain-language explanations, sensible defaults,
   helpful empty/error states (user's explicit request).

## Hard rule: everything stays inside the app folder (user requirement)
- `projects/` (project files + `.state.json`), `exports/` (graphs), `runtime/` (venv,
  optional private Python via uv, caches). All are git-ignored.
- No localStorage, no browser downloads. All saving goes through `backend/app/storage.py`.
- Launchers set PIP_CACHE_DIR / UV_CACHE_DIR / UV_PYTHON_INSTALL_DIR inside `runtime/`.
- Tested: launcher with a fresh HOME wrote nothing to HOME (system-Python and private-Python routes).

## User's setup & lessons learned (keep in mind!)
- User is on **Windows** for now (Mac later). Works at OSU Wexner (Cocucci Lab).
- First try ran from a **network drive** (`T:` = `\\cccdfs.osumc.edu\shared\...`): library install
  took very long (thousands of small files over SMB + antivirus). Advice: keep the app folder on the
  local disk. `run.bat` now detects network drives and warns (continue/quit).
- User's Windows Python 3.13 got NO ready-made wheels from pip (tried to compile SciPy → needs Fortran → failed).
  Fix: installs use `--only-binary :all:`; if that fails with system Python, launcher falls back to
  private uv Python 3.12. TEMP/TMP (TMPDIR on Mac) point to `runtime/tmp` (pip used AppData\Temp before).
- Commit only after checking the pytest summary line says no 'failed' (a piped `| tail` hides the exit code).
- Never use `--quiet` for installs: user thought it was frozen. Always show progress.
- `run.bat` must keep CRLF line endings (`.gitattributes`: `*.bat -text`, file committed as CRLF).
  After editing it on Linux, convert: `sed -i 's/\r$//; s/$/\r/' run.bat`.
- `run.bat` re-runs itself from `runtime\launcher.bat` so `git pull` can safely replace it;
  `run.sh` is wrapped in `main()` for the same reason.
- Launchers auto-update with `git pull --ff-only` at start when the folder is a git clone
  (skip with `EH_NO_UPDATE=1`). User was told to switch from the ZIP download to a clone.
- Explain things in plain, non-technical language; user prefers simple step-by-step instructions.

## How the code is laid out
- `backend/app/stats.py`: t tests, ANOVA family, normality, correlation, linear regression
- `backend/app/curvefit.py`: nonlinear models (MODELS dict, NESTED pairs) + fit() + compare()
- `backend/app/survival.py`, `backend/app/contingency.py`, `backend/app/anova2.py` (two-way, RM)
- Endpoints: /api/compare (kinds incl. rm, friedman, wilcoxon), /api/twoway, /api/fit, /api/models, /api/survival, /api/contingency (+ old /api/ttest, /api/regression)
- `backend/app/storage.py`: projects/exports, filename sanitizing, reveal folder
- `backend/app/main.py`: FastAPI server + `main()` (opens browser when ready, detects already-running)
- `backend/app/static/`: interface (vanilla JS, no build step): `index.html`, `style.css`, `app.js`
- `backend/tests/`: pytest (35 tests; dev cross-check packages in requirements-dev.txt); run with `cd backend && python -m pytest -q`
- `run.bat` (Windows), `run.sh` (Mac/Linux): use system Python ≥3.10 if present, else uv-managed
  Python 3.12 in `runtime/python`; reinstall libs when `requirements.txt` changes.
- Sizes measured: ~266 MB (system Python), ~410 MB (private Python).

## Current state
- [x] Preview app with 5 analysis types + Excel/CSV import + 11 curve models with model comparison + fit constraints + custom equations + interpolation + Excel export + series colors + outliers + AUC + correlation matrix + ROC + Bland-Altman (ROADMAP 0.6-0.14; transform dialog is frontend-only, applyTransform in app.js); 172 tests pass (incl. tests/test_ui_smoke.py: Playwright opens all 28 examples and walks every branch of the 'Help me choose' guide (GUIDE tree in app.js) and checks 'Text for your paper' (reportText in app.js); run it after UI changes). Multiple variables type also does multiple linear + logistic regression (multivar.py). 8 analysis types (+ nested): ttest, twoway, regression, survival, contingency, multivar, diagnostic (multivar.py)
- [x] User confirmed the app runs on their Windows PC (C: drive, private Python fallback)
- [x] Interface rewritten around a TYPES registry in `static/app.js` (each type: data layout,
      options, request, results renderer, graph drawer, format controls). Add new modules there.

- [x] Graph styling: every graph goes through `styledReact()` (never call Plotly.react directly in a drawer);
      `styleCtx` = the sheet's graph settings (set in drawPlot / per panel in drawLayout). New style keys live in
      COMMON_GRAPH. Layout SVG export: exportLayoutSVG (nested <svg> per panel). Test: tests/test_ui_style.py.

## AUTO-WORK MODE (user, 2026-11-07): keep going chunk by chunk without asking, until the session runs out.
Each turn: schedule the next auto-continue with send_later (1 min), do one chunk, test, commit, push, tell user in one line.
Chunk list (mark [x] when done; when all done, pick new chunks from the ideas below and add them here):
- [x] (a) normality: Anderson-Darling + KS (Lilliefors) in column stats; KS two-sample test; ratio paired t test
- [x] (b) XY fits: residual plot option + runs test
- [x] (c) nonlinear fit weighting (1/Y, 1/Y²)
- [x] (d) Dunnett T3 option for Welch's ANOVA
- [x] (e) transforms: transpose, remove baseline (subtract first row/column), fraction of total
- [x] (f) .pzfx nested table import
- [x] (g) three-way ANOVA multiple comparisons
- [x] (h) raster PDF export (Pillow)
- [x] (i) effect sizes: Cohen's d / Hedges' g (t tests), eta² / omega² (ANOVA)
- [x] (j) survival: pairwise log-rank comparisons for 3+ groups (Bonferroni/Holm-Šídák)
- [x] (k) row statistics (mean/SD/n across columns for each row) as a Compare-groups mode or transform
- [x] (l) grid conveniences: sort rows by a column, fill series (1, 2, 3… / dilution series)
- [x] (m) linear regression: force through origin, prediction bands
- [x] (n) power / sample size calculator (t test, ANOVA, proportions)
- [ ] (o) two-way ANOVA with both factors repeated

## Next step (suggested order; confirm with user)
0. Agreed order with user: (done) .pzfx import, exclude values, mean/SD/n entry, styling+editable SVG →
   (done) histograms + Q-Q plots (stats.frequency_distribution, /api/freq, ttest mode 'freq', drawFreq/renderFreq) →
   (done) ROUT (outliers.py; curvefit.rout_mask; /api/fit rout_q; /api/compare outlier_method) →
   (done) violin, stacked/horizontal bars, on-graph text editing, text labels → (done) axis breaks, X ticks → (done) Cox regression (multivar.cox) → (done) nested t test/ANOVA (nested.py, /api/nested, TYPES.nested) → (done) survival extras (Gehan-Wilcoxon, trend, risk table) → NEXT: ask user; ideas: PDF export (needs a vector library or browser print), (done: three-way ANOVA anova2.three_way, TYPES.threeway; no multiple comparisons yet), (done: Deming → multivar.deming), (done: McNemar, goodness of fit, trend → contingency.py), (done: post hoc choices, stats.one_way_anova posthoc/compare_to; two-way comparison families anova2._two_way_comparisons) Prism .pzfx nested tables import, PDF export, column/grouped data from .pzfx with SD formats.
1. (done) Two-way ANOVA + RM one-way / Friedman / Wilcoxon (`backend/app/anova2.py`, no new dependencies)
   Two-way RM (mixed) done: anova2.two_way_rm, /api/twoway rm=true. Note: within effects use Type III (SPSS-style);
   pingouin weights unequal groups differently for the row main effect (documented in tests).
   Possible follow-ups: RM on both factors, comparisons across rows / main-effect comparisons
2. Curve comparison done (curvefit.fit_multi/_global_fit, /api/fitmulti, XY yMode='datasets').
   (done) More curve models + model comparison. Constraints done (fit(fixed=...)); user-defined equations done (equation.py, model "custom"). Follow-ups: global fits sharing parameters across datasets
3. Figure layouts done (TYPES.layout: runCustom + drawLayout + exportLayout; noData hides the grid).
   Graph polish: per-group colors done (graph.colors by series name). Export size/DPI done (EXPORT_SIZES in app.js). TIFF done (Pillow); Y tick interval + hide legend done. Still: legend text editing, X tick control
   Other Prism features worth adding: ROUT outliers, (multiple t tests done: anova2.multiple_t, /api/multit),
   (column statistics done: Compare groups mode 'describe', /api/colstats)
4. Summary data done (TYPES.summary, stats.compare_summary uses exact synthetic data). Exclusions done (sheet.excluded = ['r:c'], masked(s) used for requests/draws).
   Prism .pzfx import done (importer.read_pzfx; tested only on synthetic files built to Prism's XML layout,
   ask the user to try a real file). (done) Excel/CSV import (`backend/app/importer.py`, /api/import). Excel export done (storage.save_results_xlsx, /api/exports/xlsx)
5. (done, needs first CI run) Packaged desktop app: `backend/app/desktop.py` (pywebview window,
   browser fallback), `packaging/ErwinsHypothesis.spec` (PyInstaller onedir, ~200 MB),
   `.github/workflows/build.yml` (Windows + Mac Apple Silicon zips; release on `v*` tag).
   No code signing (user's choice). Frozen app saves projects/exports/logs next to the exe
   (Mac: next to the .app, or ~/Documents/Erwins Hypothesis if translocated). Tested on Linux build.
   plotly.js is now vendored in static/vendor; plotly Python package no longer required.
6. Move UI to React only if app.js gets unwieldy (it's ~800 lines now, still fine)

## Decisions log
| Date | Decision | Why |
|---|---|---|
| 2026-11-06 | Python backend (FastAPI + SciPy/statsmodels/lmfit) | Well-tested statistical libraries; correctness matters most |
| 2026-11-06 | React + TypeScript + Vite frontend (planned) | Modern, polished UI |
| 2026-11-06 | Package as a Mac desktop app later (Tauri or Electron) | Runs fully locally, no browser tab needed |
| 2026-11-06 | Own name and design, no Prism branding or file-format copying | Reimplement functionality only |
| 2026-11-06 | Every statistical method validated against reference values in tests | Results must match established software |
| 2026-11-06 | Phase 0.5 preview UI in plain JS, no Node needed | User wanted to see a working version quickly; only Python required to run |
| 2026-11-06 | Difference reported as B − A (second group minus first) | Matches common convention of "treated minus control" |
