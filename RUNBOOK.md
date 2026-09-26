# Runbook

Operational how-to for running this project's tools. Not a replacement for
`README.md` (project state/results) or `OPERATIONS.md` (engineering-practice
lessons) -- this file only answers "what do I type to make X run."

## Fundamental screener web app

Local, single-user, read-only browser UI over the fundamental screener's
current output (all top-decile names, PASS and FAIL alike, with full
per-company fundamentals). No auth, no deployment target -- it only ever
listens on `127.0.0.1` and is meant to be opened in a browser on the same
machine.

**Prerequisite:** a populated `data/warehouse.duckdb`. `data/` is
git-ignored (see `.gitignore`), so a fresh clone does not have one --
build it first per `FUNDAMENTALS.md` (Phases A-E) and `README.md`'s
`scripts/phase1_demo_load.py` / backfill scripts. The web app itself does
not build or backfill anything; it only reads.

Once the warehouse exists:
```
pip install -r requirements.txt
python scripts/serve_screener.py
```
This opens the warehouse read-only, builds an in-memory cache once at
startup -- the momentum universe, every top-decile company's screener
verdict, and its full `fundamental_snapshot.py` report -- then prints a
URL (`http://127.0.0.1:8765`). Open that URL in a browser. Every page
request after startup is served from the cache; there is no per-request
database query and no export/copy of the warehouse.

Startup takes roughly 1-2 minutes (the momentum universe computation is
the slow step, then one fundamentals report per top-decile company,
~147 companies as of the last run). Progress lines print to the terminal
as it goes.

**Data is a snapshot, not live.** The page shows a "generated at" timestamp
and the source screener log file in its header so you can tell how stale
it is. To pick up a new screener run: re-run
`python scripts/run_fundamental_screener.py` (or whatever repopulated the
warehouse), stop the server (Ctrl+C), and start it again -- there is no
auto-refresh, by design (see `src/reports/screener_web.py`'s module
docstring).
