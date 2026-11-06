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
2. Work in small chunks. After each chunk: run the tests, commit, update this file.
3. If the user says **"stop now"**: finish the current file, commit, update
   "Current state" and "Next step" below, push.
4. Never leave uncommitted work at the end of a turn.

## Current state
- [x] Session 1: repo skeleton, roadmap, architecture decided
- [ ] GitHub access linked (pending at end of session 1)

## Next step
- Confirm the user's priority analyses (asked: dose-response/IC50, t-tests,
  ANOVA, survival, correlation?) and reorder Phase 2 of `ROADMAP.md`.
- Start Phase 1: data table model (backend) + data grid UI (frontend).

## Decisions log
| Date | Decision | Why |
|---|---|---|
| 2026-11-06 | Python backend (FastAPI + SciPy/statsmodels/lmfit) | Well-tested statistical libraries; correctness matters most |
| 2026-11-06 | React + TypeScript + Vite frontend | Modern, polished UI |
| 2026-11-06 | Package as a Mac desktop app later (Tauri or Electron) | Runs fully locally, no browser tab needed |
| 2026-11-06 | Own name and design, no Prism branding or file-format copying | Reimplement functionality only |
| 2026-11-06 | Every statistical method validated against reference values in tests | Results must match established software |
