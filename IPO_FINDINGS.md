# IPO listing-day first-candle momentum: experiments log

Companion to `PREREGISTRATION_IPO.md` (frozen rules, commit `0e7fabc`).
Records what was actually run and found, in order, per that document's
Process section. Per Section 0/Provenance: this dataset has never been
read by any prior study in this project, so the TEST window sealed below
is a genuine, first-exposure holdout -- a DEV result here is a real
Phase 1 completion record, not yet a Phase 2 trade result.

## Phase 1 completion: fetch, validation, and the sealed boundary

**Bottom line, stated first per this project's "bad results first"
discipline**: the fetch and bhavcopy cross-check surfaced a real data
problem not anticipated in the preregistration -- Angel One returns
split/bonus-ADJUSTED historical prices, not RAW ones -- which has now
been found, diagnosed, and corrected in code (`ipo_listing.rescale`)
before any Phase 2 rule touches the data. A further 3 listings were then
excluded for an independent single-tick data defect (Section 3). **Final
usable sample: 498 of 552 identified listings (90.2%)**, bhavcopy-
cross-validated 1-minute data.

### 1. Survivorship recovery outcome

33 symbols were reported unresolvable against Angel's current
instrument master at the time Phase 1's sample was approved. Running
the actual recovery against each one's FULL identity chain (via
`isin_lineage`, chasing every ISIN change, not just the listing-day
one -- this matters: Karda Constructions changed ISIN three times and
renamed twice, KARDA -> KBCGLOBAL -> DHARAN, a chain the first,
single-hop version of this recovery code missed entirely until checked
by hand against `prices_eod` directly):

- **13 recovered** via their current symbol/token: Infibeam Incorporation
  (INFIBEAM -> CCAVENUE), Larsen & Toubro Infotech (LTI -> LTM), Reliance
  Nippon Life AMC (RNAM -> NAM-INDIA), Angel Broking (ANGELBRKG ->
  ANGELONE), Restaurant Brands Asia (BURGERKING -> RBA), Zomato (ZOMATO
  -> ETERNAL), Glenmark Life Sciences (GLS -> ALIVUS), Ami Organics
  (AMIORG -> ACUTAAS), Abans Holdings (AHL -> AFSL), Sah Polymers (SAH ->
  AERONEU), Standard Glass Lining Technology (SGLTL -> SETL), ArisInfra
  Solutions (ARISINFRA -> ARIS), Amir Chand Jagdish Kumar Exports
  (AMIRCHAND -> AEROPLANE).
- **21 remain unresolved** (`NO_TOKEN`), named: Equitas Holdings, Ujjivan
  Financial Services, Khadim India, Future Supply Chain Solutions, Astron
  Paper & Board Mill, Karda Constructions, ICICI Securities, TCNS
  Clothing, Nureca, Barbeque-Nation Hospitality, Ags Transact
  Technologies, Veranda Learning Solutions, Valiant Laboratories, ESAF
  Small Finance Bank, RBZ Jewellers, Mukka Proteins, Kronox Lab Sciences,
  Stallion India Fluorochemicals, Sri Lotus Developers and Realty, Milky
  Mist Dairy Food, Jindal Supreme (India). Most are identifiable mergers/
  delistings (ICICI Securities delisted via 2024 buyback into ICICI
  Bank; Ujjivan Financial merged into its own SFB; TCNS delisted via
  Aditya Birla Fashion buyout); several (Nureca, RBZ Jewellers, Mukka
  Proteins, Stallion India, Sri Lotus, Milky Mist, Jindal Supreme) are
  recent, small/thin-liquidity listings Angel's master may simply not
  carry yet, not necessarily delisted.
- **21 / 498 final usable sample = 4.22%** -- under the 5% prominence
  threshold `PREREGISTRATION_IPO.md` Section 3a sets, but close enough
  to it that it is stated here plainly rather than waved past. The
  direction remains as recorded before this number existed: dropping
  these listings biases the usable sample toward IPOs that survived
  cleanly to 2026, which flatters this study's own result.

### 2. DEV/TEST boundary -- frozen, sealed, AFTER all exclusions (Section 3), reported before any rule runs

On the final 498 usable listings (501 that fetched `OK`, minus the 3
excluded in Section 3 below), split chronologically 60/40 by listing
date:

| | count | listing-date range |
|---|---|---|
| **DEV** | 299 | through **2024-11-29** |
| **TEST (sealed)** | 199 | from **2024-12-06** onward |

Frozen in code at `ipo_listing.test_seal` (`SEALED_AT = 2026-10-22`,
the day Phase 1's fetch AND the post-validation exclusions completed),
same `guard_date_range`/`authorize_test` mechanism as
`box_theory.test_seal`, its own independent access log. Not read unless
DEV passes `PREREGISTRATION_IPO.md` Section 9's gate AND the user
explicitly approves.

### 3. Bhavcopy validation mismatch rate -- the real number, and what drives it

**Raw, as-fetched, at the project's existing 0.1% tolerance
(`fibo.validation`'s own default): 60.28%** (501 listing-days
compared). This number is NOT primarily a listing-day-microstructure
effect as anticipated going in -- investigated before accepting it at
face value, and the dominant driver turned out to be a different,
more consequential problem:

**Angel One's `getCandleData` returns prices adjusted for every
corporate action between the historical date and TODAY; `prices_eod`
bhavcopy is always RAW for that specific historical date.** Caught by
noticing OPEN and CLOSE diverged from bhavcopy by the IDENTICAL
percentage on the same day (e.g. Varun Beverages, 2016-11-08: bhavcopy
close 459.50, Angel's fetched close 122.53, a 73.33% difference on BOTH
open and close) -- the signature of one constant per-day multiplicative
factor (a since-applied split/bonus), not timing noise. This is exactly
the RAW-vs-adjusted distinction `fibo.scale_probe` exists elsewhere in
this project to resolve; a single-isolated-day fetch has no day-to-day
timeline for that module's own jump-detection method to run against, so
a new, direct correction was written instead (`ipo_listing.rescale`):
for each listing, derive `scale = bhavcopy_close / fetched_close` and,
if it deviates from 1.0 by more than 2%, rescale that listing's ENTIRE
day's bars by that one factor. Corrections are appended as
`revision_seq=2` rows, never overwriting the as-fetched data (this
project's standing append-only discipline).

**48 of 501 listings (9.6%) needed this correction** -- the largest
factors: Easy Trip Planners (31.97x), Deepak Builders & Engineers
(10.06x), Anlon Healthcare (10.00x), Angel Broking, Exxaro Tiles, Rolex
Rings (10.00x each), Indian Energy Exchange, HMA Agro Industries, Akme
Fintrade, Waterways Leisure Tourism (~9.94-10.00x). Full list in
`data/ipo_listing/phase1_fetch_summary.json` (not committed, same
market-data licensing reasoning as `fibo_intraday.duckdb`/
`warehouse.duckdb` -- reproducible by rerunning
`scripts/ipo_listing_fetch.py`).

**Mismatch rate AFTER scale correction, at the project-standard 0.1%
tolerance -- NOT loosened, this is the number that stands: 52.89%**
(501 listing-days). The scale bug explained only a fraction of the raw
60.28%; the correction is kept, but the tolerance is not touched to
make the remaining number look better.

**Listing days are structurally different from ordinary trading
sessions, and a higher mismatch rate than this project's other studies
see is EXPECTED, not a sign of bad data**: there is a special pre-open
call-auction with no prior close to anchor price discovery to, and the
early minutes of trading are thin by construction (no settled trading
range yet exists). Context for that expectation, reported as context
only and explicitly **not adopted as a new tolerance standard**: 376 of
501 listings (**75.0%**) match bhavcopy within 0.5% on BOTH open and
close post-correction; 209 differ by only 0.1-1%, a further 53 by
1-5%. The 52.89% figure stands as the real, reported number; the 75.0%
figure exists only to show that the deviations behind it are
overwhelmingly small, not to argue the tolerance should move.

**3 listings (0.6% of the 501) differ by more than 5% -- EXCLUDED from
the usable sample**, not merely flagged, per instruction: the first
1-minute candle is exactly what `PREREGISTRATION_IPO.md` Section 5's
ENTRY rule reads, so a corrupted tick on day 1 cannot be risked into
Phase 2. All three share the identical signature -- `low_pct_diff =
100%`, open diverging 34-44%, close matching within 1% -- consistent
with a single spurious near-zero LOW tick in the fetched feed on that
one day, pointing to a data defect rather than a scale or
identification problem:

| Company | Listing date | open diff | low diff | close diff |
|---|---|---|---|---|
| Archean Chemical Industries | 2022-11-21 | 44.2% | 100.0% | 0.0% |
| Five-Star Business Finance | 2022-11-21 | 36.0% | 100.0% | 0.2% |
| Yatharth Hospital & Trauma CARE | 2023-08-07 | 34.7% | 100.0% | 0.9% |

Excluded in code (`ipo_listing.exclusions.KNOWN_DATA_DEFECTS`, applied
by `scripts/ipo_listing_fetch.py` as a named, reproducible step -- not a
one-off manual database edit), fetch_log status
`EXCLUDED_DATA_DEFECT`. **Usable sample after this exclusion: 498** (the
501 that fetched `OK`, minus these 3).

### 4. Fetch losses -- three different kinds, kept separate per instruction

- **19 listings (2016-01-06 through 2016-09-29) hit Angel's own archive
  floor**: a validly resolved token, zero candles returned. This lines
  up EXACTLY with this project's already-documented Fibo archive floor
  of 2016-10-04 -- every 2016 listing on or after that date fetched
  normally; none before it did. A hard data-availability boundary, not
  a property of the companies themselves, and not blended with the
  survivorship count above.
- **11 further listings, scattered 2018-2023, also returned zero
  candles despite falling well inside Angel's normal coverage window**:
  Bharat Dynamics (2018-03-23), Spandana Sphoorty Financial
  (2019-08-19), Mrs. Bectors Food Specialities (2020-12-24), Indigo
  Paints (2021-02-02), Home First Finance (2021-02-03), Sigachi
  Industries (2021-11-15), HP Adhesives (2021-12-27), Tamilnad
  Mercantile Bank (2022-09-15), Pyramid Technoplast (2023-08-29),
  Ratnaveer Precision Engineering (2023-09-11), Motisons Jewellers
  (2023-12-26). **Checked against bhavcopy before accepting these as
  lost, per instruction**: every one of the 11 shows substantial real
  volume and trade count in `prices_eod` that day (range: 731K-37.1M
  shares, 2,714-899,495 trades -- e.g. Mrs. Bectors Food Specialities,
  37.1M shares/899,495 trades; HP Adhesives, the thinnest of the 11,
  still 731K shares/2,714 trades). **None are a real "no trading"
  market fact -- all 11 are genuine Angel archive gaps**, a third,
  distinct kind of loss: not the 2016 floor, not a token-resolution/
  survivorship issue (every one had a valid, current Angel token), not
  thin trading -- an isolated hole in Angel's own historical archive on
  that specific day for an otherwise well-covered instrument. Not
  investigated further beyond this check.

### Final status breakdown (552 identified listings)

| status | count |
|---|---|
| OK (usable) | 498 |
| EXCLUDED_DATA_DEFECT (Section 3) | 3 |
| FETCH_FAILED (2016 archive floor) | 19 |
| FETCH_FAILED (isolated archive gap, 2018-2023, confirmed via bhavcopy volume) | 11 |
| NO_TOKEN (unresolved after recovery) | 21 |

**Total: 552.** Final usable sample for DEV/TEST: **498** (Section 2).

## Process Step 4: five hand-traced DEV-window cases, before any aggregate

All five independently verified by hand against `PREREGISTRATION_IPO.md`
Section 5's frozen rules before any aggregate number was computed, via
`scripts/ipo_listing_handtrace.py`.

### 1. TARGET hit -- Ola Electric Mobility Ltd. (OLAELEC), listed 2024-08-09

First candle (10:00): open=74.65, high=76.55, low=74.63, **close=76.34**
-- green (close > open). Fill at next candle's (10:01) open = **76.28**.
qty = floor(500/(76.28*0.05)) = floor(131.13) = **131**. Stop =
76.28*0.95 = **72.466**. Target = 76.28*1.125 = **85.815**. Scanning
forward, the 10:27 bar's high reaches target -> **TARGET**, exit_price
= 85.815 (the level itself, bar's own open was below it). pnl =
131*(85.815-76.28) = **Rs 1,249.085**. position_size = 131*76.28 =
Rs 9,992.68. **net_r (7bps) = 2.4300**.

### 2. STOP hit -- Global Surfaces Ltd. (GSLSU), listed 2023-03-23

First candle (10:00): open=166.00, close=**168.10** -- green. Fill at
10:01 open = **169.10**. qty = floor(500/(169.1*0.05)) = **59**. Stop =
169.1*0.95 = **160.645**. Target = 190.2375. At 10:20 the bar's low
breaches stop AND its own open (160.00) is already below the stop level
-- gapped through, fills at that bar's **open = 160.00**, not the stop
level. pnl = 59*(160.00-169.10) = **-Rs 536.90**. position_size =
Rs 9,976.90. **net_r (7bps) = -1.1419**.

### 3. 15:15 TIME_EXIT -- PSP Projects Ltd. (PSPPROJECT), listed 2017-05-29

First candle (11:36): open=190.00, close=**199.50** -- green (this
listing's archived bars are sparse/gapped -- 11:36, 11:40, 11:53... --
consistent with a very thinly-traded early session; `resolve_exit`
makes no assumption of one row per minute). Fill at next archived bar
(11:40) open = **199.50**. Stop=189.525, target=224.4375. Price never
moves off 199.50 for the rest of the archived day -- neither level is
ever touched. The archive has no bar exactly at ts=15:15 that day, so
the fallback fires (`time_exit_fallback=True`): exits at the latest bar
at or before 15:15, which is **15:14, close=199.50** -- unchanged from
entry. pnl = 50*(199.50-199.50) = **Rs 0**. **net_r (7bps) = -0.0681**
(cost alone, on a flat trade).

### 4. SKIPPED (red/flat first candle) -- HPL Electric & Power Ltd. (HPL), listed 2016-10-04

First candle (09:44): open=190.00, **close=190.00** -- flat
(close == open, fails the `close > open` green test). **No trade this
day**, per the frozen rule.

### 5. SCALE-CORRECTED listing -- Indian Energy Exchange Ltd. (IEX), listed 2017-10-23

Demonstrates the scale-correction fix (Section 3) mattering for the
actual ENTRY price, not just the validation step: Angel's AS-FETCHED
first bar (revision_seq=1, split-adjusted for a later ~10:1 corporate
action) shows open=**150.00**, close=161.64. The RAW-CORRECTED bars
(revision_seq=2, scale factor 9.9997, matching this listing's own
factor already logged in Section 3) show the SAME first candle as
open=**1499.95**, close=1616.35 -- still green either way, but at the
TRUE 2017 listing-day price level, consistent with IEX's real
historical listing price (~Rs 1500-1600) before its later split. Fill
at next bar (10:18) open = **1617.05**. qty = floor(500/(1617.05*0.05))
= **6**. Stop=1536.20, target=1819.18. Neither hit; **TIME_EXIT** at
15:15, exit_price=**1631.85**. pnl = 6*(1631.85-1617.05) = **Rs
88.80**. **net_r (7bps) = 0.1114**. Had the as-fetched (unscaled)
price been used instead, qty would have been computed on a ~10x-wrong
entry price (floor(500/(161.70*0.05))=61, not 6) -- an order-of-
magnitude sizing error this fix specifically prevents.

## Process Step 5: DEV run -- NO EDGE, study closes

**Bad result, stated first, per discipline**: DEV fails EVERY gate
criterion in `PREREGISTRATION_IPO.md` Section 9, and fails them
decisively, not marginally. **The sample is also far too small to have
concluded anything else**, a limitation stated prominently rather than
glossed past: of 299 DEV-window usable listings, only **41 produced a
trade** (37 distinct days) -- 256 were skipped for a red/flat first
candle, 2 had no second archived bar to fill at (`NO_FILL_BAR`), 0 hit
the zero-qty floor. **MDE = 0.3599** -- at n=41 trades/37 days, this
study could only have detected a true effect of **>=0.36R per trade** as
statistically distinguishable from zero. That is an enormous effect
size threshold (far larger than any edge this project has found
viable elsewhere); a small-to-moderate real edge would be
statistically invisible at this sample size regardless of whether it
exists. This is the single most important number in this report and is
stated here, prominently, before any other result.

**Entries are rare and concentrated in just 4 of 9 DEV calendar years**:
0 entries out of 58 2021 listings (the single busiest IPO year in the
DEV sample), 0/20 in 2018, 0/12 in 2020, 0/32 in 2022, 0/6 in 2016 --
every listing in those five years had either a red/flat first candle or
no second bar to fill at. Entries occurred only in 2017 (3/31), 2019
(1/15), 2023 (14/51), 2024 (23/73).

**Gate components, all five False**:

| Criterion | Result | Pass? |
|---|---|---|
| Mean net R > 0, 97.5% CI excludes zero | mean=-0.1488, CI=[-0.4833, 0.2323] (includes zero) | **False** |
| >=95th percentile vs TIMING null | 82.5th percentile | **False** |
| >=95th percentile vs SELECTION null | 0.0th percentile | **False** |
| Still > 0 after dropping single best year | drops 2019 (n=1, mean 0.224) -> mean=-0.1581 | **False** |
| Still > 0 at 2x cost (14bps) | mean=-0.1625 | **False** |

**Win rate 31.71%** (13/41). **Median net R -0.0679** (descriptive).
**Exit mix**: TIME_EXIT 22 (53.7%), STOP 17 (41.5%), TARGET 2 (4.9%) --
`time_exit_fallback` fired once.

**By calendar year (net R, 7bps)**: 2017 +0.194 (n=3), 2019 +0.224
(n=1), 2023 -0.292 (n=14), 2024 -0.122 (n=23). The two years with any
real trade volume (2023, 2024 -- 37 of the 41 trades) are BOTH
negative; the two positive years are single-digit-trade noise.

**Cost sensitivity, mean net R**: 7bps (floor) = -0.1488, 14bps (2x) =
-0.1625, 28bps (4x) = -0.1901. Negative and worsening at every level --
not a borderline result sensitive to the cost assumption.

**TIMING null**: 1000 seeds (preflight projected 639.8s for the full
1000, comfortably under the 1-hour budget, so no fallback to 500 was
needed). Real strategy's mean sits at the **82.5th percentile** of
1000 random-entry-timing draws on the same 41 listing-days -- better
than most random draws, but well short of the 95th-percentile bar.

**SELECTION null (the primary null, per instruction)**: built from
entering ALL 296 DEV-window usable listings at the open of the candle
after the first (regardless of colour; 299 - 296 = 3 lost to
`NO_FILL_BAR`/`ZERO_QTY` under this alternate rule too), bootstrapped
10,000 times. **That alternate's own mean net R is +0.0920 -- positive,
while the real, green-filtered strategy's mean is -0.1488.** The real
strategy's observed mean sits at the **0.0th percentile** of the
alternate's bootstrap distribution: buying every listing indiscriminately
beats being selective about the first candle's colour, in every one of
10,000 resamples. **This is the single clearest, worst result in this
study**: the green-candle filter this hypothesis is built around does
not merely fail to add value over indiscriminate buying -- it actively
subtracts value, in-sample, in DEV.

**DEV_PASS = False. Per `PREREGISTRATION_IPO.md` Section 9, the study
closes. The sealed TEST window (199 listings, from 2024-12-06) is never
read.** No rule is retried at other values (Section 12) -- the 5% stop,
12.5% target, and first-archived-candle entry interpretation are FIXED
and this result stands as reported.

## Status

**>>> STUDY CLOSED, per `PREREGISTRATION_IPO.md` Section 9/Process Step
5.** DEV fails all five gate criteria; the sealed TEST window is never
read. This is a genuine first-exposure holdout result (Section 0/
Provenance) -- not a forward-discipline DEV pass/fail the way Fibo/Box/
FVG's own re-exposed-data results are -- so this closure carries the
same standing as any of this project's other NO-EDGE closures.
