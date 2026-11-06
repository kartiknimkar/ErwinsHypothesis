# Erwin's Hypothesis

A local statistics and scientific graphing application: data tables,
statistical analyses, curve fitting and publication-quality graphs, with a
clean, modern interface. Everything runs on your own computer.

**Status:** early preview. Two-group comparisons (t tests, Mann-Whitney) and
linear regression work today. See `ROADMAP.md` for what's coming.

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

1. On the GitHub page, click **Code → Download ZIP**, then unzip it wherever
   you like (e.g. `Documents\ErwinsHypothesis`).
2. Double-click **`run.bat`**. If Windows shows "Windows protected your PC",
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

Download the new ZIP (or `git pull`) and copy your `projects` folder across.
If you use git, `projects`, `exports` and `runtime` are never touched by updates.

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
