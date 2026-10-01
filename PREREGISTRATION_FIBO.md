# Pre-registration: Fibonacci/ORB intraday study (Hypothesis B, Angel One SmartAPI data)

Frozen before any intraday data is downloaded or any backtest is run, per
this project's standing discipline (`PREREGISTRATION.md`,
`PREREGISTRATION_SWING.md`, `PREREGISTRATION_SWING_V1.md`). Nothing below
changes after this document is written except by an explicit, recorded
amendment.

**Status, updated 2026-09-28**: Steps 0/a-e, login, and Step 1 (data depth)
are complete. Section 5 (dev/test split) is now **FROZEN**, decided from
Step 1's report. Step 3 (download) and Step 5 (development backtest) have
not started.

**Amendment, 2026-09-28, BEFORE any intraday data was fetched**: the
fractal window in Section 3(b) was corrected from a standard 2-bars-each-
side (5-bar) Williams fractal to **5 bars each side (an 11-bar window)**,
per the user's own clarification that "5-bar fractal each side" meant five
bars on each side, not a 5-bar-total window -- the original wording was
ambiguous and the user's first reading of their own words (2-each-side) was
a reasonable one, corrected once the intended reading (wider window, to
capture only significant reversals) was clarified. This is a **spec
clarification, not tuning**: it happened before Step 1 ran, before any
Angel One data existed, and before any backtest of any kind was run against
this rule -- there is no possibility this change was informed by a result.
The fractal confirmation lag changes correspondingly (5 bars, not 2). See
`src/fibo/indicators.py`'s module docstring for the same note attached to
the code.

## 0. Scope and data-only guarantee

This is a **data-only** research module (`src/fibo/`). It never places,
modifies, or cancels an order, and never imports or calls an Angel One
order endpoint. Everything here reads market data and produces a
backtested trade list; nothing here touches a live position.

Credentials (`ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`,
`ANGEL_TOTP_SECRET`) live in a git-ignored `.env`, never printed, logged,
or echoed anywhere, including in exception messages (redacted before
display). See `.env.example` for the expected keys.

## 1. Universe: point-in-time, top-50-by-turnover, annually reconstituted

**Not today's Nifty 50** -- that would be survivorship-biased (today's
constituents are, by construction, the names that grew or survived to
still be in the index today). Instead, `src/fibo/universe.py`:

- Membership for calendar year Y = the **top 50 entities by MEDIAN DAILY
  TURNOVER over calendar year Y-1** (series='EQ', raw rupee turnover --
  turnover needs no split adjustment, since price x volume in rupees is
  invariant to a split). Ties broken by entity_id ascending, deterministic.
- Membership is held **fixed for the whole of year Y**, reconstituted again
  at the next calendar-year boundary -- not a continuously-rolling window
  (a stable annual list is what a study that needs to know its tradeable
  universe before downloading a year of 1-minute bars actually needs; see
  the module docstring for why this reading was chosen over a rolling
  N-trading-day alternative).
- 2016 is dropped (no preceding year to rank against). A year whose own
  data does not yet reach November is treated as still in progress and is
  never used as a ranking base (prevents an in-progress year from minting
  a membership list for a year that has not started).
- Measured against the real warehouse (`src/fibo/universe.py`,
  `membership_report`): 50 members every year from **2017 through 2026**,
  turnover of 10-20 names per year (11-20 of 50, i.e. roughly 20-40%
  annual turnover in membership -- see the table below).

| year | n_members | n_added | n_dropped |
|---|---|---|---|
| 2017 | 50 | 50 | 0 |
| 2018 | 50 | 11 | 11 |
| 2019 | 50 | 11 | 11 |
| 2020 | 50 | 10 | 10 |
| 2021 | 50 | 12 | 12 |
| 2022 | 50 | 17 | 17 |
| 2023 | 50 | 11 | 11 |
| 2024 | 50 | 15 | 15 |
| 2025 | 50 | 20 | 20 |
| 2026 | 50 | 19 | 19 |

**AMENDMENT, 2026-09-29 -- universe widened from top 50 to top 200, method
unchanged, motivation TRADE COUNT ONLY**: the development backtest
(Section 6a) produced 67 trades over 6.25 years at top-50 -- ~10.7/year.
Scaled to the sealed test window's 3.75 years, that rate implies ~40
trades, far short of Section 5a's 100-trade TEST PASS floor: spending the
one authorized test-window read on a result that cannot even be evaluated
would waste it. The fix is a WIDER UNIVERSE, not a different rule --
top 200 by the exact same point-in-time, annually-reconstituted,
trailing-median-turnover method (`src/fibo/universe.py`,
`reconstitute_annually(top_n=200)`, no code change, only the `top_n`
argument). Every rule in Section 3 is unchanged.

**Safeguard against this being a second look at strategy performance**:
the additional 150 names/year are downloaded and checked for DATA QUALITY
ONLY on the development window (Section 2a) -- scale-probe resolution
rate and HIGH/LOW agreement, by liquidity rank band. No trade, no R, no
null is computed for the new names on development data. The decision to
widen was made from the ORIGINAL top-50 development trade COUNT alone,
before any top-200 development trade existed to look at.

**Expected test-window trade count at top-200, computed 2026-09-29 BEFORE
the test runs** (`scripts/fibo_step5_cost_liquidity_check.py`): scaling
the development top-50 rate (67 trades / 74.9 months = 0.895/month) by
the 4x universe widening and the 44.5-month test window gives **~159
expected test trades under a flat per-name-rate assumption** -- comfortably
above Section 5a's 100-trade floor. Stated explicitly as an upper-bound
projection, not a calibrated forecast: the Alligator-uptrend/2xATR-swing
setup gate is not turnover-dependent by construction, but the 101-200 band
has not had its own per-name signal frequency measured, and Section 2a's
data-quality removals (NO_ORB_DATA, EXCLUDED_SCALE) are expected to be
somewhat higher there than at top-50.

### 2a. Data-quality checks for the top-200 additional names, run 2026-10-01
-- DEVELOPMENT WINDOW ONLY, no strategy/R/null computed

`scripts/fibo_step5_top200_data_quality.py`: for every (entity, day) pair
downloaded below the sealed test start (2023-01-01) across the FULL top-200
universe, classified scale-probe decision and reported by liquidity rank
band. No trade, no R, no null was computed for any entity here -- this is
purely a scale-probe/HIGH-LOW agreement check, matching the safeguard
recorded in Section 1's amendment.

| Band | Pairs | Entities | RAW_EQUIVALENT | SCALED | UNRESOLVED | EX_DATE_SKIP | GAP_GUARD_SKIP |
|---|---|---|---|---|---|---|---|
| 1-50 | 67,752 | 81 | 64.83% | 34.56% | **0.57%** | 0.03% | 0.01% |
| 51-100 | 70,005 | 122 | 71.25% | 28.17% | **0.54%** | 0.03% | 0.01% |
| 101-200 | 130,817 | 213 | 73.02% | 25.42% | **1.53%** | 0.02% | 0.01% |

**Verdict: all three bands are within the 2% UNRESOLVED threshold** --
band 101-200's 1.53% is higher than the other two bands (consistent with
thinner, noisier archive coverage at lower liquidity, as expected) but does
not trigger the STOP-and-report gate. r_high/r_low relative disagreement
(the empirical measurement underlying the scale decision itself) stays at
median 0.0000% in every band, with p99 no worse than 0.0186% -- the scale
probe's own reliability does not degrade materially by band.

10,121 (entity, day) pairs fell outside all three bands ("unranked") --
verified as the expected 2016 stub-year download (Section 3's
`build_download_plan` reuses 2017's membership list for the Oct-Dec 2016
stub, per `src/fibo/universe.py`'s documented first-year gap), confirmed by
checking `bars_1min` row counts by year (2016: 3.67M rows, in line with a
partial year vs. 15-18M rows/year 2017 onward) -- not a data-quality gap.

## 2. Data layer

- **Source**: Angel One SmartAPI, 1-minute historical bars, data-only.
- **Storage**: a SEPARATE DuckDB file (`data/fibo_intraday.duckdb`,
  `src/fibo/intraday_db.py`) -- never shared with `data/warehouse.duckdb`.
  Same append-only, `known_date`/`fetched_at`/`source`/`revision_seq`
  discipline as the main warehouse.
- **PRICE SCALE -- REVISED 2026-09-29, Step 3's validation run against real
  downloaded data CONTRADICTS the original premise below.** The original
  assumption (still recorded here for the record, then corrected): daily
  prices in the main warehouse are split-adjusted to TODAY's scale; Angel
  One's intraday bars were assumed RAW, in whatever scale the exchange
  actually quoted that day, requiring `src/fibo/price_scale.py`'s
  `zone_to_raw_scale` to convert an adjusted golden-zone level down to
  raw(D) before comparing against intraday bars. That conversion logic is
  correct in isolation (verified against a real development-window split,
  TATASTEEL 2022-07-28, `tests/test_fibo_price_scale.py`, 4/4 passing --
  originally verified against BAJFINANCE's 2025-06-16 event, replaced
  2026-09-29 since that date falls inside the sealed test window) -- **but
  the premise it rests on, "Angel's intraday bars are raw," is FALSE for a meaningful
  share of this universe**, discovered by aggregating real downloaded
  1-minute bars to daily and comparing against bhavcopy (development window
  only, 500-pair sample):
    - For (entity, day) pairs where no split/bonus has happened SINCE that
      day (`factor == 1.0`, 363/500 = 72.6% of the sample), raw bhavcopy
      and Angel's intraday close agree almost exactly (median difference
      0.000%) -- expected, since raw and adjusted are the same number there.
    - For (entity, day) pairs where a LATER split/bonus exists
      (`factor != 1.0`, 124/500 = 24.8%), Angel's intraday close matches
      **this project's own adjusted close** (raw x factor), not raw
      bhavcopy, for **102/124 (82%)** of pairs -- i.e. Angel had ALREADY
      back-adjusted its historical intraday archive for that corporate
      action, the opposite of the original assumption.
    - But **16/124 (13%)** of pairs are genuinely RAW (matching bhavcopy,
      not the adjusted close) even though a later split/bonus exists --
      e.g. TATASTEEL (`INE081A01012`, a 10x face-value split in 2022) and
      two others, consistently raw across every sampled date for that
      entity, not intermittently.
    - No clean rule was found correlating ADJUSTED-vs-RAW behavior with
      action type (bonus vs. split), combined ratio magnitude, or ISIN-
      lineage-chain length in this sample -- it did not reduce to "splits
      are raw, bonuses are adjusted" or similar. The most likely
      explanation is an inconsistency internal to Angel's own historical
      data vendor/backfill process, not a discoverable rule this project
      can derive from first principles.
  **Practical consequence**: neither "always convert to raw" nor "never
  convert" is a safe blanket rule.

- **DECISION, 2026-09-29, made BEFORE any development backtest: probe the
  scale PER ENTITY PER DAY, not per entity and not by excluding
  raw-behaving names.** Two alternatives were explicitly rejected, with
  reasons recorded because they were considered and rejected, not just
  never proposed:
    - **Per-entity classification** (decide once per entity, apply to
      every day) was rejected because it assumes the archive's behavior is
      CONSISTENT OVER TIME for a given entity -- an assumption the archive
      itself has already disproved. Concretely: TATASTEEL
      (`INE081A01012`) shows ADJUSTED behavior on 2022-07-25 (Angel's close
      that day equals bhavcopy's raw close x 0.1, the factor then in
      effect) and RAW behavior starting the very next trading day,
      2022-07-26 (Angel's close now equals bhavcopy's raw close directly)
      -- a real behavior change for the SAME entity, two trading days
      before its own real ex-date. A per-entity decision computed from
      either date would have silently mis-scaled the other.
    - **Excluding raw-behaving entities** was rejected because it would
      drop 13-18% of the universe specifically because of a data-vendor
      artifact, leaving a tested universe that no longer matches the one
      Step 2 specified (point-in-time top-50-by-turnover) -- the study
      would then be evaluating a different, survivorship-flavored universe
      without saying so.

  **Mechanism** (`src/fibo/scale_probe.py`): for entity E on trading day D,
  decide the scale using ONLY information knowable before D opens --
  day D-1, E's own previous trading day:
  ```
  ratio = Angel's D-1 last 1-minute close / bhavcopy's raw close for D-1
  if |ratio - 1.0| <= 0.5%                    -> RAW      (divisor 1.0)
  elif |ratio - factor(D-1)| <= 0.5% x factor(D-1)
                                                -> ADJUSTED (divisor factor(D-1))
  else                                          -> UNRESOLVED -- skip E on D
  ```
  D's own bhavcopy is NEVER read to decide D's own scale -- that would be a
  peek at D's close, the same lookahead discipline every other signal in
  this project already follows. An entity is also never traded on a day
  that is itself an ex-date for it: the scale can change overnight across
  an ex-date, and D-1 (the day BEFORE the change) cannot describe it.
  **All simulation -- zones, entry, stop, target, quantity, costs -- happens
  in D's RAW scale**, because quantity = floor(500 / (entry - stop)) and
  brokerage depend on real rupee prices, not an arbitrary adjusted unit.
  This probe corrects for ANGEL'S OWN archive inconsistency; it is a
  SEPARATE layer from `price_scale.py`'s conversion of THIS PROJECT'S OWN
  adjusted golden-zone levels down to raw(D) -- a live signal on day D
  needs both layers, not one in place of the other.

  Verified against two real development-window cases
  (`tests/test_fibo_scale_probe.py`, 11/11 passing): BPCL
  (`INE029A01011`, D-1=2019-12-26, factor 0.5, ratio 238.60/477.20 = 0.5
  EXACTLY) correctly classified ADJUSTED, and dividing D's (2019-12-27)
  Angel OHLC by 0.5 reproduces D's real bhavcopy OHLC to the cent
  (239.75/0.5=479.50, matching exactly); TATASTEEL
  (`INE081A01012`, D-1=2022-07-26, ratio 949.5/949.50 = 1.0 despite
  factor(D-1)=0.1) correctly classified RAW, and D's (2022-07-27) Angel
  OHLC already equals bhavcopy's raw OHLC with no conversion.

  **Development-window report** (`scripts/fibo_scale_probe_report.py`,
  70,436 real (entity, day) pairs, every pair Step 3 actually downloaded):

  | decision | count | % |
  |---|---|---|
  | RAW | 45,174 | 64.13% |
  | ADJUSTED | 14,749 | 20.94% |
  | UNRESOLVED | 10,494 | 14.90% |
  | EX_DATE_SKIP | 19 | 0.03% |

  **UNRESOLVED (14.90%) exceeds the ~2% stop threshold -- investigated, not
  silently accepted.** Diagnosis: NOT uniform noise -- 85%+ of all
  UNRESOLVED pairs trace to just 7 of 81 entities (four of them
  contributing an identical 1,539 rows each, itself a sign of a
  structural, not random, cause). Excluding those 7 entities, UNRESOLVED
  falls to **2.52%** (1,516 of 60,140), much closer to the threshold. Root
  causes identified for the concentrated entities, not left as an
  unexplained residual:
    - **KOTAKBANK** (`INE237A01028`): ratio = EXACTLY 0.2 on a spot-checked
      date (a clean 5x factor) despite this project's own `factor` = 1.0
      (no bonus/split ever recorded for it). This project's
      `corporate_actions` table only covers `ex_date >= 2016-01-05`
      (confirmed: `MIN(ex_date)` in the table) -- KOTAKBANK's 2015 merger
      with ING Vysya Bank (a real, large, pre-2016 share-structure event)
      is invisible to this project's own factor computation. This is a
      **gap in this project's own data, not a flaw in Angel's archive or
      in this probe** -- the probe correctly refuses to guess rather than
      trusting a `factor=1.0` known to be wrong for this name.
    - **IBULHSGFIN/SAMMAANCAP** (`INE148I01020`) and **TATAMOTORS/TMPV**
      (`INE155A01022`): both renamed mid-lifetime; the corporate event
      behind the rename (a major restructuring, not a simple bonus/split)
      is outside `corporate_actions.py`'s deliberately narrow scope.
    - **RELIANCE** (`INE002A01018`): a smaller, different-natured issue --
      a persistent ~1.27% drift between Angel's ratio and this project's
      own factor, plausibly because Angel's own back-adjustment folds in
      dividends (a "total return" convention) while this project's factor
      deliberately does not (`corporate_actions.py`'s stated scope: bonus
      and face-value splits only).
    - VEDL (`INE205A01025`), UPL (`INE628A01036`), BHARTIARTL
      (`INE397D01024`) show smaller or intermittent versions of the same
      pattern, not yet individually root-caused.
  **Left for the user to decide, not resolved here**: whether to backfill
  pre-2016 corporate actions for the affected names, treat UNRESOLVED as
  an acceptable per-day skip (the mechanism's own designed behavior for
  exactly this situation), or something else -- Step 5 should not start
  until this is decided, since these 7 entities would otherwise silently
  skip a disproportionate share of their signal days.

- **REVISION, 2026-09-29, made after examining the data-quality statistics
  above but BEFORE any development-backtest strategy result: the
  factor-table-dependent probe above is REPLACED** with a direct empirical
  measurement that does not use `corporate_actions`/`adjustment_factors`
  at all, and does not need to know WHY a mismatch exists. Explicit
  decision: do NOT backfill pre-2016 corporate actions -- stated for the
  record, this was never a warehouse bug (the daily warehouse starts
  2016-01, after KOTAKBANK's 2015 merger, so every daily-side return in
  this project is unaffected; the gap only mattered because the first
  probe compared Angel's archive against this project's OWN factor table).

  **New mechanism** (`src/fibo/scale_probe.py`): for entity E on day D,
  using only D-1:
  ```
  r_high = bhavcopy's raw HIGH(D-1) / Angel's HIGH(D-1)
  r_low  = bhavcopy's raw LOW(D-1)  / Angel's LOW(D-1)
  if r_high and r_low agree within 0.1% (relative to their mean):
      scale(D) = mean(r_high, r_low); D's raw bars = Angel's D bars x scale(D)
  else:
      UNRESOLVED -- skip E on D
  ```
  HIGH/LOW, not CLOSE: bhavcopy's close is NSE's own 30-minute volume-
  weighted closing-auction price, which never exactly equals Angel's last
  1-minute print, while HIGH and LOW are the same real trade prints in
  both sources. **Verified empirically before relying on it**, on the same
  500-pair development-window sample the validation step used: r_high and
  r_low agreed within 0.1% for **99.8%** of pairs (median relative
  disagreement exactly 0.0%).

  **Ex-dates still skipped outright** (unchanged). **New guard**: if D's
  converted 09:15 open differs from D-1's raw close by more than 20%
  (an unflagged overnight restructuring D-1's own bars cannot see), E is
  skipped on D regardless of how clean the HIGH/LOW match was
  (`GAP_GUARD_SKIP`).

  Verified against four real development-window cases
  (`tests/test_fibo_scale_probe.py`, 14/14 passing) -- the same two as
  before, PLUS the two the first version could not resolve:
  BPCL (scale exactly 2.0, unchanged from before), TATASTEEL (scale
  exactly 1.0, unchanged), **KOTAKBANK** (scale = EXACTLY 5.0, measured
  directly from D-1's real high/low with no factor-table lookup --
  resolves the exact case the first version could not), and **RELIANCE**
  (scale = 2.0257, NOT the theoretical 2.0 combined-bonus factor -- the
  real, dividend-inclusive scale Angel's archive actually uses, measured
  directly rather than assumed).

  **Noted because it was not something this method was told to look for**:
  RELIANCE resolving at 2.0257 rather than the theoretical 2.0 is itself
  independent confirmation that Angel's archive folds dividends into its
  back-adjustment (a "total return" convention). Nothing in the HIGH/LOW
  method was designed to detect dividend adjustment specifically -- it
  found this simply by measuring the true scale directly rather than
  assuming a formula, the same way it resolved KOTAKBANK's pre-2016 merger
  without ever being told a merger happened.

  **Development-window report** (`scripts/fibo_scale_probe_report.py`,
  same 70,436 real pairs):

  | decision | count | % |
  |---|---|---|
  | RAW_EQUIVALENT | 45,139 | 64.09% |
  | SCALED | 24,749 | 35.14% |
  | UNRESOLVED | 522 | 0.74% |
  | EX_DATE_SKIP | 19 | 0.03% |
  | GAP_GUARD_SKIP | 7 | 0.01% |

  **UNRESOLVED: 0.74%, target (<2%) met.** The 7 entities that drove 85%+
  of the first version's 14.90% UNRESOLVED now resolve at 0.58-0.78% each
  -- indistinguishable from the overall baseline, confirming the new
  method fixed the actual problem rather than relocating it:

  | entity | n | UNRESOLVED now |
  |---|---|---|
  | IBULHSGFIN/SAMMAANCAP | 1,545 | 0.71% |
  | TATAMOTORS/TMPV | 1,545 | 0.65% |
  | VEDL | 1,545 | 0.58% |
  | KOTAKBANK | 1,545 | 0.65% |
  | RELIANCE | 1,545 | 0.78% |
  | UPL | 747 | 0.67% |
  | BHARTIARTL | 1,545 | 0.71% |

  The gap guard fired 7 times total (0.010% of pairs) -- rare, as expected
  of a safety net rather than a routine filter.

- **Validation, before any bar is trusted**: `src/fibo/validation.py`
  aggregates downloaded 1-minute bars to a daily OHLC
  (`src/fibo/bars.aggregate_to_daily`) and compares against bhavcopy.
  Actually run 2026-09-29 against the real download (development window
  only, 2016-10-04..2022-12-31, 500-pair sample of the 70,436 available
  pairs): **naive raw-vs-raw mismatch rate 40.6%** -- but that number
  conflates the scale-inconsistency finding above with the comparison
  itself, not a measure of download correctness on its own; see the PRICE
  SCALE note for the decomposition. The original 0.1% tolerance
  (`DEFAULT_TOLERANCE_PCT`) is also unrealistically tight for comparing a
  1-minute "last print" close against NSE's official closing-auction
  price -- even genuinely well-behaved pairs show a few percent of normal
  microstructure noise on `close` specifically (median 0%, but a real,
  expected spread above that), a separate, smaller calibration question
  from the scale-mismatch finding.

## 3. Rules frozen

**Timeframe / session convention**: daily bars for trend/swing/zone
construction, 15-minute bars for the ORB and entry decision, 1-minute bars
to resolve which of stop/target is hit first. All times IST.

**(a) Daily trend filter -- Alligator uptrend** (`src/fibo/indicators.py`):
Bill Williams Alligator on daily median price (H+L)/2 (the original uses a
4-hour chart; DAILY is substituted here, per instruction): jaw = SMMA(13)
shifted forward 8 bars, teeth = SMMA(8) shifted forward 5, lips = SMMA(5)
shifted forward 3. **Uptrend = lips > teeth > jaw (fanned bullish) AND
close above all three lines.** Implemented as `close > lips` alone: since
the fanned condition already makes lips the highest of the three lines,
`close > lips` and "close above all three" are the same condition, not an
approximation of it.

**(b) Swing construction -- most recent confirmed swing high, lowest swing
low before it, 2xATR minimum move** (`src/fibo/indicators.most_recent_confirmed_swing`):
a fractal with **5 BARS EACH SIDE (an 11-bar window)** -- index i's high/low
strictly exceeds/undercuts ALL TEN neighboring bars, 5 on each side (a tie
against any neighbor means no fractal). This is wider than the standard
2-each-side Williams fractal, deliberately, to capture only significant
reversals (see the amendment note above this section). The swing HIGH is
the **most recent** confirmed up-fractal -- not the highest one, the most
recent one. The swing LOW is the **lowest** confirmed down-fractal in the
**60 trading days strictly before** the swing high's own date -- not the
nearest one, the lowest one. "Confirmed" respects the fractal's own 5-bar
formation lag: a fractal cannot be used until its confirming bar (5 bars
after formation) has actually occurred as of the evaluation date, which
matters once this runs as a live/backtest signal walking forward day by
day. The pair only counts as a valid SWING if
`|swing_high - swing_low| >= 2 x ATR(14)`, ATR measured **Wilder's
smoothing, evaluated as of the swing high's own date** (an explicit choice:
the rule says "2xATR(14)" without saying whose date, and the swing high --
the signal date -- is the natural anchor).

Verified against real data (`FIBO.md` has the full walkthrough): RELIANCE's
most recent swing as of 2026-09-18 is low=1249.80 (2026-07-24) ->
high=1333.00 (2026-09-04) -- unchanged in this particular case from the
2-each-side reading, because both of those points remain significant
reversals under the wider window too, but the candidate pool of down-
fractals in the 60-day window shrank from 8 to 6 (2026-07-14 and 2026-08-05
no longer qualify as 11-bar fractals), and 1249.80 remains, independently
confirmed, the minimum of the 6 that do. Move 83.20 >= 2 x ATR(21.58) =
43.16, filter passes.

**(c) Golden zone**: for the swing found in (b), the 50%-61.8% retracement
band measured back from the swing high:
`[high - 0.618*(high-low), high - 0.5*(high-low)]`. RELIANCE example above:
range=83.20 -> zone = [1281.58, 1291.40], both values hand-checked against
the formula exactly.

**(d) Opening range**: 09:15-09:30, first 15-minute bar's high/low.

**(e) Setup condition**: ON only if the ORB (09:15-09:30) range **overlaps**
the golden zone AND the Alligator uptrend (a) holds.

**(f) Entry**: the first 15-minute candle, in the window 09:30-11:30,
closing above the ORB high. Buy **at that candle's own close price** (the
entry price is the close, not the ORB high or the next bar's open). No
entry if 11:30 passes with no qualifying close. **One trade per stock per
day** -- once a stock has entered (or the 11:30 window has closed with no
entry), no second entry is taken for that stock on that day.

**(g) Stop**: the ORB low.

**(h) Target**: `min(entry + 2R, swing_high)`, `R = entry - stop`
(`src/fibo/resolution.compute_target`) -- capped at the swing high so the
target never extrapolates past the level the setup was itself measured
from.

**(i) Exit**: 15:15 if neither stop nor target has been hit.

**(j) Stop/target resolution**: walked minute-by-minute on 1-minute bars
from the bar AFTER entry through 15:15 (`src/fibo/resolution.resolve_trade`).
**If a single 1-minute bar's range touches both stop and target, it counts
as a STOP** -- conservative, per instruction, since a 1-minute bar cannot
resolve which level was actually touched first intra-minute.

**(k) Position size**: fixed Rs 500 risk per trade, `floor(500 / R)`
whole shares (`src/fibo/resolution.position_size_shares`) -- floored, never
rounded up, so a stop-out never risks more than Rs 500.

**(l) Explicitly excluded**: Fair Value Gaps (FVGs) and support/resistance
levels play no role anywhere in this rule. Not "not yet implemented" --
deliberately out of scope for this study.

## 4. Cost model

`src/swing/costs.py`, **INTRADAY** order type (buy at breakout entry, sell
same day by 15:15 -- no depository transfer, so `STT_INTRADAY_SELL_BPS`
+ `STAMP_DUTY_INTRADAY_BUY_BPS`, no DP charge). Both cost-bound ends (the
6.0-19.0bps spread/impact range, see that module's own not-yet-validated-
for-this-universe caveats) reported, never blended into one midpoint, same
discipline as the swing project.

**Liquidity check by rank band, added 2026-09-29 after the universe
widened to top-200** (`scripts/fibo_step5_cost_liquidity_check.py`):
the 6.0-19.0bps spread/impact range is FLAT -- applied unchanged across
every rank. This project's own turnover data shows band 101-200's median
daily turnover (Rs 587M) is **18.0% of band 1-50's** (Rs 3,267M); band
51-100 sits at 40.2%. The flat range itself was ground-truth-measured at
turnover rank 300-600 in a DIFFERENT (whole-market) sibling-project
universe, not this project's own population -- no absolute figures from
that source are available in this repo to place Fibo's rank 101-200
against that rank 300-600 benchmark numerically, so this is reported as a
**flagged assumption, not a re-measurement**: applying the same flat bps
range to a band with materially lower turnover than the band it was tuned
for is a directional risk of UNDERSTATING true cost at rank 101-200. The
swing project's own note that the flat range is "probably conservative"
was made for ITS more-liquid population and does not automatically
transfer here. No fresh spread measurement was taken for rank 101-200
names this session; both cost bounds (lo/hi) continue to be reported
separately, never blended, per the existing discipline above.

## 5. Dev/test split -- FROZEN 2026-09-28, after Step 1

**DEVELOPMENT: 2016-10-04 through 2022-12-31.**
**TEST (SEALED): 2023-01-01 through 2026-09-18.**

2016-10-04 is Step 1's measured floor -- the earliest date Angel One's
SmartAPI actually has 1-minute/15-minute history for this study's universe
(identical across all 3 sample stocks and both intervals), ~9 months after
this project's own daily warehouse's 2016-01-01 start. 2026-09-18 is the
warehouse's current latest daily date at the time of this freeze.

**Why the boundary sits at 2023-01-01, recorded because it was a judgment
call, not a formula**: an intraday ORB/Fibonacci setup fires far less often
than a daily-bar signal (it needs an uptrend AND a qualifying swing AND an
ORB-golden-zone overlap AND a 15-min breakout close, all on the same day,
for one stock among ~50) -- trade frequency for this exact rule is
genuinely unknown before any backtest is run. The split is chosen to give
the TEST window enough calendar time (values across 3.75 years) to
plausibly accumulate a meaningful trade count regardless of how rare
signals turn out to be, while leaving DEVELOPMENT with 6.25 years --
including all of 2020, so development sees the COVID crash regime (a sharp
uptrend-filter whipsaw stress test) rather than a development set that
never has to survive one.

**Recorded per instruction, not glossed over**: the TEST window's back
half (2025-03-19 onward) overlaps the daily-bar date range the momentum
study, its large-cap replication, and the swing project's V1 holdout have
all already read (`FINDINGS.md` Section 7 -- that window is RETIRED as a
historical holdout for THOSE hypotheses, precisely because it was read
more than once). **This is a different, unrelated seal** (`src/fibo/holdout.py`,
`SEALED_TEST_START = 2023-01-01`): the Fibo rule set (Alligator/fractal/
golden-zone/ORB, frozen in Section 3 of this document) was never designed
by, fit to, or informed by any read of daily prices in that overlapping
window -- the daily-bar reads that retired the OTHER seal happened for
entirely different hypotheses (momentum_12_1, the V1 dip rule), and reading
DAILY closes for THOSE studies teaches nothing about whether an ORB breaks
above a Fibonacci retracement zone on 1-minute bars. The overlap is a
calendar-time coincidence between two independently-governed resources,
stated here so it is not discovered later and mistaken for a leak.

**Sealed in code, not by convention** (`src/fibo/holdout.py`,
`FiboHoldoutViolationError`, same pattern as `data_layer.holdout`): any
backtest read of `end >= 2023-01-01` raises unless `authorize_holdout=True`
is passed explicitly, reserved for the one, single, end-of-project test
evaluation. `tests/test_fibo_holdout.py` (5/5 passing) exercises the guard
directly, including the boundary-touching case.

Development-only work stops at Step 5's report (trade count, win rate,
average R net of costs, t-stat, max drawdown, trades/month, plus the two
baselines below) and does not touch the test window.

### 5a. Commitments, fixed 2026-09-29 -- BEFORE any Step 5 strategy number exists

**1. The development backtest is for CODE VERIFICATION and DESCRIPTION
only.** No rule change (Section 3's frozen thresholds, the golden-zone
math, the entry/stop/target construction, position sizing) is permitted
based on what Step 5's numbers show. A BUG in the simulation code may be
fixed; a RULE may not. Any bug fix made after seeing a development number
must be reported with exactly what changed in the code and why -- never
silently absorbed into "the result."

**2. The sealed test (2023-01-01 to 2026-09-18) runs on the frozen rules
regardless of how development looks.** A clean negative result on the test
window is a valid, acceptable outcome of this study -- not a reason to
revisit Section 3, not a reason to look for a different rule. "No edge
found for this fully-specified mechanical version of the method" is an
answer this pre-registration accepts in advance.

**3. TEST PASS requires ALL of the following** (evaluated ONLY on the
sealed test window, at the one authorized end-of-project read):
   - at least 100 trades in the test window (fewer = **NOT EVALUATED**, a
     third outcome distinct from pass/fail -- the rule fired too rarely to
     say anything, not that it failed);
   - average R per trade, net of costs, > 0, with t >= 2;
   - result at or above the 95th percentile versus the SELECTION null
     (null (b), Section 6) computed on the test window's own data;
   - **ADDED 2026-09-29, after seeing development results (see Section 6's
     null (b2) and the note on why this addition is permissible)**: result
     at or above the 95th percentile versus null (b2) AS WELL AS (b),
     both computed on the test window's own data.

   Any outcome not meeting all four is **NO EDGE for these rules** -- not
   partial credit, not "promising but underpowered," a flat no-edge
   verdict for this specific, fully mechanical version of the method.

### 5b. Cost sensitivity and final TEST PASS criteria, frozen 2026-10-01 -- BEFORE the sealed read

**Approval to run the sealed test was given with one mandatory addition,
decided and frozen here before any test-window data is read.** Rationale,
stated by the person who required it: the strategy risks a fixed Rs 500 per
trade, so positions are small and the flat spread/impact cost assumption
(Section 4) could dominate net R; Section 2a's own liquidity-by-band check
found band 101-200's turnover at only 18.0% of band 1-50's, and the flat
6.0-19.0bps range was tuned on a different, more-liquid population -- an
understated cost at the thinner bands could manufacture a pass that would
not survive a more realistic cost assumption.

**The test is read ONCE. Three cost scenarios are computed from that SAME
trade list -- no second read, no re-fetch of test-window data for any
scenario:**
- **(i) current flat model, low bound** -- `net_r_lo_cost` as already
  defined (Section 4), unchanged.
- **(ii) current flat model, high bound** -- `net_r_hi_cost` as already
  defined, unchanged.
- **(iii) PESSIMISTIC, banded**: band 1-50 unchanged (1x the high-bound
  spread/impact component); band 51-100 at 2x the high bound; band 101-200
  at 4x the high bound. Statutory + Groww fixed costs (Section 4) are
  untouched in all three scenarios -- only the spread/impact component is
  rescaled.

  **Multiplier justification, stated as conservative, not measured**:
  Section 2a's turnover medians give band 51-100 at 40.2% of band 1-50's
  turnover and band 101-200 at 18.0%. A strict inverse-turnover scaling
  would imply roughly 2.5x and 5.6x respectively. The chosen multipliers
  (2x, 4x) are ROUND NUMBERS BELOW that naive inverse-turnover
  extrapolation -- a deliberately moderate stress assumption, not a
  precise re-measurement of actual spread impact at those bands (no fresh
  spread data was collected for this test). They are picked to be large
  enough to meaningfully stress-test the headline result's dependence on
  the cost assumption, not to claim the true cost at those bands is known.

**TEST PASS now requires ALL FOUR of the following criteria to hold under
ALL THREE cost scenarios, simultaneously, from the one read:**
1. at least 100 trades (fewer = **NOT EVALUATED**, unchanged from Section 5a);
2. mean net R per trade > 0, with t >= 2;
3. result at or above the 95th percentile versus the SELECTION null (b),
   computed on the test window's own data;
4. result at or above the 95th percentile versus the SELECTION null (b2),
   computed on the test window's own data.

For scenario (iii), criteria 2-4 are evaluated using cost recomputed under
the pessimistic banded assumption for BOTH the strategy's trades and the
null draws' own (entity, day) pairs (each null draw's band is determined
the same way, by its own entity's rank in the year it was drawn) -- a fair
like-for-like comparison, not the strategy alone held to a harsher
standard than the null it is compared against.

**Any scenario failing any criterion makes the overall verdict NO EDGE for
these rules.** Not partial credit across scenarios, not "robust to two of
three" -- all four criteria, all three scenarios, or no edge.

**Also reported from the same single read, descriptive, not pass/fail
criteria:**
- trades and net R broken down BY RANK BAND (1-50, 51-100, 101-200), to
  show whether the result depends on the thinner, newly-added names;
- exit-reason breakdown (TARGET/STOP/TIME_EXIT), as in Section 6a;
- by year;
- the TIMING null (a), for comparison with development's 8.9th percentile
  finding -- descriptive only, not a TEST PASS criterion (Section 5a).

**This is frozen before the read. One read. No tuning, no second pass,
whatever the numbers say.**

## 6. Development-backtest baselines -- REVISED 2026-09-29 (three nulls, one designated primary)

- **(a) TIMING null**: the SAME (entity, day) pairs the strategy actually
  traded, entry re-drawn uniformly from 09:30-11:30 (a random qualifying
  15-minute candle), same stop distance (R, in rupees) and same target
  rule (`min(entry + 2R, swing_high)`) as that day's real trade, resolved
  on 1-minute bars the same way. Tests whether the ORB-breakout TRIGGER
  itself (this specific entry timing) adds anything beyond entering
  somewhere in the golden-zone-overlap window. 1000 seeds.
- **(b) SELECTION null -- PRIMARY**: random (entity, day) pairs from that
  YEAR's own point-in-time universe (Section 1), matched count per month
  to the strategy's own trade count, entry drawn uniformly from
  09:30-11:30, stop distance drawn from the strategy's OWN empirical
  distribution of R distances, flat 2R target (not swing-high-capped).
  Tests whether the Fibonacci+ORB CONFLUENCE picks genuinely better DAYS
  than random days in the same universe -- this is the null the TEST PASS
  criterion (Section 5a) is evaluated against. 1000 seeds.
- **(c) Buy-and-hold baseline**: buy 09:30, sell 15:15, same stocks and
  days as the strategy's own signal set. Deterministic (no seeds) -- a
  reference point, not a statistical null.
- **(b2) SELECTION null, UPTREND-RESTRICTED -- ADDED 2026-09-29, PRIMARY
  ALONGSIDE (b)**: identical construction to (b) in every respect (matched
  count per month, stop distance from the strategy's own R distribution,
  flat 2R target, 1000 seeds) except the sampling POOL: only (entity, day)
  pairs where that entity ALSO satisfies the daily Alligator uptrend that
  day, not every day in that year's universe. **Why added**: every real
  strategy trade, by construction, occurs on an uptrend day -- null (b)'s
  100th-percentile result on development data could therefore only be
  showing that uptrending stocks drift up intraday (already-known
  momentum), not that the Fibonacci+ORB confluence adds anything beyond
  being in an uptrend. (b2) isolates that by holding the uptrend condition
  fixed in the null too, so what's left to test is the swing/golden-zone/
  ORB confluence specifically.

  **Why adding this to the TEST PASS criteria AFTER seeing development
  results is permissible, stated because it would ordinarily be exactly
  the kind of post-hoc change this pre-registration exists to prevent**:
  (b2) is STRICTLY HARDER to clear than (b) alone -- it can only narrow the
  set of results that count as a pass (a result must now beat a null that
  already controls for uptrend, not just the weaker any-day null), never
  loosen it. A change that only makes a study harder to pass, added before
  the one authorized test-window read, does not create the file-drawer/
  garden-of-forking-paths risk a change that makes it easier to pass
  would. The development number vs (b2) is reported below for the record;
  it is NOT itself evaluated pass/fail (Section 5a) -- only the sealed
  test window's read against it is.

The strategy's result is reported as a percentile against (a), (b), and
(b2); (b) and (b2) are BOTH load-bearing for the TEST PASS criterion, (a)
is descriptive only.

## 6a. Development backtest results, run 2026-09-29 -- DESCRIPTIVE ONLY, per Section 5a

**Per Section 5a, commitment 1: nothing below authorizes any rule change.
This is a report of what the frozen rules, as coded, produced on
development data -- code verification, not a tuning signal.**

**Engine verification**: 5 real trades hand-traced against the frozen
rules before any aggregate was computed (`src/fibo/backtest.py`,
`tests/test_fibo_backtest.py` 15/15, `tests/test_fibo_signals.py` 5/5) --
a flat-2R winner (INE522F01014, 2016-11-10, gross R exactly 2.0), a
swing-high-capped winner (INE397D01024, 2017-05-10, target 361.95 capped
below the flat-2R level of 379.39), a stop (INE160A01022, 2017-02-01,
gross R exactly -1.0), and a 15:15 time exit (INE038A01020, 2016-11-22).
Every field (ORB, zone, entry, stop, target, exit, qty, R) checked by
hand against the frozen rules and the actual 1-minute bars. **No same-bar
stop+target tie occurred among the 67 real trades** -- the mechanism
itself is separately covered by
`test_trade_same_bar_tie_resolves_as_stop`; none was fabricated here to
force a fifth category.

**Category breakdown, every downloaded development-window (entity, day)
pair (70,436 total)**:

| category | count | % |
|---|---|---|
| NO_SIGNAL (no uptrend or no confirmed swing) | 49,679 | 70.53% |
| SETUP_OFF (uptrend+swing exist, ORB doesn't overlap zone) | 20,023 | 28.43% |
| EXCLUDED_SCALE (scale UNRESOLVED/ex-date/gap-guard) | 548 | 0.78% |
| TRADE | 67 | 0.10% |
| NO_ORB_DATA (Diwali Muhurat sessions, a handful of genuine mid-day data gaps e.g. 2017-07-10 affecting multiple entities at once) | 66 | 0.09% |
| SETUP_ON_NO_TRIGGER | 53 | 0.08% |

**Setup-ON days: 120** (67 triggered + 53 did not) -- of every day the
rule identified as a genuine confluence, **55.8% actually produced an
entry** before 11:30.

**Trade list: 67 trades**, 2016-10-04 to 2022-12-31 (~10.7/year), spread
across 34 of the 75 months in the window (41 months had zero trades).

**Win rate and R**: 48 wins / 19 losses = **71.6% win rate**. Average win
+0.980R gross (+0.827R net, lo-cost). Average loss -0.645R gross (-0.808R
net, lo-cost) -- losses cost more net-of-cost than they cost gross,
exactly the fixed-Rs-500-risk-means-small-positions effect Section 5's
simulation details flagged: small qty means the flat Groww brokerage
floor is a larger fraction of a losing trade's R.

**Mean R net of costs** (never blended, both bounds reported):
- Lo-cost: **+0.3637R**, SE 0.1131, **t = 3.216**
- Hi-cost: **+0.2731R**, SE 0.1128, **t = 2.420**

**Exit-reason breakdown**: TARGET 10 (14.9%), STOP 7 (10.4%), TIME_EXIT 50
(74.6%) -- most winners never reach target; they are marked to close at
15:15 still ahead. **Recorded descriptively, per instruction**: 50 of 67
exits (74.6%) are TIME_EXIT, only 10 reach TARGET and 7 STOP -- the
development result is mostly intraday drift held to the close, not
bounces to a Fibonacci target. Consistent with the TIMING null finding
below (the breakout trigger itself underperforms random entry): the edge,
such as it is, looks like it comes from being on the right stock on the
right day and holding, not from the specific mechanics of the bounce off
the golden zone.

**Max drawdown**: -4.31R (lo-cost) / -4.98R (hi-cost), cumulative net R
ordered by exit time.

**By year**:

| year | n | win rate | mean gross R | mean net R (lo-cost) |
|---|---|---|---|---|
| 2016 (partial) | 5 | 100.0% | 0.902 | 0.780 |
| 2017 | 16 | 68.8% | 0.408 | 0.249 |
| 2018 | 5 | 40.0% | -0.345 | -0.496 |
| 2019 | 10 | 80.0% | 0.833 | 0.693 |
| 2020 | 3 | 100.0% | 1.580 | 1.427 |
| 2021 | 12 | 83.3% | 0.628 | 0.461 |
| 2022 | 16 | 56.3% | 0.304 | 0.138 |

2018 is the only losing year; 2020 (the small-sample COVID stretch) is
the strongest -- neither observation changes anything (Section 5a,
commitment 1).

**Nulls, 1000 seeds each**:
- **(a) TIMING null: strategy at the 8.9th percentile.** The strategy's
  mean R is WORSE than 91.1% of random-entry-timing draws on the exact
  same (entity, day) pairs, same stop distance, same target rule. Stated
  plainly: on the days the rule correctly identifies as a genuine setup,
  the SPECIFIC ORB-breakout entry trigger appears to be a worse way to
  enter than a random time in the same window -- consistent with a
  breakout-exhaustion pattern (buying right as the move that triggered
  entry is already extended). This is a descriptive finding about THIS
  version's entry mechanic, not a rule change (Section 5a, commitment 1).
  **Recorded as a candidate for a future, SEPARATELY pre-registered study**
  (e.g. testing entry at a random or fixed time within the golden-zone-
  overlap window instead of an ORB breakout) -- not implemented, not
  substituted, not tested here. The entry rule in Section 3 is unchanged.
- **(b) SELECTION null -- PRIMARY: strategy at the 100.0th percentile.**
  The strategy's mean R exceeds all 1000 random-day draws (matched count
  per month, same universe, stop distance drawn from the strategy's own
  distribution, flat 2R target). The Fibonacci+ORB CONFLUENCE picks
  genuinely better days than random selection from the same universe --
  this is the null the eventual TEST PASS criterion is measured against.
- **(b2) SELECTION null, UPTREND-RESTRICTED -- strategy at the 99.9th
  percentile (gross R), 100.0th percentile (net R, both cost bounds)**,
  1000 seeds, pool restricted to uptrend days (20,017 of 67,293 candidate
  pairs, 29.7%). **This was the specific risk (b2) existed to test, and it
  held**: null (b) alone could only have shown that uptrending stocks drift
  up intraday, which is already-known momentum, not evidence the
  Fibonacci+ORB confluence adds anything on top of the uptrend filter.
  (b2) isolates exactly that question by holding the uptrend condition
  fixed inside the null too -- and the strategy still clears it decisively.
  Recorded here, before the sealed test, as the result that justifies
  treating (b2) as load-bearing (Section 5a) rather than merely
  informational.
- **(c) Buy-and-hold baseline**: mean R-equivalent **+1.0844** (n=66),
  computed on the SAME 67 days using each trade's own R as the sizing
  reference. Higher than the strategy's own net R on these days -- not
  risk-comparable (buy-and-hold carries no stop), but stated as required,
  without spin.

**TEST PASS bar (Section 5a), applied informationally to development data
ONLY -- this is not the test, and nothing here is evaluated against it for
real**:
- >= 100 trades: **67 -- would be NOT EVALUATED, not a fail**, if this
  were the test window.
- mean net R > 0 with t >= 2: **met at both cost bounds** (t = 3.216 lo,
  2.420 hi).
- >= 95th percentile vs the SELECTION null: **met** (100.0th).

Two of three criteria would be met on development-shaped data; the trade
count would not clear the bar. Stated because Section 5a requires it, not
because it predicts the test outcome: development and test are different
data, and the whole point of pre-registering the bar was to decide it
before knowing whether it would be met.

## 6b. SEALED TEST RESULTS -- run 2026-10-02, THE ONE AUTHORIZED READ -- FINAL

**Per Section 5b: one read, no tuning, no second pass. This section
reports exactly what that one read produced, in full, including the
outcome that was not hoped for.**

`scripts/fibo_test_backtest.py` (the sealed read, `authorize_holdout=True`,
top-200 universe, 2023-01-01 to 2026-09-18) followed by `scripts/
fibo_test_nulls.py` (TIMING, SELECTION (b), SELECTION (b2) on the test
window's own data, 1000 seeds each) and `scripts/fibo_test_report.py`
(the Section 5b table). **188 trades** -- well above the 100-trade floor,
confirming the top-50-to-top-200 universe widening (Section 1's amendment)
achieved its stated, sole purpose.

**Exit-reason breakdown**: TIME_EXIT 147 (78.2%), TARGET 29 (15.4%), STOP
12 (6.4%) -- consistent with development's own finding that most of this
rule's result is intraday drift held to the close, not bounces off the
golden zone.

**By rank band** (mean R, all three cost scenarios):

| band | n | win rate | gross | net (lo) | net (hi) | net (pessimistic) |
|---|---|---|---|---|---|---|
| 1-50 | 45 | 75.6% | 0.5876 | 0.4211 | 0.3194 | 0.3194 |
| 51-100 | 34 | 73.5% | 0.4447 | 0.3056 | 0.2307 | 0.1212 |
| 101-200 | 109 | 70.6% | 0.5070 | 0.3543 | 0.2696 | **-0.1021** |

**This is the exact mechanism the cost-sensitivity requirement (Section
5b) was added to catch**: band 101-200 is 58% of all test trades (109 of
188) and its pessimistic-cost mean R is NEGATIVE, flipping from solidly
profitable under the flat model to a net loser once spread/impact is
stress-tested at 4x the high bound for that band. Bands 1-50 and 51-100
stay profitable even under their own (1x/2x) pessimistic multipliers --
the fragility is concentrated entirely in the newly-added, thinner names.

**By year**: 2023 n=48 (64.6% win, gross 0.4405), 2024 n=43 (76.7% win,
gross 0.7373), 2025 n=47 (83.0% win, gross 0.7112), 2026 n=50 (66.0% win,
gross 0.2109) -- no single year drives the result; all four years are
individually net-positive gross.

**TIMING null (descriptive only, not a TEST PASS criterion)**: strategy at
the **2.3rd percentile** (net, both cost bounds) -- consistent with, and
slightly more extreme than, development's 8.9th-percentile finding that
the specific ORB-breakout entry trigger underperforms a random entry time
on the same good days. Unchanged conclusion from Section 6a: a candidate
for a future, separately pre-registered study, not acted on here.

**TEST PASS TABLE (Section 5b: all four criteria, all three scenarios)**:

| scenario | mean net R | t | vs null (b) | vs null (b2) | verdict |
|---|---|---|---|---|---|
| (i) flat low | +0.3615 | 5.947 | 100.0th | 100.0th | **PASS** |
| (ii) flat high | +0.2745 | 4.569 | 100.0th | 100.0th | **PASS** |
| (iii) pessimistic banded | +0.0392 | 0.645 | 100.0th | 100.0th | **FAIL** (t < 2) |

Criterion 1 (>=100 trades): met, 188. Criteria 3 and 4 (>=95th percentile
vs nulls (b) and (b2)) are met at the 100.0th percentile in EVERY scenario,
including the pessimistic one -- the Fibonacci+ORB confluence still
clearly beats random selection and random-selection-within-uptrend even
under the harshest cost assumption tested. What fails scenario (iii) is
criterion 2 alone: mean net R is no longer statistically distinguishable
from zero (t = 0.645) once band 101-200's cost is stress-tested at 4x.

**FINAL VERDICT: NO EDGE for these rules**, per Section 5b's explicit
requirement that all four criteria hold under all three scenarios. Not
partial credit for passing two of three cost scenarios decisively; not
"robust except at the margin" -- the pre-registered bar required
robustness to the pessimistic cost scenario specifically because that
scenario was added to test exactly this failure mode, and the rule did
not survive it.

**What this does and does not mean, stated plainly and without spin**: the
Fibonacci+ORB confluence genuinely picks better days than random selection
-- that finding (criteria 3/4) is not in question and held at the 100th
percentile under every cost assumption tried. What is in question is
whether the EXECUTION of that edge survives realistic costs at thinner
liquidity, where this exact rule risks a fixed Rs 500 per trade regardless
of the name's liquidity -- and under a deliberately conservative (not
measured) stress on spread/impact at the bands added specifically to
reach the trade-count floor, it does not. This is NOT evidence that a
differently-sized, liquidity-aware, or band-101-200-excluded version of
the rule would fail the same way -- it is evidence that THIS fully
mechanical, fixed-risk, liquidity-blind version does not clear a
conservative cost bar once it trades thin enough names to hit 100+ trades.
No rule was changed to investigate that distinction; per Section 5a/5b,
this was the one read, and it stands as reported.

## 7. What is NOT being tested

- Portfolio-level capital constraints (unlimited capital assumed, same
  convention as `PREREGISTRATION_SWING.md`).
- FVGs, support/resistance, or any discretionary discretion beyond the
  rules frozen in Section 3.
- Any order placement, modification, or cancellation -- this study only
  ever produces a backtested trade list from historical/forward market
  data.
