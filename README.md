# NSE Factor & Fundamentals System

See `LICENSE_ASSESSMENT.md` for the source-by-source licensing decision.
See `PREREGISTRATION.md` / `PREREGISTRATION_COMBINATION.md` for locked
study designs and decision rules.

## Final project state

| component | status |
|---|---|
| `momentum_12_1` | **Established.** Replicated in two differently-constructed Indian universes (microcap whole-market, large-cap top-200). Sealed holdout evaluated once and passed. |
| `earnings_yield` | **Suggestive, not established.** Independent of momentum (near-zero cross-sectional correlation), but fails multiple-comparisons correction on its own. |
| momentum + earnings_yield combination | **Untestable on this data, at any reachable horizon.** A power analysis (portfolio margin, then the more efficient paired rank-IC difference) found the measurement too noisy relative to any economically plausible effect size — not evidence the effect is absent, evidence it can't be distinguished from noise here. |
| sealed price holdout | **Spent** (one pre-registered study, passed). Cannot be re-read, re-run, or appealed. |
| final pre-registered study slot | **Held, unspent** — deliberately not spent on a test that couldn't have passed. |

Full detail, in reading order: `FINDINGS.md` (the momentum studies and the
combination power-analysis finding), `FUNDAMENTALS.md` (the fundamentals
data layer build, phase by phase, including the Integrated Filing
fetcher), `BUGS.md` (every bug found along the way, mechanism and fix),
`OPERATIONS.md` (logging/resume lessons from long-running extractions).

The most transferable result of this project is arguably not about either
factor: testing an incremental improvement over an already-working
strategy is usually limited by the *variance* of the difference between
the two, not by the size of the improvement — see `FINDINGS.md` Section 12
for the numbers (an 87-year requirement on the intuitive portfolio-margin
metric, 8-72 years even on the more efficient paired-IC metric, for
effect sizes a second factor could plausibly produce).

## Layout
```
config/config.yaml           source URLs, throttles, universe definition
src/data_layer/
  db.py                      DuckDB schema + as_of query guard (HoldoutViolationError)
  prices_nse.py              NSE bhavcopy (UDiFF) fetch + parse + load
  fundamentals_nse.py        NSE-hosted XBRL financial-results fetch + load
  xbrl_parser.py             long-format XBRL fact extraction
scripts/phase1_demo_load.py  one-off driver proving the pipeline against real data
tests/test_known_date_guard.py  unit tests for the known_date <= as_of invariant
data/warehouse.duckdb        the point-in-time warehouse (append-only)
data/raw/                    cached raw files (bhavcopy zips, XBRL XML)
```

## Running
```
pip install -r requirements.txt
python scripts/phase1_demo_load.py
python -m pytest tests/ -v
```
