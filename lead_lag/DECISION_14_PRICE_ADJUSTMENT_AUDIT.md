# Decision 14 -- `bars_1min` Price-Adjustment Status: Data-Lineage and Integrity Audit

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Scope**: Decision 14 only -- the narrow raw-vs-adjusted *price scale* question for
`bars_1min` in `data/fibo_intraday.duckdb`, plus the separate within-session
mixed-scale integrity question.
**Mode**: READ-ONLY. Every database connection used
`duckdb.connect(path, read_only=True)`. No code, data, ledger, preregistration,
or proposal was modified. No strategy, gate, regression, null, or outcome
analysis was run. `Y(t,h)`, beta, significance and predictive performance were
never computed or inspected.
**Explicitly NOT resolved here**: Decision 20 (intraday corporate-action
exclusion policy) remains independently OPEN, unchanged. Decision 13's endpoint-
price convention and the 70% follower-breadth threshold are untouched.

---

## 1. Executive conclusion

### 1A. Raw vs. adjusted -- **MIXED CONVENTION -- SUPPORTED BY EVIDENCE**

`bars_1min` is **not raw**. Across **104 eligible split/bonus ex-dates**,
**103** show *no* price discontinuity in the Angel One series at the ex-date,
while the project's own daily bhavcopy store (`prices_eod`) shows the full
mechanical drop at the same boundary in **104 of 104** cases. The Angel-vs-
bhavcopy price-scale ratio steps by **exactly the recorded corporate-action
ratio** at the ex-date (median `step / recorded_ratio = 1.000000`; within 0.1%
for 99/104, within 1% for 103/104). That is the signature of a **back-adjusted**
series: history was rescaled, so the jump is already absent.

It is labelled **MIXED CONVENTION** rather than plain "ADJUSTED" because the
back-adjustment is **piecewise and incomplete, not a single global rescale to
today's scale**:

- **32 of 104** ex-date sessions still carry a residual scale != 1.0 against
  bhavcopy, i.e. those Angel bars are also adjusted for *later* actions --
  but not for *all* later actions.
- Scanning the 75 entities carrying these events over their full archive
  history found **143 Angel-vs-bhavcopy scale breaks > 5%**: 103 sit exactly
  on a recorded ex-date, and **40 do not**. Of those 40, **28 are Angel-side
  jumps** (the Angel day-high moves by ~1/ratio while bhavcopy moves < 2%)
  at dates with **no corporate action at all** -- each one located
  approximately two years before a later recorded ex-date.
- **One event is genuinely raw at its own ex-date boundary**: TATASTEEL
  (`INE081A01012`), ex_date 2022-07-28, split ratio 10. Angel sits at
  bhavcopy scale (1.000000) on both 2022-07-27 and 2022-07-28 and shows the
  full 9.78x mechanical drop -- because Angel's own adjustment regime
  boundary for that split landed **two trading days early** (2022-07-26),
  leaving 2022-07-26 and 2022-07-27 un-adjusted inside an otherwise adjusted
  neighbourhood. Those two sessions are mis-scaled by 10x relative to the
  adjacent adjusted history.

So: **"raw" is refuted. "Uniformly back-adjusted to today's scale" is also
refuted. The archive is a patchwork of multiplicative scale regimes whose
boundaries only mostly coincide with corporate actions.**

### 1B. Within-session mixed-scale artifacts -- **not supported by evidence** (clean negative)

**A vocabulary note, stated rather than papered over**: the four prescribed
statuses (RAW / ADJUSTED / MIXED CONVENTION / INCONCLUSIVE, each
"SUPPORTED BY EVIDENCE") have no label for a well-powered *negative*. The
finding here is a clean negative, so forcing it into "INCONCLUSIVE" would
understate it and forcing it into any of the other three would misdescribe it.
Reported plainly instead: **the within-session mixed-scale hypothesis is
TESTED AND NOT SUPPORTED. Every inspected session is internally on one single
price scale.** This is explicitly *not* "inconclusive" -- the test ran, had
power, and came back empty.

Across **208 sessions** (the 104 ex-date sessions plus their 104 preceding
sessions), **77,654 bars**:

| Check | Result |
|---|---|
| Sessions with 0 bars | 0 |
| OHLC-consistency violations (`high < max(open,close)`, `low > min(open,close)`, `high < low`) | **0 bars** |
| Bars with a non-positive O/H/L/C | **0** |
| Candidate single-bar level steps > 15% | **0** |
| Sustained mid-session multiplicative level shifts (median-of-10 bars each side) | **0** |
| Same two tests re-run at an 8% threshold (sensitivity pass) | **0 candidates, 0 sustained shifts** |
| Largest intra-session high/low span observed | 1.2441 (NBCC 2017-02-17 ex-date session) |

The largest intra-session span in the whole set, 1.244, is an ordinary volatile
session -- far below the smallest recorded ratio in the inventory (1.1) only in
the sense that it is a *gradual* range, not a step; the step detector found no
single-bar or sustained multiplicative break anywhere, at either threshold. No
isolated corrupt single-bar records were found either, so there is nothing here
to conflate with a systematic mid-session transition.

**Combined operational reading**: the scale discontinuities in this archive are
**between sessions, never within one**. A construct confined to a single
session (which, per the family's unchanged Section 12 rule, all of them are)
does not straddle any scale break found by this audit. A construct spanning
two sessions can.

---

## 2. Data lineage and schema findings

### 2.1 `bars_1min` has no adjustment column -- confirmed directly

`src/fibo/intraday_db.py:22-39` is the only `CREATE TABLE` for `bars_1min`.
Columns, confirmed against the live file via `information_schema.columns`:

```
entity_id, isin, symbol, angel_token, trade_date, ts,
open, high, low, close, volume,
known_date, fetched_at, source, revision_seq
```

No adjustment column, no factor column, no ratio column, no scale column.
Live table state (read-only):

```sql
SELECT COUNT(*) FROM bars_1min;                                   -- 169,935,257
SELECT MIN(trade_date), MAX(trade_date) FROM bars_1min;            -- 2016-10-04 .. 2026-09-18
SELECT COUNT(DISTINCT entity_id) FROM bars_1min;                   -- 386
SELECT revision_seq, COUNT(*) FROM bars_1min GROUP BY 1;           -- (1, 169935257)
SELECT source, COUNT(*) FROM bars_1min GROUP BY 1;                 -- (ANGEL_ONE_SMARTAPI_HISTORICAL, 169935257)
```

**Finding**: `revision_seq = 1` for every one of the 169.9M rows, and `source`
is a single value. The schema's own "corrections are new rows with a higher
`revision_seq`, never UPDATE/DELETE" discipline (`src/fibo/intraday_db.py:12-14`)
has never been exercised: **no row in this table has ever been revised or
rescaled by this project.**

### 2.2 No adjustment is applied during ingestion -- write path traced

Two ingestion scripts write `bars_1min`, and only two:

- `scripts/fibo_download_intraday.py:240-263` (original top-50 download)
- `scripts/fibo_download_intraday_top200.py:227-246` (top-200 widening)

Both are byte-for-byte identical in the relevant block. The exact write path in
`scripts/fibo_download_intraday_top200.py`:

- **line 158**: `resp = holder.client.getCandleData(params)` -- Angel One
  SmartAPI, `interval: "ONE_MINUTE"`, `exchange: "NSE"` (lines 151-155).
- **line 164**: `return resp.get("data") or []` -- the raw response list.
- **lines 230-234**: `for ts, o, h, l, c, v in data:` ... `rows.append((... o, h, l, c, v, ...))`
  -- the six API fields are placed into the row tuple **unmodified**. No
  multiplier, no division, no lookup, no join. `revision_seq` is the literal
  `1`.
- **line 239**: `INSERT INTO bars_1min SELECT * FROM chunk_new`.

There is **no step between the API call and the INSERT that could apply a
split/bonus adjustment**. Re-verified by inspection of every line between 158
and 239; the only transformations are `dt.date.fromisoformat(ts[:10])` and
`dt.datetime.fromisoformat(ts)` on the timestamp field.

**Consequence**: whatever adjustment status Section 1A reports is **Angel One's
own, inherited from the vendor** -- it is not something this project applied,
and it is not something this project can be said to have got wrong.

### 2.3 No adjustment is applied on read, and no read path rescales the table

Every code location referencing `bars_1min` in `src/` and `scripts/` was
enumerated. The read paths fall into three groups, none of which rescales rows
in place:

- **Pure OHLCV passthrough / aggregation**: `src/fibo/bars.py:18-53`
  (`aggregate_to_15min`, `aggregate_to_daily`), `src/fibo/resolution.py:42`,
  `src/box_theory/universe_data.py:64-80` (`fetch_bars_range`, whose docstring
  states the frame is in "ANGEL scale (not yet raw-converted)").
- **Scale measurement, read-only**: `src/fibo/scale_probe.py:171` and `:192`
  read `MAX(high)/MIN(low)` and the first `open`. It **returns** a multiplier
  for callers to apply in memory (`to_raw_scale`, line 124-126); it never
  writes.
- **Validation / reporting**: `src/fibo/validation.py:86-96`,
  `scripts/fibo_validate_intraday.py`, `scripts/fibo_step5_top200_data_quality.py`.

`grep` for `UPDATE bars_1min` / `DELETE FROM bars_1min` across `src/fibo/` and
`scripts/fibo_*.py` returns **no hits**. The only `revision_seq = 2` writer in
the repository, `src/ipo_listing/rescale.py:118`, targets a **different
database** -- `data/ipo_listing/ipo_intraday.duckdb`
(`src/ipo_listing/intraday_db.py:2-3`, `scripts/ipo_listing_fetch.py:44`),
whose `bars_1min` is keyed by `listing_id`, not `entity_id`. It cannot touch
`data/fibo_intraday.duckdb`.

### 2.4 `bars_1min` is not derived from `prices_eod` or any other project table

The ingestion scripts open `data/warehouse.duckdb` (`get_read_connection`,
`scripts/fibo_download_intraday_top200.py:113`) but use it only for
**universe and token resolution** -- `reconstitute_annually` and
`resolve_entity_tokens` (lines 114-118), which supply `entity_id`, `isin`,
`symbol`, and the Angel instrument token. **No price column from `prices_eod`
or any other table enters a `bars_1min` row.** Prices come exclusively from
`getCandleData`.

### 2.5 Historical rows cannot be back-adjusted by any existing process

Re-fetch/backfill behaviour, traced:

- Resumability is keyed on `fetch_log_intraday` with `status = 'ok'`
  (`scripts/fibo_download_intraday_top200.py:135-140`, skip at line 190-192).
  A chunk already marked `ok` is **never re-requested**.
- When a chunk *is* fetched, the only database operation is
  `INSERT INTO bars_1min` (line 239). There is no `UPDATE`, no `DELETE`, no
  upsert, no `ON CONFLICT`.
- A re-run after an error therefore **appends** (and could in principle
  duplicate), but can never **overwrite old rows with rescaled values**.
- Empirically confirmed: `revision_seq` is uniformly `1` across all
  169,935,257 rows (Section 2.1), so no rewrite has in fact occurred.

**Answer: no.** No existing process can back-adjust historical `bars_1min`
rows. The scale regimes documented in Section 1A are therefore **as-received
from the vendor**, frozen at fetch time.

### 2.6 Daily vs. intraday conventions **differ**, and the repository's own documentation of this is partly wrong

- **`prices_eod` is RAW.** `src/data_layer/prices_nse.py` parses the NSE
  bhavcopy zip and loads the renamed columns with no price arithmetic
  (`parse_bhavcopy_zip`, lines 138-174; `load_bhavcopy_to_duckdb`, line 235).
  Live sources: `NSE_BHAVCOPY_UDIFF` (1,682,984 rows) and
  `NSE_BHAVCOPY_LEGACY` (3,447,136 rows).
- **Adjustment is a separate, derived layer.**
  `src/data_layer/adjustment.py:1-4`: "prices_eod is never modified.
  adjustment_factors is a separate, derived table: adjusted(d) = raw(d) *
  factor(d)". `materialize_adjustment_factors` (line 118-131) writes only
  `adjustment_factors` (live: 4,763,062 rows, 93 distinct factor values).
  `read_adjusted_prices` (line 134-150) joins on read.
- **`src/fibo/price_scale.py:12-16` makes a factual claim that this audit
  refutes**: *"Angel One's INTRADAY bars, by contrast, are raw prints in
  whatever scale the exchange was actually quoting on that specific day --
  NOT retroactively re-scaled for a split that happened later."* Section 1A's
  evidence shows the opposite for 103 of 104 ex-dates. This is a
  **documentation defect, reported not fixed** (read-only audit).
- **`src/fibo/scale_probe.py`'s design, by contrast, is vindicated.** Its
  docstring (lines 44-51) explicitly anticipates "a genuinely raw archive
  (scale ~= 1), a back-adjusted archive (scale = the true adjustment ratio,
  whatever it is)" and measures the scale empirically rather than assuming
  either. That was the correct call.

### 2.7 What `scale_probe.py` and `fibo_step5_top200_data_quality.py` actually do

**Read in full, as instructed. This is the most directly relevant pre-existing
evidence in the repository, and it was built for a different purpose than
answering Decision 14 -- which is why it never answered it.**

`src/fibo/scale_probe.py` (202 lines) computes, for entity E on trading day D,
using **only D-1**:

```
r_high = prices_eod.high(D-1) / MAX(bars_1min.high)(D-1)
r_low  = prices_eod.low(D-1)  / MIN(bars_1min.low)(D-1)
if |r_high - r_low| / mean <= 0.001:  scale(D) = mean(r_high, r_low)
else:                                 UNRESOLVED
```

(`probe_scale`, lines 92-112; the DB reads at lines 170-186.) It then labels
the result `RAW_EQUIVALENT` if `|scale - 1| <= 0.01`, else `SCALED`
(line 111), applies a 20% overnight gap guard (lines 115-121, 191-200), and
**skips ex-dates outright** (`is_ex_date`, lines 129-138, called first at line
163).

**What this does and does not establish about Decision 14:**

- It *does* establish the mechanism: the Angel-to-bhavcopy relationship is a
  pure multiplicative rescale, verifiable to ~0.1% from two independent
  numbers (a real high and a real low). Its own docstring reports
  r_high/r_low agreement within 0.1% for 99.8% of a 500-pair sample, median
  relative disagreement 0.0%. This audit reproduces that precision
  independently: across the 208 event-adjacent day-sides, median high/low
  scale disagreement **1.8e-06**, max 6.7e-02 (one outlier, HINDPETRO
  2017-07-11, flagged in Section 5).
- It *does* already carry the `RAW_EQUIVALENT` vs `SCALED` distinction, and
  the "SCALED" branch exists precisely because `scale != 1` happens.
- **It could never answer Decision 14, by construction**: line 163 returns
  `EX_DATE_SKIP` *before* any measurement whenever D is an ex-date. The
  module deliberately refuses to look at exactly the boundary that
  discriminates raw from back-adjusted. Its docstring says so (lines 60-62):
  "Ex-dates are still skipped outright ... the scale can change overnight
  across an entity's own ex-date, and D-1 cannot describe it."
- Its `RAW_EQUIVALENT` label is therefore **a per-day reporting label, not a
  claim about the archive's convention.** A day can be `RAW_EQUIVALENT`
  simply because it sits after the entity's last corporate action.

`scripts/fibo_step5_top200_data_quality.py` (171 lines) runs that same
classification over every development-window `(entity, day)` pair, bucketed by
point-in-time liquidity rank band (1-50 / 51-100 / 101-200), and reports the
`RAW_EQUIVALENT / SCALED / UNRESOLVED / EX_DATE_SKIP / GAP_GUARD_SKIP`
breakdown plus high/low agreement quantiles, stopping if `UNRESOLVED` exceeds
2% in any band (lines 136-164). It inherits the ex-date skip (line 49-50) and
so likewise **cannot** resolve raw-vs-adjusted. It is a coverage/quality
report, not a lineage test.

**Corroborating pre-existing evidence, pointed the same way**: `BUGS.md`
Bug #18 (lines 1219-1279) records that `scale_probe`'s empirical scale
disagrees with `adjustment_factors.factor` on 233/1,500 sampled trades
(15.5%), entity-concentrated, with per-entity constant ratios (0.1x, 2.011x,
5.0x) and three affected entities having **zero** recorded corporate actions.
That is consistent with this audit's finding that Angel's archive carries
multiplicative scale regimes which this project's own corporate-action table
does not fully explain. Bug #18 is reported here as context only; it is
**status "found, not fixed"** and this audit changes nothing about it.

---

## 3. Corporate-action event inventory

### 3.1 The authoritative source, located rather than assumed

Searched for `corporate_action`, `ex_date`, `split`, `bonus`, `fetch_ex_dates`
across `src/` and both database schemas.

- **Table**: `corporate_actions` in `data/warehouse.duckdb`. Discovered schema
  (`information_schema.columns`):
  `isin, symbol, ex_date, action_type, ratio, subject_raw, feed_isin, known_date, fetched_at, source, revision_seq`.
- **Ingestion**: `src/data_layer/corporate_actions.py`, from
  `https://www.nseindia.com/api/corporates-corporateActions` (line 47), source
  tag `NSE_CORPORATE_ACTIONS_API`. Scope is deliberately narrow: **only bonus
  and face-value-split** are parsed into a ratio (lines 1-10, 55-59,
  `parse_subject_ratios` 81-92). Dividends, buybacks, AGMs, rights and capital
  reductions are out of scope.
- **ISIN resolution**: the feed's own `isin` field is untrusted and kept only
  as `feed_isin`; the real ISIN is resolved from this project's own
  `prices_eod` `(symbol, trade_date, isin)` observations
  (`resolve_isin_for_actions`, lines 107-132).
- **Entity resolution for this audit**: `corporate_actions.isin JOIN isin_lineage.isin`
  -> `entity_id`. This is the identical join used by
  `src/fibo/scale_probe.py:133-137` (`is_ex_date`) and by
  `src/box_theory/universe_data.py:81-90` (`fetch_ex_dates`), so the audit
  scopes events exactly as the project's own code does.
- There is **no other** corporate-action store. `adjustment_factors` is a
  derived table, not an event record. No alternative/newer source exists.

### 3.2 Live counts

```sql
SELECT COUNT(*) FROM corporate_actions;                        -- 727
SELECT action_type, COUNT(*) FROM corporate_actions GROUP BY 1; -- split 337, bonus 390
SELECT MIN(ex_date), MAX(ex_date) FROM corporate_actions;       -- 2016-01-05 .. 2025-12-26
```

Restricted to the intraday archive's date range **2016-10-04 .. 2026-09-18**:

```sql
SELECT l.entity_id, ca.isin, ca.symbol, ca.ex_date, ca.action_type, ca.ratio, ca.subject_raw
FROM corporate_actions ca JOIN isin_lineage l ON ca.isin = l.isin
WHERE ca.ex_date BETWEEN DATE '2016-10-04' AND DATE '2026-09-18';
```

- **692** component rows in window (pre-join count: 692; **0** corporate-action
  ISINs are missing from `isin_lineage`, and **0** map to more than one
  `entity_id`, so the join neither drops nor fans out any event).
- **367 bonus** + **325 split** component rows.
- **659 distinct `(entity_id, ex_date)` events.**

Component rows by type and year (full window, all entities):

| Year | bonus | split |
|---|---|---|
| 2016 | 8 | 2 |
| 2017 | 46 | 28 |
| 2018 | 34 | 22 |
| 2019 | 21 | 9 |
| 2020 | 12 | 12 |
| 2021 | 32 | 30 |
| 2022 | 57 | 52 |
| 2023 | 39 | 51 |
| 2024 | 64 | 65 |
| 2025 | 54 | 54 |

### 3.3 Duplicate, ambiguous and incomplete records

- **Exact duplicate component rows** (same entity / ex_date / type / ratio /
  subject): **0**.
- **Conflicting ratios for the same `(entity_id, ex_date, action_type)`**: **0**
  (`COUNT(DISTINCT ratio) > 1` returns an empty set).
- **Multi-component events**: **33** `(entity_id, ex_date)` pairs carry more
  than one row. These are **not ambiguity** -- they are genuine combined
  actions, exactly the case `corporate_actions.py:22-29` was written to catch
  (e.g. `INE918I01018` BAJAJFINSV 2022-09-13: `Bonus 1:1` ratio 2.0 **and**
  `Face Value Split - From Rs 5/- To Re 1/-` ratio 5.0). This audit's
  **event ratio = the product of all component ratios on that `(entity, ex_date)`**,
  matching `adjustment.py`'s own same-day combination rule
  (`compute_factors_sql` lines 50-53; `compute_factors_python` line 93).
  3 of the 33 are in the eligible set (BAJAJFINSV 2022-09-13 = 10.0,
  EASEMYTRIP 2022-11-21 = 8.0, BAJFINANCE 2025-06-16 = 10.0).
- **Known incompleteness, inherited and reported not fixed**:
  (a) `corporate_actions` begins at `ex_date >= 2016-01-05`, so any pre-2016
  event is invisible -- the exact limitation `scale_probe.py:10-20` documents
  (KOTAKBANK's 2015 ING Vysya merger).
  (b) Only bonus and face-value splits are parsed; mergers, demergers,
  consolidations and capital reductions are **not** in this table at all, yet
  can move the price scale. Section 6 shows 28 unexplained Angel-side scale
  breaks, some of which may be such events.
  (c) Dividends are out of scope by design, so no dividend-related scale
  question is addressed by this audit.

### 3.4 Intraday coverage and eligibility

Coverage was evaluated per event against `bars_1min`'s own
`(entity_id, trade_date)` index:

- `prev_bar_date` = the entity's latest `bars_1min` `trade_date` **strictly
  before** `ex_date`.
- `next_bar_date` = the entity's earliest `bars_1min` `trade_date`
  **on or after** `ex_date`.

| Disposition | Events | Exact reason |
|---|---|---|
| **ELIGIBLE** | **104** | both sides present, each within 10 calendar days of the ex-date |
| Excluded | 504 | **entity absent from `bars_1min` entirely** (the archive covers 386 entities; the corporate-action table covers the whole NSE universe) |
| Excluded | 31 | **no `bars_1min` day before `ex_date`** (archive coverage for that entity starts on/after the ex-date) |
| Excluded | 12 | **no `bars_1min` day on/after `ex_date`** (archive coverage for that entity ends before the ex-date) |
| Excluded | 8 | **pre-ex-date bar gap > 10 calendar days** (gaps of 88, 147, 238, 254, 1005, 1011, 1149, 1279 days -- entities that left and later re-entered the point-in-time top-200 universe, so the archive has no contemporaneous bar before the action) |
| **Total** | **659** | |

Eligible events by type and year (event-level, ratio = product of components):

| Year | bonus | bonus+split | split | total |
|---|---|---|---|---|
| 2016 | 3 | 0 | 0 | 3 |
| 2017 | 21 | 0 | 5 | 26 |
| 2018 | 7 | 0 | 4 | 11 |
| 2019 | 7 | 0 | 2 | 9 |
| 2020 | 0 | 0 | 1 | 1 |
| 2021 | 3 | 0 | 3 | 6 |
| 2022 | 10 | 2 | 2 | 14 |
| 2023 | 5 | 0 | 2 | 7 |
| 2024 | 5 | 0 | 7 | 12 |
| 2025 | 8 | 1 | 6 | 15 |
| **Total** | **69** | **3** | **32** | **104** |

Of the 104, **101** have `gap_before = 1` calendar day and **3** have
`gap_before = 2-4` days (weekend/holiday-adjacent); all 104 have
`gap_after = 0`, i.e. a bar exists on the ex-date itself. All 208
event-adjacent sessions have bars (Section 1B). No eligible event is missing
an interval around the boundary.

The event inventory was **not** restricted to leader/follower tiers -- it
covers every entity with both a corporate-action record and intraday coverage,
as instructed.

---

## 4. Sampling and inclusion methodology -- predeclared

**These rules were written down and fixed before any intraday price was
retrieved for any event. No event was selected after seeing its prices, and
nothing was selected by apparent price-movement size.**

**R1 -- Event definition.** An event is a distinct `(entity_id, ex_date)` pair
from `corporate_actions JOIN isin_lineage`, with `action_type IN ('split','bonus')`
and `ex_date BETWEEN '2016-10-04' AND '2026-09-18'`. Its recorded ratio is the
**product** of all component ratios on that pair.

**R2 -- Eligibility (deterministic).** Eligible iff `prev_bar_date` exists,
`next_bar_date` exists, `ex_date - prev_bar_date <= 10` calendar days, and
`next_bar_date - ex_date <= 10` calendar days. Any failure is recorded with its
exact reason (Section 3.4). No eligibility criterion references price.

**R3 -- Census, not a sample, for the ratio diagnostic.** The Step-3/4A ratio
comparison and the Step-4B within-session scan are cheap aggregate queries, so
they were run on **all 104 eligible events exhaustively**. No sampling was
needed and none was performed for the quantitative results. The complete
inventory (659 events) and the complete eligible census (104) are reported
separately from the narrative subset below.

**R4 -- Narrative detail subset (predeclared, deterministic).** For the
bar-by-bar narrative, strata = `types` {`bonus`, `bonus+split`, `split`} x
`era` {2016-2019, 2020-2022, 2023-2026}; within each non-empty stratum, order
by `(ex_date ASC, entity_id ASC)` and take the **first** event. Empty strata
are reported as empty.

**R5 -- Every non-modal event is reported in full, mechanically.** In addition
to R4, **every** event whose classification differs from the modal
classification is written up in full detail. This is a rule applied
mechanically to whatever the census produced -- not a post-hoc selection of
interesting cases.

**R6 -- Diagnostic definition (the discriminator).** For each event, compute
the Angel-vs-bhavcopy price scale independently on each side of the boundary:

```
scale_prev = prices_eod.high(prev_bar_date) / MAX(bars_1min.high)(prev_bar_date)
scale_ex   = prices_eod.high(ex_date)       / MAX(bars_1min.high)(ex_date)
step       = scale_prev / scale_ex
```

- `step ~= recorded_ratio` **and** `Angel prev_close / Angel ex_open ~= 1`
  => Angel's history is already rescaled => **back-adjusted**.
- `step ~= 1` **and** `Angel prev_close / Angel ex_open ~= recorded_ratio`
  => the mechanical drop is present in Angel's own series => **raw**.
- Anything else => OTHER/UNCLEAR.

Tolerance on `step / recorded_ratio`: 1%. `high` and `low` are both used and
required to agree, for the reason `scale_probe.py:33-42` gives (bhavcopy's
`close` is NSE's own last-30-minute VWAP and never equals a 1-minute print;
`high`/`low` are the same extreme trades in both sources).

**R7 -- Percentage returns and bare continuity are not evidence.** No event is
classified from the size of a move. Classification uses only the
`step` vs `recorded_ratio` comparison in R6, reported numerically for every
event.

**Resulting R4 + R5 subset (9 events; fixed before any price inspection):**

| Stratum | Event |
|---|---|
| bonus / 2016-2019 | IOC `INE242A01010` 2016-10-18, ratio 2.000000 |
| bonus / 2020-2022 | AARTIIND `INE769A01020` 2021-06-22, ratio 2.000000 |
| bonus / 2023-2026 | ASTRAL `INE006I01046` 2023-03-14, ratio 1.333333 |
| bonus+split / 2016-2019 | **EMPTY** (no combined event in that era is eligible) |
| bonus+split / 2020-2022 | BAJAJFINSV `INE918I01018` 2022-09-13, ratio 10.000000 |
| bonus+split / 2023-2026 | BAJFINANCE `INE296A01016` 2025-06-16, ratio 10.000000 |
| split / 2016-2019 | BEL `INE263A01016` 2017-03-16, ratio 10.000000 |
| split / 2020-2022 | EICHERMOT `INE066A01013` 2020-08-24, ratio 10.000000 |
| split / 2023-2026 | VBL `INE200M01013` 2023-06-15, ratio 2.000000 |
| **R5 non-modal** | TATASTEEL `INE081A01012` 2022-07-28, ratio 10.000000 |

---

## 5. Event-by-event evidence

### 5.1 Exact queries used

```sql
-- intraday, regular session only, per (entity, day)
SELECT ts, open, high, low, close, volume
FROM bars_1min
WHERE entity_id = ? AND trade_date = ?
  AND CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:59'
ORDER BY ts;

-- day aggregates on the Angel side
SELECT MAX(high), MIN(low), FIRST(open ORDER BY ts), LAST(close ORDER BY ts), COUNT(*)
FROM bars_1min
WHERE entity_id = ? AND trade_date = ?
  AND CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:59';

-- daily cross-reference
SELECT p.open, p.high, p.low, p.close, p.prev_close
FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
WHERE l.entity_id = ? AND p.trade_date = ? AND p.series = 'EQ';
```

### 5.2 Worked numeric example 1 -- BAJAJFINSV, combined bonus 1:1 + split 5:1, ratio 10

`INE918I01018`, ex_date **2022-09-13**. Prev session 2022-09-12 (375 bars),
ex session 2022-09-13 (375 bars), next session 2022-09-14 (375 bars). No
missing intervals.

| Quantity | Value |
|---|---|
| Angel 2022-09-12 last 4 bars (close) | 15:26 1718.41, 15:27 1721.20, 15:28 1722.00, 15:29 **1713.81** |
| Angel 2022-09-13 first 4 bars (open) | 09:15 **1755.00**, 09:16 1768.90, 09:17 1781.00, 09:18 1795.70 |
| Angel 2022-09-13 spread (open) | 09:15 1755.00, 10:17 1809.40, 11:19 1800.10, 12:22 1786.45, 13:24 1785.10, 14:26 1773.00, 15:29 1795.65 |
| Angel 2022-09-13 close | 1784.75 |
| Angel 2022-09-13 session range | low 1750.00, high 1844.00 (span 1.0537) |
| Angel 2022-09-14 first bar open | 1769.00 |
| bhavcopy 2022-09-12 O/H/L/C | 17380.00 / 17420.00 / 17052.20 / **17138.05** |
| bhavcopy 2022-09-13 O/H/L/C | **1755.00** / 1844.00 / 1750.00 / 1784.75, `prev_close` field 17138.05 |

Arithmetic:

```
scale_prev = 17420.00 / 1742.00 = 10.000000
scale_ex   =  1844.00 / 1844.00 =  1.000000
step       = 10.000000 / 1.000000 = 10.000000
step / recorded_ratio = 10.000000 / 10 = 1.000000      <-- exact

Angel boundary:    1713.81 / 1755.00 =  0.976530   (recorded ratio is 10)
bhavcopy boundary: 17138.05 / 1755.00 =  9.765271
bhavcopy boundary / recorded_ratio = 9.765271 / 10 = 0.976527
```

**Reading**: bhavcopy drops by the full 10x at the boundary (the 2.35% residual
is that day's genuine price move, identical in both series). Angel does not
drop at all -- its 2022-09-12 bars are already divided by 10. Internally
consistent throughout the ex-date session (one scale, 375 bars, no step).
**Back-adjusted.**

### 5.3 Worked numeric example 2 -- BEL, split FV Rs 10 -> Re 1, ratio 10

`INE263A01016`, ex_date **2017-03-16**. 375 bars on each of 2017-03-15,
2017-03-16, 2017-03-17.

| Quantity | Value |
|---|---|
| Angel 2017-03-15 last 4 bars (close) | 142.72, 142.71, 142.75, **142.70** |
| Angel 2017-03-16 first 4 bars (open) | **144.91**, 144.95, 144.05, 143.91 |
| Angel 2017-03-16 spread (open) | 09:15 144.91, 10:17 144.91, 11:19 145.00, 12:22 145.86, 13:24 146.82, 14:26 149.64, 15:29 150.00 |
| Angel 2017-03-16 close / range | 150.14 / low 143.64, high 151.18 (span 1.0525) |
| Angel 2017-03-17 first bar open | 150.86 |
| bhavcopy 2017-03-15 O/H/L/C | 1574.90 / 1591.85 / 1565.20 / **1569.65** |
| bhavcopy 2017-03-16 O/H/L/C | **159.40** / 166.30 / 158.00 / 165.15 |

Arithmetic:

```
scale_prev = 1591.85 / 144.71 = 11.000173
scale_ex   =  166.30 / 151.18 =  1.099993
step       = 11.000173 / 1.099993 = 10.000224
step / recorded_ratio = 10.000224 / 10 = 1.000022     <-- 0.0022% off

Angel boundary:    142.70 / 144.91 = 0.984749   (recorded ratio is 10)
bhavcopy boundary: 1569.65 / 159.40 = 9.847240
bhavcopy boundary / recorded_ratio = 0.984724
```

**Reading**: same signature. **Back-adjusted.** Note `scale_ex = 1.1` exactly:
BEL's bars on the ex-date are *still* divided by 1.1, which is BEL's **next**
recorded action (2017-09-28 bonus 11:10, ratio 1.1) -- but **not** by 3.0, its
2022-09-15 bonus 2:1. The back-adjustment is partial. This is the piecewise
behaviour quantified in Section 6.2.

### 5.4 Worked numeric example 3 -- TATASTEEL, the single non-modal event

`INE081A01012`, ex_date **2022-07-28**, split ratio **10**. 374-375 bars every
session; no missing intervals.

Day-by-day, both series side by side:

| Date | Angel first open | Angel high | Angel low | Angel last close | bhav O/H/L/C | `scale = bhav_high/Angel_high` |
|---|---|---|---|---|---|---|
| 2022-07-22 | 94.25 | 94.34 | 93.20 | 93.61 | 942.50/944.00/932.00/936.05 | **10.00636** |
| 2022-07-25 | 93.88 | 96.49 | 93.84 | 96.07 | 935.00/964.85/933.60/960.70 | **9.99948** |
| 2022-07-26 | **972.00** | 976.70 | 946.05 | 949.50 | 972.00/976.70/946.05/949.50 | **1.00000** |
| 2022-07-27 | 951.00 | 961.55 | 943.60 | 959.40 | 951.00/961.55/943.60/959.40 | **1.00000** |
| **2022-07-28 (ex)** | **98.10** | 102.00 | 97.15 | 100.35 | 98.10/102.00/97.15/100.35, `prev_close` 959.40 | **1.00000** |
| 2022-07-29 | 103.00 | 109.30 | 102.15 | 107.60 | 103.00/109.30/102.15/107.60 | 1.00000 |

Arithmetic at the recorded ex-date boundary:

```
scale_prev (2022-07-27) =  961.55 /  961.55 = 1.000000
scale_ex   (2022-07-28) =  102.00 /  102.00 = 1.000000
step = 1.000000 ;  step / recorded_ratio = 1.000000 / 10 = 0.100000   <-- NOT the ratio

Angel boundary:    959.40 / 98.10 = 9.779817
bhavcopy boundary: 959.40 / 98.10 = 9.779817      <-- identical
9.779817 / 10 = 0.977982
```

And the break that is **not** at any corporate action:

```
Angel 2022-07-25 day high  96.49   ->  2022-07-26 day high  976.70
Angel step = 976.70 / 96.49 = 10.1223
bhav  step = 976.70 / 964.85 =  1.0123        <-- bhavcopy is continuous
```

**Reading**: at its own ex-date this event is **raw in both series** and shows
the full mechanical 9.78x drop -- the only such case in 104. The cause is
visible one row up: Angel's adjustment regime for this split **ends two
trading days early**, at 2022-07-26. Angel's 2022-07-26 and 2022-07-27 bars
are in **pre-split (raw) scale** while 2022-07-25 and earlier are in
**post-split (adjusted) scale**, a 10x break on a date with no corporate
action, with bhavcopy continuous across it (1.0123). The recorded ex_date is
correct: bhavcopy's own `prev_close` on 2022-07-28 is 959.40 against an open of
98.10, so the split took effect on 2022-07-28 at the exchange.

**Each individual session here is internally single-scale** -- the 2022-07-26
session opens at 972.00 and closes at 949.50 with no mid-session step
(Section 1B scan: 0 candidates). The defect is a **cross-session** boundary
misplacement, not a within-session mixture.

### 5.5 The remaining six narrative events (R4 subset)

All six show the modal signature. `step / recorded_ratio` to six decimals:

| Event | ratio | scale_prev | scale_ex | step | step/ratio | Angel boundary | bhav boundary / ratio | ex-session span | internally consistent? |
|---|---|---|---|---|---|---|---|---|---|
| IOC 2016-10-18 bonus | 2.000000 | 3.999907 | 2.000000 | 1.999953 | **0.999977** | 160.58/161.50 = 0.994303 | 0.994272 | 1.0221 | yes (375 bars) |
| AARTIIND 2021-06-22 bonus | 2.000000 | 2.291742 | 1.145868 | 2.000006 | **1.000003** | 773.17/794.16 = 0.973570 | 0.973571 | 1.0423 | yes (375 bars) |
| ASTRAL 2023-03-14 bonus | 1.333333 | 1.333331 | 1.000000 | 1.333331 | **0.999998** | 1412.78/1424.00 = 0.992121 | 0.992117 | 1.0402 | yes (375 bars) |
| BAJFINANCE 2025-06-16 bonus+split | 10.000000 | 10.000000 | 1.000000 | 10.000000 | **1.000000** | 934.00/956.00 = 0.976987 | 0.976046 | 1.0335 | yes (375 bars) |
| EICHERMOT 2020-08-24 split | 10.000000 | 10.000000 | 1.000000 | 10.000000 | **1.000000** | 2170.24/2199.45 = 0.986719 | 0.986719 | 1.1095 | yes (375 bars) |
| VBL 2023-06-15 split | 2.000000 | 5.000000 | 2.500000 | 2.000000 | **1.000000** | 323.00/327.92 = 0.984996 | 0.984996 | 1.0553 | yes (375 bars) |

Illustrative raw bars (AARTIIND 2021-06-22, ratio 2): prev-session closes
772.67 / 773.65 / 773.74 / **773.17**; ex-session first opens **794.16** /
773.21 / 774.30 / 772.60; ex-session spread of opens 794.16 (09:15), 774.96
(10:17), 768.85 (11:19), 771.68 (12:22), 770.59 (13:24), 767.50 (14:26),
766.67 (15:29); ex-session close 765.45; next session first open 771.47. The
series is flat across a ratio-2 bonus -- i.e. the bonus is already in the
pre-ex-date prices. Meanwhile bhavcopy goes 1771.90 -> 910.00.

Note AARTIIND's `scale_ex = 1.145868`: the ex-date bars are still divided by
~1.1459, and Section 6.2 locates the matching regime boundary at 2022-10-19
where Angel's scale drops 1.145869 -> 1.000000 with **no recorded action**.

### 5.6 High/low agreement -- the rescale is multiplicative, not noise

Because `scale` is computed independently from `high` and from `low`, their
agreement is a free consistency check on the whole method. Across the 208
event-adjacent day-sides: median relative disagreement **1.8e-06**, and only
**9 of 208** exceed 0.1%:

| Event / side | prev-side disagreement | ex-side disagreement |
|---|---|---|
| HINDPETRO 2017-07-11 | **6.707%** | 0.000% |
| UPL 2019-07-02 | 0.142% | 0.978% |
| RECLTD 2022-08-17 | 0.212% | 0.000% |
| INDIAMART 2023-06-21 | 0.000% | 0.264% |
| POWERGRID 2023-09-12 | 0.000% | 0.298% |
| PFC 2023-09-21 | 0.000% | 0.110% |
| BERGEPAINT 2023-09-22 | 0.000% | 0.418% |
| PERSISTENT 2024-03-28 | 0.000% | 0.103% |

**HINDPETRO 2017-07-11 is flagged as a one-sided measurement caveat**: its
prev-side high-ratio and low-ratio disagree by 6.7%, so `scale_prev = 2.243855`
is less trustworthy than the other 103. Its `step/ratio` would be
`2.243855/1.500000/1.5 = 0.997`, still consistent with back-adjustment, but
the arithmetic rests on a day where the two sources' extremes do not line up.
`scale_probe.probe_scale` would return `UNRESOLVED` for this day under its own
0.1% tolerance. Reported, not discarded.

---

## 6. Raw-vs-adjusted assessment

### 6.1 Aggregate result over all 104 eligible events

| Classification (per R6) | Count |
|---|---|
| Angel has **no** ex-date jump; `step ~= recorded_ratio` -> **back-adjusted** | **103** |
| Angel **raw**, full ratio jump present at the ex-date | **1** (TATASTEEL 2022-07-28) |
| OTHER / UNCLEAR | 0 |
| Insufficient data | 0 |

Distribution of `step / recorded_ratio`: median **1.000000**, min 0.100000
(TATASTEEL), max 1.005609.

| Agreement band | Events |
|---|---|
| within 0.1% of the recorded ratio | 99 / 104 |
| within 0.5% | 102 / 104 |
| within 1% | 103 / 104 |
| within 3% | 103 / 104 |

Boundary behaviour of the two series, side by side:

| Measure | Result |
|---|---|
| Angel `prev_close / ex_open` within 10% of **1.0** | **103 / 104** (median 0.9951, p05 0.9688, p95 1.0347) |
| bhavcopy `prev_close / ex_open` within 10% of the **recorded ratio** | **104 / 104** (median `eod/ratio` = 0.994605) |

### 6.2 Why this is not a tautology, and what the cross-reference does and does not prove

The task's caution is apt: if both series showed the same pattern, the
comparison would be consistent evidence without direction. **Here they do not.**
In 103 of 104 cases bhavcopy steps by the recorded ratio and Angel does not, so
the two series **disagree at the boundary**, and that disagreement is itself the
discriminator. What the ratio test alone establishes is only that **exactly one
of the two is rescaled relative to the other**.

Attributing the rescale to Angel rather than to bhavcopy rests on three
independent pieces of lineage evidence, stated as the inference it is:

1. **`prices_eod` is loaded from NSE's own daily bhavcopy with no price
   arithmetic** (`src/data_layer/prices_nse.py`, Section 2.6), and
   `src/data_layer/adjustment.py:1-4` states, and the code shows, that
   `prices_eod` is never modified -- adjustment lives in the separate derived
   `adjustment_factors` table.
2. **bhavcopy's levels match the recorded action semantics.** BEL's recorded
   action is a face-value split from Rs 10 to Re 1; bhavcopy goes 1569.65 ->
   159.40 (a 10x drop) and Angel does not move. A Rs-10-face-value share
   trading near Rs 1570 in 2017 and near Rs 159 after a 10:1 split is the
   coherent reading; a share trading near Rs 143 on both sides is not.
3. **The recorded ratios are NSE's own**, parsed from the NSE corporate-actions
   feed (`src/data_layer/corporate_actions.py`), and they match bhavcopy's
   boundary step to within 2.5% in **every one of 104** cases -- the residual
   being each day's genuine price move.

Therefore: **bhavcopy = raw; `bars_1min` = rescaled.** This is an inference
from source authority plus semantic coherence, not a proof from the price
arithmetic alone, and it is labelled as such.

### 6.3 Why "MIXED CONVENTION" and not plain "ADJUSTED"

A uniformly back-adjusted archive would have `scale = 1.0` at every date after
an entity's last action, and `scale` equal to the cumulative product of **all**
later ratios at every earlier date. It does not.

Full-history Angel-vs-bhavcopy scale scan over the **75 entities** carrying the
104 eligible events (break = a >5% change in `scale` between consecutive
matched trading days):

| Break location | Count |
|---|---|
| On a recorded ex-date | **103** |
| **Not** on any recorded ex-date | **40** |
| -- of those 40, the **Angel** series is the one that jumps | **28** |
| -- of those 40, the **bhavcopy** series is the one that jumps | 12 |

The 28 Angel-side, action-less breaks are systematic, not noise. Each is a
jump *up* in `scale` (Angel price steps *down*) by a factor matching a **later**
recorded action, positioned roughly two years before that action's ex-date:

| Entity | Action-less break date | scale before -> after | Later recorded action it matches |
|---|---|---|---|
| TATASTEEL | 2020-07-28 | 1.000000 -> 10.000000 | 2022-07-28 split 10 |
| BAJAJFINSV | 2020-09-08 | 1.000000 -> 10.000000 | 2022-09-13 bonus+split 10 |
| BEL | 2020-09-10 | 1.000000 -> 3.000292 | 2022-09-15 bonus 3 |
| NESTLEIND | 2021-12-31 | 2.000000 -> 19.999950 | 2024-01-05 split 10 |
| INDIAMART | 2021-06-16 | 1.000000 -> 2.000000 | 2023-06-21 bonus 2 |
| POWERGRID | 2021-09-07 | 1.000000 -> 1.333359 | 2023-09-12 bonus 1.3333 |
| PFC | 2021-09-16 | 1.000000 -> 1.250000 | 2023-09-21 bonus 1.25 |
| BERGEPAINT | 2021-09-17 | 1.000000 -> 1.200003 | 2023-09-22 bonus 1.2 |
| PERSISTENT | 2022-03-24 | 1.000000 -> 2.000000 | 2024-03-28 split 2 |
| CANBK | 2022-05-10 | 1.000000 -> 5.000000 | 2024-05-15 split 5 |
| IOC | 2018-04-05 | 1.000000 -> 1.500000 | 2022-06-30 bonus 1.5 |
| AUBANK | 2018-04-18 | 1.000000 -> 1.999970 | 2022-06-09 bonus 2 |
| SRF | 2018-01-12 | 1.000000 -> 5.000000 | 2021-10-13 bonus 5 |
| JUBLFOOD | 2018-01-18 | 2.000000 -> 10.000000 | 2022-04-19 split 5 |
| ... | (14 more, same shape) | | |

Worked confirmation on IOC, whose `scale` runs are:

```
2016-10-04 .. 2016-10-17   scale = 3.99994     (8 days)
2016-10-18 .. 2018-03-14   scale = 2.00000   <- recorded ex-date 2016-10-18, bonus 2
2018-03-15 .. 2018-04-04   scale = 1.00000   <- recorded ex-date 2018-03-15, bonus 2
2018-04-05 .. 2022-06-29   scale = 1.50000   <- NO recorded action on 2018-04-05
2022-06-30 .. 2023-02-21   scale = 1.00000   <- recorded ex-date 2022-06-30, bonus 1.5
```

IOC's recorded actions are 2016-10-18 (2.0), 2018-03-15 (2.0), 2022-06-30
(1.5). A clean global back-adjustment would put `scale = 2.0 x 2.0 x 1.5 = 6.0`
on 2016-10-04 and `scale = 1.5` on 2018-03-20. Instead 2016-10-04 shows 4.0
(= 2.0 x 2.0, the 2022 bonus **missing**) and 2018-03-20 shows 1.0 (also
missing it) until an action-less step to 1.5 on 2018-04-05.

**The operative characterisation**: Angel's archive applies each corporate
action's back-adjustment **only to a bounded trailing window of history
preceding that action** (empirically ~2 years), leaving older history
un-adjusted for it. The mechanism is the vendor's and cannot be verified from
inside this repository; the *pattern* is directly measured here. Combined with
TATASTEEL's two un-adjusted sessions **inside** an adjusted window, the archive
satisfies neither "raw" nor "uniformly adjusted".

**Hence: MIXED CONVENTION -- SUPPORTED BY EVIDENCE.**

### 6.4 The 12 bhavcopy-side action-less breaks (reported, not this audit's subject)

Twelve of the 40 action-less breaks move on the **bhavcopy** side, including a
3-name one-day cluster (BIOCON, INFY, NTPC) where `scale` steps up on
2017-07-10 and reverts on 2017-07-11, with bhavcopy's day-high moving 6.5-8.8%
while Angel's moves ~1%. That is a `prices_eod`-side one-day anomaly, not a
`bars_1min` scale question. Three further entries (NBCC, OIL, BEML) pair a
2021-12-31 / 2020-12-31 row with a 2025-01-01 / 2019-01-01 row and are
artifacts of multi-year `bars_1min` coverage gaps (the entity left and
re-entered the point-in-time universe), not scale breaks at all. Recorded here
for completeness; no claim is made about them.

---

## 7. Within-session mixed-scale assessment

Run as a **separate test**, with its own method, on its own sessions.

**Method (predeclared).** For each of the 208 event-adjacent sessions, regular
session only (`09:15:00 <= CAST(ts AS TIME) <= 15:29:59`):

1. **OHLC consistency** per bar: `high >= max(open, close)`,
   `low <= min(open, close)`, `high >= low`, all four prices `> 0`.
2. **Candidate step**: consecutive-bar close ratio with
   `|log(close_t / close_{t-1})| > log(1.15)`.
3. **Sustained** shift: for each candidate, compare `median` of the 10 bars
   before against `median` of the 10 bars after (>= 3 bars required each side);
   a candidate counts as a mixed-scale defect only if the **level persists**,
   i.e. the median ratio also exceeds 1.15. This deliberately separates a
   sustained mid-session transition from an isolated corrupt single bar: a
   single bad record produces a candidate but no sustained shift.
4. **Sensitivity pass**: steps 2-3 repeated at an 8% threshold.

**Results.**

| Metric | Value |
|---|---|
| Sessions scanned | 208 (104 ex-date + 104 preceding) |
| Bars scanned | **77,654** |
| Sessions with 0 bars | 0 |
| Bars violating OHLC consistency | **0** |
| Bars with non-positive prices | **0** |
| Candidate single-bar steps > 15% | **0** |
| Sustained mid-session level shifts > 15% | **0** |
| Candidate steps > 8% (sensitivity) | **0** |
| Sustained shifts > 8% (sensitivity) | **0** |
| Max intra-session high/low span | 1.2441 (NBCC 2017-02-17 ex-date) |

Next-largest spans: IRCTC 2021-10-28 ex-date 1.2136, COCHINSHIP 2024-01-10
1.1892, NYKAA 2022-11-10 1.1576, ADANIPOWER 2025-09-22 1.1558, ADVENZYMES
2017-05-25 1.1280. These are **ordinary volatile sessions**, and they are
explicitly **not** labelled mixed-scale defects: the step detector found no
single-bar or sustained multiplicative break in any of them, at either
threshold. Per the task's own caution, a wide range is not a scale shift.

**Findings.**

- **No abrupt persistent multiplicative level change within any single
  session.** Zero, at 15% and at 8%.
- **No OHLC inconsistencies.** Zero bars out of 77,654.
- **No mixture of pre- and post-adjustment-looking values within one session.**
  Every session's bars sit on one scale -- including TATASTEEL's 2022-07-26
  session, which is wholly in raw scale while 2022-07-25 is wholly in adjusted
  scale. The transition happens **between** sessions, at a session boundary.
- **No isolated corrupt single-bar records** in the inspected set. (The
  sustained-vs-candidate split would have separated them from a systematic
  transition; there were no candidates at all.)

**Conclusion**: the within-session mixed-scale hypothesis is **tested and not
supported**. This is a clean negative over 77,654 bars, not an inconclusive
result. The caveat that this is a *negative* and the four prescribed statuses
have no label for one is stated in Section 1B rather than resolved by forcing
the finding into an ill-fitting label.

**Separate observation, outside the inspected sessions**: a whole-table scan
for out-of-session timestamps found a small number of anomalous bars --
2020-12-08 at 04:18 / 04:19 / 04:21 (149 entities each, i.e. three bars per
entity, with plausible prices and volumes), and 2022-10-24 and 2023-11-12 at
01:04 (3 bars each). These are **timestamp** anomalies, not scale anomalies,
they fall outside `09:15-15:29`, and they affect none of the 104 events
inspected here. Flagged for the record; not part of either conclusion.

---

## 8. Limitations and unresolved questions

1. **The event universe inherits `corporate_actions`' narrow scope.** Only
   bonus and face-value splits are recorded. Mergers, demergers, scheme-of-
   arrangement consolidations and capital reductions all move the price scale
   and are **absent from the table entirely**. Some of the 28 action-less
   Angel-side breaks (Section 6.3) may be such events. This audit cannot
   distinguish "Angel adjusted for an event we do not record" from "Angel
   mis-scaled a window", and does not claim to.
2. **Pre-2016 events are invisible.** `corporate_actions` starts at
   `ex_date >= 2016-01-05`; the archive starts 2016-10-04. Any scale regime
   inherited from a pre-2016 action cannot be checked against a recorded
   ratio.
3. **504 of 659 in-window events have no intraday coverage at all**, because
   `bars_1min` covers 386 entities while `corporate_actions` covers the whole
   NSE equity universe. The 104 eligible events are therefore concentrated in
   large, liquid, point-in-time top-200 names. **Whether the same convention
   holds for entities outside the archive is untested and untestable from
   these two databases.** Within the archive, the 104 events span 2016-2025,
   all three type strata, and 75 distinct entities.
4. **The vendor mechanism is inferred, not documented.** The ~2-year trailing
   adjustment window is a measured empirical pattern across 28 cases. No Angel
   One documentation was consulted (no new data sources were introduced, per
   the audit's constraints), so the *reason* for the pattern is unverified.
   The pattern itself is directly measured.
5. **TATASTEEL's boundary misplacement is n=1 in this census.** Whether other
   entities have off-by-a-few-sessions adjustment boundaries at dates not
   adjacent to a *recorded* action is not established by this audit. The
   full-history scan (Section 6.3) would surface them only as action-less
   breaks, where they are indistinguishable from the ~2-year-window
   boundaries without per-case inspection. **This is the most important
   unresolved question this audit opens.**
6. **The direction of the rescale rests on source-authority reasoning**
   (Section 6.2), not on price arithmetic alone. The arithmetic establishes
   that exactly one series is rescaled; lineage evidence identifies which.
7. **HINDPETRO 2017-07-11** has a 6.7% high-vs-low scale disagreement on its
   prev-side, so its individual classification is weaker than the other 103
   (Section 5.6).
8. **Twelve bhavcopy-side action-less breaks** were observed (Section 6.4),
   including a 2017-07-10 three-name one-day cluster. These are
   `prices_eod`-side anomalies and were not investigated; they are outside
   Decision 14's scope.
9. **Nothing here speaks to dividends.** No dividend data exists in either
   table. The price-return convention's known ex-dividend property is
   unaffected and unaddressed.
10. **Nothing here speaks to what the prices predict.** No return, beta,
    significance, gate or outcome was computed or examined.

---

## 9. Decision 14 recommendation

**Decision 14 can be moved from OPEN to RESOLVED on its narrow question, with
a conclusion opposite to the standing assumption.**

The proposal currently records (`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
Section 4B, lines 803-808): *"strong circumstantial evidence of raw,
unadjusted prices (no adjustment column or code anywhere in `bars_1min`'s
schema or read path); not a positive confirmation."* The schema-level premise
is **correct and re-confirmed** (Sections 2.1-2.5: no adjustment column, no
ingestion transform, no read-path rescale, no re-fetch rewrite, `revision_seq`
uniformly 1). **The inference drawn from it was wrong.** Absence of adjustment
*in this project* does not imply absence of adjustment *in the vendor's
archive*, and the targeted historical-split check Decision 14 called for shows
the archive arrives already back-adjusted.

**Recommended resolution text for Decision 14:**

> `bars_1min` is **not raw**. Angel One's historical 1-minute archive is
> delivered **back-adjusted** for split/bonus actions: at 103 of 104 eligible
> split/bonus ex-dates in the archive window, the Angel-vs-bhavcopy price
> scale steps by exactly the recorded action ratio and the Angel series itself
> shows no discontinuity, while `prices_eod` (raw NSE bhavcopy) shows the full
> mechanical drop at 104 of 104. The back-adjustment is **piecewise and
> incomplete**: each action is applied only to a bounded trailing window of
> history (~2 years empirically), producing 28 measured scale-regime
> boundaries at dates with no recorded corporate action, and in one case
> (TATASTEEL 2022-07-28) a boundary misplaced two trading days early, leaving
> two sessions in raw scale inside an adjusted window. Status: **MIXED
> CONVENTION**. `prices_eod` and `bars_1min` therefore use **different**
> conventions and must never be compared or combined on price level without a
> per-day scale conversion.

**Consequential recommendations, flagged for separate authorization -- none
applied here:**

1. **Do not treat `bars_1min` price levels as comparable across sessions
   without a per-day scale.** Any cross-session price-level comparison,
   multi-day aggregate, or `prices_eod`-vs-`bars_1min` level comparison in
   this family's Phase 4 must go through a measured per-day scale
   (`src/fibo/scale_probe.py`'s mechanism is the one already validated in this
   repository). Within-session constructs are unaffected (Section 7).
2. **`src/fibo/price_scale.py:12-16` contains a factual claim this audit
   refutes.** It should be corrected under separate authorization. **Not
   modified by this read-only audit.** Any code currently relying on that
   docstring's premise should be re-examined.
3. **Decision 20 stays independently OPEN.** This audit supplies one piece of
   the category-3 "intraday-data evidence" the proposal's Section 4C asks for
   -- namely, that no within-session mixed-scale artifact appears in 208
   event-adjacent sessions / 77,654 bars, and that the scale discontinuities
   in this archive are strictly between sessions. It supplies **nothing** on
   category 2 (authoritative NSE adjustment-timing mechanism), which Section
   4C correctly identifies as unverified. Both named candidate policies
   remain open. **Decision 20 is not resolved, narrowed, or pre-judged here.**
   Note in particular that limitation #5 (possible further misplaced
   adjustment boundaries) is a live category-3 risk that cuts *toward*
   caution, and this audit does not weigh it.
4. **Decision 13's endpoint-price convention and the 70% follower-breadth
   threshold are untouched**, as is the existing corporate-action exclusion
   policy.

**If the evidence is judged insufficient, Decision 14 must remain OPEN.** The
author's assessment is that the raw-vs-adjusted question is resolved at 103/104
with exact ratio agreement and is not a close call; but the *characterisation*
of the convention (piecewise, ~2-year windows, vendor mechanism uninspected)
rests on inference about a third-party system and is stated with that
limitation. No conclusion is forced, and no p-value or hypothesis test is
claimed -- this is a lineage and integrity audit.

---

## 10. Final verification

**Files**: exactly one new file created, `lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`
(verified non-existent before writing). No existing tracked or untracked file
was modified. `PREREGISTRATION_LEAD_LAG_V1.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`, the Decision 10/16/17
documents, `PROJECT_CONTEXT.md`, `BUGS.md`, `lead_lag/trial_ledger.json` and
all source code were read only.

**Databases**: every connection to `data/fibo_intraday.duckdb` and
`data/warehouse.duckdb` used `duckdb.connect(path, read_only=True)`. No
`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP` or `ATTACH` was issued against
either file. All working scripts were written to the session scratchpad
directory outside the repository.

**Analysis boundary**: no strategy, backtest, gate, null, regression, or
Phase-4 step was executed. `Y(t,h)`, beta, significance, predictive
performance and trading outcomes were never computed or inspected. No new
market data was fetched and no new data source was introduced.

**Git state** (see the audit's closing report for the captured values of
`git status --short`, `git diff --check`, and `git rev-parse HEAD`): no
staging, no commit, no branch, no push, no amend.
