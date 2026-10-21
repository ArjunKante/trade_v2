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
before any Phase 2 rule touches the data. 501 of 552 identified listings
(90.8%) now have usable, bhavcopy-cross-validated 1-minute data.

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
- **21 / 501 final usable sample = 4.19%** -- under the 5% prominence
  threshold `PREREGISTRATION_IPO.md` Section 3a sets, but close enough
  to it that it is stated here plainly rather than waved past. The
  direction remains as recorded before this number existed: dropping
  these listings biases the usable sample toward IPOs that survived
  cleanly to 2026, which flatters this study's own result.

### 2. DEV/TEST boundary -- frozen, sealed, reported before any rule runs

On the 501 usable (`OK`) listings, split chronologically 60/40 by
listing date:

| | count | listing-date range |
|---|---|---|
| **DEV** | 301 | through **2024-11-27** |
| **TEST (sealed)** | 200 | from **2024-11-29** onward |

Frozen in code at `ipo_listing.test_seal` (`SEALED_AT = 2026-10-22`,
the day Phase 1's fetch completed), same `guard_date_range`/
`authorize_test` mechanism as `box_theory.test_seal`, its own
independent access log. Not read unless DEV passes
`PREREGISTRATION_IPO.md` Section 9's gate AND the user explicitly
approves.

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

**Mismatch rate AFTER correction: 52.89%** -- barely moved, which is
itself the real finding: the scale bug explained only a fraction of the
60.28%. The REMAINING ~53% is overwhelmingly tiny and not a sign of bad
data: post-correction, median difference on every OHLC field is
~0.00%, 90th-percentile difference is under 1% on three of four fields,
and **75% of all 501 listings match bhavcopy within 0.5% on BOTH open
and close**. The headline "mismatch rate" is almost entirely an
artifact of the EXISTING 0.1% tolerance (`fibo.validation`'s own
default, calibrated for box theory's liquid top-200 names on ordinary
trading days) being far tighter than a listing day's own special
pre-open call-auction and early price-discovery noise warrants -- 209 of
501 differ by only 0.1-1%, a further 53 by 1-5%, and only **3 listings
(0.6%) differ by more than 5%**, named below rather than hidden in the
aggregate:

| Company | Date | open diff | low diff | close diff |
|---|---|---|---|---|
| Archean Chemical Industries | 2022-11-21 | 44.2% | 100.0% | 0.0% |
| Five-Star Business Finance | 2022-11-21 | 36.0% | 100.0% | 0.2% |
| Yatharth Hospital & Trauma CARE | 2023-08-07 | 34.7% | 100.0% | 0.9% |

All three share the same `low_pct_diff = 100%` signature with a
near-perfect close match -- consistent with a single spurious near-zero
LOW tick in one feed on that specific day (a known broker-feed artifact
type, not re-investigated further here), not a scale or identification
problem. Not excluded from the usable sample; flagged for awareness
going into Phase 2's hand-traces.

**This project's existing 0.1% tolerance is not loosened here** --
that is a methodology decision for the user, not mine to make silently;
the number above is reported as computed, with the diagnosis attached so
it is not read as "the data is unreliable" when the evidence says
otherwise.

### 4. Fetch losses -- two different kinds, kept separate per instruction

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
  (2023-12-26). This is a THIRD, distinct kind of gap -- not the 2016
  floor, not a token-resolution/survivorship issue (every one of these
  had a valid, current Angel token) -- an isolated archive hole on that
  specific day for an otherwise-covered instrument. Not investigated
  further; named here rather than folded into either of the other two
  categories.

### Final status breakdown (552 identified listings)

| status | count |
|---|---|
| OK (usable) | 501 |
| FETCH_FAILED (2016 archive floor) | 19 |
| FETCH_FAILED (isolated archive gap, 2018-2023) | 11 |
| NO_TOKEN (unresolved after recovery) | 21 |

## Status

**>>> STOPPING HERE, per the user's explicit instruction and
`PREREGISTRATION_IPO.md` Process Step 3/4 boundary.** No hand-trace has
been performed and no DEV backtest code exists yet. The three items
above are reported for review before anything further is built or run.
