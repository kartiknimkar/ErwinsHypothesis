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

## How the code is laid out
- `backend/app/stats.py`: all statistics (pure functions, lists in → dict out)
- `backend/app/storage.py`: projects/exports, filename sanitizing, reveal folder
- `backend/app/main.py`: FastAPI server + `main()` (opens browser when ready, detects already-running)
- `backend/app/static/`: interface (vanilla JS, no build step): `index.html`, `style.css`, `app.js`
- `backend/tests/`: pytest (17 tests); run with `cd backend && python -m pytest -q`
- `run.bat` (Windows), `run.sh` (Mac/Linux): use system Python ≥3.10 if present, else uv-managed
  Python 3.12 in `runtime/python`; reinstall libs when `requirements.txt` changes.
- Sizes measured: ~266 MB (system Python), ~410 MB (private Python).

## Current state
- [x] Session 1: repo skeleton, roadmap, architecture decided
- [x] GitHub access linked; pushing works
- [x] Phase 0.5 preview app built, tested, screenshots checked
- [x] Self-contained storage + Windows launcher (user is on Windows for now, Mac later)
- [ ] `run.bat` not yet tested on a real Windows machine (written carefully; Linux run.sh path tested)
- [ ] User to try it and give feedback

## Next step
- Get the user's feedback on the preview (look, wording, workflow).
- Confirm priority analyses (dose-response/IC50, ANOVA, survival, correlation?) and
  reorder Phase 2 of `ROADMAP.md`.
- Then decide: keep growing the vanilla-JS UI, or move the UI to React (Phase 0)
  before it gets large. Recommendation: move to React before Phase 1's richer data tables.

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
