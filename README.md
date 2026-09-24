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
src/reports/fundamental_snapshot.py  per-company fundamental snapshot (research tool, see below)
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

## Fundamental snapshot (research tool, not a study)

Reads growth/profitability/returns/balance-sheet/cash-flow/efficiency/
valuation/momentum-context for one company, or the current momentum top
decile in batch:
```
python scripts/run_fundamental_snapshot.py TCS
python scripts/run_fundamental_snapshot.py INE467B01029
python scripts/run_fundamental_snapshot.py --batch-top-decile
```
No composite score, no pre-registration, no study slot spent. Deliberately
reads current (not pre-holdout-truncated) price data and deliberately does
NOT read the SEBI Integrated Filing fundamentals source (unverified context
convention) — both explained in `src/reports/fundamental_snapshot.py`'s
module docstring, along with why quarterly/annual fundamentals in this
warehouse currently top out around late 2024 / FY2024 regardless of which
company you ask about.

## Fundamental screener (research tool, not a study)

**What this actually is, measured directly (not assumed): a cash-flow
quality screen with secondary checks attached, not a balanced multi-factor
filter.** On the 2026-09-23 run, the two CFO checks alone accounted for
48%/38% of all FAILs; debt/equity and the liquidity-tercile check each
fired once; the BE/BZ series check never fired. Read a PASS as "did not
fail hard on cash-flow quality primarily," not as "cleared nine
independent tests" — see `src/reports/fundamental_screener.py`'s module
docstring for the full correction (a description fix, not a threshold
change).

Filters the current momentum top decile down to a shortlist on fixed,
pre-stated P&L / balance-sheet / liquidity thresholds:
```
python scripts/run_fundamental_screener.py
```
**This filter is an untested modification to `momentum_12_1`** — the
holdout-passed result is on the unfiltered top decile (FINDINGS.md). Every
company gets a verdict (PASS / FAIL / INSUFFICIENT DATA / FINANCIALS-PARTIAL,
never silently dropped), FAILs show the specific metric and value, and
financials get the D/E and interest-coverage checks skipped (flagged, not
silently passed or failed) since those ratios don't mean the same thing for
banks/NBFCs. No composite score, no threshold tuning after seeing results.
Full per-company detail, including known_date/staleness and the FAILED
names with their reasons (for measuring the filter's cost later, with no
modelling), is logged to `data/screener_logs/` on every run — see
`src/reports/fundamental_screener.py`'s module docstring for the verdict
precedence rule and the accepted turnaround-story trade-off.
