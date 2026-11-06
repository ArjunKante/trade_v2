# PROJECT CONTEXT

**Purpose:** bring a cold session up to speed on what this project is, what has
been tested, what was found, and the rules that govern how work is done here.
Written 2026-11-06.

**This is a living cross-session document, meant to be appended to over time —
unlike a preregistration or a per-study findings record, which this project's
own rule annotates rather than edits once closed.** §7's numbering originates
in this document: findings #1-12 were written here today (2026-11-06) from
the conversation record, and no earlier numbered ledger of transferable
findings exists anywhere in this project or its predecessor. §7 numbering is
append-only from this point forward — never renumbered, never reused, even
for a finding later retracted (a retracted finding keeps its number and gains
a RETRACTED annotation instead).

Read this before proposing any new study.

---

## 1. WHAT THIS PROJECT IS

A systematic research programme on NSE equities, run by one person with Claude
Code, starting late September 2026. The question was whether any tradeable edge
could be found and validated honestly.

**What has been tested is enumerated in §5, not totalled here.** The unit
of account differs by family — Liquidity counts lettered trials, POC counts
sequential revisions under one heading, Swing counts variants within a
single multi-arm test, Per-stock counts (stock, rule) combinations under
one correction, others count one heading each — and no single running
total survives mixing those units honestly. §3's trial-count table states
each family's own count and correction separately, which is the form this
fact actually has. **One strategy passed a clean sealed test. One passes
under heavy caveats. Everything else enumerated in §5 is closed.**

The project's real output is not a strategy. It is a method for distinguishing
a real result from a convincing one, and a long record of ideas that looked
convincing and were not.

### Repositories

- **trade-info** — the original ML project. Closed. NO EDGE.
- **trade-new** (github.com/ArjunKante/trade_v2) — everything since.

### Data

- Point-in-time NSE daily prices, 2016-01 onward, with entity resolution
  through ISIN changes, corporate actions and split adjustment
- 1-minute intraday bars, 2016-10-04 onward (Angel One's archive floor),
  top-200 universe
- Fundamentals from XBRL filings (balance-sheet data only reaches FY2022-23)
- NIFTY options EOD, 2016-2026, 5.6M rows
- IPO listing-day 1-minute bars, 498 usable mainboard listings

### Infrastructure

- Fundamental screener web app (47 surviving names from 147 momentum candidates)
- Momentum persistence monitor (descriptive only, asserts nothing)
- Streamlit research browser for inspecting closed studies' trades on charts
- Fibo forward paper-trading system (GitHub Actions + cron-job.org +
  healthchecks.io)
- Live options depth collector
- Spread measurement tooling

---

## 2. CURRENT LIVE STATE

| Thing | Status |
|---|---|
| Momentum basket | Recorded 2026-10-26, 147 holdings, check-in ~2027-01-27 (calendar-uncertain, 2027 holiday master not loaded) |
| Fibo forward test | Running. Morning job on GitHub Actions, triggered by cron-job.org, monitored by healthchecks.io. Evening job on the laptop at 18:30, manual if missed. |
| Options depth collector | Scheduled on the laptop, 10:30/12:30/14:30 |
| Spread estimator validation | Specified, 24 names selected, awaiting market-hours collection |
| Historical holdout | **RETIRED.** No sealed window remains for any equity study except IPO listing's unread 199 trades. |
| Liquidity family | **CLOSED, 2026-11-07.** 4 DEV failures, 2 Phase 1 abandonments, 1 withdrawn measurement. No Study G. See `LIQUIDITY_FAMILY_CLOSED.md`, §10. |

### Known operational constraints

- Evening job requires the laptop on and logged in at 18:30. Running it late is
  fine and actually safer for bhavcopy availability.
- Angel One: ~3 requests/second on candles, undocumented daily quota, 50
  instruments per quote call (error AB4029 above that).
- Long unattended runs get killed by the environment frequently. Everything
  must checkpoint mid-stage.
- Task Scheduler Operational log is disabled; enable it before any future
  scheduler change.

---

## 3. THE METHOD

This matters more than any individual result. It evolved in response to
specific failures.

### Pre-registration

Every study has a frozen document written and **committed alone** before any
result exists. The commit timestamp is the evidence that the design preceded
the number. It specifies: rules, universe, costs, windows, nulls, gate
conditions, and a verdict rule.

### Gates

A study passes only if **all** conditions hold. Typically:
- mean return > 0 with a day-clustered bootstrap CI excluding zero
- ≥95th percentile against both nulls
- still positive after dropping the best calendar year
- positive within the liquid bands alone

If the first condition fails decisively, the run is killed — the nulls cannot
rescue it.

### Nulls

Two comparisons, both essential:
- **TIMING null** — same stock-days, random entry time. Tests whether the
  entry trigger adds anything.
- **SELECTION null** — random stock-days from the same universe. Tests whether
  the day selection adds anything.

Several studies passed both nulls at the 100th percentile and still lost money.
Beating random is necessary, not sufficient.

### Sealed windows

Read once, after DEV passes and the human approves. A DEV failure closes the
study automatically — no human decision needed, which is what stops a failed
study being talked back to life.

### Trial counting

Every revision of a failed idea increments a family's trial count and is
recorded as carrying selection pressure. Multiple configurations in one study
require Bonferroni correction.

**Trial, defined**: any configuration that reached a pre-registered gate OR
was killed at a Phase 1 feasibility check. Both carry selection pressure. A
configuration blocked before either (never run, no gate reached, not
Phase-1-killed — e.g. Swing's own V5/V6, blocked by Bug #12) is not a trial
under this definition.

**Per-family trial count, derived from the committed preregistrations and
findings files, not from §5's own prose** (2026-11-07):

| Family | Trials run | Outcomes | Bonferroni denominator (as committed) |
|---|---|---|---|
| Swing | 6 (V1, V2, V3, V4, V7, V8 — `PREREGISTRATION_SWING_V1.md` §0; V5/V6 never run, not counted) | V1 passed DEV (100th pctile) then **failed** the sealed holdout (61.4th); V8 also cleared DEV (100th pctile) but was never taken to holdout; V2/V3/V4/V7 failed DEV | 6, explicit (`Bonferroni (α/6)`) |
| Box theory | 4 (V1-FAST, V1-SLOW, V2-FAST, V2-SLOW) | all 4 failed | 2 per generation (V1's FAST/SLOW pair, then V2's FAST/SLOW pair separately — `PREREGISTRATION_BOX_V2.md`: "no further Bonferroni adjustment beyond this") |
| FVG | 2 (A, B) | both failed | 2, explicit |
| POC | 5 (V1-V5, sequential) | 5 failed (V4 passed both nulls, still failed its own gate on cost) | **Stale as committed**: the gate's own CI machinery stayed "Bonferroni-built for 2" through V2-V5 even as the family's trial count reached 5 — each of V3/V4/V5's own preregistration explicitly flags this as a growing, unresolved gap (V4's own section title: "the Bonferroni caveat is now WORSE, stated again") |
| Liquidity | 6 (A-F) | 4 DEV failures (A, B, C, D — all passing both nulls at the 100th percentile); 2 Phase 1 abandonments (E, F) | Not one family-wide number: A+B share one Bonferroni-2; C's own denominator is not stated explicitly in its committed text (UNVERIFIED); D states Bonferroni-4 explicitly; E's and F's "4"/"2 configurations" appear in their committed findings docs only as runtime-estimate context, never as a stated gate threshold (UNVERIFIED as committed, despite being proposed with that framing in chat before each was abandoned) |
| Per-stock weekly | 42 (21 stocks × 2 rules, actually run — `PER_STOCK.md` §4: preregistered for 50×2=100, only 42 actually run) | 0 survivors | 42, explicit ("across ALL trials actually run") |
| Momentum (63-day) | 2 (Study 1; Study 2, large-cap replication) | Study 1 passed its sealed holdout; Study 2 ran CV-only, no holdout spent | UNVERIFIED for this pair specifically — no numbered correction found in `FINDINGS.md` for Studies 1/2 themselves (a *different* study, the momentum+fundamentals combination, states "m=8" for its own nine-factor screen — not reused here) |
| Fibo | 1 | Passed, after two corrections to the same trial (cost model, then a price-scale bug) — one authorized sealed-test read, not three trials | None found or stated — single trial, no multi-config split |

**Disagreements found between this table and §5's own prose, reported, not
reconciled here**: §5 names only two of Swing's six run variants (V1, V4)
and does not mention that V8 also cleared both corrections. §5's POC rows
do not mention the Bonferroni-denominator staleness documented in POC's own
V3-V5 preregistrations. Liquidity E's and F's Bonferroni figures, stated
elsewhere (including by Claude, in chat) as settled design parameters, are
not actually present in either study's own committed closure document.

### Hand-tracing

Five trades traced by hand against raw data before any aggregate is computed,
covering the awkward cases (gap-through stop, same-bar tie, each skip reason).
This has caught real bugs repeatedly.

### Blast-radius measurement

When a bug is found, measure what it affected **before** fixing it, and
**in both directions**. Bug #18's first measurement only asked which selected
trades would be rejected; the full correction showed it had also wrongly
rejected trades, and the second effect was 6x larger.

### Feasibility and power checks first

Three studies were closed before running on cheap pre-checks:
- **Portfolio construction** — the minimum detectable difference was 45-75
  percentage points of annual return. No plausible effect is that large.
- **Liquidity E** — the design was confounded (see §7 finding #8).
- **Liquidity F** — the design was unidentifiable, not merely confounded
  (see §7 finding #13).

All three saved days (Liquidity F: an estimated ~37 hours) of compute on
questions that could not have been answered.

### Recording

Failures are recorded as prominently as successes. Wrong predictions are
recorded as wrong. Superseded documents are annotated, never edited. Logs are
append-only; corrections are new rows.

---

## 4. WHAT WORKED

### 63-day momentum — the only clean pass

Buy the top decile by `momentum_12_1` (12-month return skipping the most
recent month), hold 63 trading days, equal weight, long only.

**Sealed holdout: 14.72% vs 10.85% CAGR, +3.87 points, all three
pre-registered conditions passed.** Large-cap replication +6.56 points (CV
only).

Verified against the Bug #11 same-ISIN exclusion: margin moved 3.87 → 3.64,
still clearing the 3.0 threshold. Max drawdown actually *worsened* when those
entities were excluded, which argues against them flattering the result.

**Never run live until 2026-10-26.** One basket now recorded with a January
check-in.

### Fibonacci/ORB intraday — passes with four caveats

Daily Alligator uptrend + 50-61.8% golden zone + opening range overlap, entry
on a 15-minute close above the opening-range high, stop at the opening-range
low, target min(2R, swing high), exit 15:15.

| Section | Result |
|---|---|
| 6b | Original sealed test: **NO EDGE** |
| 9 | After cost correction: **PASS** |
| 13 | After scale correction: **PASS**, +0.2679, t=4.661, 100th percentile both nulls, 216 trades |

**The four caveats, which must appear wherever the figure appears:**
1. The window was read three times
2. The cost correction was made after seeing a failure
3. The cost model rests on 5 snapshots across 3 days in October 2026
4. The trade list itself was wrong in both directions until Bug #18 was fixed

This is the most-corrected result in the project. A pass earned through three
amendments is a reason to continue the forward test, not to believe the
backtest.

---

## 5. WHAT FAILED

Every study below reached a pre-registered gate and failed it. Units differ —
early studies report R (fixed ₹500 risk), later ones report percentage of a
fixed ₹25,000 position. **These are not comparable across studies.**

### ML on price/volume (trade-info)
LightGBM, 25 features, 20-seed ensemble. IC 0.0281 against a 0.03 threshold.
`entity_id` as a categorical feature supplied 55% of the gain but scored IC
0.0006 on unseen names and **reduced** IC overall. Holdout reversed sign:
+0.0816 → −0.0206.

### Swing V4 — dip + volume + regime
9.8th percentile against its own pool. Worse than random.

### Swing V1 — dip only
**The most important failure in the project.** 100th percentile in development,
p=0.001, 65,219 trades, cleared Bonferroni and Benjamini-Hochberg across a
six-variant family, with a plausible mechanism.

**Sealed holdout: 61.4th percentile.** Indistinguishable from random.

Every subsequent study cites this. A large sample, a corrected significance
threshold and a sensible mechanism are not substitutes for a holdout.

### Momentum + fundamentals — untestable
Earnings yield t=2.75 (fails correction across nine factors), correlation with
momentum +0.0003. Testing the combination requires **8-72 years** of data. The
binding constraint is the variance of the difference, not the effect size.

### Box theory V1 — buy yesterday's low on a green candle
−0.138R. **0th percentile** against the selection null — the touch-days were
worse than random days. 100th percentile against TIMING. The entry timing was
better than random; the day selection was actively harmful.

### Box theory V2 — strength-filtered
Required a candle ≥1.5× trailing range and volume, plus 5% room. 401 trades,
−0.104R, 27.7th percentile. Moved from harmful to merely useless.

### Darvas box
200-day high confirmed over 3 days, bottom likewise, buy the breakout, trail
the stop below each new box. 757 trades, held median 20 days, max 252.

**0.0 / 0.3 / 0.3** percentiles against TIMING, SELECTION and MOMENTUM nulls.
Lost to random entry timed off its own boxes. The book it came from is
promotional material for the author's scanning software and contains no
backtest.

### Fair Value Gap (FVG), A and B
Three-candle gap on 1-hour candles. A = breakout, B = retest. −0.128R and
−0.169R, both **0th percentile** against TIMING.

### IPO listing-day green first candle
498 mainboard listings. 41 trades, −0.149R, MDE 0.36R. The green-candle filter
was **worse than buying every listing indiscriminately** (−0.149 vs +0.092,
losing in all 10,000 resamples).

### Per-stock weekly rules
21 stocks × 2 rules = 42 trials with FIT/CHECK split and Bonferroni.
**Zero survivors.** VBL passed FIT at t=3.60 and cleared Bonferroni by under
0.1%, then failed CHECK — the illustrative case.

### NIFTY options pricing
Monthly ATM straddle price vs realised move, 2016-2026. **No detectable
mispricing.** Mean R +0.11 dev (+0.02 excluding 2020), −0.13 test, CIs
including zero.

### POC family — five trials, all failed
| Version | Change | Result |
|---|---|---|
| V1 | 0.5% below POC | −0.6733R, **sizing pathology** |
| V2 | Fixed capital, 5-day low stop | −0.4077% |
| V3 | Hourly confirmation | −0.3176% |
| V4 | Liquidity sweep + reclaim | −0.2862%, **passed both nulls** |
| V5 | 10-day hold | −0.6302%, worse than intraday |

V4 is notable: it passed both null comparisons and still lost. The selection
edge was real and smaller than friction. V5 tested whether a longer horizon
would let it grow past costs — it made things worse, because delivery costs are
higher and overnight gaps bypass stops.

### Liquidity family — six specified, four failed, two abandoned, one withdrawn measurement
Multi-timeframe confluence (3-month, 1-week, 1-day highs and lows clustering
within 0.5 ATR), sweep below by 0.1-1.0 ATR, reclaim within 3 candles, scaled
exit at 1.5R and 3R.

| Study | Change | Long | Short |
|---|---|---|---|
| A | base, long | −0.2841% | — |
| B | base, short | — | −0.1212% |
| C | require a retest | −0.2694% | −0.1096% |
| D | require ascending lows | −0.2926% | −0.1383% |
| E | hourly sweep AND reclaim vs 5-min | abandoned at Phase 1, confounded — reclaim-window width varied silently with the sweep timeframe | |
| F | hourly sweep, fixed 15-min 5-min reclaim | abandoned at Phase 1, unidentifiable — the reclaim-window's *start* is welded to the sweep timeframe by actionability (a slower candle is only knowable at its own close), so the comparison could not be fixed by holding width constant alone | |

All four completed trials passed both nulls at the 100th percentile. All
lost. A counterfactual measurement of F's own rejected buckets was
withdrawn after failing an arithmetic reconciliation against its own
Phase 1 counts — selective sampling, not a random loss (see
`MEASUREMENT_F_REJECTED_BUCKETS.md`).

**CLOSED, 2026-11-07. No Study G** — see `LIQUIDITY_FAMILY_CLOSED.md`
for the full closure reasoning.

### Portfolio construction — underpowered
24 configurations of concentration × weighting × rebalance frequency.
**Never run.** The MDE at 80% power under 24-trial Bonferroni was **45-75
percentage points** of annual return. Plausible effects are low single digits.
The baseline stands by default, not because alternatives lost.

---

## 6. BUGS — roughly 18 documented

Every one produced a plausible wrong number rather than an error. Selected:

**#2 — stale-gap contamination in the LABEL**, not just the features. Found by
chasing a decile/IC sign conflict.

**#7 — ISIN mismatch.** The fundamentals feed uses the original ISIN, not the
active one. 166 orphaned companies, 226,715 fact rows rematched. The fix was
not propagated to fetch-scoping — the fifth instance of that pattern.

**#11 — same-ISIN uncorrected corporate actions.** 78 entities. Seven other
scripts were later found computing persistence/IC without the exclusion.

**#12 — fundamentals screener is current-state only.** No point-in-time
history, so any screener-based historical variant is uncomputable.

**#15 — a 404 cached as a holiday.** A backfill ran at 00:23 before the day's
bhavcopy existed, got a 404, and recorded the day as permanently no-data.
Every later retry skipped it. Caused a stale watchlist that would have missed
four of ten stocks.

**#18 — two unreconciled price scales.** `scale_probe` (validated) used for
ORB and entry; the `adjustment_factors` table (blind to unrecorded corporate
actions) used for zone and swing. They disagreed on ~15-18% of days, and the
disagreement changed **which stocks were selected**. In the Fibo sealed test it
added 9 false positives averaging 0.875R against the population's 0.342R —
inflating the result — and wrongly rejected 37 others. Found by accident during
an unrelated holding-period diagnostic.

**Sizing pathology (POC V1).** A stop ₹0.000495 from entry produced 1,010,101
shares and a ₹130.5M position on a ₹500 risk budget, costing ₹137,450 in fees
on a trade that lost exactly 1R on price. The worst single trade was −480R.

---

## 7. TRANSFERABLE FINDINGS

These outlive the strategies.

**1. `entity_id` defeats time-based purging.** It supplied 55% of the model's
gain, scored IC 0.0006 on unseen names, and *reduced* overall IC.

**2. Corwin-Schultz and Roll overstate Indian spreads by 12-31×** on normally
traded EQ names, and are accurate (~1.0×) on trade-to-trade names. Proposed
mechanism: CS assumes the daily high-low range contains a bid-ask bounce; on
continuously traded names, intraday netting absorbs it. Not documented
elsewhere for NSE as far as is known. A proper validation study is specified
but not yet run.

**3. Variance of the difference, not effect size, is the binding constraint.**
Twice: the momentum+fundamentals combination needed 8-72 years; portfolio
construction needed effects 10-20× larger than any that exist.
→ **Standing rule: compute MDE before finalising any comparison study.**

**4. "Fixed where noticed, not everywhere the pattern recurs."** Seven
instances. Grep the codebase for the same defect shape before closing any bug.
*(Note: this entry's own list position, "#4," is unrelated to OPERATIONS.md's
"fourth occurrence" label for the same defect shape — that label counts
recurrences at the time it was written and is a different, and now stale,
number. The coincidence that both read "4" is accidental; no catalog ties the
two together.)*

**5. A gross-return null cannot see position sizing.** The Fibo timing null
showed breakout entry picked worse prices than random. I inferred removing the
breakout would help. It made things dramatically worse — the breakout was
providing a **cost cushion** by widening R, which a gross-return measure is
blind to. Entry-rule comparisons must be run on net R.

**6. Confirmation filters discard the winners.** Measured twice. Study C's
`no_retest` bucket averaged **+1.0%**; Study D's `PATTERN_INCOMPLETE` averaged
**+0.87% to +0.91%**. A filter requiring price to come back necessarily excludes
the moves that don't come back, and those are disproportionately the winners.

**NARROWED 2026-11-07:** As originally written ("confirmation filters
discard the winners") this generalised beyond its evidence. The evidence
is two retest-type filters (Study C `no_retest` +1.0%, Study D
`PATTERN_INCOMPLETE` +0.87% to +0.91%). The defensible statement is
structural, not empirical: a filter's condition determines WHICH
subsequent price behaviour it cannot select. A filter requiring price to
RETURN to a level cannot select trades where price ran away, so its
discards skew toward runs. A filter requiring RECOVERY from an adverse
move cannot select trades where price continued adversely, so its
discards skew toward continuations. These are opposite discards and
there is no reason to expect the same return sign. The reclaim-type case
is UNTESTED. The Study F measurement intended to test it was withdrawn
(see `MEASUREMENT_F_REJECTED_BUCKETS.md`) and not retried, because the
family closed. This narrowing rests on construction, not measurement,
and is flagged as such.

**7. A stop pinned to a price level other than entry needs a minimum-distance
floor**, or fixed-risk sizing produces unbounded positions. FVG had one; POC
V1 did not.

**8. Candle-counted rules change meaning when candle size is the variable.**
"Reclaim within 3 candles" is 15 minutes at 5-minute candles and 3 hours at
hourly. Any timeframe comparison must hold time windows constant in minutes.

**9. Blast radius must be measured in both directions.** A selection bug that
wrongly includes also wrongly excludes.

**10. Jensen's inequality on ratio tests.** Testing mean log(payoff/price) = 0
reports overpricing even when options are fairly priced, because payoffs are
right-skewed. Verified empirically: the replaced log test came back negative in
all three windows including one where buying straddles actually made money.

**11. Calendar-year windows are convenient, not principled.** Mechanical
peak-to-trough-to-recovery is the correct framing for a drawdown episode.

**12. Matched random entry from the same pool is the discriminating
benchmark.** Buy-and-hold and coin-flip comparisons are weak.

**13. Window width and window start are separate parameters.** Establishing
structure on a slower timeframe necessarily delays the start of any
confirmation window by up to one slow candle, because the structure is not
knowable until that candle closes. Holding the window's WIDTH constant in
minutes (finding #8) does not control its START. Where actionability forces
the delay, a timeframe comparison is not merely confounded but unidentifiable:
no outcome is attributable to the timeframe. Measured in Liquidity F Phase 1,
where the delay roughly doubled the trade count against the direction the
coarser grid alone predicted.

**14. A counterfactual must reuse the original setup, not re-derive it.**
The withdrawn Study F measurement resolved exits for its rejected
buckets by calling A/B's full entry pipeline, which independently
re-detects its own sweep from scratch. ~90% of rows dropped for one
outcome-correlated reason — the re-detected sweep also failed to
reclaim — leaving a ~6% biased subsample whose CIs looked clean and
narrow. Any counterfactual, null or bucket comparison must be
constructed by reusing the recorded setup (extreme, level, timestamp)
from the stage under study, never by re-running a detector. Studies C
and D use the correct construction and are unaffected.

---

## 8. THE STRUCTURAL FINDING

**Costs are fixed per trade. The available move shrinks with the horizon.**

A round trip costs roughly 0.2-0.3% regardless of holding period. An intraday
move might be 0.5%; a 63-day move might be 8%. So intraday needs a signal
several times stronger to end up in the same place.

Phase 1's cost gate established this before any strategy was tested: only one
configuration cleared break-even in theory, requiring IC 0.05 at a 5-day
horizon — roughly double what was later measured at 63 days on an easier
problem.

**Eleven intraday strategies with completely different logic — Darvas boxes,
Fibonacci zones, volume profile, fair value gaps, IPO openings, liquidity
sweeps — all landed between roughly −0.1 and −0.3 per trade.** That consistency
is not eleven bad ideas. It is one constant seen through eleven lenses.

**And the escape is not simply "hold longer."** POC V5 held 10 days and did
worse: delivery costs are higher than intraday and overnight gaps bypass stops.
The escape requires a signal whose expected move genuinely grows with time.
Momentum has one. The chart patterns did not.

One further measurement, across 32,515 Liquidity trades: the strategy's own
stop is touched within 10 days on **84-86% of all trades**. Of same-day
stop-outs, 69-73% eventually reach 1.5R. But when both stop and 3R target are
reached, **the stop comes first 2.6-3.3× as often**. Direction was often right;
the path made it unharvestable. Held with no stop at all, the mean stays
negative at both 10 and 30 days, with worst cases of −87% (long) and −155%
(short).

---

## 9. CALIBRATION NOTES

**On predictions.** Claude pre-committed a prediction before several studies.
The verdict was right nearly every time; **the mechanism was wrong nearly every
time.**

- Fibo open-entry: predicted costs were the issue → it was position sizing via
  stop distance
- Liquidity A: predicted costs would eat a real edge → costs were ₹10,095
  total (~0.005%); it failed on follow-through
- Liquidity B: predicted shorts would fare worse against upward drift → they
  fared better

**Named bias — coarser-timeframe setup-count direction, wrong twice:**
Predicted FEWER setups on the coarser timeframe in both Liquidity E Phase 1
and Liquidity F Phase 1. Both times there were MORE. Direction wrong, not
just mechanism. Diagnosed cause: reasoning about the count of qualifying
LEVELS (coarser grid, fewer levels) while ignoring the CONVERSION RATE from
sweep to reclaim, which the delayed check inflates. The conversion-rate
effect dominated in both cases. Liquidity family running total: 4 of 4
mechanism predictions wrong, 2 of 2 count-direction predictions wrong.

**Study F rejected-buckets measurement**: pre-committed a guardrail
against over-reading a POSITIVE result and built none for a negative
one, which shows which way the expectation ran. The first numbers came
back negative and were then withdrawn as unmeasured, so the prediction
was neither confirmed nor refuted — it was moot. Recorded because the
asymmetric guardrail is itself the tell. Liquidity family: 5 of 5
mechanism predictions wrong, 2 of 2 count-direction predictions wrong,
1 implicit expectation moot.

Five-for-five in the Liquidity family: verdict right, mechanism wrong.
Treat Claude's mechanism reasoning as a hypothesis to test, not a finding.

**On where the knowledge came from.** Claude's training contains extensive
trading material — Darvas, ICT, volume profile, FVG. That material would have
predicted all of those strategies work. All failed here. The accurate
predictions came from *this project's own results*, not from prior knowledge.
Treat any strategy Claude can describe fluently as having a poor prior,
precisely because fluency comes from promotional material.

**2026-11-07:** issued two location-scoped documentation instructions in one
session (OPERATIONS.md title without its body; §2 and §10 without §5), each
reproducing finding #4's defect shape in documents about that shape. Both
caught by Claude Code flagging rather than editing. Recorded as an
instruction-design defect, not a verdict change.

**On chart observation.** Four observations made from browsing charts have been
tested — degenerate confluence, turnover dependence, retest confirmation,
ascending lows. **All four came back null.** The research browser is for
understanding what happened, not for generating the next hypothesis.

---

## 10. WHAT IS STILL OPEN

**The forward tests.** Fibo needs ~19 trades to distinguish decay from noise in
its weakest year, ~100 for a verdict. Momentum's basket resolves in January.
Neither is accelerable.

**The spread estimator validation.** Specified, 24 names stratified by
liquidity, series, price and volatility, protocol written with explicit
refutation criteria. Awaiting ~10 trading days of collection. This is the one
piece of work here that is not about making money, and possibly the most
original.

**IPO listing's sealed TEST window.** 199 listings, never read, the only
untouched sealed data in the project.

**Liquidity family — CLOSED, 2026-11-07.** No longer open. Study F's
Phase 1 estimate found the comparison unidentifiable (fixing Study E's
window-width confound left the window's start uncontrolled) and it was
abandoned before preregistration, matching Study E. Final tally: 4 DEV
failures, 2 Phase 1 abandonments, 1 withdrawn measurement. No Study G —
see `LIQUIDITY_FAMILY_CLOSED.md` for the closure reasoning.

---

## 11. RULES FOR A COLD SESSION

1. **Do not propose a strategy without checking whether it has already been
   tested.** §5 is the enumeration; no single total is maintained across it
   (§1). Check §5 first.
2. **Any intraday mean-reversion or level-bounce idea has a very poor prior.**
   Eleven have failed, all clustering at −0.1 to −0.3.
3. **Compute MDE before finalising a comparison study.** Three times a fully
   specified study turned out to be unanswerable (Portfolio construction,
   Liquidity E, Liquidity F).
4. **Hold time windows constant in minutes, not candles**, when timeframe is
   the variable.
5. **Measure blast radius in both directions** when a bug affects selection.
6. **The historical holdout is retired.** Any new equity study is
   development-only; a pass justifies forward testing and nothing more.
7. **A DEV failure closes a study automatically.** No approval needed, and no
   retry at other parameter values.
8. **Report bad results in the first sentence.**
9. **Long runs must checkpoint mid-stage.** The environment kills them
   frequently; a job estimated at four hours took seventeen.
10. **Trust nothing that was not measured.** Including — especially — Claude's
    explanation of why something failed.
