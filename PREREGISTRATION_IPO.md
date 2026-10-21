# Pre-registration: IPO listing-day first-candle momentum, NSE mainboard

Frozen before any trade is simulated, any R value exists, or Phase 2 code
runs, per this project's standing discipline (`PREREGISTRATION.md` and
family). Nothing below changes after this document is committed except by
an explicit, recorded amendment, made before the next result that
amendment could have been shaped by.

## Provenance -- stated plainly, as instructed

**This hypothesis comes from the user, based on a single observed
listing on 2026-10-21.** It is not from academic literature, not a
replication of a published factor, and not derived from any pattern this
project has previously backtested. **Family trial count for IPO
listing = 1.**

**This is NOT the same provenance situation as FVG, Box Theory, or
Fibo.** Those studies' preregistrations state plainly that the 2016-2026
historical window has already been read by prior studies in this
project, so their own DEV passes are development evidence for forward
paper trading, never a validity claim, because no genuinely unseen
holdout exists for that data any more (`FINDINGS.md` Section 7). **The
IPO listing-day dataset does not yet exist anywhere in this project.**
It must be freshly collected (Phase 1, below) from a combination of
third-party listing-date sources and a fresh Angel One intraday fetch,
and nothing in this project has ever computed a trade, an R value, or a
null against it. The sealed TEST window defined in Section 7 is
therefore treated as a **genuine, first-exposure holdout** for this
specific hypothesis -- not a forward-only discipline device -- and a
clean TEST pass here would carry real evidentiary weight a Fibo or Box
Theory TEST pass no longer can. This also means the sealing discipline in
Section 7 is enforced with no slack: once DEV is read, this document's
own existence is proof the TEST window was still unseen at that moment,
and it must stay that way until DEV passes and is explicitly approved.

## 0. Scope and reuse boundaries

**New code lives in `src/ipo_listing/` only**, written after this
document is committed. The following existing modules are imported and
reused **read-only, unmodified**:

- `data_layer.prices_nse` (`fetch_raw_zip` / `parse_bhavcopy_zip` /
  `load_bhavcopy_to_duckdb`) -- the same NSE bhavcopy fetcher/loader every
  other study in this project uses, for the listing-day OHLC
  cross-validation (Section 3). `data/warehouse.duckdb`'s `prices_eod`
  table (already populated, full-market, 2016-01-01 through the present)
  is read directly; nothing is re-fetched for this check.
- `data_layer.nse_holidays.is_nse_holiday` -- unchanged, same holiday
  master every fetch script in this project already relies on.
- `fibo.auth.login` -- unchanged, the ONLY authenticated path to Angel
  One's SmartAPI in this project, including its credential-safety
  discipline (never logs/prints tokens). Reused for the Phase 1 intraday
  fetch exactly as `scripts/fibo_download_intraday.py` already uses it.
- `fibo.download.chunk_date_ranges` / `fetch_chunk_with_retry` /
  `looks_rate_limited` / `looks_token_expired` -- unchanged. A single
  listing day never needs chunking (it is always <=1 day, far under the
  25-day chunk size), but the truncation-detection and
  rate-limit-vs-token-expiry distinction this module encodes are real,
  previously-hard-won lessons (see that module's own docstring) and are
  reused as-is rather than risk re-discovering the same failure modes.
- `spread_monitor.tokens.resolve_tokens` -- unchanged, direct
  symbol-to-Angel-token lookup against Angel's current instrument master
  (cached to `data/cache/`), used to resolve each listing's own
  listing-day-era symbol to a token for the Phase 1 fetch.
- `box_theory.inference.day_clustered_bootstrap` / `excludes_zero` /
  `percentile_vs_null` -- unchanged. This module's own 97.5% two-sided CI
  ([1.25th, 98.75th] percentile, `Z_CRITICAL=2.2414`) is reused because it
  is numerically exactly what Section 9's gate calls for ("a bootstrap
  97.5% CI excluding zero"), not because of its docstring's own
  Bonferroni-for-2-configurations framing, which does not apply here
  (family trial count = 1, Section 0 above). Reused verbatim; the
  coincidence in the resulting percentile bounds is stated here so it is
  not mistaken for an unexplained Bonferroni correction being smuggled in
  for a single-configuration study.
- `box_theory.resolution.position_size_shares` -- unchanged. Its
  signature already accepts an arbitrary `stop_pct`
  (`floor(fixed_risk_rs / (stop_pct * entry_price))`); called here with
  `stop_pct=0.05` to get exactly this study's own sizing rule
  (`floor(500 / (entry * 0.05))`), not re-derived.
- `swing.costs.buy_leg_cost_rs` / `sell_leg_cost_rs` -- unchanged, the
  same INTRADAY statutory + Groww fixed-fee formulas every other study's
  cost model is built from.

**New in `src/ipo_listing/`, because nothing in this project does this
today**: the listing-date/symbol identification and cross-validation
pipeline (Section 2); a listing-day-only intraday fetcher into a
**new, separate database file** `data/ipo_listing/ipo_intraday.duckdb`
(never `data/fibo_intraday.duckdb`), same throttle/backoff/resumable/
flush-heartbeat conventions as `scripts/fibo_download_intraday.py` but
operating on single-day windows keyed by listing rather than
multi-year chunks keyed by entity; `ipo_listing.costs.round_trip_cost_rs`
-- structurally identical to `box_theory.costs.round_trip_cost_rs`
(same statutory+Groww-fixed-cost call into `swing.costs`, same
"spread bps on top" shape) but parameterized by an explicit bps value
rather than box theory's fixed 3-band dict, because Section 6 requires
evaluating the SAME trade set at three different bps levels (7/14/28),
not three different rank bands; a new, FVG/Box-independent sealed-window
guard instance `ipo_listing.test_seal` (Section 7); entry/exit mechanics
specific to this study's single-day, fixed-percentage stop/target
(Section 5) -- new code, not an adaptation of `box_theory.resolution`'s
touch/arm/FAST-SLOW machinery, which this study's much simpler rule does
not need.

## 1. The question

Among NSE mainboard IPOs, does buying the listing day's first green
1-minute candle, at the open of the next candle, produce positive net
return after costs -- and does the green-candle filter itself add
anything over simply buying every listing regardless of its first
candle's colour?

## 2. Universe and listing identification -- Phase 1, as executed

**Scope**: every NSE MAINBOARD IPO listing, 2016-01-01 through the most
recently completed month (2026-09-30 at the time of this document).
SME/NSE-Emerge listings excluded throughout.

**Identification, by era**:

- **2020-01-01 through 2026-09-30**: `ipo_cohort_verified.csv` from the
  public GitHub repository `bebhuvan/ipo-performance-verification`
  (`data/verified/ipo_cohort_verified.csv`), itself built and
  cross-validated by its author against official NSE/BSE bhavcopy and
  Kite Connect candles. Filtered to `board_type = Main Board`; 4 Main
  Board rows whose only listing venue was BSE (CAMS, Protean eGov
  Technologies, NSDL, NSE Ltd itself) were excluded, since this study's
  scope is NSE listing-day price action specifically.
- **2016-01-01 through 2019-12-31**: chittorgarh.com's mainboard
  listing-date report. This page is JS/AJAX-rendered (a plain HTTP fetch
  returns an empty "Total Records: 0" shell), so it was rendered via
  browser automation and queried **month by month**, because the
  rendered table appears to cap at 5 rows per query -- querying by month
  kept every single query's real row count at or under that cap, verified
  against each page's own stated "Total Records" field to rule out
  silent truncation.

**Cross-validation against this project's own archive**: every one of
the resulting 552 candidate listings was checked against
`data/warehouse.duckdb`'s `prices_eod` table -- confirmed to be the
**full-market** NSE bhavcopy (not a curated top-N subset), covering
2016-01-01 through the present, 4,097 distinct ISINs. 537/552 matched
the claimed listing date within 5 trading days on first pass. The
remaining 15 were off by 500-2,900 days for an identifiable, structural
reason: the listing-date source's quoted ISIN is each company's
**current** ISIN, and 13 of these 15 companies have since had their
ISIN renumbered (a face-value split/consolidation) while keeping the
same trading symbol throughout -- tracing by symbol instead of by the
stale ISIN resolved all 13 to an exact match. The remaining 2
(**Infibeam Incorporation**, listed 2016-04-04 as `INFIBEAM`, renamed
`CCAVENUE` in 2026; **Karda Constructions**, listed 2018-04-02 as
`KARDA`, renamed `DHARAN` in 2021) involve an actual symbol rename, not
just an ISIN renumbering -- resolved the same way, by using the
listing-day-era symbol rather than the current one. **Net: 552/552
(100%) resolve to an exact listing-day match in this project's own
bhavcopy once each listing's symbol-at-the-time is used.**

**By year** (2026 partial, through September):

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 27 | 34 | 24 | 16 | 13 | 64 | 38 | 58 | 90 | 103 | 85 | **552** |

## 3. Phase 1 intraday fetch -- into `data/ipo_intraday.duckdb`

For each of the 552 identified listings, fetch 1-minute bars for the
**listing day only** via Angel One (`fibo.auth.login`, same
authentication module every other fetch in this project uses), into
`data/ipo_listing/ipo_intraday.duckdb` -- a new, separate file;
`data/fibo_intraday.duckdb` is never opened for writing by this study.
Same throttle (Angel's documented 3 req/sec, 150/min, 5000/hour, slept
conservatively between calls), same resumable/flush/heartbeat
conventions, same chunking/truncation-retry machinery
(`fibo.download.fetch_chunk_with_retry`, Section 0) as every other fetch
in this project, even though a single listing day never actually needs
to split into sub-chunks. **A failed fetch (no token resolvable, API
error, rate-limit, or a resolved token returning zero candles) is
recorded as `FETCH_FAILED`, with its specific reason, and is never
conflated with "no data because the market was closed."**

**VALIDATE**: the fetched listing-day 1-minute bars are aggregated to a
single daily OHLC bar (`fibo.bars.aggregate_to_daily`, unchanged, the
same function `fibo.validation` already uses for this exact purpose) and
compared against that day's own `prices_eod` bhavcopy row for the same
ISIN. The mismatch rate is reported in the Phase 1 completion report,
along with how many listings ended up with usable data versus how many
were lost, broken out by reason -- per the two limitations below, **kept
separate, never blended into one combined loss count**.

### 3a. LIMITATION -- survivorship bias, direction known, recorded now

**33 of the 552 identified symbols (5.98%) do not resolve against
Angel One's CURRENT instrument master** (Section 0's `resolve_tokens`,
a live-only snapshot). These 33 are disproportionately likely to be
companies that were delisted, renamed, or merged since their listing --
not a random subset of the 552. If a symbol-resolution failure removes
a listing from the usable sample, **the direction of the resulting bias
is known in advance**: a delisted/renamed/merged company is, on net,
more likely to have been a weaker performer (voluntary delisting via
buyout aside) than one still trading cleanly under its original name a
few years later, so **dropping these listings biases the usable sample
toward IPOs that survived, which flatters this study's own result**.
This is recorded here, before the Phase 1 fetch is run and before any
number from this study exists, per instruction.

**Before this bias is accepted at face value, each of the 33 is
re-attempted using its listing-day-era symbol** (not its current one)
against Angel's master, since Angel's snapshot may simply not have
caught up to a rename that this project's own `prices_eod` already
shows (exactly the same lineage issue Section 2 found and fixed for
Infibeam/Karda above). The Phase 1 completion report states, by name:
how many of the 33 were recovered this way, how many remain genuinely
unfetchable, and why (delisted outright, merged into another listed
entity with no clean 1:1 share-for-share price continuation, or a token
Angel's master has simply never carried). **If more than ~5% of the
final USABLE sample (after this recovery attempt) is still lost to this
effect, that is stated prominently in the Phase 1 completion report and
in every later findings report's own first paragraph -- not folded
into a footnote.**

### 3b. LIMITATION -- the 2016 archive floor, a different kind of gap

**Separately, and not to be blended with 3a**: a live test against
Angel One's `getCandleData` for a stock listed 2016-01-06 (Narayana
Hrudayalaya, `NH`) returned a validly resolved token but **zero
candles** -- Angel's own 1-minute archive does not reach back that far,
consistent with this project's existing Fibo archive's own documented
floor (`data/fibo_intraday.duckdb` confirmed present only from
2016-10-04 onward). Listings from later in 2016 onward returned full
sessions in every other sample tested (2017, 2020, 2023, 2026). **This
means roughly the first 27 listings of 2016 (all of 2016 through
somewhere in early-to-mid October) are likely lost to a hard data-
availability boundary, not to any property of the companies
themselves** -- this is NOT a selection effect and carries no directional
bias the way Section 3a's survivorship gap does; it is reported as its
own line in the Phase 1 completion report, distinct from 3a's count.

### 3c. LIMITATION -- the listing-day open is not 09:15

Confirmed live, across every post-2016 sample tested (2017, 2020, 2023,
2026): the first 1-minute candle on an actual listing day starts at
**09:44 or 10:00**, not 09:15 -- NSE runs an extended special pre-open
call-auction price-discovery session for a security with no trading
history, which delays the start of continuous trading by 30-45 minutes
versus an ordinary day. **Per explicit user decision, the ENTRY rule
(Section 5) is operationalized as "the first 1-minute candle actually
present in the archive for that listing day, whatever its clock time,"
not literally "the 09:15-09:16 candle."** This is recorded as a
limitation/deviation from the literal rule text, not a silent
reinterpretation: the rule's intent ("first candle of the day") is
preserved; its incidental 09:15 timestamp label is not.

## 4. Universe caveat -- no rank, no turnover history

Unlike every prior study in this project, IPO listings have **no
pre-listing turnover history** and therefore no rank/band the way
`box_theory.costs.band_for_rank` assigns one. Per instruction, the cost
model (Section 6) uses the single WIDEST existing band (101-200, 7bps
round trip) as an explicit **floor, not a measurement** -- a brand-new
listing's actual spread is plausibly wider still, and the 2x/4x
sensitivity reporting in Section 6 exists specifically to surface how
much that assumption matters.

## 5. Entry, stop, target, time exit -- FIXED

**ENTRY**: the first 1-minute candle of the listing day present in the
archive (Section 3c -- not necessarily 09:15-09:16). If that candle is
green (`close > open`), enter at the **open of the immediately following
1-minute candle**. If that first candle is red or flat, **no trade that
day**.

**STOP** = `entry_price * 0.95`. **TARGET** = `entry_price * 1.125`.
Both resolved on 1-minute bars, the scan starting with the entry fill
bar itself. **If both levels are touched within the same 1-minute bar,
STOP wins** (same tie convention `box_theory.resolution.resolve_exit`
already uses).

**TIME EXIT**: close of the 15:15 candle, if neither stop nor target has
been hit by then.

**Long only. One trade per listing.**

**Sizing**: `qty = floor(500 / (entry_price * 0.05))` --
`box_theory.resolution.position_size_shares(entry_price, stop_pct=0.05)`,
unchanged (Section 0).

**These values -- the 5% stop, the 12.5% target, and the first-1-minute-
candle entry rule -- are FIXED by this document.** If DEV fails, they
are not retried at other values.

## 6. Costs

`ipo_listing.costs.round_trip_cost_rs(position_size_rs, spread_bps)` --
new code (Section 0), combining `swing.costs`'s unchanged INTRADAY
statutory + Groww fixed-fee formulas with an explicit spread/impact bps
parameter (rather than box theory's 3-band dict, since this study needs
one population evaluated at three different bps levels, not three
different populations each at their own band). Reported at:

- **7 bps** round trip (the WIDEST existing band, 101-200, used as a
  floor per Section 4 -- stated as a floor, not a measurement)
- **14 bps** (2x)
- **28 bps** (4x)

## 7. Windows and seal

**Split by listing date, chronologically, on the final USABLE sample**
(after Phase 1's fetch and the recovery attempt in Section 3a --
`FETCH_FAILED` listings contribute no trade and are not part of either
window): the earlier 60% of usable listings by listing date = **DEV**;
the most recent 40% = **TEST**, sealed in code
(`ipo_listing.test_seal`, a new instance, same mechanism as
`box_theory.test_seal`/`options_history.test_seal` -- `guard_date_range`,
an `authorize_test` bypass exercised at most once, its own append-only
access log, no state shared with any other study's seal). The exact
boundary date and the count in each window are determined and frozen
the moment Phase 1's fetch completes -- before any Phase 2 code is run
against either window -- and reported then, not guessed now while the
full fetch is still outstanding.

Per Section "Provenance" above, this seal is enforced as a genuine
unseen holdout: `authorize_test=True` is exercised at most once, only
after DEV passes Section 9's gate AND the user explicitly approves.

## 8. Nulls

**TIMING null**: the same listing days the real strategy actually
entered (i.e. the ones with a green first candle). A random 1-minute
candle in the 09:16-15:00 window replaces the real entry trigger; same
5%/12.5% stop/target percentages, same cost model. 1000 seeds; a
representative-slice timed probe decides, before the full run commits,
whether 1000 is affordable within roughly an hour -- if not, 500 seeds
is substituted and the substitution is logged at the time (same
contingency `PREREGISTRATION_BOX_V2.md` Section 6 and
`PREREGISTRATION_FVG.md` Section 8 already use). `percentile_vs_null`
(Section 0, unchanged) against the resulting 1000 (or 500) null means.

**SELECTION null (the primary null, per instruction)**: NOT a
comparable-day-pool construction (there is no pool of non-listing days
for the same stock) -- instead, the **alternate strategy of entering
every one of the 552 usable listings at 09:16 regardless of the first
candle's colour**, same 5%/12.5% stop/target, same cost model. This is
a single, deterministic alternate backtest, not a seeded random draw --
to compare it against the real (green-filtered) strategy on the same
97.5%-CI/percentile footing Section 9's gate uses, its own trade set is
run through the same `box_theory.inference.day_clustered_bootstrap`
(unchanged, `trade_date` = each listing's own listing date) to produce
10,000 resampled means, and the real strategy's observed mean is located
within that resampled distribution via `percentile_vs_null` (unchanged).
This operationalization is stated explicitly because the instruction
does not specify seed mechanics for an inherently non-random alternate,
and this reuses exactly the inference machinery already built rather
than inventing a new comparison.

## 9. Gate

**DEV PASSES only if ALL hold**:

- mean net R > 0 with the day-clustered 97.5% CI excluding zero
- mean net R's percentile is >= 95th against BOTH the TIMING null and
  the SELECTION null (Section 8)
- mean net R remains > 0 after dropping the single best calendar year
  (by that year's own mean net R) from the DEV sample
- mean net R remains > 0 at the 14bps (2x) cost scenario

**Anything else = NO EDGE, study closes, TEST is never read.** Per
Section 7's "genuine holdout" framing, a DEV failure here closes the
study exactly as finally as every prior NO-EDGE closure in this project
-- there is no weaker standing to fall back to, because unlike Fibo/Box/
FVG there was never a prior exposure that could have already discounted
this result.

## 10. Report contents

**Phase 1 completion** (before Phase 2 exists): listings found, usable,
and excluded with reasons -- Section 3a's survivorship-bias count and
Section 3b's 2016-archive-floor count reported **separately, never
summed into one "lost" figure**; the bhavcopy mismatch rate; the DEV/
TEST boundary date and count once frozen (Section 7).

**Phase 2 (DEV, then TEST upon approval)**: trades taken versus listings
skipped for a red/flat first candle; win rate; mean net R with its
97.5% CI; median net R (descriptive); MDE from the bootstrap SE alone
(never from the observed mean); exit mix (STOP/TARGET/TIME_EXIT); by
calendar year (and the ex-best-year mean); both null percentiles (with
each null's own seed count); results at all three cost levels (7/14/28
bps). **Bad results are reported in the first sentence**, same standing
instruction as every prior study here.

## 11. Process, in this order, stopping where marked

1. Phase 1 methodology, sample, and counts reported; user approval of
   the sample obtained. **>>> DONE.**
2. Write this document. **Commit and push it alone**, before any IPO
   backtest or fetch code exists. Report the commit hash. **>>> this
   step.**
3. Build the Phase 1 fetch (Section 3) into `src/ipo_listing/` and run
   it: fetch, validate against bhavcopy, attempt the Section 3a symbol
   recovery, freeze the DEV/TEST boundary (Section 7). Report the Phase
   1 completion numbers per Section 10, with Sections 3a/3b/3c's three
   limitations stated plainly, not as footnotes.
4. Hand-trace 5 real DEV-window cases before any aggregate number is
   computed: one target hit, one stop hit, one 15:15 time exit, one
   red/flat-first-candle skip, and one same-bar stop-and-target tie if
   one exists in the real data (if none exists, state that plainly
   rather than manufacturing one).
5. Run **DEV only** (real trades, TIMING null, SELECTION null, in that
   order, checkpointed at each stage). Report per Section 10.
   **>>> STOP. The user approves before the sealed TEST window is
   read.**
6. Only after that approval: authorize `ipo_listing.test_seal`, read
   TEST once, report per Section 10.

## 12. Discipline

**No rule in this document changes after any number from this study's
own Phase 1 fetch, DEV, or TEST has been seen.** The 5% stop, the 12.5%
target, and the first-archived-candle entry interpretation (Section 5,
Section 3c) are FIXED and are not retried at other values if DEV fails.
**Bad results, and both survivorship-related limitations (Sections 3a
and 3b), are reported in the first sentence** of whatever reports them,
never buried after a methods recap.

## Status

**>>> STOPPING HERE, per Process Step 2.** No `src/ipo_listing/` code
exists yet, and no intraday fetch has been run beyond the 6-sample
connectivity test already reported and approved as part of Phase 1's
sample. This document is being committed and pushed alone, before the
real Phase 1 fetch, so Step 3's fetch/validation numbers and every later
step cannot have shaped anything written above.
