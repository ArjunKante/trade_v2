# Corwin-Schultz / Roll spread-estimator validation for NSE equities

**This is not a trading study. It is a measurement study about a
method.** It does not propose, test, or evaluate any trading strategy,
entry rule, or portfolio construction. It asks one question: on NSE
equities, how well do two widely-used high-low/close-only spread
estimators (Corwin-Schultz 2012, Roll 1984) track the ACTUAL quoted
spread, and does any discrepancy track a specific, pre-stated mechanism
or something else. New family, new module (`src/spread_validation/`),
first trial.

## THE FINDING THIS BUILDS ON -- and where it actually lives

**Stated precisely, because every mention of this finding inside this
project so far is a citation, not an original result**: in September
2026, the sibling `trade-info` project (`C:/projects/trade-info/`, a
separate repository on this machine, not a subdirectory or submodule of
this one) measured live bid-ask spreads on Groww market depth for 5 NSE
names (2 readings each, 2026-09-15, 14:20 and 14:40 IST) and compared
them against Corwin-Schultz estimates computed from the same stocks'
daily high-low data (`trade-info/ops/report_capacity_slippage_
groundtruth.py`, `trade-info/FINDINGS.md` Section 7).

**The real result, exactly**:

| symbol | observed spread (bps, mean of 2 readings) | CS estimate (bps) | CS/observed ratio |
|---|---|---|---|
| INTELLECT | 4.50 | 100.2 | 22.27x |
| DEEPAKFERT | 4.25 | 82.7 | 19.46x |
| FSL | 2.65 | 82.9 | 31.28x |
| KNRCON | 5.74 | 68.5 | 11.93x |
| LOTUSDEV (BE/T2T) | 87.80 | 87.6 | 0.9977x ~ 1.0x |

CS overstated the observed spread by **12-31x, mean ~21x**, on the 4
normally-traded EQ names; it was accurate (0.9977x) on the one BE/T2T
name in the sample (LOTUSDEV). **This project's own files
(`NEW_RESEARCH_DIRECTION.md`, `OPERATIONS.md`, `scripts/run_momentum_
backtest.py`, `FIBO_FINDINGS.md`) all cite this same `trade-info`
result -- none of them re-derive it, and this document does not either.**
Do not write or repeat "5 NSE names, 12-31x" as if it were native to
`trade-new` -- it is an import, correctly cited, from a different
project's own single-session measurement.

**Proposed explanation, stated at the time, not re-derived here**:
Corwin-Schultz and Roll both assume the daily high and low bracket a
pure bid-ask bounce around an unchanging efficient price -- no
within-day netting by a market maker. On continuously (EQ) traded
names, a market maker absorbs intraday order flow, so the realized
high-low range reflects genuine price VOLATILITY, not the bid-ask
spread the estimator is trying to measure -- overstating it. On
trade-to-trade (T2T/BE) names, every trade settles individually with no
intraday netting, so the no-netting assumption the estimator was built
on actually holds, and it is accurate.

**That was 5 stocks, one session, one proposed mechanism. It is
suggestive, not established.** This study exists to test it properly:
a larger, stratified sample, multiple sessions, and an analysis
design specified BEFORE any new data exists, built specifically to be
able to say whether the EQ/T2T split is really what is driving the gap,
or whether something else (liquidity, price level, volatility) explains
more of it.

## TONIGHT'S SCOPE: SPECIFICATION ONLY

Markets are closed. **No live data is collected tonight.** Everything
built tonight is either (a) pure specification (this document) or (b)
code and queries that touch only the warehouse's own already-recorded
historical data (`prices_eod`, `isin_lineage`, `adjustment_factors`) to
CHOOSE which names to monitor later -- never a call to Angel One, never
a live quote. The user starts the actual collection during market
hours, separately, after this document and the sample are committed.

## Section 0: reuse boundaries, read-only

- `src/spread_monitor/` (`tokens.py::resolve_tokens`, `quotes.py::
  parse_full_quote_row`/`compute_spread`/`compute_move_pct`,
  `market_hours.py::check_market_hours`, `trading_day.py::
  verify_trading_day`, `writer.py::append_rows`, `config.py::
  load_symbols`) -- **reused entirely unchanged. No second collection
  path is built.** `scripts/snapshot_spreads.py`'s own existing call
  chain (`check_market_hours` -> `load_symbols` -> `resolve_tokens` ->
  `login` -> one `getMarketData("FULL", ...)` call -> `verify_trading_day`
  -> `parse_full_quote_row` per name -> `append_rows`) is exactly what
  this study's own collection runs -- pointed at this study's own symbol
  list (`config/spread_validation_symbols.txt`, Section 2 below) via
  `load_symbols`'s own existing `path` parameter, not a hardcoded
  default. `config/spread_monitor_symbols.txt` (the FIBO cost-model
  monitor's own 20-symbol list) is untouched; this study writes to a
  separate output path (Section 3) so the two monitors' own records
  never mix.
- `fibo.universe.reconstitute_annually` -- the current point-in-time
  top-200-by-turnover universe, unchanged, same canonical source every
  other point-in-time study in this project uses.
- `factors.lowvol.compute_trailing_vol` -- unchanged, the one existing
  cross-sectional volatility definition in this project, reused rather
  than inventing a second one for this study alone.
- `scripts/run_lowliq_cost_calibration_diagnostic.py`'s own
  `corwin_schultz` function -- copied, not re-derived, into `src/
  spread_validation/estimators.py` (that script has no shared module to
  import from; a unit test confirms the copy is byte-for-byte identical
  to the original on synthetic input, so the two can never silently
  drift).

**New code**: `roll_1984` (`src/spread_validation/estimators.py`) does
not exist anywhere in `trade-new` before this study -- ported from the
sibling `trade-info` project's own corrected implementation (`ops/
report_capacity_slippage.py`'s `roll_1984_annual`, itself a fix for that
project's own Bug #8, where an earlier version silently treated Roll's
undefined case as a zero spread inside a `.median()`). This port
preserves the fix: it returns `(spread, was_defined)`, never silently
substitutes a number for an undefined estimate. `src/spread_validation/
sampling.py` (Section 2) is new -- no prior script in this project has
built a stratified live-monitoring sample.

**Not reused, deliberately**: `data_layer.entity_panel`/
`entity_prices_daily` (the pre-holdout-truncated table most factor code
in this project reads) is NOT used anywhere in this study. There is no
holdout concern in selecting which stocks to monitor live -- `FINDINGS.
md` Section 7's retirement is specifically about the momentum factor's
own sealed-test evaluation window, and using a table frozen at
2025-03-18 to choose a sample for TODAY'S live market would be actively
wrong, not merely over-cautious. `src/spread_validation/sampling.py`
reads `prices_eod` directly through the warehouse's own latest date.

## Section 1: sample -- the exact rule, and the resulting list

**Stratified across four dimensions, not just more of the same names**,
per instruction. 24 names total (18 EQ + 6 BE), chosen tonight by
`scripts/build_spread_validation_sample.py` against the real warehouse
(no live data) and written to `config/spread_validation_symbols.txt`.

**Liquidity (EQ names only)**: the current point-in-time top-200
universe (`reconstitute_annually`, year 2026, ranked off calendar-year
2025's own median daily turnover), banded `rank<=50` -> "1-50",
`rank<=100` -> "51-100", else "101-200". **6 names per band, 18 EQ
total** (the required minimum, exactly).

**Series**: EQ (above) vs. BE (trade-to-trade). **6 BE names**, selected
from the ACTIVELY TRADING BE population (>=20 distinct BE-series trading
days in the trailing ~95 calendar days -- 308 symbols clear this bar,
confirmed by direct query before writing this document; T2T names are
not scarce, this requirement was never close to binding), spread across
that population's OWN median-turnover distribution at evenly-spaced
percentiles (5th, 24th, 43th, 62nd, 81st, 95th-ish, exact indices
rounded to the nearest available rank) -- not the 6 MOST liquid T2T
names, which would misrepresent the T2T population's own typical
liquidity.

**Price level AND volatility, within each EQ band**: rather than bolting
price/vol extremes on as an afterthought, each band's own 6 slots are
filled by one deterministic rule that guarantees both are represented:
rank the band's own eligible members by trailing-252-day annualized
volatility (`factors.lowvol.compute_trailing_vol`, latest available
value); take the **2 highest-vol** and **2 lowest-vol** names; from
whatever remains in the band, take the **highest-price** and
**lowest-price** name not already selected. This guarantees every band
contributes both a volatility spread and a price-level spread, rather
than leaving either to chance from a vol-only or price-only sort.

**The resulting list** (symbol, band/series, rank, close price, trailing
annualized vol, reason selected):

| Symbol | Band | Rank | Close (Rs) | Vol (ann.) | Reason |
|---|---|---|---|---|---|
| KOTAKBANK | 1-50 | 16 | 440.75 | 163.7% | high_vol |
| MCX | 1-50 | 40 | 3111.80 | 164.8% | high_vol |
| SUNPHARMA | 1-50 | 37 | 1740.00 | 19.3% | low_vol |
| NTPC | 1-50 | 44 | 300.00 | 19.3% | low_vol |
| MARUTI | 1-50 | 24 | 11220.00 | 23.9% | price_extreme (high) |
| IDEA | 1-50 | 28 | 11.95 | 44.5% | price_extreme (low) |
| ANGELONE | 51-100 | 71 | 282.60 | 234.9% | high_vol |
| POLICYBZR | 51-100 | 74 | 1023.00 | 57.7% | high_vol |
| APOLLOHOSP | 51-100 | 64 | 7844.00 | 20.5% | low_vol |
| LUPIN | 51-100 | 99 | 1959.90 | 19.6% | low_vol |
| ULTRACEMCO | 51-100 | 52 | 11180.00 | 23.5% | price_extreme (high) |
| CANBK | 51-100 | 56 | 116.71 | 29.2% | price_extreme (low, within-band) |
| APOLLO | 101-200 | 192 | 410.90 | 54.9% | high_vol |
| HINDCOPPER | 101-200 | 139 | 407.55 | 53.2% | high_vol |
| BRITANNIA | 101-200 | 119 | 4580.00 | 19.9% | low_vol |
| MARICO | 101-200 | 150 | 775.15 | 18.6% | low_vol |
| POWERINDIA | 101-200 | 102 | 26850.00 | 44.1% | price_extreme (high) |
| YESBANK | 101-200 | 106 | 15.86 | 32.3% | price_extreme (low) |
| BNALTD | T2T/BE | -- | 360.05 | -- | BE turnover percentile |
| ALKALI | T2T/BE | -- | 77.63 | -- | BE turnover percentile |
| SUPTANERY | T2T/BE | -- | 7.28 | -- | BE turnover percentile |
| KALYANIFRG | T2T/BE | -- | 756.15 | -- | BE turnover percentile |
| AARTISURF | T2T/BE | -- | 453.45 | -- | BE turnover percentile |
| BIRLACABLE | T2T/BE | -- | 376.55 | -- | BE turnover percentile |

Price spans Rs 7.28 (SUPTANERY) to Rs 26,850 (POWERINDIA) across the
full sample. Volatility spans 18.6% to 234.9% annualized among the EQ
names. `config/spread_validation_symbols.txt` carries this same list
with every entity's own selection reason recorded inline, so the sample
is independently reconstructable from the file alone.

**Token budget**: 24 symbols + 1 (Nifty 50 index, `NIFTY_50_INDEX_
TOKEN`) = 25 of the confirmed 50-token-per-`getMarketData`-call hard
limit (`AB4029` at 51+, `OPERATIONS.md`) -- 25 tokens of headroom,
deliberately kept well clear of the limit rather than run close to it.
One `getMarketData` call per snapshot, no chunking needed.

## Section 2: measurement protocol

- **Reuses `src/spread_monitor/` entirely** (Section 0) -- the existing
  `getMarketData` FULL path, pointed at `config/spread_validation_
  symbols.txt` instead of the FIBO monitor's own list, writing to its
  OWN output path (`data/spread_logs/spread_validation_log.csv`, a
  distinct file from `data/spread_logs/spread_log.csv` -- both write
  through the same `writer.append_rows`, parameterized by path, never
  mixed in one file).
- **At least 3 snapshots per trading day, at fixed times away from the
  open and close, across at least 10 trading days.** `market_hours.
  check_market_hours`'s own existing open/close guard (refuses the
  first/last 15 minutes, 09:15-09:30 and 15:15-15:30) already enforces
  "away from the open and close" structurally -- this study's own
  schedule picks three FIXED times inside the remaining window (e.g.
  11:00, 12:45, 14:30 IST, spread across the mid-session rather than
  clustered), run on at least 10 distinct trading days. Run timing
  itself is the user's own responsibility ("I will start the collection
  during market hours") -- not built or scheduled by this specification.
- **Recorded per snapshot, per name** (already exactly `QuoteRow`'s own
  schema, Section 0 -- no new fields needed for the LIVE side): timestamp
  (IST), best bid, best ask, quantities at best, LTP. **That day's
  eventual high/low/open/close** is NOT part of `QuoteRow` -- it is
  joined in afterward, at analysis time, from the same day's own
  `prices_eod` row once the trading day has closed and the bhavcopy is
  available (never from an incomplete, still-forming day's own
  intraday high/low).
- **The measured quantity is the QUOTED spread -- best-ask minus
  best-bid at one instant, exactly what `quotes.compute_spread` already
  computes.** Stated explicitly, per instruction, because the three are
  genuinely different things and this study measures only the first:
  - **Quoted spread** (this study): the gap between the best resting
    bid and ask at a point in time -- what a marketable limit order
    would face if it crossed the book right now.
  - **Effective spread**: 2x the distance between an ACTUAL executed
    trade's own price and the quote midpoint at the time of execution --
    reflects real order flow and any price improvement, not measured
    here (this study never places an order).
  - **Realized spread**: the effective spread adjusted for subsequent
    price movement after the trade (a proxy for the market maker's own
    realized profit, net of adverse selection) -- also not measured
    here.
  Corwin-Schultz and Roll are themselves attempts to RECOVER something
  closer to the quoted/effective spread from price data alone, so
  comparing them against a DIRECTLY measured quoted spread is the
  correct, like-for-like comparison this study can actually make -- it
  says nothing about effective or realized spreads.

## Section 3: estimator computation

- **Corwin-Schultz**, exactly as Corwin & Schultz (2012) specify, and
  exactly as this project's own existing validated implementation
  computes it (`src/spread_validation/estimators.py::corwin_schultz`,
  copied from `scripts/run_lowliq_cost_calibration_diagnostic.py`,
  confirmed byte-identical by unit test): the two-day overlapping-window
  construction --
  `beta[t] = log(H[t]/L[t])^2 + log(H[t-1]/L[t-1])^2`,
  `gamma[t] = log(max(H[t],H[t-1]) / min(L[t],L[t-1]))^2`,
  `k = 3 - 2*sqrt(2)`,
  `alpha[t] = (sqrt(2*beta[t]) - sqrt(beta[t]))/k - sqrt(gamma[t]/k)`,
  `S[t] = 2*(exp(alpha[t])-1) / (1+exp(alpha[t]))`
  -- with the original paper's own negative-value handling: a negative
  `S[t]` (the known small-sample artifact, from a day pair where the
  two-day range is unusually narrow relative to either single day's own
  range) is floored to zero for that day, never left negative or
  dropped.
- **Roll's (1984) covariance estimator**, `S = 2*sqrt(-Cov(dP_t,
  dP_{t-1}))`, computed on daily log-return first differences -- **new
  code** (`estimators.py::roll_1984`, Section 0), since no implementation
  existed in this project before this study. **How often it is
  undefined is reported explicitly, per instruction, not hidden**: Roll
  is structurally undefined whenever the first-order autocovariance is
  non-negative (economically inconsistent with the model's own pure-
  bid-ask-bounce assumption -- a trending, not mean-reverting, return
  series). `roll_1984` returns `(spread, was_defined)`; the analysis
  (Section 4) reports the fraction of name-days where Roll is undefined,
  broken down by the same strata as the main analysis, and excludes
  undefined observations from any mean/median rather than silently
  coding them as zero -- the exact mistake `trade-info`'s own Bug #8
  made and this port exists specifically not to repeat.
- **Computed on the SAME days the live quotes were captured** -- for
  each (name, day) with at least one live snapshot, Corwin-Schultz and
  Roll are both computed using that day and however many PRIOR trading
  days each estimator's own construction needs (2 days for CS's own
  overlapping window ending on that day; a trailing window, length
  specified before any data exists -- 20 trading days, matching `roll_
  1984`'s own `min_obs` default and standard practice for the Roll
  estimator) ending on that same day, from `prices_eod`'s own daily
  high/low/close. Contemporaneous, not averaged across some other
  period and compared to a different day's own live reading.

## Section 4: analysis plan -- specified now, before any data exists

- **Primary quantity**: `ratio = estimated_spread / observed_spread`,
  per (name, day) -- one ratio per name per trading day with both a live
  reading and a computable estimator value, for CS and for Roll
  separately (Roll's own ratio computed only where `was_defined=True`).
- **Broken down by liquidity band, series (EQ/BE), price level
  (continuous, plus a simple above/below-median split), and volatility
  (continuous, plus a simple above/below-median split)** -- the question
  is not only "is CS wrong," which the September finding already
  suggested, but **"is it wrong in a way that tracks the proposed
  mechanism specifically, or in a way that tracks something else."**
  Reported as both a summary table (mean/median ratio per stratum) and
  the full per-name-per-day scatter, so a reader can see the spread
  within each stratum, not just its center.
- **Whether EQ-vs-T2T is the DOMINANT explanatory factor**, tested
  directly, not asserted: a simple decomposition (e.g. how much of the
  total variance in `log(ratio)` across the sample is explained by the
  series dummy alone, vs. by liquidity band alone, vs. by price level
  alone, vs. by volatility alone, and vs. all four together) -- reported
  plainly, in whichever direction it comes out.
- **What would REFUTE the proposed mechanism, stated now, not decided
  after seeing the result**:
  - If the T2T (BE) names ALSO show large overstatement (ratio
    materially above 1.0x, comparable in magnitude to the EQ names),
    the intraday-netting explanation is wrong -- T2T's own lack of
    netting was the entire proposed reason CS/Roll should be accurate
    there.
  - If the ratio tracks PRICE LEVEL more strongly than series type
    (e.g. low-priced names show large overstatement regardless of
    EQ/BE, or high-priced names show it regardless of series), the
    mechanism is more likely tick-size-driven (a coarse tick relative to
    price inflating the apparent high-low range) than netting-driven,
    and the September finding's own proposed explanation does not hold
    as stated.
  - If liquidity band (independent of series) is the dominant factor,
    the mechanism is more likely a general liquidity story than the
    specific EQ-netting-vs-T2T-no-netting story proposed in September.

## Section 5: limitations, stated up front

- **One broker's depth feed (Groww via Angel One's own `getMarketData`
  API), one country (NSE), one measurement period.** Generalization to
  other venues, other brokers' own order books, or other periods is not
  claimed.
- **Quoted spreads only** (Section 2) -- not effective, not realized.
  A finding here about quoted-spread accuracy says nothing directly
  about transaction-cost accuracy for an actual executed trade, which
  depends on effective/realized spread, not quoted spread alone.
- **Corwin-Schultz and Roll are designed for use where NO quote data
  exists at all** -- typically historical periods, or markets without a
  continuously recorded limit order book. **Demonstrating they fail
  where quotes ARE available does not establish how they behaved, or
  would have behaved, historically**, when they were the only tool
  available. A large discrepancy measured in 2026 is not direct evidence
  about their accuracy in, say, 2016-2020 NSE data, where no live quote
  ground truth exists to check against at all -- it is evidence about
  their accuracy NOW, under conditions where a better measurement was
  available and chosen instead.
- **This is a measurement study, not a causal one.** Section 4's
  variance decomposition identifies which factors the discrepancy
  TRACKS, not which factor CAUSES it -- liquidity, series, price, and
  volatility are correlated with each other in this universe (a T2T
  name is almost always also low-liquidity, for instance), and this
  study's own stratified design reduces but does not eliminate that
  confounding. A factor explaining most of the variance is evidence
  toward, not proof of, the mechanism it is associated with.

## Section 6: why this might matter -- motivation, not an established claim

Corwin-Schultz and Roll are used widely in academic and practitioner
research wherever intraday quote data is unavailable, including a
substantial share of emerging-market microstructure and transaction-cost
research on markets like India's, where continuous historical quote
archives are far less available than in the US. **If these estimators
are systematically wrong on Indian equities by an order of magnitude --
which the September finding suggests but does not establish -- work
relying on them for NSE cost estimates, including this project's own
prior cost-model work (`PREREGISTRATION.md`'s own low-liquidity tercile
figure, `scripts/run_lowliq_cost_sensitivity.py`), would be affected.**
Stated here as the reason this study is worth running, not as a
conclusion already reached -- the September finding is one session on
five names, and this study exists specifically to find out whether it
generalizes.

## Section 7: process

1. Write this document and build the stratified sample (`scripts/
   build_spread_validation_sample.py`, read-only, no live data).
   Commit and push tonight. Report the hash.
2. The user starts live collection during market hours, separately, via
   `scripts/snapshot_spreads.py` pointed at `config/spread_validation_
   symbols.txt` (or a thin wrapper of the same call chain -- Section 0 --
   not a new collection path).
3. Once at least 10 trading days of collection exist, run the Section 3
   estimator computation and the Section 4 analysis, reported in full,
   including whatever strata turn out NOT to support the proposed
   mechanism, per the refutation criteria stated in Section 4 -- not
   just the strata that do.

## Section 8: discipline

The sample (Section 1), the measurement protocol (Section 2), the
estimator construction (Section 3), and the analysis plan including its
own refutation criteria (Section 4) are all fixed now, before any new
data exists. If the result is ambiguous or null, this exact sample and
protocol are not silently re-run with different stocks or different
snapshot times to find a cleaner signal -- a materially different design
would be a new, separately specified trial of this same measurement
question, not a quiet adjustment of this one.

## Status

Specification complete. Sample built and written to `config/spread_
validation_symbols.txt` (read-only against the warehouse; no live data
collected). Next: commit, report the hash, and wait for the user to
start live collection during market hours.
