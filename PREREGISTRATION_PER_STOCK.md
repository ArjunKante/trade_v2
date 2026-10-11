# Pre-registration: Per-Stock Weekly Rules Study

Frozen before this study's full-universe trial results were computed, per
this project's standing discipline (`PREREGISTRATION.md`,
`PREREGISTRATION_FIBO.md`, `PREREGISTRATION_SWING.md`). Nothing below
changes after this document is written except by an explicit, recorded
amendment. See `PER_STOCK.md` for the results this document governs.

**NEW, SEPARATE MODULE** (`src/per_stock/`): this study does not touch
Fibo (`src/fibo/`, `src/fibo_live/`), momentum (`src/factors/`), or any of
their results. It READS two existing, unmodified tools -- Fibo's
point-in-time turnover universe (`src/fibo/universe.py`) and the
fundamental screener (`src/reports/fundamental_screener.py`) -- the same
way those tools are already read elsewhere in this project, without
changing either.

## 0. The idea, and what judges it

Each stock may have its own weekly behaviour -- a tendency (or its
opposite) to mean-revert or continue after an unusually large weekly move,
specific to that stock, not shared market-wide. A rule found for one stock
is used ONLY for that stock, never transferred to another. A stock where
nothing is found is dropped, not forced into a strategy.

**ALL HISTORICAL DATA HAS ALREADY BEEN EXAMINED** in earlier projects
sharing this warehouse. The historical (FIT/CHECK) results in `PER_STOCK.md`
are **DEVELOPMENT EVIDENCE, not validation** -- they inform which
stock+rule pairs are worth forward-testing, nothing more. **Only forward
paper trading, logged before outcomes are known, validates anything here**,
exactly as this project's other live studies (Fibo) already treat their
own historical backtests.

## 1. Universe: top-50 by turnover, current point-in-time, screener-gated

`src/per_stock/universe.py::build_study_universe`:

- **Top 50 by turnover**: the LATEST calendar year's membership from
  `src/fibo/universe.py::reconstitute_annually(con, top_n=50)` -- the same
  point-in-time, annually-reconstituted (top 50 by median daily turnover
  over the PRIOR calendar year, held fixed all year) construction the
  Fibo study already uses. This is **current point-in-time membership**
  (this year's list), not a historically-reconstituted-per-year rolling
  universe -- the backtest below reads each selected stock's own FULL
  available history regardless of whether it would have been in a top-50
  list at some earlier date. This is a deliberate, stated choice: the
  screen selects WHICH 50 stocks are worth testing a per-stock rule on
  GOING FORWARD; it does not claim the universe itself is survivorship-
  bias-free across the backtest window.
- **AND currently passes the fundamental screener**
  (`src/reports/fundamental_screener.py::evaluate_company`, unmodified):
  verdict PASS or FINANCIALS-PARTIAL, the same definition `run_screener`'s
  own `survivors` uses.

**LOOKAHEAD CAVEAT, stated plainly**: the fundamental screener is
CURRENT-STATE ONLY (BUGS.md Bug #12 -- no point-in-time history). Gating
this study's universe by today's screener verdict is a MILD LOOKAHEAD: a
selected stock could have failed this same screen for most of its own
history and only cleared it recently, or the reverse, and this selection
has no way to know that. Accepted here because the screener is being used
to decide which 50 names deserve a per-stock rule tested on them GOING
FORWARD, not to certify every historical bar the backtest will read. Not
hidden, not corrected for -- stated.

**Report required**: how many of the top 50 pass the screener gate.

## 2. Rules: exactly two candidates per stock, fixed now, never tuned

For each stock, using ONLY that stock's own history (`src/per_stock/weekly.py`,
`src/per_stock/rules.py`):

- `sigma` = sample standard deviation (ddof=1) of that stock's own weekly
  returns over the trailing 52 weeks, INCLUDING the week being measured as
  the most recent of the 52 -- point-in-time, recomputed every week.
- **R_REVERSAL**: if the prior week's return < -1.0 x that week's own
  trailing sigma, buy next week's Monday open, sell that week's Friday
  close.
- **R_CONTINUATION**: if the prior week's return > +1.0 x that week's own
  trailing sigma, same entry/exit mechanics.
- **Stop**: exit if a day's CLOSE falls to or below entry x (1 - 1.0 x
  sigma), checked once per trading day within the entry week, first
  breach wins (same day). If never breached, exit at that week's own
  Friday close (or the week's last traded day, if Friday itself did not
  trade -- a holiday Monday/Friday is handled the same way on both ends).
- **Long only. One position per stock at a time** -- automatic by
  construction here: every trade both enters and fully resolves (stop or
  week close) inside the SAME calendar week, so no two trades for one
  stock can ever overlap.
- The **1.0 sigma multiples (entry threshold AND stop) are fixed and are
  not tuned** at any point in this study -- `SIGMA_MULTIPLE = 1.0` is a
  single named constant in `src/per_stock/rules.py`, read, never searched
  over.

**Costs -- DELIVERY** (positions held overnight, multiple days):
`src/swing/costs.py::round_trip_cost_rs(position_size_rs, "DELIVERY")`,
UNMODIFIED, read-only -- the same STT (0.1% both sides)/DP charge/
brokerage/GST/measured-spread model already documented there. **Position
size**: a fixed-risk convention (stop and entry are both well-defined
here), `FIXED_RISK_RS = Rs 2,000` per trade (`src/per_stock/costs.py`) --
a round, stated, NOT-tuned number, independent of (not matched to) Fibo's
own unrelated Rs 500 fixed-risk constant. The round-trip cost's midpoint
(of swing.costs' stated lo/hi spread+impact range) is subtracted from each
trade's raw return to get its net return; the range itself is carried into
the report as a stated sensitivity note, not collapsed silently.

## 3. Selection: specified now, before any result is seen

**FIT window**: 2016-10-01 to 2022-12-31.
**CHECK window**: 2023-01-01 to 2026-09-30.
(A trade belongs to whichever window its OWN entry week falls in.)

For each stock and each rule (50 x 2 = up to 100 trials, fewer if a stock
lacks enough history to produce a computable FIT statistic -- see
"trials actually run" below):

Keep a stock+rule ONLY if ALL of the following hold:
1. **FIT window**: mean net return per trade > 0 AND t >= 2.
2. **CHECK window**: mean net return per trade > 0.
3. **CHECK window**: at least 15 trades.
4. **Survives Bonferroni correction across ALL trials actually run** --
   "trials actually run" = every (stock, rule) pair with a computable FIT
   t-test (at least 2 FIT trades with nonzero variance; a trial that
   cannot even produce a FIT p-value does not count toward the
   denominator OR the numerator). The FIT two-sided p-value must be <=
   0.05 / (number of trials actually run).
5. **Beats its own random-entry null** (see below).

**If both rules qualify for the same stock, keep NEITHER** (conflicting
evidence about that stock's own weekly behaviour). **If neither qualifies,
drop the stock.**

**Random-entry null** (`src/per_stock/stats.py::random_entry_null`): for
every stock+rule, 1000 seeds, each drawing (without replacement) as many
RANDOM weeks from that stock's own CHECK-window entry-candidate pool as
the rule actually produced CHECK-window trades, applying the IDENTICAL
exit/stop mechanics (same stop distance convention, same cost model) to
each randomly-entered week. The rule's actual CHECK-window mean net return
is located as a percentile of this 1000-draw null distribution.
**"Beats random weeks" is fixed here, before any trial ran, at the actual
CHECK-window mean sitting at or above the 95th percentile of its own
null** (`NULL_BEAT_PERCENTILE = 95.0`) -- the user's instruction states the
null and the requirement qualitatively ("beat random weeks") without
naming an exact percentile; 95% is filled in here as the single number
needed to apply it, matching this study's other one-sided 95%-type
conventions, and is stated as a filled gap, not presented as if it had
been specified verbatim.

## 4. Report, before any forward logging

For all 50 x 2 trials, INCLUDING every rejected one: trades (FIT, CHECK),
mean net return (FIT, CHECK), t (FIT, CHECK), null percentile, and
pass/fail on each of the five conditions above, individually.

Then: how many survive and which; the expected number of survivors by
chance alone (reported two ways -- naive uncorrected alpha x n_trials, and
the Bonferroni-corrected expectation, which is pinned near alpha
regardless of n_trials, by construction); and for each survivor, the
number of forward trades needed to reach t >= 2 at its own CHECK-window
mean/std (`N = (2 x std / mean)^2`), converted to a time estimate at that
stock's own historical CHECK-window trading rate (trades per year).

## 5. Pre-committed reading of the headline result (recorded NOW)

- **Zero survivors** -> per-stock weekly patterns of this kind do not
  exist in this data at a detectable level, given this study's own
  thresholds. Record and stop.
- **Survivors roughly equal to the chance expectation** -> treat as luck.
  Record and stop.
- **Survivors clearly above chance** -> forward paper trade them.

**STOP after the report.** Forward logging (Section 6) starts only after
the user has seen the report and explicitly approves it -- never
automatically, regardless of which of the three readings above the result
lands on.

## 6. Forward logging (not built until approved)

Same pattern as Fibo live (`scripts/fibo_evening.py`/`fibo_morning.py`):
a Friday-evening job computes next week's entries per surviving stock,
emails them, appends to an append-only log of its own
(`data/per_stock/v1/events.jsonl`, planned -- not yet created), and
git-syncs it the same way `src/fibo_live/git_sync.py` does for Fibo's own
log (a separate call, a separate file, never touching Fibo's). Outcomes
are recorded at Friday close. No performance is shown before each
surviving stock has reached its own required forward trade count from
Section 4.
