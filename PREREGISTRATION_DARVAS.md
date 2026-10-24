# Pre-registration: Darvas Box theory, faithful version, daily data

Frozen before any box is detected, any trade is simulated, or any R value
exists, per this project's standing discipline (`PREREGISTRATION.md` and
family, including `PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md`/
`PREREGISTRATION_FVG.md`). Nothing below changes after this document is
committed except by an explicit, recorded amendment, made before the next
result that amendment could have been shaped by.

## Provenance -- stated plainly, as instructed

**This hypothesis's source is Nicolas Darvas's method as described in
"Darvas Box Trading" (Watkins, Pro Trader 2003), a book the user supplied.**
It is not from academic literature, not a replication of a peer-reviewed
factor, and not derived from any pattern this project has previously
backtested. **That book is promotional material for the author's own
stock-scanning software and contains no backtested evidence of its own**
-- it describes Darvas's method narratively, with no reported trade
statistics, win rate, or return series to check against. Everything below
is this project's own, fully mechanical reduction of that narrative
description, written down precisely enough to run exactly once without
ambiguity -- not a verified replication of a number that already exists
anywhere.

**This is a NEW family, trial count 1.** It is explicitly **NOT a
box-theory V3**. `PREREGISTRATION_BOX.md`/`PREREGISTRATION_BOX_V2.md`'s
own "box theory" studies tested a different strategy that shares only the
word "box" with this one: that family bought at the **previous session's
LOW**, intraday, on 5-minute candles, after mechanical reversal-candle
confirmation, selling back up near the previous session's high. This study
buys on a **BREAKOUT ABOVE a multi-week box TOP**, on **daily** bars, long
only, trailing a stop upward as new, higher boxes form. Opposite direction
(breakout-high vs. reversal-at-low), different timescale (weeks vs.
intraday), different construction (a multi-day consolidation range vs. a
single prior session's range) -- the earlier box studies' own trial count,
Bonferroni correction, and pass/fail status are untouched by this one, and
this study starts its own, independent trial counter at 1.

**All 2016-2026 data in this project's archives has already been read by
prior studies and the historical holdout is retired** (`FINDINGS.md`
Section 7, the same retirement `PREREGISTRATION_BOX.md`/`PREREGISTRATION_
FVG.md`/`PREREGISTRATION_IPO.md` already rely on). Consequently **a DEV
pass below is development evidence justifying forward paper trading,
never a validity claim** -- the same standing every other non-IPO study's
own DEV pass/fail carries here, not a stronger one. The DEV/TEST split
below (Section 7) is a forward-only discipline device, not a claim of
genuine-holdout cleanliness.

**A second, independent caveat, on top of the data-reuse one above: this
is ONE mechanical interpretation of a discretionary method.** The book
describes a trader's judgment calls -- which highs "feel" like a real
box top, how long to wait, when a trailing stop should move and by how
much -- in narrative terms, not as a fully specified algorithm. Every
judgment call below has been replaced with a fixed, mechanical rule (a
200-day lookback, a 3-day confirmation, a specific trailing-stop
threshold) so the test is reproducible. **A pass or fail below is a
statement about THIS VERSION ONLY** -- it does not confirm or refute
Darvas's broader discretionary method, which no mechanical document can
fully test, the same stance `PREREGISTRATION_BOX.md`'s own preamble
already takes toward its source idea.

## 0. Scope and reuse boundaries

**New, separate module: `src/darvas/`.** This study never modifies
`src/fibo/`, `src/box_theory/`, `src/fvg/`, `src/ipo_listing/`, `src/
per_stock/`, `src/swing/`, or `src/factors/`. It is data-only: reads
`data/warehouse.duckdb` read-only, writes only to its own new paths
(`data/darvas/...`). It never places, modifies, or cancels an order.

**Reused, read-only, unmodified** (imported, never copied or re-derived):

- `fibo.universe.reconstitute_annually(con, top_n=200)` / `effective_
  universe` / `restrict_to_universe` / `assert_universe_membership` --
  the identical point-in-time, annually-reconstituted, trailing-median-
  turnover construction `PREREGISTRATION_BOX.md` Section 2a already
  reuses with the same `top_n=200`, including the same 2016-stub-year
  fix (`effective_universe(universe, stub_year=2016)` copies 2017's
  membership onto 2016, since the warehouse has no 2015 data to rank
  2016 against).
- `fibo.daily_ohlc.build_daily_ohlc_panel` -- the existing entity-adjusted
  daily OHLC panel (open/high/low/close, one `adjustment_factors.factor`
  applied uniformly across all four so intra-day ranges are preserved),
  already built for Fibo's own daily-side rules and already documented
  as holdout-free (its own docstring: "FINDINGS.md Section 7 retired the
  sealed historical holdout ... so reading the full daily history through
  the present is not a leak"). This is the ONLY source of price data for
  this study -- box construction, the 50-day trend filter, and the
  momentum null's own momentum computation all read from it, never from
  `prices_eod` directly.
- `data_layer.nse_holidays.is_nse_holiday` -- unchanged, the same holiday
  master every fetch/backtest script in this project already relies on
  (used only incidentally here, since box construction walks each
  entity's own trading-day index, not the calendar, so no explicit
  holiday stepper is needed -- listed for completeness, not because this
  study calls it directly).
- `fibo.jump_guard.combined_unexplained_jump_dates` -- the same combined
  lineage-jump (Bug #1) and same-ISIN-jump (Bug #11) exclusion set every
  other daily-panel study in this project applies. A flagged (entity,
  date) is excluded from that entity's series entirely for this study's
  purposes (box construction, trend filter, and momentum): the day's row
  is dropped from the panel before any rolling computation touches it,
  so a fabricated price jump cannot manufacture a false 200-day high, a
  false box bottom, or a false momentum reading, and cannot silently
  reappear later as an unflagged neighbor of a dropped day.
- `factors.momentum.compute_momentum_12_1` -- unchanged, the project's
  existing Jegadeesh-Titman 12-1 momentum construction (252-trading-day
  lookback skipping the most recent 21), reused verbatim for the
  MOMENTUM null's own alternative stock-selection rule (Section "Nulls"
  below). It already accepts an `unexplained_jump_dates` argument wired
  to the same jump guard above, so momentum and box construction use the
  identical exclusion set, not two independently-derived ones.
- `box_theory.inference.day_clustered_bootstrap` / `excludes_zero` /
  `percentile_vs_null` -- unchanged. Reused verbatim for the same reason
  `PREREGISTRATION_IPO.md` Section 0 already states for its own reuse of
  this module: this is a general day-clustered-bootstrap implementation,
  not box-theory-V1-specific code, and its 97.5% two-sided CI ([1.25th,
  98.75th] percentile) is numerically exactly what this study's own gate
  calls for at family trial count 1 (no Bonferroni correction needed
  beyond what the function already applies for its documented 2-config
  framing; this study only ever runs ONE configuration, so the resulting
  interval is, if anything, slightly conservative for a 1-trial family --
  stated here, same as `PREREGISTRATION_IPO.md` Section 0, so it is not
  mistaken for an unexplained correction being smuggled in).
- `swing.costs.buy_leg_cost_rs` / `sell_leg_cost_rs` / `round_trip_cost_rs`
  -- unchanged, called with `order_type="DELIVERY"` (positions here are
  held open-ended, multi-day to multi-month -- never a same-day
  square-off), the identical DELIVERY statutory (STT 0.1% both sides,
  stamp duty, exchange/SEBI fees, GST) + Groww fixed-fee (brokerage,
  DP charge) + ported spread/impact range formula `PREREGISTRATION_
  PER_STOCK.md` Section 2 already uses for its own overnight,
  multi-day-hold study.

**New in `src/darvas/`, because nothing in this project constructs a
multi-week price box or a stop that trails upward as new boxes form**:
the box-detection state machine (`boxes.py`, Section 1 below); the
position-resolution/trailing-stop engine (`resolution.py`, Section 2
below); this study's own cost/sizing wrapper (`costs.py`) --
structurally identical in spirit to `per_stock.costs`'s DELIVERY
midpoint-of-range convention, but with this study's own `FIXED_RISK_RS
= 500.0` (not per_stock's 2000, not matched to it -- independently fixed
here, per instruction) and this study's own `floor(500/(entry-stop))`
sizing rule with NO minimum-1-share override (per_stock's override is
that study's own stated choice for a different problem; this study's
instruction gives the formula with no floor-at-1 carve-out, so a
zero-quantity result is a skip, not a forced 1-share trade -- see Section
3); the three nulls (`nulls.py`, Section "Nulls"); and this study's own
sealed-window guard (`test_seal.py`), its own window dates, its own log
path, sharing no state with any other study's seal.

## 1. Box construction -- FROZEN, operationalized precisely

**Universe for box construction**: every entity that is EVER a member of
the top-200-by-turnover universe (Section 4) at any point 2016-2026 --
the union across all reconstituted years, read via `fibo.daily_ohlc.
build_daily_ohlc_panel(con, entity_ids=...)` for exactly that entity set.
Box construction itself runs over each such entity's **FULL available
daily history** (not clipped to its own membership years) because a
200-day lookback and a 50-day trend filter both need real pre-membership
history to warm up correctly; a trade is only ever COUNTED (Section 4) if
its own entry date falls in a year that entity actually was a declared
universe member.

**Warmup**: an entity needs >=200 trading days of its own history before
its first day is even eligible to be checked for a 200-day-high trigger.
Days before that are skipped entirely (not treated as a failed check).

**All price levels below are `fibo.daily_ohlc`'s entity-adjusted
open/high/low/close** -- never raw.

### 1a. 200-day high trigger and top confirmation

Day D (D having >=200 prior trading days of this entity's own history) is
a **200-day-high trigger** if `adjusted_high[D] >= MAX(adjusted_high[D-199
.. D])` -- i.e. D's own high is at least tied with the highest high over
the trailing 200-trading-day window that ends at D itself (inclusive).

Once triggered, D becomes the **running top candidate**
(`peak_price = adjusted_high[D]`, `peak_date = D`). Scanning forward one
day at a time:

- If `adjusted_high[D'] >= peak_price`: the candidate ROLLS FORWARD --
  `peak_price = adjusted_high[D']`, `peak_date = D'`, and the 3-day
  confirmation count resets to 0. (Any day exceeding the current running
  top candidate is, by construction, itself at least as high as the
  trailing-200-day max, so it is automatically also a valid trigger --
  this needs no separate 200-day check.)
- Else (`adjusted_high[D'] < peak_price`): the confirmation count
  increments. On the **3rd such consecutive day with no new high**, the
  TOP is **confirmed** at `peak_price`, on that 3rd day (call it
  `top_confirm_date`) -- per instruction's rule 1 ("that price is not
  touched or exceeded for the next 3 trading days").

### 1b. Trend filter -- OUR definition, stated as such

**A box is only valid if the stock is in an upward trend entering it.**
The book says "upward trend" without specifying a test; **this document's
own operationalization, not the book's**: `adjusted_close[top_confirm_
date] > SMA(adjusted_close, 50)[top_confirm_date]`, the 50-day simple
moving average computed with `min_periods=50` (a day without 50 full
prior trading days cannot pass this filter -- treated as a fail, not a
skip). If this fails, the box TOP is **INVALID** -- discarded in full
(no bottom is ever sought for it), and the overall scan for the entity's
NEXT 200-day-high trigger resumes from the day after `top_confirm_date`.
Reported as its own count (`TREND_FILTER_FAILED`).

### 1c. Box bottom, and same-day top+bottom confirmation

**Bottom tracking runs IN PARALLEL with the top's own confirmation count,
starting from `peak_date` itself** -- this is this document's own
operationalization of instruction rule 2 ("after a top is confirmed, the
box bottom forms"), chosen specifically because rule 3 requires that top
and bottom be ABLE to confirm on the same day, which a strictly sequential
reading (bottom tracking starts only once the top has already finished
confirming) can never produce. Concretely: every time the top candidate
rolls forward to a new `peak_date` (Section 1a), the bottom candidate
resets too (`trough_price = adjusted_low[peak_date]`, `trough_date =
peak_date`, bottom confirmation count = 0) -- a new, higher peak makes any
earlier pullback low irrelevant, the same way it makes the old top
irrelevant. On every day the top candidate does NOT roll forward:

- If `adjusted_low[D'] < trough_price`: `trough_price = adjusted_low[D']`,
  `trough_date = D'`, bottom confirmation count resets to 0.
- Else: bottom confirmation count increments. On its 3rd consecutive day,
  the BOTTOM is **confirmed** at `trough_price`, on that day.

Because both counts start at 0 together at the same `peak_date` and the
bottom's count can only ever be <= the top's own count (both increment
together on days neither resets; the bottom resets strictly more often,
never less), **the bottom can never confirm before the top, and confirms
in the SAME day as the top exactly when no new low occurred between
`peak_date` and `top_confirm_date`** -- reported per instruction rule 3
as `same_day_top_bottom_count / total_complete_boxes`.

**Once the top is confirmed (Section 1a) and passes the trend filter
(Section 1b), the top price is FIXED** -- it never rolls forward again,
even if a later high exceeds it (that is the breakout condition, Section
2, not a redraw). Bottom tracking continues exactly as above (still
capable of resetting to a new, lower low) until it confirms.

### 1d. Box resolution -- six mutually exclusive outcomes, all reported

**AMENDMENT, recorded now, before any box has been detected or counted
anywhere (found while writing `src/darvas/boxes.py`, the first code this
study's build produced -- i.e. before any number this amendment could
have been shaped by):** the original five outcomes below all implicitly
presupposed that, once the top confirms and passes the trend filter, the
bottom's own status (confirmed or not) is already known by the time
resolution logic runs. That's false in one real case this document failed
to name: **the top can confirm and pass the trend filter, and the window
can then simply end before the bottom ever reaches its own 3 clean days**
-- not "still rolling" (outcome 5, which is about the TOP never
confirming) and not "bottom confirmed but no breakout/breakdown yet"
(outcome 4, which requires the bottom to already be confirmed). A sixth
outcome is added to name this case, and outcome 4's own wording is
unchanged (it already correctly required a confirmed bottom):

Once the top is confirmed and trend-filter-valid, each subsequent day is
checked, in this order, until one of the following resolves the box (or
the available data window ends first):

1. **`BROKE_OUT_BEFORE_BOTTOM_CONFIRMED`**: `adjusted_close[D'] >
   peak_price` on a day before the bottom has confirmed. **Our
   operationalization, stated plainly**: a box with no confirmed bottom
   has no defined stop, so this is NOT a tradeable entry -- the box is
   discarded with no trade, and the scan resumes for the next 200-day-high
   trigger from `D'+1`. Tracked separately from "never broke out" below,
   since this box DID break out, it simply could not be traded.
2. **`COMPLETE_BREAKOUT`** (the tradeable case): bottom already confirmed,
   and `adjusted_close[D'] > peak_price` on some later day. This is the
   ENTRY signal (Section 2).
3. **`COMPLETE_BREAKDOWN`**: bottom already confirmed, and
   `adjusted_close[D'] <= trough_price` on some day with no prior
   breakout close. The box fails before ever offering a trade.
4. **`COMPLETE_UNRESOLVED_AT_WINDOW_END`**: bottom confirmed, but neither
   a breakout nor a breakdown close occurs before the available data
   (DEV or TEST window, Section 7) ends.
5. **`TOP_NEVER_CONFIRMED_AT_WINDOW_END`**: the top candidate is still
   rolling forward (or still within its own 3-day count) when the window
   ends -- no box ever resolves either way.
6. **`BOTTOM_NEVER_CONFIRMED_AT_WINDOW_END`** (added by the amendment
   above): the top confirmed and passed the trend filter, and the bottom
   was still actively tracking (never breached long enough to confirm,
   and no breakout closed above the top either) when the window ends.

**"Boxes that never broke out"** (the report metric named explicitly in
the task) = outcomes 3 + 4 combined (a complete box that either failed
downward or simply ran out of data without ever closing above its own
top) -- reported as that sum, with 3 and 4 also broken out separately so
neither is hidden inside the other. Outcome 6 is reported on its own,
alongside outcome 5, as "box formation incomplete at window end" --
neither is folded into "never broke out," since neither ever became a
complete box in the first place.

After ANY of outcomes 1/3/4/5/6, the scan resumes searching for the next
200-day-high trigger from the day after resolution, independent of
whether a position happens to be open in this entity from an EARLIER,
already-resolved box (Section 2's trailing-stop mechanism needs box
detection to keep running even while a position is open, to find a later,
higher box to raise the stop toward).

## 2. Entry and exit -- FROZEN

**ENTRY**: buy at the next trading day's OPEN after a `COMPLETE_BREAKOUT`
close (Section 1d outcome 2). Long only. **One position per entity at a
time** -- if a later box's own `COMPLETE_BREAKOUT` fires while this entity
already has an open position, it does NOT open a second trade; that later
box is still used for the trailing-stop mechanism below, just not as a
fresh entry.

**Initial stop** = that box's own confirmed bottom price (`trough_price`).
**Initial risk fraction** `rho = (entry_price - initial_stop) / entry_price`,
fixed at entry, used only by the trailing mechanism below (never
re-measured mid-trade).

**Trailing stop -- the book's qualitative rule, reduced to two fully
mechanical sub-rules, checked once per trading day, in this order, after
that day's exit check (never before it, so a trade cannot be exited and
have its own exit-day stop simultaneously "raised" using same-day
information -- the stop in effect on day D was fixed using data only
through D-1):**

1. **New box above**: if, as of day D, ANY later box for this entity has
   reached `COMPLETE_*` status (top AND bottom both confirmed, Section 1d)
   with `trough_price` (that later box's own bottom) HIGHER than the
   current stop level, raise the stop to that `trough_price`. This is
   triggered by box COMPLETION, not by that later box's own eventual
   breakout/breakdown -- "a new box forms above the current one" (the
   instruction's own words) reads as the box existing, not as it
   necessarily working out.
2. **Run well above, no new box yet**: OUR filled gap, stated as such --
   the book describes "trail the stop to maintain the initial risk
   percentage" once price has run "well above" the box top, without
   giving a numeric threshold for "well above." This document fixes
   `RUN_THRESHOLD_R = 2.0` (price must have advanced by at least 2x the
   trade's own initial per-share risk, in rupees, beyond the ENTRY box's
   own top) before this sub-rule applies, chosen as a round, stated,
   never-tuned number in the same spirit as `PREREGISTRATION_BOX.md`'s
   own 0.995 arming threshold or `PREREGISTRATION_PER_STOCK.md`'s 95th-
   percentile null-beat bar -- a filled specification gap, not a
   discovered optimum. Concretely: if no Sub-rule 1 raise applies today,
   and `adjusted_close[D] >= entry_box_top + RUN_THRESHOLD_R * (entry_
   price - initial_stop)`, set a candidate stop = `adjusted_close[D] *
   (1 - rho)`.

**The stop NEVER moves down**: whichever of the two sub-rules above
produces a higher candidate than the current stop is applied; if neither
does, the stop is unchanged for the next day.

**EXIT**: on each trading day (starting the day after entry), if
`adjusted_close[D] < current_stop_level` (the level in effect as of the
previous day's close, per the ordering above), exit at that close. **No
time limit, no profit target** -- trades run until stopped out, or until
forcibly closed at a window boundary (below).

**OPEN TRADES AT WINDOW BOUNDARIES**: any position still open at the last
trading day of its window (DEV end or, later, TEST end) is closed at that
day's close and counted as a trade with that forced exit reason. Reported
separately: how many, and their pooled contribution to the window's mean
net R (so a reader can see whether the forced closures are propping up or
dragging down the headline number).

## 3. Sizing and costs -- FROZEN

**Sizing**: `qty = floor(FIXED_RISK_RS / (entry_price - initial_stop))`,
`FIXED_RISK_RS = Rs 500`. **No minimum-1-share override** -- unlike
`per_stock.costs.position_size_shares`'s own stated choice for a
different study, this document's instruction gives the bare formula with
no floor-at-1 carve-out, so if `floor(...) == 0` (a box whose range is
wide enough, relative to entry price, that even 1 share would risk more
than Rs 500), **no trade is taken** -- counted and reported as a distinct
skip reason (`ZERO_QTY_SKIP`), never silently forced to 1 share.

**Costs -- DELIVERY** (`swing.costs.round_trip_cost_rs(position_size_rs,
"DELIVERY")`, unchanged, Section 0): STT 0.1% both sides, stamp duty,
exchange/SEBI fees, GST, Groww brokerage, the DELIVERY-only DP charge, and
the ported spread/impact range (6.0-19.0bps round trip). As `PREREGISTRATION_
PER_STOCK.md` Section 2 already does for the same reason (one point
estimate is needed per trade), the MIDPOINT of that lo/hi range is used
for the headline net R; the range itself is carried into the report as a
stated sensitivity note, never silently collapsed to the point estimate
alone.

**Net R** = `(pnl_rs - cost_rs) / FIXED_RISK_RS` -- the NOMINAL Rs 500
target is the denominator throughout, not each trade's own realized
`qty * (entry - stop)` (which is <= 500 by construction of the floor) --
the identical convention `PREREGISTRATION_BOX.md` Section 4 already
states explicitly for its own fixed-risk sizing ("R is fixed by the
sizing formula, not measured after the fact"), reused here rather than
re-derived.

**Rank bands** (1-50 / 51-100 / 101-200 / unranked), read off each
entity-year's own `rank` column from `reconstitute_annually`'s output,
are tracked and reported as a BREAKDOWN dimension (the report explicitly
asks for results "by band") -- they do NOT feed into the cost model
itself, which (per the DELIVERY formula above) is flat/unbanded, unlike
`box_theory.costs`'s intraday banded-spread overlay. Stated explicitly so
the absence of banding in the cost model is not mistaken for an
oversight.

## 4. Universe and windows -- FROZEN

**Universe**: point-in-time top 200 by trailing median turnover, annually
reconstituted, `fibo.universe.reconstitute_annually(con, top_n=200)`
against `data/warehouse.duckdb`, identical to `PREREGISTRATION_BOX.md`
Section 2a. 2016 stub year handled identically (`effective_universe(
universe, stub_year=2016)` copies 2017's membership onto 2016). A trade
counts toward a given year's results by its OWN ENTRY DATE's calendar
year, and only if that entity is a declared member of that year's
universe (`restrict_to_universe` + `assert_universe_membership`, applied
to the realized trade list, not to the box-detection input -- Section 1's
own note on why box detection itself runs over each entity's full
history).

**Data range**: daily data in `data/warehouse.duckdb` / `fibo.daily_ohlc`
goes back to **2016-01-01** -- unlike the 1-minute intraday archive's
2016-10-04 floor that `PREREGISTRATION_BOX.md`/`PREREGISTRATION_FVG.md`
are both constrained by, this study uses the FULL available daily range,
stated here so the earlier floor is not assumed to carry over by habit.

**DEV**: 2016-01-01 to 2022-12-31 (entry dates in this range).
**TEST (sealed in code)**: 2023-01-01 to 2026-09-30, guarded by
`src/darvas/test_seal.py` -- its own `TestWindowViolationError`, its own
append-only access log at `data/darvas/test_window_access_log.txt`, no
shared state with Fibo's, box theory's, FVG's, or IPO's own seals.
`authorize_test=True` is exercised at most once, only after DEV passes
Section 6's gate AND the user explicitly approves.

Box-detection lookback is allowed to read pre-2016-01-01... there is no
such data (the warehouse itself starts 2016-01-01), so in practice the
first ~200 trading days of 2016 (roughly through October 2016) produce no
box-construction decisions at all for any entity -- not a bug, a natural
consequence of the 200-day warmup requirement stated in Section 1, and
reported as a count of entity-days lost to warmup.

## Nulls -- three, and the third is the primary one

**All three are restricted to the window being evaluated (DEV, then
later TEST) and share this study's own cost model and sizing formula.**

### TIMING null

Restricted to the exact (entity, box) pairs that produced a REAL
`COMPLETE_BREAKOUT` entry. For seed `s`, each real trade's entry date is
replaced by a day drawn uniformly at random from the 20 trading days
starting at that box's OWN `top_confirm_date` (not the real entry date,
which can be much later than top confirmation once the bottom, and then
the breakout itself, are both waited out) -- per instruction, "random
entry day within 20 trading days of the box top confirming." Entry price
= that random day's open. **Initial stop = the SAME real box's own
confirmed bottom** (unchanged -- the null varies entry timing only, not
the stop). Exit mechanics: the SAME two trailing sub-rules (Section 2),
run forward from the null's own random entry date. 1000 seeds; a timed
20-seed probe decides, before the full run commits, whether 1000 is
affordable within roughly an hour -- if not, 500 seeds is substituted and
the substitution is stated at the time it happens (same contingency
`PREREGISTRATION_BOX.md` Section 6 / `PREREGISTRATION_FVG.md` Section 8 /
`PREREGISTRATION_IPO.md` Section 8 already use).

### SELECTION null

Random (entity, day) pairs drawn from the same universe-year population
(any trading day for any that-year universe member -- no requirement that
a real box exist there), **matched count per calendar month** to the real
strategy's own per-month entry count. Entry price = that random day's
open. **Stop distance**: drawn (with replacement) from the REAL trades'
own pooled initial-risk-fraction distribution (`rho` values, Section 2) --
per instruction, "same stop distance distribution." **Exit mechanics --
OUR stated simplification**: Sub-rule 2 only (the run-well-above trailing
rule, which depends only on entry price and `rho`, both well-defined for
a null draw) -- Sub-rule 1 (raise the stop toward a "new box above") is
NOT applied, because a null's synthetic entry has no corresponding box
lineage to search forward from; inventing one would conflate the null
with the real strategy's own box machinery rather than testing against
it. Stated here, before any null number exists, so this is not read as
an oversight. 1000 seeds (500-seed fallback under the same timed-probe
contingency as the TIMING null).

### MOMENTUM null -- THE PRIMARY ONE

For each real entry, an alternative position in the universe-year member
with the **highest `momentum_12_1`** value as of that SAME entry date
(`factors.momentum.compute_momentum_12_1`, Section 0 -- point-in-time,
no lookahead; the real Darvas stock is not excluded from eligibility if
it happens to also be the top-momentum name that day, since no exclusion
was specified). **Same holding logic and sizing -- OUR operationalization
of that phrase, stated plainly**: entry price = that momentum stock's own
open on the SAME entry date; initial risk fraction = the REAL trade's own
`rho` (the same per_trade `rho` used for Section 2's trailing Sub-rule 2),
applied to the momentum stock's own entry price to derive its stop;
sizing = the identical `floor(500/(entry-stop))` formula; exit mechanics
= Sub-rule 2 only, same reasoning as the SELECTION null above (a momentum
stock has no box lineage of its own to raise a stop against). This is a
**single, deterministic alternate trade set**, not seed-drawn (there is
exactly one top-momentum stock per date, the same non-random-alternate
shape `PREREGISTRATION_IPO.md` Section 8's own SELECTION null already
uses and names its reasoning for) -- run through `box_theory.inference.
day_clustered_bootstrap` (`trade_date` = each alternate trade's own entry
date) to produce 10,000 resampled means, and the REAL strategy's own
observed mean located within that distribution via `percentile_vs_null`.

This tests whether Darvas adds anything over a signal (`momentum_12_1`)
that has ALREADY passed a sealed, genuinely-unseen holdout evaluation in
this project (`PREREGISTRATION.md`/`FINDINGS.md` Study 1). **If Darvas
does not beat this null, the finding is that Darvas is a more complicated
way of measuring momentum** -- not that Darvas has no signal at all, but
that whatever signal it has is not shown to be incremental to one this
project already trusts more, on weaker, non-sealed evidence.

## 6. Gate -- FROZEN

**DEV PASSES only if ALL hold**:

- mean net R > 0 with a day-clustered 97.5% bootstrap CI excluding zero
  (`box_theory.inference.day_clustered_bootstrap`, `trade_date` = entry
  date, Section 0)
- mean net R's percentile is >= 95th against BOTH the TIMING and
  SELECTION nulls
- mean net R's percentile is >= 95th against the MOMENTUM null
- mean net R remains > 0 after dropping the single best calendar year (by
  that year's own mean net R) from the DEV sample

**Anything else = NO EDGE. The study closes; the sealed TEST window is
never read.** No partial credit for passing some but not all of the above
-- the same all-or-nothing standard every prior gate in this project uses.

## 7. Report contents

Trades taken; distinct entry days; win rate; mean net R with its 97.5%
CI; median net R (descriptive); MDE (from the bootstrap SE alone, never
from the observed mean); all three null percentiles (with each null's own
seed count, or "deterministic" for MOMENTUM); breakdown by calendar year;
breakdown by rank band; holding-period distribution (mean, median, max --
open-ended by construction, Section 2); exit-reason mix (STOP /
FORCED_WINDOW_CLOSE); boxes found, split by Section 1d's six outcomes (per its own amendment);
how often top and bottom confirmed the same day (Section 1c); boxes that
never broke out (outcomes 3+4 combined, and separately); peak concurrent
positions and peak deployed capital; the `ZERO_QTY_SKIP` and `TREND_
FILTER_FAILED` and `BROKE_OUT_BEFORE_BOTTOM_CONFIRMED` counts; forced
window-boundary closures, their count, and their pooled contribution to
the window's own mean net R. **Bad results are reported in the first
sentence**, the same standing instruction every prior study here follows.

## 8. Process, in this order, stopping where marked

1. Write this document. **Commit and push it alone**, before any box is
   detected or any trade exists anywhere in this study. Report the commit
   hash. **>>> this step.**
2. Build `src/darvas/` and test it. **Hand-trace 5 real DEV-window trades
   before any aggregate number is computed**: one stopped at the initial
   box bottom, one where the stop trailed up through a genuinely new box,
   one long-running winner (Sub-rule 2's run-up trailing active), one box
   that formed (top and bottom both confirmed) but never broke out, one
   box where top and bottom confirmed on the same day. If the real DEV
   data does not happen to contain one of these five shapes, that is
   stated plainly rather than manufactured.
3. Run **DEV only** (real trades, then TIMING, SELECTION, and MOMENTUM
   nulls, in that order, checkpointed at each stage, timing and memory
   measured before the long stages per instruction). Report per Section
   7. **>>> STOP. The user approves before the sealed TEST window is
   read.**
4. Only after that approval: authorize `darvas.test_seal`, read TEST
   once, report per Section 7.

## 9. Discipline

**Trial counter for this family = 1.** The 200-day lookback, the 3-day
confirmation, and the 50-day MA trend filter are **FIXED** -- if DEV
fails, they are not retried at other values, and no variant (a different
lookback, a different confirmation window, a different trend filter, a
different `RUN_THRESHOLD_R`) is folded into this document after the fact;
any such variant is a NEW trial requiring its own pre-registration. **No
rule in this document changes after any number from DEV or TEST has been
seen.** **Bad results are reported in the first sentence** of whatever
reports them, never buried after a methods recap. **Pyramiding is
deliberately NOT implemented** -- Darvas's own account attributes much of
his return to concentrating capital into winners by adding to them as new
boxes formed; this version tests the breakout-and-trail SIGNAL on a
fixed, single-position-per-entity basis so its per-trade statistics stay
comparable to every other study in this project, at the stated cost that
it does not measure his full method, only the signal underneath it.

## Status

**>>> STOPPING HERE, per Process Step 1.** No `src/darvas/` code exists
yet, and no box, trade, or R value has been computed anywhere in this
study. This document is being committed and pushed alone, before any of
that exists, so Step 2's build and every later step cannot have shaped
anything written above.
