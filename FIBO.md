# Fibonacci/ORB intraday research (Hypothesis B): Angel One SmartAPI, data-only

**These rules are one mechanical interpretation of a discretionary trading
method shared on social media, reduced here to a fully specified,
backtestable rule set (`PREREGISTRATION_FIBO.md`). Every discretionary
judgment call the original method leaves to a human chart-reader has been
replaced by an explicit, stated formula or threshold. Results in this
document and its preregistration test THIS specific version -- they say
nothing about the original author's own discretionary results, which were
never systematized or backtested by anyone.**

**Rules frozen in `PREREGISTRATION_FIBO.md`.** This file is the
phase-by-phase process record for `src/fibo/`; that document is the frozen
rule set, updated only by explicit amendment.

**Data-only, always**: this module never places, modifies, or cancels an
order, and never imports or calls an Angel One order endpoint. It reads
market data (daily bhavcopy already in this project's main warehouse, plus
new 1-minute intraday bars from Angel One SmartAPI) and produces a
backtested trade list. See `PREREGISTRATION_FIBO.md` Section 0.

**Separate from** every other hypothesis in this repository (momentum,
fundamentals, swing): its own code (`src/fibo/`), its own storage
(`data/fibo_intraday.duckdb`, never `data/warehouse.duckdb`), its own docs
(this file + `PREREGISTRATION_FIBO.md`), its own log directory
(`data/fibo_logs/`, mirroring `data/screener_logs/`'s convention). Shares
the main warehouse strictly READ-ONLY for daily data (universe
reconstitution, the Alligator/fractal/ATR/golden-zone rules, the price-scale
conversion, the bhavcopy cross-check) -- no change has been made or is
planned to any data-layer table, guard, or schema for this module.

## Status

**COMPLETE. The sealed test has been run, once, per explicit user approval
-- FINAL VERDICT: NO EDGE for these rules.** All prior steps (0-5,
universe widening to top-200, null (b2), data-quality checks, cost
sensitivity) led up to the one authorized read of 2023-01-01 to
2026-09-18, run 2026-10-02. 188 trades cleared the 100-trade floor and the
confluence beat both selection nulls at the 100th percentile under every
cost assumption tested -- but mean net R failed to clear t>=2 under the
pessimistic banded cost scenario (added specifically to stress-test this
risk), driven entirely by band 101-200 (58% of trades) flipping to a net
loser at 4x the high-bound spread/impact assumption. Per the frozen
all-four-criteria/all-three-scenarios bar, this is a clean NO EDGE
verdict, not a partial pass. Full result in `PREREGISTRATION_FIBO.md`
Section 6b. No rule was changed to investigate or avoid this outcome.

## Step 0: credential safety, one real finding

Before ever calling `generateSession`, reading `smartapi-python`'s own
source (`SmartApi/smartConnect.py`) turned up a real defect: its bundled
`logzero` logger attaches a file handler (`logs/<date>/app.log`, relative
to CWD) and logs, at ERROR level, `Request: {params}` on ANY failed API
call -- for a login call, `params` is the raw MPIN and TOTP in cleartext.
The same code path also logs `Headers: {...}` on failure for every OTHER
authenticated call (historical data included), which would include the
session's own Authorization bearer token. This is a defect in the
third-party SDK, not something this project's code does by default.
`src/fibo/auth.py`'s `_neutralize_sdk_logger` strips every handler from
that logger immediately after constructing the client and before any
credential-bearing call, and every script in this module reuses that ONE
authenticated client (never constructs a second `SmartConnect`, which
would reattach a fresh handler). Verified after the login test: the
`logs/<date>/app.log` file the SDK created was present but **empty** --
confirmed by direct inspection, then deleted (not needed, not tracked;
`*.log` in `.gitignore` would have caught it either way).

## Step 1: data depth (RELIANCE / INDIGO / MCX, ONE_MINUTE / FIFTEEN_MINUTE)

**Two methodology corrections made live during this step, recorded because
both were wrong on the first attempt** (full detail in
`scripts/fibo_step1_data_depth.py`'s module docstring):

1. A request with a huge date range does **not** error -- it silently
   returns a TRUNCATED response anchored to `todate`. Confirmed directly:
   requesting 800/1600/3200-day windows ending on the same date all
   returned byte-identical output. An early version of this script walked
   backward in large (640-day) chunks assuming the full requested range
   came back each time; it did not, leaving ~600-day gaps between chunks
   unprobed, so that version's "earliest date" numbers were discarded, not
   reported.
2. A corrected small-window search still went wrong once more: it reported
   "no boundary within 4000 days" for every symbol, but a direct manual
   check at 2016-01-15 (inside that range) came back empty -- the
   bracket-verification step (confirm the search's own endpoints are
   actually empty/populated before trusting a binary search between them)
   was missing. Added, then the real boundary was found immediately.

**Measured, not assumed, per-request truncation**: an oversized request
silently returns only the most recent slice:
- `ONE_MINUTE`: ~7,200 candles, spanning **28 calendar days** ending at
  `todate`.
- `FIFTEEN_MINUTE`: ~3,300 candles, spanning **~199 calendar days** ending
  at `todate`.

**Earliest usable data -- identical across all 3 stocks AND both
intervals** (a platform-wide historical-archive start date, not a
per-symbol listing constraint): empty at **2016-10-02**, populated at
**2016-10-04**. This is ~9 months after this project's own daily-bhavcopy
warehouse's earliest date (2016-01-01) -- the Fibo study's real
usable-data floor is **2016-10-04**, not 2016-01-01.

**Rate limit**: 70 historical-data requests this run at a 0.4s throttle
(observed actual inter-request gap 0.75-0.83s including API round-trip);
zero rate-limit-shaped errors encountered.

| piece | module | tests | status |
|---|---|---|---|
| credentials scaffold | `.env.example`, `.gitignore` | `git check-ignore -v` confirmed | done |
| point-in-time top-50-by-turnover universe | `src/fibo/universe.py` | `tests/test_fibo_universe.py` (6/6) | done, run against real warehouse (see PREREGISTRATION_FIBO.md Section 1) |
| daily OHLC panel (entity-adjusted) | `src/fibo/daily_ohlc.py` | exercised by indicator hand-verification below | done |
| Alligator, fractals, ATR, exact swing-selection rule, 2xATR filter, golden zone | `src/fibo/indicators.py` | `tests/test_fibo_indicators.py` (12/12), hand-verified on RELIANCE/TCS/INFY | done |
| price-scale conversion, OUR OWN factor (adjusted -> raw, date-specific) | `src/fibo/price_scale.py` | `tests/test_fibo_price_scale.py` (4/4), against the real TATASTEEL 2022-07-28 split (dev window) | done, one layer of two -- see scale_probe below |
| per-entity-per-day Angel-archive scale probe | `src/fibo/scale_probe.py` | `tests/test_fibo_scale_probe.py` (11/11), real BPCL (adjusted) + TATASTEEL (raw) dev-window cases | done, added 2026-09-29 after validation found the archive is inconsistently adjusted |
| intraday DuckDB schema | `src/fibo/intraday_db.py` | schema only | done, populated by Step 3's real download (43M rows) |
| 1-min -> 15-min / daily aggregation | `src/fibo/bars.py` | `tests/test_fibo_bars.py` (3/3) | done |
| stop/target resolution on 1-min bars | `src/fibo/resolution.py` | `tests/test_fibo_resolution.py` (7/7) | done |
| daily-vs-bhavcopy validation | `src/fibo/validation.py` | `tests/test_fibo_validation.py` (4/4) on synthetic bars | run against real Step 3 data 2026-09-29 -- see Step 3 section |
| `PREREGISTRATION_FIBO.md` | -- | -- | frozen: rules, dev/test split, code seal, revised price-scale method |

## Hand-verification of the daily-side rules (Step 4b), on real data

**Fractal window corrected 2026-09-28, before any intraday data was
fetched**: the user clarified "5-bar fractal each side" meant 5 bars on
EACH side (an 11-bar window), not the standard 2-each-side (5-bar total)
Williams fractal this module originally built. `FRACTAL_WING` changed from
2 to 5 in `src/fibo/indicators.py`; the confirmation lag changed from 2
bars to 5 correspondingly. This is a spec clarification of ambiguous
wording, made before Step 1 ran and before any backtest of any kind --
not tuning. All numbers below are re-verified under the corrected,
wider window.

Run against `data/warehouse.duckdb` for RELIANCE (`INE002A01018`), TCS
(`INE467B01029`), and INFY (`INE009A01021`), late Aug-Sep 2026 (a real
declining stretch for all three, useful because it visibly puts the
Alligator into a bearish fan -- jaw > teeth > lips -- consistent with the
falling price, a sanity check the indicator behaves correctly in both
directions, not just the uptrend case the rule actually trades):

- **Fractals (11-bar window, 5 each side)**: RELIANCE 2026-09-04 up-fractal,
  high 1333.0 vs all 10 neighbors (1291.8/1297.6/1311.8/1321.9/1316.8 before,
  1324.2/1306.8/1294.7/1285.3/1267.4 after) -- strictly the highest, correct.
  TCS 2026-08-27 down-fractal, low 2243.9 vs all 10 neighbors
  (2288.1/2263.3/2279.5/2262.0/2266.4 before, 2263.3/2306.2/2325.0/2303.5/2316.1
  after) -- strictly the lowest, correct. Both examples happen to survive
  the widened window unchanged (they were already significant reversals).
- **ATR/true range**: RELIANCE 2026-08-24 TR = max(H-L=17.6, |H-prevclose|=4.0,
  |L-prevclose|=13.6) = 17.6, matches the printed value exactly.
- **Swing selection, golden zone, 2xATR filter** (`most_recent_confirmed_swing`,
  the exact frozen rule -- most recent confirmed swing high, lowest swing
  low in the 60 trading days before it, now on the 11-bar fractal): as of
  2026-09-18, RELIANCE's swing high is 2026-09-04 (1333.00) and its swing
  low is 2026-07-24 (1249.80) -- numerically unchanged from the narrower
  window, because both points remain significant reversals either way, but
  the candidate pool shrank correctly: only **6** down-fractals now qualify
  in the 60-day window (2026-06-11 1253.2, 2026-06-30 1290.0, 2026-07-08
  1271.6, **2026-07-24 1249.8**, 2026-08-17 1298.1, 2026-08-31 1271.0) --
  down from 8 under the narrower window (2026-07-14 1286.9 and 2026-08-05
  1270.1 no longer qualify as 11-bar fractals). 1249.8 is independently
  confirmed to still be the minimum of the six. Golden zone: range=83.20,
  zone_low = 1333.00 - 0.618*83.20 = 1281.58, zone_high = 1333.00 -
  0.5*83.20 = 1291.40 -- both match the code's output exactly. Filter
  check: 83.20 >= 2 x 21.58 (ATR at the swing high's date) = 43.16,
  correctly passes.

## Dev/test split and code seal (frozen 2026-09-29)

Development 2016-10-04..2022-12-31, test (SEALED) 2023-01-01..2026-09-18,
frozen in `PREREGISTRATION_FIBO.md` Section 5 with the rationale (trade-
frequency uncertainty, 2020 crash coverage in development, the recorded-
not-hidden overlap with the momentum/swing daily-window studies). Sealed
in code, not by convention: `src/fibo/holdout.py`'s `FiboHoldoutViolationError`
mirrors `data_layer.holdout`'s pattern exactly, `tests/test_fibo_holdout.py`
(5/5) exercises it directly.

## Step 3: download and validation

**Download**: `scripts/fibo_download_intraday.py`, full range 2016-10-04
to 2026-09-18, 517 (entity, year) units, **7,071/7,071 chunks succeeded, 0
errors**. Documented Angel One limits confirmed live
(https://smartapi.angelone.in/docs/RateLimit, .../docs/Historical):
getCandleData = 3 req/sec, 150 req/min, 5000 req/hour, no daily cap;
ONE_MINUTE max 30 days/request (this project used 25, with margin). 11
entities excluded (delisted/merged/renamed, no current Angel token --
HDFC, DHFL, JETAIRWAYS, MINDTREE, and 7 others), logged not silently
dropped.

Two real bugs found and fixed live during the run, both recorded in
`src/fibo/download.py` and `scripts/fibo_download_intraday.py`'s own
docstrings so the fix's reasoning isn't lost:
1. A successful nested truncation-retry split returned a non-None
   informational "note" as its second value, and the parent frame's error
   check (`if lerr is not None`) mistook that note for a failure, silently
   discarding good candles. Never corrupted data (resumability just
   retried the wasted chunks) but was wasteful. Fixed; regression test
   added (`test_fetch_chunk_with_retry_nested_split_success_not_mistaken_for_parent_error`).
2. The Angel One session's JWT expired after ~2 hours of continuous use;
   every subsequent request failed identically with "Invalid Token,"
   which the first version of the script treated as an ordinary
   skip-and-continue error (this is DIFFERENT from a rate-limit error --
   the account is fine, the session is just stale). Fixed with automatic
   re-login-and-retry, capped at `MAX_RELOGINS=5` so a genuinely broken
   session still surfaces as a stop.

The background process was also killed twice by the environment itself
(not the API -- confirmed no rate-limit/access-denied text in either log),
handled by simply re-running the fully resumable script.

**Validation** (`scripts/fibo_validate_intraday.py`, 500-pair sample from
the DEVELOPMENT window only, per instruction -- the sealed test window was
never read): surfaced a major finding that revised this module's original
PRICE SCALE assumption. See `PREREGISTRATION_FIBO.md`'s revised PRICE
SCALE section for the full decomposition; headline: **Angel One's
historical intraday data is inconsistently split/bonus-adjusted** -- 82%
of (entity, day) pairs where a later corporate action exists show
intraday prices ALREADY adjusted to today's scale (contradicting the
"intraday is raw" premise `src/fibo/price_scale.py` was built on), while
13% are genuinely raw, with no clean rule found separating the two.

## Price-scale decision (frozen 2026-09-29, before any development backtest)

**Probe the scale PER ENTITY PER DAY** (`src/fibo/scale_probe.py`), not per
entity and not by excluding raw-behaving names -- both alternatives were
considered and explicitly rejected (per-entity assumes time-consistency
the archive has already disproved, most concretely via TATASTEEL changing
behavior from ADJUSTED to RAW between 2022-07-25 and 2022-07-26, two days
before its own real split; exclusion would drop 13-18% of the universe on
a vendor artifact, testing a different universe from the one Step 2
specified). Full mechanism, real-case verification
(`tests/test_fibo_scale_probe.py`, 11/11), and the development-window
report (70,436 pairs: 64.13% RAW, 20.94% ADJUSTED, 14.90% UNRESOLVED,
0.03% EX_DATE_SKIP) are in `PREREGISTRATION_FIBO.md`'s revised PRICE SCALE
section.

**UNRESOLVED exceeded the 2% stop threshold -- investigated, not
smoothed over.** 85%+ of it concentrates in 7 of 81 entities. Root cause
for the largest one (KOTAKBANK) is now known: this project's own
`corporate_actions` table only covers `ex_date >= 2016-01-05`, so
KOTAKBANK's real 2015 ING Vysya Bank merger (a clean, confirmed 5x price
factor) is invisible to this project's own adjustment computation -- a gap
in this project's data, not a flaw in Angel's archive or in the probe.
Excluding those 7 entities, UNRESOLVED falls to 2.52%.

**REVISION, same day, after examining these statistics but BEFORE any
development-backtest result**: decided NOT to backfill pre-2016 corporate
actions (stated for the record: never a warehouse bug -- the daily
warehouse starts 2016-01, after KOTAKBANK's merger, so no daily-side
return in this project is affected; the gap only mattered because the
probe compared Angel's archive against this project's OWN factor table).
Replaced the factor-table-dependent probe with a **direct empirical
measurement**: for entity E on day D, using only D-1's HIGH and LOW in
both sources (`r_high = bhav_high/angel_high`, `r_low = bhav_low/angel_low`
-- HIGH/LOW because they're the same real trade prints in both sources,
unlike CLOSE, which is NSE's own 30-minute volume-weighted auction price
and never exactly matches Angel's last 1-minute print; verified
empirically first: 99.8% agreement within 0.1% on the same 500-pair
sample). If the two ratios agree within 0.1%, `scale(D) = mean(r_high,
r_low)`; otherwise UNRESOLVED. Added a 20%-gap guard (D's converted open
vs. D-1's raw close) for unflagged overnight events. Full mechanism and
the four real verification cases (BPCL, TATASTEEL unchanged; KOTAKBANK
now resolved at an exact 5.0 scale; RELIANCE now resolved at its real
2.0257 scale, not the theoretical 2.0) are in `PREREGISTRATION_FIBO.md`'s
REVISION note.

**New development-window report**: RAW_EQUIVALENT 64.09%, SCALED 35.14%,
**UNRESOLVED 0.74%** (target <2% met), EX_DATE_SKIP 0.03%, GAP_GUARD_SKIP
0.01%. All 7 previously-concentrated entities now resolve at 0.58-0.78%
each -- indistinguishable from baseline, confirming the fix addressed the
actual problem rather than relocating it.

## Step 5: development backtest (run 2026-09-29, DESCRIPTIVE ONLY)

Full engine: `src/fibo/signals.py` (daily uptrend+swing+zone, cross-checked
against `indicators.most_recent_confirmed_swing`), `src/fibo/backtest.py`
(ORB, entry scan, trade construction -- 15/15 tests covering every exit
reason), `scripts/fibo_step5_backtest.py` (orchestration),
`scripts/fibo_step5_nulls.py` (the three benchmarks, 1000 seeds each for
(a)/(b)). 5 real trades hand-traced and checked by hand before any
aggregate was computed.

**Headline, development window (2016-10-04..2022-12-31)**: 67 trades
(120 setup-ON days, 55.8% triggered), 71.6% win rate, mean net R
+0.36 (lo-cost, t=3.22) / +0.27 (hi-cost, t=2.42). **100.0th percentile
vs the SELECTION null** (the Fibonacci+ORB confluence picks genuinely
better days than random selection) but **8.9th percentile vs the TIMING
null** (the specific ORB-breakout entry trigger underperforms a random
entry time on those SAME good days -- a real, descriptive finding about
this version's entry mechanic, not a rule change per Section 5a's
commitment). Full breakdown, by-year table, and the TEST PASS bar applied
informationally (67 trades would be NOT EVALUATED on the trade-count leg;
the other two legs are met) are in `PREREGISTRATION_FIBO.md` Section 6a.

**Per Section 5a: nothing above changes any rule.** Stopped after this
report, per instruction. The sealed test window has not been touched.

## Post-development: null (b2) and universe widening to top-200 (2026-09-29 to 2026-10-01)

**Two issues found after seeing the development report, both addressed
before the test, per `PREREGISTRATION_FIBO.md` Section 6/6a/5a:**

**1. Selection null (b) alone was judged too weak.** Added null (b2):
same SELECTION-null construction as (b), but the candidate pool is
restricted to (entity, day) pairs where that entity's Alligator uptrend
condition already holds -- a harder null, since it removes the "picks an
uptrend day at all" advantage and isolates whether the Fibonacci+ORB
confluence adds anything ON TOP of an uptrend day. `scripts/
fibo_step5_null_b2.py`, 1000 seeds: pool size 20,017 (29.7% of null (b)'s
67,293-pair pool). **Result: 99.9th percentile (gross R), 100.0th
percentile (net R, both cost bounds)** -- the strategy remains a strong
outlier even against this harder benchmark. Added to the TEST PASS bar
(Section 5a) as a required fourth leg alongside (b).

**2. The development trade rate (67 trades / 6.25 years, top-50) implied
only ~40 test-window trades -- short of the 100-trade TEST PASS floor.**
DECISION: widen the universe from top-50 to top-200 by the exact same
point-in-time, trailing-median-turnover method (`src/fibo/universe.py`,
`reconstitute_annually(top_n=200)`), motivation trade-count only, every
other rule unchanged. Safeguard against this being a second look at
performance: the additional names' 1-minute data was downloaded and
checked for DATA QUALITY ONLY on the development window -- no trade, R, or
null computed for them.

**Download** (`scripts/fibo_download_intraday_top200.py`, same chunking/
truncation-retry/rate-limit-stop safety as Step 3): 380 additional
entities (343 with resolvable Angel One tokens, 37 delisted/merged/
renamed and excluded), 21,021 total chunk requests. Took several
relaunch cycles to complete -- the download was interrupted repeatedly by
this environment's own external process kills (unrelated to the API,
confirmed by the absence of any rate-limit text at each stop) and once by
a genuine Angel One rate-limit block that required the user's explicit
go-ahead to retry (recorded, not silently retried); a disk-full crash
partway through (`_duckdb.FatalException`, C: drive down to 50MB free)
was resolved by deleting two superseded warehouse backup files
(`warehouse.duckdb.bak_before_web2_recovery_20260925`,
`...bak_before_isin_fix_20260924`, ~3GB, user-approved) after confirming
no other large, needed files existed in the project. Final result:
**7,087 new chunks fetched, 0 errors, `stop_reason=completed`.**

**Data-quality check** (`scripts/fibo_step5_top200_data_quality.py`,
Section 2a of the preregistration): scale-probe UNRESOLVED rate by
liquidity rank band -- 1-50: 0.57%, 51-100: 0.54%, 101-200: 1.53%, all
within the 2% stop threshold. r_high/r_low agreement stays at median
0.0000% in every band. 10,121 pairs fell outside all bands, verified as
the expected 2016 stub-year download, not a gap.

**Cost-model liquidity check** (`scripts/fibo_step5_cost_liquidity_check.py`,
Section 4 of the preregistration): band 101-200's median turnover is
18.0% of band 1-50's -- the cost model's flat 6.0-19.0bps spread/impact
range was tuned on a different (more liquid, whole-market) population, so
applying it unchanged to band 101-200 is flagged as a likely UNDERSTATEMENT
of true cost there, not a re-measurement. Expected test-window trade
count at top-200, scaled from the top-50 development rate: **~159 trades**
under a flat per-name-rate assumption -- comfortably above the 100-trade
floor, though stated as an upper bound, not a calibrated forecast.

**The sealed test window (2023-01-01 to 2026-09-18) remains untouched.**
Per instruction, stopped here -- the test runs only on the user's explicit
approval.

## THE SEALED TEST (run 2026-10-02) -- FINAL

**Approval was given with one mandatory addition, decided and frozen
BEFORE the read** (`PREREGISTRATION_FIBO.md` Section 5b): report the test
under THREE cost scenarios from the same single trade list -- (i) flat
low, (ii) flat high, (iii) a PESSIMISTIC banded scenario (band 1-50
unchanged, band 51-100 at 2x the flat high-bound spread/impact, band
101-200 at 4x), multipliers justified from turnover ratios and explicitly
stated as a conservative stress test, not a measurement. TEST PASS was
redefined to require all four original criteria (>=100 trades, mean net
R>0 with t>=2, >=95th percentile vs null (b), >=95th percentile vs null
(b2)) to hold under ALL THREE scenarios simultaneously, with null draws
re-costed under the same pessimistic assumption for a fair comparison --
anything less is NO EDGE. The reasoning given for requiring this: the
strategy risks a fixed Rs 500/trade, so positions are small and spread
cost dominates, and the newly-added band 101-200 (needed to reach the
100-trade floor) has only 18% of band 1-50's turnover against a cost model
tuned on a more liquid population -- an understated cost there could
manufacture a pass that would not survive a realistic one.

**New scripts, built for this one read only**: `scripts/fibo_test_backtest.py`
(mirrors `fibo_step5_backtest.py` exactly, pointed at the sealed window with
`authorize_holdout=True`, top-200 universe, plus rank-band tagging and the
pessimistic-cost column), `scripts/fibo_test_nulls.py` (mirrors
`fibo_step5_nulls.py`, TIMING/SELECTION(b)/SELECTION(b2) all computed fresh
on the test window's own data per Section 5a, each null draw also re-costed
under all three scenarios using its own entity's rank band), `scripts/
fibo_test_report.py` (assembles the Section 5b pass/fail table).

**Real engineering problem hit live**: this environment killed the nulls
process externally dozens of times in a row during this run -- far more
frequently than Step 3's download ever experienced, sometimes within a
single minute. The nulls script originally had no checkpointing (only the
download scripts did), so the first several kills each cost the entire
in-progress null type's seeds. Fixed by adding a `CHECKPOINT_EVERY`-seed
save to `scripts/fibo_test_nulls.py` (pickled per-null-type results list,
atomic-swap write), tightened from 50 to 10 seeds once kills kept arriving
faster than a 50-seed checkpoint could complete. With that in place the
computation survived ~15 relaunches to finish all 3000 seeds (1000 each
for TIMING, (b), (b2)) without losing more than 10 seeds' work to any one
kill. No trade, no rule, and no already-computed seed's result was ever
touched or redone by this process -- purely infrastructure resilience, not
a second analytical pass.

**RESULT -- 188 trades** (comfortably above the 100-trade floor,
confirming the universe widening worked). Exit reasons: TIME_EXIT 78.2%,
TARGET 15.4%, STOP 6.4% (consistent with development). All 4 years
individually gross-positive. TIMING null: strategy at the 2.3rd percentile
(net), consistent with and slightly sharper than development's 8.9th --
the entry trigger itself still looks like a weak spot, unchanged
conclusion, not acted on.

**By rank band, the mechanism Section 5b was built to catch, exactly as
anticipated**: band 101-200 (109 of 188 trades, 58%) has mean net R
**-0.1021 under the pessimistic scenario** -- a net loser -- while bands
1-50 and 51-100 stay solidly profitable even under their own (1x/2x)
pessimistic multipliers. The thin, newly-added names are exactly where the
cost assumption breaks the result.

**TEST PASS TABLE**:
| scenario | mean net R | t | vs (b) | vs (b2) | verdict |
|---|---|---|---|---|---|
| flat low | +0.3615 | 5.947 | 100.0th | 100.0th | PASS |
| flat high | +0.2745 | 4.569 | 100.0th | 100.0th | PASS |
| pessimistic banded | +0.0392 | 0.645 | 100.0th | 100.0th | **FAIL** |

The confluence beats both selection nulls at the 100th percentile in
EVERY scenario including the harshest -- criteria 3/4 are not in question.
What fails is criterion 2 alone, only under the pessimistic scenario:
mean net R collapses to statistical noise (t=0.645) once band 101-200's
cost is stress-tested at 4x.

**FINAL VERDICT: NO EDGE for these rules**, per the frozen
all-four-criteria/all-three-scenarios bar. Not a partial pass. This is NOT
evidence that a liquidity-aware or band-101-200-excluded version would
fail the same way -- it is evidence that THIS fully mechanical,
fixed-risk, liquidity-blind rule set does not clear a conservative cost
bar once it trades thin enough names to reach 100+ trades. No rule was
changed to investigate or soften this finding. The sealed test was read
exactly once.
