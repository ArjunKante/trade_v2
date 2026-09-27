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

**Known discrepancy, not silently resolved**: this reuses
`scripts/run_momentum_persistence_regime_count.py`'s original definition
exactly, per explicit instruction. That script does not exclude the 78
same-ISIN-jump entities BUGS.md Bug #11 found, unlike every other
rigorous computation in this project (the swing decomposition, the swing
V1 checks, the swing V1 holdout read). Whether the 3-regime figure below
would change under that exclusion is open and not answered here.

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

**trade-new's own holdout**: the closer, more directly relevant question.
Getting a "measured through" date near the true latest price requires
`data_layer.entity_panel.read_full_entity_panel_authorized(con,
authorize_holdout=True)` -- a THIRD use of that bypass in this project
(`FINDINGS.md` Section 7: 2 of 3 slots already spent). Applying the same
principle `trade-info`'s own contract states explicitly (a descriptive,
non-pass/fail statistic is not "an evaluation"), this read is treated as
NOT charging the third slot -- **an inference by analogy, not a rule this
project has written down for itself**, flagged so it can be overridden.
Every such read is logged to `data/holdout_access_log.txt` with this
distinction stated, regardless of whether the reasoning is accepted.

## Usage

```
python scripts/run_momentum_persistence_regime_count.py   # pre-holdout only, no authorization, unchanged since last run
python scripts/run_momentum_persistence_monitor.py         # live reading, appends one row to monitor_logs/momentum_persistence_log.csv
python scripts/serve_screener.py                           # screener web app, now with a "Momentum Persistence Monitor" tab
```

`monitor_logs/momentum_persistence_log.csv` is append-only, one row per
CLI run, committed with the code (deliberately not under `data/`, which
is gitignored).
