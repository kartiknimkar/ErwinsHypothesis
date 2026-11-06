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
- Never use `--quiet` for installs: user thought it was frozen. Always show progress.
- `run.bat` must keep CRLF line endings (`.gitattributes`: `*.bat -text`, file committed as CRLF).
  After editing it on Linux, convert: `sed -i 's/\r$//; s/$/\r/' run.bat`.
- `run.bat` re-runs itself from `runtime\launcher.bat` so `git pull` can safely replace it;
  `run.sh` is wrapped in `main()` for the same reason.
- Launchers auto-update with `git pull --ff-only` at start when the folder is a git clone
  (skip with `EH_NO_UPDATE=1`). User was told to switch from the ZIP download to a clone.
- Explain things in plain, non-technical language; user prefers simple step-by-step instructions.

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
