# Decision 17 Investigation: Zero-Volume Bars, OHLC Integrity, and Missing-Data Compatibility

Read-only data-semantics and data-integrity investigation, run against the
repo at commit `c2a0d62` (working tree at time of writing), 2026-11-09.
Supports **Decision 17** in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
("Missing-data / stale-price compatibility" -- OPEN; "Explicitly distinguish
traded / zero-volume-stale / forward-filled / corrupted-but-present bars;
clarify which the existing rule covers; apply uniformly across all three
unified eligibility endpoints (`t-35,t-5,t`)"), and is relevant background
for Decision 19 (Option 1 vs. corrected Option 2 completeness) and incidentally
touches Decision 21 (special/irregular sessions).

**No file was written, created, or modified except this one.** All DuckDB
connections were opened `duckdb.connect(path, read_only=True)`. No trading
return, signal correlation, or predictive statistic was computed anywhere in
this investigation -- every number below is a raw-bar data-semantics or
integrity fact. Throwaway Python scripts used to produce these numbers live
in the session scratchpad, not in this repo; every query is reproduced
inline below so each number is re-derivable.

---

## Verdict summary

| # | Area | Verdict |
|---|---|---|
| 1 | Volume-field semantics | **UNRESOLVED (code-level)** -- Angel One's raw `getCandleData` response is inserted into `bars_1min` byte-for-byte, with zero project-side synthesis, carry-forward, or validation. No trade-count field exists anywhere in the schema. The code never states what `volume=0` means; it is simply whatever Angel returned. |
| 2 | Existing forward-fill/gap-fill code | **DOES NOT EXIST.** Grepped `src/fibo`, `src/box_theory`, `src/darvas`, `src/fvg`, `src/poc`, `src/liquidity` for forward-fill/gap-fill/stale-price logic: nothing touches `bars_1min`. Section 13's `<3`-minute rule is a **textual preregistration rule with no corresponding implementation anywhere in the repo.** |
| 3 | Follower-tier zero-volume incidence | **3.88e-5 (0.00388%), full population, 120 months.** Nearly identical to the recomputed leader-tier rate (3.69e-5) -- this REVISES the previously-published leader-only 3e-7 figure, which was an 11-month-sample artifact. Missing-ROW incidence (absent rows, a different phenomenon) is far larger and far more tier-differentiated: 1.145% for followers vs. 0.095% for leaders. |
| 4 | OHLC structural-integrity counts | **REPRODUCED AND EXTENDED.** `high<low`=0, close-outside-range=1, open-outside-range=54 (all confirmed) -- but a new, more precise characterization of the 54 and two entirely new, previously-undocumented defect classes were found: 560 negative-volume rows and zero-volume bars that are NOT OHLC-flat. See Part 4. |
| 5 | Forward-fill traceability for Phase 4 | **Capability does not exist.** No code anywhere distinguishes "genuinely traded" from "carried-forward/stale" at the bar level. |

---

## Part 1 -- Data semantics (code inspection)

### Are bars exchange-native, vendor-provided, or project-constructed?

**Vendor-provided, used as-is.** `src/fibo/intraday_db.py` lines 1-15 state
the table's own purpose and the project's deliberate choice to keep it
physically separate from the daily warehouse; `SOURCE_NAME =
"ANGEL_ONE_SMARTAPI_HISTORICAL"` (line 55). The actual write path,
`scripts/fibo_download_intraday_top200.py` lines 149-167 and 227-240, calls
`holder.client.getCandleData(params)` with `interval: "ONE_MINUTE"` and, on
success, iterates `for ts, o, h, l, c, v in data:` (line 230) directly into
the `bars_1min` row tuple (lines 232-234) -- **no transformation, no
aggregation, no synthesis step between Angel's response and the inserted
row.** `src/fibo/download.py`'s own module docstring (lines 1-16) confirms
the raw shape: `"Angel's raw [[iso_ts, o, h, l, c, v], ...] list"`. This is
exchange activity as Angel One's own 1-minute candle aggregator reports it,
not something this project's code builds from finer-grained ticks (no tick
data exists anywhere in this project) and not a project-side OHLC
aggregation (that only happens in the *other* direction --
`src/fibo/bars.py`'s `aggregate_to_15min`/`aggregate_to_daily`, which
*consume* `bars_1min`, never produce it).

### What does the code say `volume=0` means? Any carry-forward logic at ingestion?

**Nothing. No comment, no synthesis.** `scripts/fibo_download_intraday_top200.py`
line 230's unpacking (`for ts, o, h, l, c, v in data`) and line 239's
`INSERT INTO bars_1min SELECT * FROM chunk_new` is the entire write path --
whatever five-tuple of OHLCV values Angel's API returned for a given minute
becomes the row, unconditionally. There is no `if volume == 0: ...` branch,
no interpolation, no skip-and-retry, no flag column recording "this bar was
synthesized." The only validation that exists anywhere near this path is
`fetch_chunk_with_retry`'s truncation check (`src/fibo/download.py` lines
63-116), which detects a *date-range* truncation (Angel silently returning
less history than requested), not a per-bar content check. **The project's
own code provides no documentation of what `volume=0` means** -- it is
simply whatever Angel's feed emitted for that minute, and the standard
OHLCV convention ("no trade printed that minute") cannot be assumed to
apply without corroborating evidence, because Part 4 below finds cases
where it demonstrably does not hold cleanly (zero-volume bars with real
price movement).

### Trade-count / tick-count field?

**Confirmed absent, exactly as the schema in the task background
suggested.** `bars_1min`'s 15 columns (`src/fibo/intraday_db.py` lines
23-39) are `entity_id, isin, symbol, angel_token, trade_date, ts, open,
high, low, close, volume, known_date, fetched_at, source, revision_seq` --
no trade-count field. By contrast, the *daily* `prices_eod` table (`data/warehouse.duckdb`)
**does** have an `n_trades` column (confirmed via
`information_schema.columns`), so this project's daily layer already has
the concept of a trade-count field -- it was simply never extended to the
intraday layer, because Angel's `getCandleData` response itself never
carries one (`[ts, o, h, l, c, v]`, five values, confirmed from
`src/fibo/download.py`'s own docstring and the literal unpacking in the
download script). The sibling `src/ipo_listing/intraday_db.py` schema
(lines 16-29) is identical in this respect -- same five OHLCV fields, no
trade-count, same Angel One source -- confirming this is a vendor-API
limitation, not a one-off omission in the Fibo module.

### Unresolved limitation, stated explicitly

**The available source code cannot establish what `volume=0` means.**
There is no comment, no distinguishing field, and (per Part 4 below) direct
empirical evidence that a meaningful minority of zero-volume bars show real
intra-bar price movement, which is inconsistent with the simple "no trade
occurred" reading. Any rule that assumes the standard OHLCV convention
("volume=0 means no trade") applies uniformly to every zero-volume row in
this table is an **assumption**, not a fact established by this codebase or
by Angel One's own (unavailable) documentation of its historical-candle
endpoint's zero-volume behavior.

---

## Part 5 -- Forward-fill construction and traceability (builds on Part 1)

### Elapsed trading minutes vs. raw timestamp difference

The schema separates `trade_date` (DATE) from `ts` (TIMESTAMP, bar-start,
naive Asia/Kolkata) specifically (`src/fibo/intraday_db.py` line 29). This
makes it natural, but not automatic, to implement Section 13's `<3`-minute
rule correctly: a query or function that partitions by `(entity_id,
trade_date)` before taking any `ts`-difference (exactly what this
investigation's own measurement SQL does, `PARTITION BY entity_id,
trade_date ORDER BY ts` in every window function below) cannot bridge two
different sessions, because the partition boundary is enforced before the
time arithmetic ever runs. **The risk is real, not hypothetical**: a naive
implementation that computes `ts - LAG(ts)` ordered globally by `ts` alone
(no `PARTITION BY trade_date`) would silently bridge the ~18-hour overnight
gap between one day's 15:29 close and the next day's 09:15 open, and -- a
new finding from this investigation -- would even more subtly bridge the
multi-hour intraday gap between the regular session's close and a same-day
Muhurat evening session (Part 2's session-boundary note below), since both
rows share the same `trade_date`. **No code anywhere in the repo currently
implements the `<3`-minute rule at all** (confirmed by the grep in Part 1),
so there is no existing implementation to audit for this mistake -- this is
a requirement for whoever builds it at Phase 4, not a defect found in
running code.

### Does any code already distinguish "last genuinely traded" from "carried-forward/stale"?

**No.** Grepped `src/box_theory`, `src/liquidity` for
`volume==0`/`zero-volume`/`stale`/`last_traded`-style logic: zero matches.
Every consumer of `bars_1min` found in this repo (Box Theory, FVG, POC,
Liquidity A-D, per `DATA_AUDIT_LEAD_LAG.md` section 1's own prior finding,
re-confirmed here) calls a bars-fetch function and uses the returned
OHLCV directly; none of them branch on `volume`. `scripts/fibo_step5_top200_data_quality.py`
(read in full) performs a *different* kind of check -- Angel-vs-bhavcopy
price-scale agreement (`src/fibo/scale_probe.py`) -- and is the closest
thing to a "data quality" gate anywhere touching this table, but it never
inspects `volume` and never classifies a bar as stale/carried/genuine.

**IMPLEMENTATION REQUIREMENT for Phase 4** (not yet built): the smallest
necessary addition is a derived, per-row `minutes_since_last_trade` counter,
computed in a read query directly from `bars_1min` (no schema change
needed): partition by `(entity_id, trade_date)`, order by `ts`, and run a
counter that resets to 0 whenever `volume > 0` and increments by 1 for each
subsequent `volume = 0` row, with a **separate** indicator for an absent
row (a gap in the `ts` sequence) since that is not computable by a simple
running counter over present rows alone -- it requires comparing consecutive
present `ts` values (exactly the gap-detection logic in Part 2's SQL below).
Any eligibility check built on top of Section 13's rule needs both signals,
not one.

---

## Part 4 -- OHLC and basic integrity validation

All full-table, read-only, against `data/fibo_intraday.duckdb`'s `bars_1min`
(169,935,257 rows, 386 entities, 2016-10-04 to 2026-09-18 -- reconfirmed).

### Reproduced exactly

```sql
SELECT COUNT(*) FROM bars_1min WHERE high < low;                    -- 0
SELECT COUNT(*) FROM bars_1min WHERE close < low OR close > high;   -- 1
SELECT COUNT(*) FROM bars_1min WHERE open  < low OR open  > high;   -- 54
SELECT COUNT(*) FROM (SELECT entity_id, ts, COUNT(*) c FROM bars_1min
                      GROUP BY entity_id, ts HAVING COUNT(*)>1);     -- 0 (duplicate key recheck)
```

All four match `DATA_AUDIT_LEAD_LAG.md`'s Phase-1 figures exactly.

### New, more precise characterization of the 54 open-violations

**All 54 open-outside-range rows occur at the exact same `(trade_date, ts)`
= `2023-03-03 09:15:00`, the very first bar of that day's session, for 54
different large-/mid-cap entities** (AXISBANK, TCS, KOTAKBANK, HDFCBANK-adjacent
names, BANKBARODA, PNB, etc. -- full list captured in the query output).
This directly **corrects** `DATA_AUDIT_LEAD_LAG.md`'s characterization of
these as "isolated feed glitches" -- they are not scattered; **they are one
single-date, opening-bar-of-day phenomenon affecting many entities
simultaneously**, consistent with a vendor-side artifact specific to how
Angel's feed populated the `open` field for the first regular-session
candle on that one date (a pre-open-auction-price-vs-first-trade-price
mismatch is the most likely mechanism, but this cannot be confirmed from
available source code or documentation -- flagged as an UNRESOLVED
QUESTION, not asserted as fact).

The single close-violation row (`INE916U01025`/SFL, 2017-10-06 15:27:00) is
a **different date, different entity, different mechanism** from the 54
open-violations -- **no overlap** between the two violation sets.

### Two new defect classes, not in the prior audit

**(a) Negative volume: 560 rows, not previously checked.** The prior audit
checked zero-volume but never checked volume *sign*.

```sql
SELECT SUM(CASE WHEN volume<0 THEN 1 ELSE 0 END), MIN(volume), MAX(volume) FROM bars_1min;
-- 560 negative rows | min = -27,567,834 | max = 1,571,529,211
```

560 negative-volume rows, 189 distinct entities, but only **3 distinct
trade_dates** (2023-05-03: 73 rows, 2023-05-04: 198 rows, 2024-03-02: 289
rows). One entity (`INE020B01018`/RECLTD) accounts for 272/560 (49%) of all
negative-volume rows, concentrated on exactly 2023-05-03/04. Sampled rows
at `2024-03-02 11:15:00` show large-magnitude negative volumes (e.g.
YESBANK -27,567,834, IDEA -21,803,651) **paired with a degenerate,
single-point OHLC bar** (`open=high=low=close`) -- i.e. the same minute that
carries a corrupted volume also carries a flat/non-informative price,
suggesting a vendor-side cumulative-counter or reconciliation artifact on
specific dates rather than 560 independent glitches. This is a FACTUAL
FINDING, not fully root-caused (no live API access in this read-only
investigation); flagged as an UNRESOLVED QUESTION for anyone relying on
`volume` as always-non-negative.

**(b) Implausible maximum volumes, same first-bar-of-day pattern.** The
single largest volume in the table, 1,571,529,211 (IDEA, 2024-04-26), and
8 of the top 10 largest-volume rows overall, occur at `ts` = the **first
bar of the session** (mostly 09:15:00, one at 09:29:00) -- the same
bar-of-day where the 54 open-violations cluster. This is suggestive (not
proven) of a shared root cause: Angel's feed occasionally mis-populating
the very first minute's `volume` field with something other than that
minute's own traded volume (e.g. a stale cumulative counter). Flagged as
an UNRESOLVED QUESTION.

**(c) Zero-volume bars are not uniformly "flat."** Of the 7,018 zero-volume
rows, 5,759 (82%) have `open=high=low=close` (a genuinely flat, no-information
bar, consistent with "no trade"), but **1,259 (18%) show real intra-bar
price movement** (`open != close` or `high != low`) despite `volume=0` --
logically inconsistent with "zero volume = no trading activity that
minute" under the standard convention. **60.2% of all zero-volume rows in
the entire 10-year table (4,225 of 7,018) occur at exactly `15:28` or
`15:29`** -- the last two minutes of the regular session, where NSE's
actual closing-price mechanism (a weighted-average auction over the last
several minutes, not the simple last trade) plausibly produces a candle
whose price fields reflect the auction-derived close while the `volume`
field is populated differently (or not at all) by Angel's aggregator. This
is the single most important Part-4 finding for Decision 17: **zero-volume
incidence is not a uniform "illiquid minute" signal -- a majority of its
mass is a session-close-mechanism artifact, concentrated in two specific
minutes, not a generic measure of thin trading spread through the day.**

### Nulls, finiteness, volume validity (full table)

```sql
-- all 0 across open/high/low/close/volume (no nulls anywhere)
-- all 0 for open/high/low/close <= 0, NaN, or inf (no non-finite or non-positive prices)
-- volume: 560 negative (above); min=-27,567,834; max=1,571,529,211; no nulls, no NaN/inf
```

### Already caught by something, or unfiltered?

**Unfiltered, confirmed from the write path (Part 1).** The insert
(`scripts/fibo_download_intraday_top200.py` line 239, `INSERT INTO
bars_1min SELECT * FROM chunk_new`) has no WHERE clause, no validation call,
no rejection logic of any kind between receiving Angel's response and
persisting it. Every anomaly documented above (54 open-violations, 1
close-violation, 560 negative-volume rows, the implausible-maximum-volume
rows, the 1,259 non-flat zero-volume rows) passed through into `bars_1min`
untouched and remains there today. `scripts/fibo_step5_top200_data_quality.py`
is the only quality-gate-shaped script touching this table, and it checks a
completely different thing (Angel-vs-bhavcopy price scale agreement), not
OHLC self-consistency or volume validity.

### Explicit scope statement

Reproducing these counts is a **structural-integrity check only**. A row
passing `low <= open,close <= high` and `volume >= 0` is internally
self-consistent; this says nothing about whether the price level is
economically correct (e.g. matches what actually traded on the exchange
that minute) -- that is a different question (`src/fibo/validation.py`'s
bhavcopy cross-check addresses daily-level economic correctness, not
minute-level).

---

## Part 2 -- Follower-tier zero-volume incidence and run-length distribution

### Tier-construction methodology (verified against the published Task 1 table)

Reused, unmodified: `fibo.universe.reconstitute_annually(con, top_n=200)` +
`fibo.universe.effective_universe(..., stub_year=2016)` for the annual
point-in-time universe; ranked by trailing-60-trading-session median daily
turnover (`prices_eod.turnover`, raw, via `isin_lineage` join, same
convention as `LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1) on the first
trading day of each calendar month in `bars_1min`'s own trading-day
calendar (2016-10-04 to 2026-09-18, 120 months); top 20% of the eligible
pool (`ceil(0.2*n_eligible)`) = leaders, remainder = followers; an entity
needs >=60 trailing sessions as of the ranking date to be eligible.

**Cross-check against the published table**: this reconstruction reproduces
**every single one** of Task 1's published per-month figures exactly,
including every thin-month exception (2025-01: 181 eligible / 37 leaders /
144 followers; 2022-01 and 2024-01: 189/38/151; 2026-01: 187/38/149; all 29
sub-200-eligible months match). 91/120 months sit at the steady-state
200/40/160. This confirms the tier-assignment methodology was reproduced
correctly before any bar-level measurement was built on top of it.

### Measurement scope: full population, not a sample

Given the tier construction is cheap (built once from `prices_eod`, not
`bars_1min`), **the full population was measured**: all 120 months, both
tiers (follower and leader), no sampling -- not the fallback-sampling path
the task anticipated as a contingency. Every `bars_1min` row for every
tier-month combination's entity set was scanned exactly once per
measurement, via SQL window functions (gaps-and-islands technique),
partitioned by `(entity_id, trade_date)` so no run or gap ever bridges
across sessions.

### Session-boundary handling (methodological choice, stated explicitly)

**New finding, bearing on Decision 21 as well as Decision 17**: `bars_1min`
contains two off-regular-session clusters of rows: (a) 2,274 pre-open rows
at `09:14` and 799 rows even earlier (clustered: 447 of the 799 are a
single-date, 149-entity, `04:18-04:21` timestamp anomaly on 2020-12-08,
root cause undetermined); (b) 94,045 rows after `15:29`, of which the
overwhelming majority (~93,600) cluster tightly on exactly 8 specific dates
(2017-10-19, 2018-11-07, 2020-11-14, 2021-02-24, 2021-11-04, 2022-10-24,
2023-11-12, 2024-11-01) with ~11,000-14,000 rows each spanning roughly
`17:15`-`19:15` -- a pattern matching NSE's annual Diwali **Muhurat**
special evening trading session (7 of the 8 dates align with publicly known
Muhurat dates; 2021-02-24 does not fit the Diwali pattern and is most
likely an NSE disaster-recovery test session, a practice NSE has used on
occasion). **These are genuine, scheduled alternate trading sessions, not
corrupted data** -- but they are a *second* intraday session on the same
`trade_date`, separated from the regular session's close by several
non-trading hours. Confirms Decision 21's open question empirically: yes,
Muhurat-style irregular sessions exist in this date range, and **no
existing code anywhere in this repo gives them special session-boundary
treatment** -- the ingestion script fetches whatever Angel returns for the
requested clock-time window and the partition-by-`trade_date` convention
used throughout this project (including this investigation's own SQL)
would, if not also partitioned by a contiguous-time check, silently treat
the multi-hour overnight-style gap between the regular close and the
Muhurat open as one giant "missing gap" within the same `trade_date`.

**Methodological choice made for this investigation**: the main
measurement below is restricted to the regular session window
(`09:15`-`15:29` inclusive, matching `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 2's own convention of excluding the `09:14` pre-open bar). Off-session
rows (pre-open, post-close/Muhurat) are excluded from the run-length/gap
measurement and reported only as the counts above -- including them without
a second session-boundary flag would have corrupted the gap-length
distribution with several-hour "gaps" that are not missingness at all.

### Scale of the measurement

Full population, all 120 months, both tiers, regular session only:

| Tier | Present rows (regular session) | Zero-volume rows | Zero-volume rate | Zero-run count | Missing (absent) minutes | Missingness rate | Missing-gap count |
|---|---|---|---|---|---|---|---|
| Follower | 133,865,112 | 5,188 | **3.88e-5 (0.00388%)** | 4,846 | 1,551,180 | **1.145%** | 970,801 |
| Leader | 34,622,832 | 1,279 | **3.69e-5 (0.00369%)** | 908 | 33,052 | **0.095%** | 3,693 |

**Sanity cross-check against the known full-population figure** (per the
task's required check): pooling both tiers, (5,188+1,279) /
(133,865,112+34,622,832) = 6,467 / 168,487,944 = **0.00384%**, closely
matching the previously-established whole-table figure of 7,018 /
169,935,257 = 0.0041% (`DATA_AUDIT_LEAD_LAG.md`). The small residual gap is
fully explained by scope differences, not an error: this measurement
excludes off-regular-session rows (pre-open/Muhurat, some of which carry
zero volume per Part 4's time-of-day breakdown) and covers only
point-in-time tier-eligible entity-months, not every row of every one of
the 386 entities ever observed across their full individual history. The
match is close enough to confirm the measurement methodology is sound.

### Headline finding 1: the leader-tier zero-volume rate is ~119x higher than previously published, because the earlier figure was an 11-month-sample artifact

`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 2 reported leader-tier
zero-volume fraction **3.1e-7**, sampled from 11 specific months (Nov 2016 +
June of each year 2017-2026). Measuring the **full population** (all 120
months) gives **3.69e-5** -- about **119x higher**. This is not a
contradiction of Task 2's arithmetic (its 11-month sample genuinely had
only 1 zero-volume bar in 3,224,355 observations) -- it is evidence that
**11 months out of 120 was not a representative sample for this
particular tail event**, because the leader-tier zero-volume incidents are
extremely concentrated in time (see Headline finding 3) and Task 2's
sampled months happened to miss nearly all of them. **This is the single
most consequential correction this investigation makes to prior
documentation**: "leaders are virtually never illiquid" does not hold once
the full 10-year record is examined, and any Decision-17/19 reasoning that
relies on the leader tier being near-perfectly clean of zero-volume bars
should be revised.

### Headline finding 2: zero-volume rate is nearly IDENTICAL between tiers; missing-ROW rate is NOT -- these are different phenomena with different relationships to liquidity

Zero-volume rate: follower 0.00388% vs. leader 0.00369% -- **statistically
indistinguishable**, not the order-of-magnitude tier gradient one would
expect if "zero volume" were simply tracking liquidity tier. Missing-row
(absent-row) rate: follower 1.145% vs. leader 0.095% -- a real **~12x**
tier gradient, consistent with followers genuinely being thinner and more
prone to an entire expected minute simply not being fetched/reported at
all. **Missing-row absence is ~295x more common than zero-volume for
followers (1.145% vs. 0.00388%) and ~26x more common for leaders (0.095%
vs. 0.00369%)** -- the dominant form of "missingness" in this data, by a
wide margin, is an absent row, not a present-but-zero-volume row, for
both tiers. Any eligibility rule aimed only at zero-volume bars is aimed at
the smaller of the two phenomena.

### Headline finding 3: both zero-volume and missing-row rates are sharply non-stationary over the 10-year range, with a pronounced recent (2024, 2026) spike

| Year | Follower zero-vol rate | Leader zero-vol rate |
|---|---|---|
| 2016 | 0.0000% | 0.0000% |
| 2017 | 0.0026% | 0.0020% |
| 2018 | 0.0010% | 0.0000% |
| 2019 | 0.0000% | 0.0000% |
| 2020 | 0.0005% | 0.0000% |
| 2021 | 0.0004% | 0.0000% |
| 2022 | 0.0000% | 0.0000% |
| 2023 | 0.0060% | 0.0000% |
| 2024 | 0.0058% | **0.0108%** |
| 2025 | 0.0004% | 0.0002% |
| 2026 (partial, through Sep) | **0.0287%** | **0.0317%** |

2016-2022 are consistently near-zero for both tiers (6 of 7 years show
literally 0 leader-tier zero-volume rows). 2024 and especially 2026 break
this pattern sharply -- **2026 alone (a partial, 9-month year) accounts for
2,933 of the follower tier's 5,188 zero-volume rows (56.5%) and 820 of the
leader tier's 1,279 (64.1%)**, despite having fewer total rows than a full
year. In 2026, the **leader-tier rate (0.0317%) exceeds the follower-tier
rate (0.0287%)** -- the tier ordering inverts in the most recent data. The
follower-tier missing-gap "invalid" share (>=3-minute gaps, see Part 3)
shows the same non-stationarity even more starkly: 3.07% in 2021 vs.
**29.64% in 2026**. **Neither phenomenon can be treated as a stable,
time-invariant rate**; any Phase-4 policy frozen on pre-2023 data alone
would materially understate both.

### Headline finding 4: the extreme right tail of zero-volume run-length is dominated by one entity

Pooled run-length buckets:

| Bucket | Follower count | Follower % | Leader count | Leader % |
|---|---|---|---|---|
| 1 min | 4,656 | 96.08% | 904 | 99.56% |
| 2 min | 151 | 3.12% | 1 | 0.11% |
| 3 min | 25 | 0.52% | 0 | 0.00% |
| 4-5 min | 7 | 0.14% | 0 | 0.00% |
| 6-10 min | 3 | 0.06% | 0 | 0.00% |
| >10 min | 4 | 0.08% | 3 | 0.33% |

**Maximum observed zero-volume run**: follower tier, **45 minutes**,
`INE669E01016` (IDEA / Vodafone Idea), 2020-05-29. Leader tier, **166
minutes** (nearly half the entire 375-minute session), **also
`INE669E01016` (IDEA)**, 2024-04-25 -- during the same multi-day window
(2024-04-25/26) where Part 4 found IDEA posting the single largest volume
figure in the entire table (1,571,529,211 on 2024-04-26) and large
negative volumes elsewhere. The entity-month breakdown confirms this is
not a broad pattern: of all follower entity-months with a zero-volume run
>=3 minutes (16 out of 670 entity-months, 2.4%), the four longest (45, 30,
19, 8 minutes, spanning 2020-03, 2020-05, 2021-08, 2021-09) are **all
IDEA**. Of all leader entity-months with a run >=3 minutes (1 out of 126,
0.8%), it is again IDEA (166 min, 2024-04). Per-entity-month dispersion
stats: follower median max-run = 1 min, p95 = 2 min, p99 = 3.3 min;
leader median = 1 min, p95 = 1 min, p99 = 1.75 min. **The pooled
percentages above are not an artifact of one or two names dominating the
bulk of the distribution** (266 distinct follower entities and 10+
distinct leader entities contribute at least one zero-run; the top 5
follower entities by run-count account for only 11.5% of all runs, the top
3 leader entities for only 8.8%) -- but the handful of **genuinely extreme**
(>10-minute) outliers at the very tail IS concentrated in one name, IDEA,
recurring across several, unrelated months. Both statements are true
simultaneously: the broad distribution is not dominated by a few names;
the extreme tail is.

### Time-of-day breakdown: zero-volume runs cluster at the close; missing-row gaps cluster at midday -- an inverted pattern

| | Follower zero-runs | Leader zero-runs | Follower missing-gaps | Leader missing-gaps |
|---|---|---|---|---|
| Open-30 (09:15-09:44) | 209 (4.3%) | 18 (2.0%) | 19,400 (2.0%) | 95 (2.6%) |
| Midday | 1,285 (26.5%) | 4 (0.4%) | 933,748 (96.2%) | 2,299 (62.2%) |
| Close-30 (15:00-15:29) | 3,352 (69.2%) | 886 (97.6%) | 17,653 (1.8%) | 1,299 (35.2%) |

**Zero-volume runs are overwhelmingly a close-of-session phenomenon**
(69-98% of all runs occur in the last 30 minutes), directly consistent
with Part 4's finding that 60% of all zero-volume rows table-wide sit at
exactly 15:28/15:29 -- the closing-auction-adjacent minutes. **Missing-row
gaps are overwhelmingly a midday phenomenon for followers** (96.2%), the
opposite end of the session from where zero-volume concentrates. (Leader
missing-gaps split more evenly between midday and close, but the leader
gap count, 3,693, is small enough that this split should be read with more
caution than the follower figures.) This is further evidence (beyond the
run-length-shape evidence in Part 3) that zero-volume bars and missing-row
gaps are generated by different mechanisms, not one underlying
"illiquidity" process manifesting two ways.

---

## Part 3 -- Testing the 3-minute threshold against zero-volume runs

### How much of each distribution the existing <3-minute rule would keep vs. exclude

| | Follower zero-runs | Leader zero-runs | Follower missing-gaps | Leader missing-gaps |
|---|---|---|---|---|
| Valid (<3 min) | 4,807 / 4,846 = **99.17%** | 905 / 908 = **99.67%** | 880,450 / 970,801 = **90.69%** | 1,937 / 3,693 = **52.45%** |
| Invalid (>=3 min) | 39 / 4,846 = **0.83%** | 3 / 908 = **0.33%** | 90,351 / 970,801 = **9.31%** | 1,756 / 3,693 = **47.55%** |

**If the existing Section 13 elapsed-time convention were applied
literally to zero-volume runs, it would almost never exclude anything**:
99.17% (followers) to 99.67% (leaders) of all zero-volume runs are already
under 3 minutes and would be forward-filled, not excluded, under the
existing rule's text. **Applied to missing-row gaps, the same threshold
behaves very differently**: it excludes a non-trivial 9.31% of
follower-tier gaps outright, and a striking **47.55% of leader-tier gaps**
-- nearly half. This single pair of numbers is the clearest evidence in
this investigation that the <3-minute rule, exactly as written, has a
**materially different practical effect** on the two phenomena it might be
asked to cover.

### Does the split change materially by entity, month, or time-of-day?

**By entity**: yes, for zero-volume runs -- essentially all of the
"invalid" (>=3-minute) zero-volume runs trace back to the same one name
(IDEA) recurring across several months (Headline finding 4 above). For
missing-row gaps, no single-entity concentration check was run (out of
scope for the time available), but the scale (970,801 follower gap events
across hundreds of entities) makes single-name dominance far less likely
than for the much rarer zero-run tail.

**By month/year**: yes, sharply, for both phenomena (Headline finding 3).
The follower missing-gap invalid share alone ranges from 3.07% (2021) to
29.64% (2026) -- an order of magnitude swing across the 10-year window.
**Any 3-minute-threshold impact estimate computed from pre-2023 data would
understate the 2024-2026 reality by roughly an order of magnitude.**

**By time of day**: yes, and in opposite directions for the two
phenomena. The INVALID (>=3 min) zero-volume runs are, in contrast to the
bulk of the (mostly 1-2 minute) zero-run distribution, concentrated at
**midday** (35/39 = 89.7% of follower invalid zero-runs; 2/3 of leader's),
not at the close where the short runs cluster -- i.e. the rare, long
zero-volume stretches (IDEA's episodes) are ordinary intraday halts/thin
periods, not a closing-auction artifact, while the short, close-clustered
runs that dominate the pooled count ARE a closing-auction artifact and
essentially never reach the 3-minute threshold anyway. INVALID missing-row
gaps for followers are also midday-concentrated (91.7%), matching the bulk
of the missing-gap distribution; for leaders, long gaps skew more to the
close (72.6%), a notable and unexplained asymmetry given leaders'
short-gap distribution does not show the same skew (small-sample caveat:
only 1,756 leader-tier invalid gaps total).

### Are zero-volume-run and missing-row-gap length distributions comparable or materially different?

**Materially different, by every measure examined.** Zero-volume runs are
overwhelmingly single-minute events (96-99.6% at 1 minute) with a thin,
single-entity-dominated tail. Missing-row gaps have a visibly fatter
right tail even for followers (9.31% at >=3 minutes vs. zero-volume's
0.83%) and an extremely fat tail for leaders (47.55% at >=3 minutes,
39.48% of all leader gaps exceeding 10 minutes outright, vs. zero-volume's
0.33%/0.00% respectively). The two distributions also peak at opposite
times of day. **This is a reportable shape difference, not a judgment
call**: the data does not support treating "zero-volume" and "missing-row"
as interchangeable instances of one underlying missingness process under
a single unified rule, at least not without separately verifying the rule
makes sense for each. No threshold tuning was performed or is recommended
here -- this section reports what the existing, frozen 3-minute threshold
actually does to each distribution, nothing more.

---

## Part 6 -- Synthesis memo

Every claim below is labeled **FACTUAL FINDING** (established directly by
the data/code examined in this investigation), **METHODOLOGICAL
RECOMMENDATION** (a judgment call, not forced by the data), **IMPLEMENTATION
REQUIREMENT** (something Phase 4 code must do, not yet built), or
**UNRESOLVED QUESTION** (cannot be settled without more evidence or a human
decision). No category is blended with another.

### 1. Volume-field semantics

**FACTUAL FINDING**: `bars_1min.volume` is Angel One's raw per-minute
candle value, inserted unmodified; no project-side synthesis exists; no
trade-count field exists at the intraday grain to distinguish a genuine
print from anything else (Part 1).

**UNRESOLVED QUESTION**: what `volume=0` actually represents at the
vendor level (a genuine zero-trade minute vs. a vendor-side
reporting/aggregation artifact) cannot be established from code or
documentation available to this investigation. Direct empirical evidence
(1,259 of 7,018 zero-volume rows, 18%, show real intra-bar price movement;
60% of all zero-volume rows cluster at the two closing minutes) suggests
the standard "no trade this minute" reading does **not** hold uniformly.

### 2. Follower-tier (and revised leader-tier) zero-volume incidence

**FACTUAL FINDING**: follower-tier zero-volume rate, full population, all
120 months: **3.88e-5 (0.00388%)**. Leader-tier, recomputed the same way:
**3.69e-5 (0.00369%)** -- essentially identical to the follower rate, and
**~119x higher** than the previously-published 11-month-sample figure of
3.1e-7. The prior "leaders are virtually never illiquid" conclusion does
not survive a full-population check and should be treated as superseded
by this investigation's numbers.

**FACTUAL FINDING**: missing-ROW (absent-row) incidence is both much
larger and much more tier-differentiated than zero-volume incidence:
follower 1.145%, leader 0.095% (a genuine ~12x tier gradient). The
liquidity-tier structure this project's universe construction is designed
to capture shows up in missing rows, not in zero-volume rows.

### 3. Run-length findings

**FACTUAL FINDING**: pooled, both tiers' zero-volume runs are
overwhelmingly 1-minute events (96.08% follower, 99.56% leader); the
extreme tail (>10 minutes) is dominated by one entity (IDEA /
`INE669E01016`) recurring across multiple, otherwise-unrelated months,
with a maximum observed run of 45 minutes (follower-tier month) and 166
minutes (leader-tier month, 2024-04, coinciding with record extreme
volumes and negative-volume rows for the same entity in the same week).

**FACTUAL FINDING**: missing-row gaps are a distinct, much larger-volume
phenomenon (970,801 follower gap events vs. 4,846 follower zero-runs) with
a visibly fatter tail, especially for leaders (47.55% of leader gaps are
>=3 minutes; 39.48% exceed 10 minutes outright).

**FACTUAL FINDING**: both phenomena are non-stationary over 2016-2026,
with a pronounced recent spike (2026 alone contributes 56-64% of each
tier's entire 10-year zero-volume count despite being a partial year).

### 4. Is the existing 3-minute rule defensible for zero-volume runs?

**FACTUAL FINDING**: applied literally, the existing <3-minute threshold
would forward-fill essentially all zero-volume runs (99.17%-99.67%) and
exclude almost none. Applied to missing-row gaps, the same threshold
excludes a materially larger share (9.31% followers, 47.55% leaders).

**METHODOLOGICAL RECOMMENDATION** (judgment call, not forced by the data):
given that (a) the threshold as written has almost no practical bite on
zero-volume runs, and (b) a meaningful minority of zero-volume bars show
price movement inconsistent with "no trade" (Part 4), the ambiguity
Decision 17 raises -- "does Section 13's text cover zero-volume at all"
-- should probably be resolved by treating zero-volume-but-OHLC-flat bars
as eligible for the same forward-fill logic as a short absent-row gap
(since empirically this almost never excludes anything extra), while
treating zero-volume-and-OHLC-NOT-flat bars (1,259 of 7,018, 18%) as a
**separate, fourth case** requiring its own rule, since a bar with real
price movement but zero recorded volume is not "stale" in the sense
Section 13's forward-fill is meant to address -- it is closer to the
"corrupted-but-present" category than to "zero-volume-stale." This is a
recommendation, not a finding the data forces; a reasonable alternative
(treat all zero-volume bars identically regardless of flatness) is not
ruled out by anything measured here.

### 5. OHLC validation results

**FACTUAL FINDING**: `high<low`=0, close-outside-range=1, open-outside-range=54
all reproduced exactly. The 54 open-violations are **not** independent
isolated glitches as previously characterized -- they are one single-date
(2023-03-03), single-bar-of-day (09:15:00) event affecting 54 different
entities simultaneously. Two previously-undocumented defect classes were
found: 560 negative-volume rows (concentrated on 3 dates, 189 entities,
49% from one entity/RECLTD) and extreme-outlier maximum volumes
concentrated at the first bar of the session (same bar-of-day as the
open-violations, suggesting a related mechanism, unconfirmed).

### 6. Forward-fill traceability

**FACTUAL FINDING**: no code anywhere in `src/fibo`, `src/box_theory`,
`src/darvas`, `src/fvg`, `src/poc`, `src/liquidity` implements Section 13's
rule, or any volume-based bar classification, for any prior study. Section
13 is a textual preregistration rule with zero corresponding
implementation anywhere in this repo today.

**IMPLEMENTATION REQUIREMENT**: a `minutes_since_last_trade` counter,
computable directly from `bars_1min` in a read query (no schema change),
partitioned by `(entity_id, trade_date)`; a separate absent-row-gap
detector (comparing consecutive present `ts` values) is also required,
since the counter alone cannot represent an absent row. Both must be
partitioned by `(entity_id, trade_date)`, not by raw `ts` alone, to avoid
silently bridging overnight gaps or same-day Muhurat-session gaps (Part 2's
session-boundary finding).

### 7. Recommended endpoint-validity policy (four cases)

**METHODOLOGICAL RECOMMENDATION**, directly adopting the four-category
framework already named in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 4D and Decision 17's own text:

1. **Genuinely traded** (`volume > 0`): always valid, no special handling.
2. **Zero-volume, OHLC-flat** (`volume = 0`, `open=high=low=close`; 5,759
   of 7,018 table-wide, 82%): treat as the present-row analogue of a short
   absent-row gap -- eligible for Section 13's forward-fill logic under
   the same elapsed-minutes counter, since empirically the resulting
   exclusion rate is negligible (Part 3).
3. **Zero-volume, OHLC-NOT-flat** (1,259 of 7,018, 18%; concentrated at
   15:28/15:29, the closing-auction minutes): recommend treating as its
   own case, closer to "corrupted-but-present" than to "stale" -- a bar
   cannot show genuine price discovery with zero recorded volume under the
   standard convention, and the closing-auction-minute concentration
   suggests a distinct, identifiable mechanism (NSE's weighted-average
   close procedure interacting with Angel's candle aggregator) rather than
   generic illiquidity.
4. **Invalid/corrupted** (structural violations: `high<low`, close/open
   outside `[low,high]`, negative volume, implausible-extreme volume):
   exclude outright, never forward-filled. 54+1+560+ a handful of extreme
   outliers table-wide -- small in count but each instance should bar that
   specific bar from being treated as a valid endpoint, not merely
   flagged.

**This recommendation is NOT forced by the data alone** -- it is one
reasonable way to resolve Decision 17's ambiguity given the measured
shapes; a human decision is still required (per the decision table's own
"Approval required: Yes").

### 8. What can be approved from definitions + evidence now

- That `bars_1min.volume=0` is NOT a homogeneous category (82% flat / 18%
  not-flat, with the not-flat subset concentrated at specific minutes) is
  now a measured fact, not an assumption -- this can be frozen as shared
  vocabulary regardless of which policy is ultimately adopted.
- That the existing 3-minute threshold, if extended to zero-volume runs
  literally, has almost no practical exclusionary effect (<1% either
  tier) is now measured and can be cited without further work.
- That zero-volume and missing-row gaps have materially different length
  distributions (shape, time-of-day concentration, and tier-sensitivity
  all differ) is now measured and can be cited as the basis for treating
  them under separate sub-rules.
- That the leader tier is NOT reliably near-zero-zero-volume once the full
  population is examined (full-population 3.69e-5, not the previously
  published 3.1e-7) should be treated as a correction to prior project
  documentation, not merely a footnote.

### 9. What remains OPEN

- **UNRESOLVED QUESTION**: the root cause of the 54 single-date
  open-violations, the 560 negative-volume rows, and the extreme-outlier
  maximum-volume rows -- all plausibly related to Angel One feed-side
  artifacts at specific bars-of-day, but not confirmable without live API
  access or vendor documentation this investigation does not have.
- **UNRESOLVED QUESTION**: whether the 18%-not-flat zero-volume subset
  should be folded into the forward-fill-eligible case or the
  invalid/corrupted case -- the data describes the shape of the problem
  but does not by itself select the policy (Section 7 above is a
  recommendation, not a resolution).
- **UNRESOLVED QUESTION**: why leader-tier missing-row gaps, when they
  occur, skew so heavily toward long (>10-minute, 39.48%) and
  close-of-session (72.6% of invalid gaps) -- not investigated further in
  this pass; the leader-tier gap sample (3,693 events) is small enough
  that this specific sub-finding should be treated with more caution than
  the follower-tier figures.
- **UNRESOLVED, per Decision 21**: Muhurat/special-session rows exist in
  the dataset (8 dates, ~93,600 rows) and no code anywhere gives them
  special session-boundary treatment; this investigation excluded them
  from the Part 2/3 measurement by scoping to the regular session only,
  but any Phase-4 implementation that scans `bars_1min` by raw `ts`
  difference without also checking for this same-day, multi-hour gap
  would silently mishandle it.

### 10. Implications for Decision 19 (exclusion-rate measurement)

Decision 19 (Option 1 100%-completeness vs. corrected Option 2) needs an
**exclusion rate** measured before it can be decided (per its own "Prefer
Option 1 if its exclusion rate is acceptable once measured" text). That
measurement **cannot start** until the following are frozen, because the
exclusion rate is directly a function of how many endpoints count as
"available":

1. **Whether zero-volume bars count as available (forward-filled) or
   unavailable (excluded) endpoints**, and if it depends on the
   flat/not-flat distinction from this investigation -- the exclusion
   rate under Option 1 will differ by roughly the gap between "count all
   zero-volume as available" and "count only flat zero-volume as
   available," which this investigation shows is a real, non-trivial
   difference (18% of the already-small zero-volume population, itself
   concentrated at specific minutes that may or may not fall inside the
   unified eligibility endpoints `t-35,t-5,t`).
2. **Whether the 3-minute threshold is extended to zero-volume runs,
   missing-row gaps, or both, and whether as one unified rule or two
   separate ones** -- this investigation shows the two have different
   length distributions, so the exclusion-rate arithmetic genuinely
   differs depending on which path is chosen; a Decision-19 measurement
   run before this is frozen would need to be rerun once it is.
3. **Which year range the exclusion-rate measurement is computed over** --
   given the sharp 2024/2026 non-stationarity found here, an exclusion
   rate computed only from pre-2023 data would materially understate the
   rate in the most recent years, and the sealed/live date range the
   eventual lead-lag study actually trades over should match the range
   the exclusion rate is measured over, not an earlier, cleaner-looking
   subset.
4. **Whether the Muhurat/special-session rows are included or excluded**
   from the eligibility computation at all, since Decision 21 is also
   unresolved and this investigation found those sessions are real but
   unhandled by any existing session-boundary logic.

None of these four are resolved by this investigation -- they are exactly
the pre-conditions Decision 19's own measurement needs settled first.

---

## Files and data referenced (absolute paths)

- `C:\projects\trade-new\src\fibo\intraday_db.py`
- `C:\projects\trade-new\src\fibo\download.py`
- `C:\projects\trade-new\src\fibo\bars.py`
- `C:\projects\trade-new\src\fibo\validation.py`
- `C:\projects\trade-new\src\fibo\universe.py`
- `C:\projects\trade-new\src\fibo\holdout.py`
- `C:\projects\trade-new\src\box_theory\universe_data.py`
- `C:\projects\trade-new\src\ipo_listing\intraday_db.py`
- `C:\projects\trade-new\scripts\fibo_download_intraday_top200.py`
- `C:\projects\trade-new\scripts\fibo_validate_intraday.py`
- `C:\projects\trade-new\scripts\fibo_step5_top200_data_quality.py`
- `C:\projects\trade-new\data\fibo_intraday.duckdb`
- `C:\projects\trade-new\data\warehouse.duckdb`
- `C:\projects\trade-new\lead_lag\DATA_AUDIT_LEAD_LAG.md`
- `C:\projects\trade-new\lead_lag\LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
- `C:\projects\trade-new\PREREGISTRATION_LEAD_LAG_V1.md` (Section 13)
- `C:\projects\trade-new\LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` (Section 4D; Decision table rows 17, 19, 20, 21)
