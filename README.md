# Erwin's Hypothesis

A local statistics and scientific graphing application for macOS: data tables,
statistical analyses, curve fitting and publication-quality graphs, with a
clean, modern interface. Everything runs on your own computer.

**Status:** early preview. Two-group comparisons (t tests, Mann-Whitney) and
linear regression work today. See `ROADMAP.md` for what's coming.

## Run it on your Mac

You need Python 3 (check with `python3 --version` in Terminal; if it's missing,
install it from https://www.python.org/downloads/).

```bash
git clone https://github.com/kartiknimkar/ErwinsHypothesis.git
cd ErwinsHypothesis
./run.sh
```

The first run takes about a minute to set up. Your browser then opens the app.
To quit, close the Terminal window (or press Ctrl+C).

To update to the newest version later: `git pull`, then `./run.sh` again.

## Structure
```
backend/app/stats.py     Statistics engine
backend/app/main.py      Local server
backend/app/static/      User interface
backend/tests/           Correctness tests (cd backend && python -m pytest -q)
```
