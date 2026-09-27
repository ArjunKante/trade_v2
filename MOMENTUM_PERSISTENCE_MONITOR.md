# Momentum Persistence Monitor -- descriptive only

Implements Hypothesis A-descriptive from `NEW_RESEARCH_DIRECTION.md`.
Code: `src/monitor/persistence.py` (statistic + regime rule),
`src/monitor/web.py` (web-app payload), `scripts/run_momentum_persistence_
monitor.py` (CLI, appends one log row per run),
`scripts/run_momentum_persistence_regime_count.py` (the original
diagnostic, refactored to import from `src/monitor/persistence.py` rather
than duplicate it).

## What this is and is not

It measures whether `momentum_12_1` has recently been ranking stocks in
the same order their subsequent returns turned out. **It does not
predict returns, does not change any position, does not emit a
buy/sell/reduce signal, and makes no claim that a regime will persist.**
Nothing here is wired into `src/reports/fundamental_screener.py`'s
filtering or ranking, and nothing here should ever be used to select or
tune a strategy. This is the SAME statement in the module docstring, the
log header, and the web UI's non-dismissible note -- reproduced here as
the fourth place, per instruction, so it cannot drift.

## The statistic (verbatim -- do not redefine elsewhere)

Per signal date: the cross-sectional Spearman rank correlation between
`momentum_12_1` (12-month trailing return, skip most recent month) and
the SAME date's forward 63-trading-day return, on the same universe, both
gap-guarded (`STALE_GAP_DAYS`, `factors.momentum`/`factors.target`'s own
lineage-jump-guard convention). Dates with fewer than
`MIN_CROSS_SECTION_N` (20) names in the merged cross-section are dropped.

**Known discrepancy, now resolved**: the original instruction to reuse
the regime-count script's definition exactly, AND apply same-ISIN
exclusions, was self-contradictory -- that script did not originally
apply them. Fixed by adding the exclusion in one place
(`monitor.persistence.same_isin_jump_excluded_entities`), used
identically by the regime-count script, the CLI monitor, and the web
payload. Rerun after the fix: still exactly 3 regimes -- the count below
is unchanged. **Grep-for-siblings**: 7 other scripts in this project
compute cross-sectional persistence/IC without this exclusion (BUGS.md
Bug #11's update, 2026-09-27, names them) -- all predate Bug #11 and feed
already-published results, not retroactively recomputed here.

## The lag

A persistence value for signal date D requires returns through D+63
trading days (`factors.target.compute_forward_return`'s own `eval_date`
column -- a real calendar date, never a fixed offset, since the horizon
is trading days). The most recent measurable value is therefore always
roughly a quarter behind the latest available price date, by
construction. Every display shows both the signal date and the
measured-through date; the current-state readout states the lag in a
plain sentence.

## Point-in-time invariant

`compute_daily_persistence(panel, jump_dates, as_of=...)` filters every
row on its own `eval_date <= as_of` BEFORE aggregating -- no persistence
value for a given `as_of` ever uses a return realized after it. Tested
directly: `tests/test_monitor_persistence.py`.

## Regime label

Mechanical rule, fixed before any regime count was ever run: a regime is
a maximal contiguous run of calendar years whose annual-mean persistence
correlation shares the same sign. On trade-new's own pre-holdout history
this reproduces exactly 3 regimes -- **2017-2019 (+), 2020 (-), 2021-2024
(+)** -- asserted directly by
`tests/test_monitor_persistence.py::test_reproduces_the_three_published_
pre_holdout_regimes`.

The CURRENT rolling reading (trailing 12 non-overlapping 63-day periods,
~3 years; SE from those 12 period-level points, never from overlapping
daily values) is labeled `positive` / `negative` / **`indistinguishable
from zero`** whenever its 95% interval spans zero -- the third label is
not a hedge, it is what is shown exactly as often as the data says so.

## Firewalls checked before this was built

**Study 3 (`trade-info`)**: does not apply. This module reads trade-new's
own `data/warehouse.duckdb` exclusively and never opens
`trade-info/data/nsepit.duckdb`, where Study 3's fresh window actually
lives -- structurally inapplicable. Checked anyway, in case that ever
changes: `trade-info/FRESH_DATA_CONTRACT.md` Section D restricts its
firewall to "a model or strategy evaluated for a pass/fail verdict";
Section C explicitly names "regime-indicator audits" as the category
distinguished FROM evidence of a tradeable edge -- exactly what this
module is.

**trade-new's own holdout -- RETIRED, not merely "not charged."** Getting
a "measured through" date near the true latest price requires
`data_layer.entity_panel.read_full_entity_panel_authorized(con,
authorize_holdout=True)`, the same bypass used a third time by this
module. The original reasoning here (by analogy to `trade-info`'s own
contract, a descriptive statistic doesn't charge a study-cap slot) is
**superseded**: `FINDINGS.md` Section 7 now records the historical
holdout (`SEALED_HOLDOUT_START` onward) as **RETIRED**. A one-time read
might not spend a sealed window, but this monitor reads it on every run,
permanently -- a window continuously displayed is not sealed in any
meaningful sense, and it had already been read twice by actual strategies
(Study 1, swing V1) before this monitor existed. There is no slot left
to charge or not charge. `data/holdout_access_log.txt` still logs every
read, but as an audit trail only -- not a record of a resource being
preserved. All future validation for anything in this repository is
forward-only, from 2026-09-27.

## Usage

```
python scripts/run_momentum_persistence_regime_count.py   # pre-holdout only, no authorization, unchanged since last run
python scripts/run_momentum_persistence_monitor.py         # live reading, appends one row to monitor_logs/momentum_persistence_log.csv
python scripts/serve_screener.py                           # screener web app, now with a "Momentum Persistence Monitor" tab
```

`monitor_logs/momentum_persistence_log.csv` is append-only, one row per
CLI run, committed with the code (deliberately not under `data/`, which
is gitignored).
