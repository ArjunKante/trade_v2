# Box Theory intraday test: previous-session high/low reversal, data-only

**These rules are ONE mechanical interpretation of a discretionary idea
the user described in conversation ("buy at the previous low with
reversal candles, sell near the previous high"), reduced here to a fully
specified, backtestable rule set (`PREREGISTRATION_BOX.md`). A pass or
fail below tests THIS specific version only -- it says nothing about
whether the broader discretionary idea has edge under some other
mechanical reading of it.**

**All 2016-2026 data in this project's archives has already been read by
earlier projects (Fibo, momentum, swing, per_stock, options). The
hypothesis was not derived from this data, but there is no genuinely
untouched window left to test it on -- a DEV or TEST pass is development
evidence that justifies forward paper trading, never a claim of
validity.** See `PREREGISTRATION_BOX.md`'s opening section for the full
statement; it must travel with every result this study reports.

**Rules frozen in `PREREGISTRATION_BOX.md`.** This file is the
phase-by-phase process record for `src/box_theory/`; that document is the
frozen rule set, updated only by explicit, recorded amendment.

**Data-only, always**: this module never places, modifies, or cancels an
order. It reads `data/fibo_intraday.duckdb` (1-minute bars) and
`data/warehouse.duckdb` (daily bhavcopy, universe, holiday master, jump
guards) strictly READ-ONLY, and writes only to its own new paths
(`data/box_theory/...`).

**Separate from every other hypothesis in this repository** (Fibo,
momentum, swing, per_stock, options): its own code (`src/box_theory/`),
its own docs (this file + `PREREGISTRATION_BOX.md` + `BOX_FINDINGS.md`,
the experiments log, once results exist), its own sealed test-window
guard (`src/box_theory/test_seal.py`, independent of Fibo's and options'
own seals). No code in `src/fibo/`, `src/swing/`, `src/per_stock/`, or
`src/options_history/` has been or will be modified. Reused read-only,
imported never copied: `fibo.universe` (top-200, same point-in-time
annually-reconstituted method as Fibo's own sealed test), `fibo.
jump_guard`, `fibo.scale_probe`'s primitives, the frozen Section 8c
banded spread model combined with `swing.costs`'s INTRADAY formulas, and
the sealed-test-window guard PATTERN from `src/options_history/
test_seal.py` (a fresh instance, not a shared one).

## Module layout

- `src/box_theory/holiday.py` -- market-wide previous-NSE-trading-day
  stepper (`data_layer.nse_holidays`-backed), independent of `fibo.
  scale_probe.previous_trading_day`'s entity-specific notion (see its
  docstring for why the two must not be conflated).
- `src/box_theory/bars.py` -- 1-minute -> 5-minute candle aggregation, a
  plain-numpy bucket-and-reduce (not `groupby().agg()` -- see its
  docstring for the profiling finding that drove this).
- `src/box_theory/context.py` -- the shared per-(entity, day) eligibility
  pipeline (jump guard, ex-date, previous-session validity, scale
  resolution) both the real backtest and the SELECTION null draw from, so
  the two can never define "valid box-day" differently by accident.
- `src/box_theory/resolution.py` -- touch, FAST/SLOW confirmation, entry
  fill, room filter, the 3% stop, arming, the FAST/SLOW armed red-candle
  exit, and the 15:15 time exit. Two equivalent implementations: a
  DataFrame-based reference (`resolve_exit`, used by the real backtest and
  all hand-traceable unit tests) and an array-native fast path
  (`resolve_exit_arrays`, used only by the null simulations, which call
  it on the order of 10^7-10^8 times) -- cross-checked for identical
  output on every unit-test scenario and a broad real-data sample before
  use (`tests/test_box_theory_resolution.py`).
- `src/box_theory/costs.py` -- the frozen Section 8c banded spread
  (2.0/4.0/7.0 bps by rank band) combined with `swing.costs`'s INTRADAY
  statutory + Groww fixed-fee formulas.
- `src/box_theory/universe_data.py` -- batched (per-entity, not
  per-entity-day) data fetches, needed to make ~10^5-10^6 entity-day
  evaluations tractable without a DB round trip per day.
- `src/box_theory/backtest.py` -- orchestration: streams the window one
  entity-year at a time, runs both configs per eligible day, returns the
  trade list and skip-reason counts.
- `src/box_theory/inference.py` -- the day-clustered bootstrap (10,000
  resamples, 97.5% Bonferroni CI, MDE from variance only).
- `src/box_theory/nulls.py` -- TIMING, SELECTION, BASELINE null
  generators.
- `src/box_theory/test_seal.py` -- the sealed TEST-window guard.

## Status

**Step 1 complete**: `PREREGISTRATION_BOX.md` committed and pushed alone,
commit `dbc29ab21e0eb531b96c33946f82af3b28f4b787`, before any backtest
code existed.

**Step 2 in progress**: `src/box_theory/` built; 21 unit tests passing
(`tests/test_box_theory_resolution.py`, `tests/test_box_theory_
inference.py`), including a byte-for-byte cross-check of the fast null
path against the reference implementation on real archive data. A
significant performance pass was required and is recorded here rather
than glossed over: an initial implementation ran at ~19s per entity-year
and, independently, ~5ms per null draw -- at this study's real scale
(~200 entities x ~7 years for DEV alone; a null pool sized to the actual
touch-and-confirm trade count, which turned out to be far larger than a
Fibo-style confluence rule, since "touch yesterday's low" is a much
looser gate) that would have made DEV take over an hour and a single
null type take over a day. Profiling found the cost concentrated in
pandas/pyarrow overhead on this environment's build (`groupby().agg()`,
`.dt.time` extraction, repeated `.iloc[]` row access, object-dtype column
comparisons) rather than in the actual logic; replacing those call shapes
with plain-numpy equivalents (verified identical output throughout)
brought entity-year evaluation to ~2.9s and null draws to ~65-85
microseconds -- roughly a 6x and 70x improvement respectively, documented
in each affected module's own docstring at the point of change.

Hand-trace of 5 real trades (one stop, one armed exit, one 15:15 time
exit, one gap-down touch at the open, one skipped for no room) is next,
before any aggregate DEV number is computed, per `PREREGISTRATION_BOX.md`
Process Step 2.
