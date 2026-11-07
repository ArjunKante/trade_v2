# Data Audit: Cross-Stock Lead-Lag Propagation (Phase 1)

Read-only audit, run against commit `c2a0d62`, 2026-11-07. Builds on
`LEAD_LAG_RECONNAISSANCE.md` (Phase 0) -- that document's own open
questions (§9) are what this audit answers. **No file was written,
updated, or deleted except this one.** All DuckDB connections opened via
`duckdb.connect(path, read_only=True)` directly (no write connection ever
opened). Queries were run with a throwaway script in the session scratchpad
(not committed to the repo); the exact SQL is reproduced inline below so
every number here is re-derivable.

---

## Verdict summary

| # | Area | Verdict | One-line reason |
|---|---|---|---|
| 1 | Existing per-study intraday DuckDB coverage | **PARTIAL** | One broad, reused store exists (`fibo_intraday.duckdb`, 386 entities, 2016-10-04 to 2026-09-18, top-200-by-turnover universe) and is already shared by Box Theory/FVG/POC/Liquidity A-D; IPO's store is narrow (listing-day only) and does not meaningfully extend it; Darvas never touches intraday at all. |
| 2 | `index_eod` population | **FAIL** (for sector use) | Only `NIFTY50` is populated (2016-01-01 to 2026-11-05, 2676 rows). Zero sectoral indices (NIFTYBANK, NIFTYIT, etc.) exist in the table. |
| 3 | Daily-bar coverage (`prices_eod` / `entity_panel`) | **PARTIAL** | `prices_eod` itself is current and complete (2016-01-01 to 2026-11-05, 5.13M rows, 4047 symbols). But the *materialized* convenience panel (`entity_prices_daily`, read via `entity_panel.read_entity_panel()`) is **stale**, physically truncated at 2025-03-18 -- the now-retired sealed-holdout boundary -- because it has not been re-materialized since the holdout was retired project-wide. A lead-lag study must not call the default `read_entity_panel()` without noticing this. |
| 4 | Sector-membership churn feasibility | **UNVERIFIABLE with current data** (reportable finding, not estimated) | Current-only snapshot (755 symbols, 22 industries), no `known_date`/point-in-time versioning anywhere in the repo. Churn cannot be measured, only assumed away or built fresh. |
| 5 | Angel One fetch feasibility arithmetic | **PARTIAL / feasible but not cheap** | Order-of-magnitude estimate below: a fresh N=200, Y=10-year 1-minute fetch is on the same order as the backfill already sitting in `fibo_intraday.duckdb` (386 entities, ~10 years) and that took ~4 elapsed calendar days of intermittent, supervised, restart-heavy fetching (13 separate script invocations), not one unattended run. |
| 6 | Data integrity spot checks | **PASS** | On the broadest store (`fibo_intraday.duckdb`, 169.9M rows): 0 duplicate (entity_id, ts) rows, 0 high<low rows, 1 close-outside-range row, 54 open-outside-range rows, 7018 zero-volume bars -- all negligible fractions of 169.9M. |

---

## 1. Existing per-study intraday DuckDB coverage

Schema confirmed first from `src/fibo/intraday_db.py` (table `bars_1min`,
columns `entity_id, isin, symbol, angel_token, trade_date, ts, open, high,
low, close, volume, known_date, fetched_at, source, revision_seq`) and
`src/ipo_listing/intraday_db.py` (table `bars_1min`, keyed by `listing_id`
rather than `entity_id`).

**Important correction to the Phase 0 recon's framing**: grepping
`box_theory/`, `fvg/`, `poc/`, and `liquidity/{a,b,c,d}.py` shows every one
of them takes an `intraday_con: duckdb.DuckDBPyConnection` parameter and
calls `fetch_bars_range(intraday_con, entity_id, ...)` against a
`bars_1min` table -- they do **not** maintain their own separate intraday
DuckDB files. Checking the driver scripts (`scripts/box_theory_dev_run.py`,
`scripts/box_theory_v2_dev_run.py`, `scripts/liquidity_{a,b,c,d}_dev_run.py`,
`scripts/liquidity_abc_horizon_diagnostic.py`, etc.) confirms
`INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"` in every one of
them. So **Box Theory, FVG, POC, and Liquidity A-D all read from the SAME
file, `data/fibo_intraday.duckdb`, not from separate per-study stores.**
Darvas never reads intraday data at all (`src/darvas/boxes.py`'s own
comment: operates on daily CLOSE only). This means the "fragmented across
multiple DuckDB files" framing in the Phase 0 recon applies to storage
*mechanism* (each major fetch effort chose its own file) but not to
*reuse* -- in practice there are really only two intraday stores that
matter: Fibo's (shared by five families) and IPO's (used only by IPO).

### `data/fibo_intraday.duckdb` (5.43 GB)

```sql
SELECT COUNT(*), COUNT(DISTINCT entity_id), MIN(trade_date), MAX(trade_date),
       COUNT(DISTINCT trade_date)
FROM bars_1min;
-- 169,935,257 rows | 386 distinct entities | 2016-10-04 | 2026-09-18 | 2468 distinct trade_dates

SELECT COUNT(DISTINCT entity_id || '|' || trade_date) FROM bars_1min;
-- 459,318 distinct (entity, trade_date) pairs
```

- Universe: `scripts/fibo_download_intraday_top200.py`'s own docstring
  confirms this is the **annually-reconstituted top-200-by-turnover
  universe** (`fibo.universe.reconstitute_annually`, top_n=200), full range
  2016-10-04 (Angel One's archive floor) to 2026-09-18 -- i.e. this is the
  project-wide "top-200 universe, 2016-10-04 onward" fact cited in
  `PROJECT_CONTEXT.md` §1, now confirmed to actually be backed by one real,
  persisted table (386 distinct entities, since annual top-200 turns over
  year to year; 386 > 200 because membership is not static across 10
  years).
- Sanity cross-check: 169,935,257 rows / 459,318 entity-days ≈ 369.8 bars
  per entity-day, consistent with a ~375-bar session (09:15-15:30, 1-minute
  bars) -- no gross row-count anomaly.
- `fetch_log_intraday`: 28,092 rows, **all** `status = 'ok'`. This number
  is smaller than the 459,318 entity-date pairs in `bars_1min` because the
  fetch log is written **per fetch chunk** (`CHUNK_DAYS = 25` in
  `src/fibo/download.py`), not per trading day -- one log row covers up to
  25 trading days. 28,092 chunks x ~16.3 avg trading days/chunk ≈ 459K,
  consistent order-of-magnitude; not a reconciliation defect, just a
  different granularity, noted explicitly per the stage-reconciliation
  standing rule.

### `data/ipo_listing/ipo_intraday.duckdb` (10.5 MB)

```sql
SELECT COUNT(*), COUNT(DISTINCT listing_id), MIN(listing_date), MAX(listing_date)
FROM bars_1min;
-- 178,393 rows | 501 distinct listings | 2016-10-04 | 2026-09-30
```

This store is **listing-day-only** (per listing: typically 1-3 days of
1-minute bars around its IPO listing date, not a continuous history) --
178,393 rows / 501 listings ≈ 356 bars/listing, i.e. roughly one trading
day's worth per listing on average. It is keyed by `listing_id`, not
`entity_id`, and has no ISIN/entity-lineage join path recorded in its own
schema (per its own docstring: "a listing has no pre-IPO entity identity in
this project's existing entity/ISIN-lineage system"). **This store does not
meaningfully extend or union with `fibo_intraday.duckdb`** for a cross-stock
lead-lag design: it covers isolated single days per name around IPO events,
not the sustained multi-year, multi-name overlap a lead-lag scan needs.

### Other per-study DuckDB files under `data/`

Full filesystem walk of `data/` for `*.duckdb`:

```
data/fibo_intraday.duckdb              5,434,781,696 bytes
data/warehouse.duckdb                  1,649,684,480 bytes
data/ipo_listing/ipo_intraday.duckdb      11,022,336 bytes
data/options_history/options_history.duckdb 173,289,472 bytes
```

No `box_theory`, `darvas`, `fvg`, `poc`, or `liquidity` -specific `.duckdb`
file exists anywhere under `data/` -- confirmed by the code-level finding
above: those five families read `fibo_intraday.duckdb` directly rather than
persisting their own. `options_history.duckdb` is NIFTY options EOD, not
equities, irrelevant to this study.

### Verdict for area 1

**`fibo_intraday.duckdb` is the one and only broad, reusable cross-stock
1-minute store in the repo**: 386 names, ~10 years, already covering the
exact top-200-by-turnover universe convention this project uses elsewhere.
It is the natural seed for an intraday-granularity lead-lag design with
**zero new fetching for any pair/combination drawn from its own 386-name,
2016-10-04-to-2026-09-18 coverage.** `ipo_intraday.duckdb` does not add
useful incremental coverage (different shape of data entirely -- isolated
listing-day windows, not a continuous panel) and should not be treated as a
second seed to union.

---

## 2. `index_eod` population (`data/warehouse.duckdb`)

Schema confirmed from `src/data_layer/db.py` (lines 71-82): `index_eod(index_name,
trade_date, open, high, low, close, known_date, fetched_at, source, revision_seq)`.

```sql
SELECT index_name, MIN(trade_date), MAX(trade_date), COUNT(*)
FROM index_eod GROUP BY index_name ORDER BY index_name;
-- NIFTY50 | 2016-01-01 | 2026-11-05 | 2676 rows
```

**Only one index, `NIFTY50`, is populated.** No row for NIFTYBANK, NIFTYIT,
NIFTYAUTO, NIFTYPHARMA, NIFTYFMCG, NIFTYMETAL, NIFTYENERGY, NIFTYREALTY,
NIFTYPSUBANK, or any other sectoral index exists in this table. The
Phase 0 recon's suspicion (table is generic, population is
backfill-script-dependent, `backfill_nifty_index.py`'s name suggests
Nifty-50-only) is **confirmed exactly**: the table has the schema to hold
sectoral indices but was never backfilled with them.

### Verdict for area 2

**FAIL for any design that wants a sectoral index level series
(e.g. "NIFTYBANK return as the sector benchmark").** The only ready-made
market/sector-level benchmark in this warehouse is the broad-market NIFTY50
series. A sector-based design would need either (a) a fresh NSE
all-indices backfill extended to sectoral index codes (new ingestion work,
out of scope for read-only Phase 1), or (b) a hand-built equal-weighted
sector proxy constructed from `prices_eod`/`entity_panel` plus the
current-only `symbol_industry_map.csv` (which inherits that file's
point-in-time blindness -- see area 4).

---

## 3. Daily-bar coverage (`prices_eod` / `entity_panel`, `data/warehouse.duckdb`)

```sql
SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM prices_eod;
-- 5,130,120 rows | 4047 distinct symbols | 2016-01-01 | 2026-11-05

SELECT COUNT(*), COUNT(DISTINCT entity_id), MIN(trade_date), MAX(trade_date) FROM entity_prices_daily;
-- 3,455,273 rows | 2464 distinct entity_id | 2016-01-01 | 2025-03-18
```

`prices_eod` (the raw NSE bhavcopy fact table) is current through
2026-11-05, 4047 distinct symbols, 10+ years -- this is the real, usable
daily-bar universe for a lead-lag design, no gaps found at this
coarse-grained check.

**Finding, not previously documented in the Phase 0 recon**:
`entity_prices_daily` -- the table behind `entity_panel.read_entity_panel()`,
the convenience function the recon flagged as "almost certainly the base
panel a lead-lag study would read from" -- stops at **2025-03-18**, roughly
20 months stale relative to `prices_eod`'s 2026-11-05. Reading
`src/data_layer/entity_panel.py` explains why exactly:
`materialize_entity_panel()` hard-codes
`end = SEALED_HOLDOUT_START - timedelta(days=1)` and
`SEALED_HOLDOUT_START = date(2025, 3, 19)` (`src/data_layer/holdout.py` line 22,
comment: "fixed permanently from here"). `2025-03-19 - 1 day = 2025-03-18`,
matching the observed max exactly. `PROJECT_CONTEXT.md`'s live-state table
says the historical holdout is now **RETIRED** project-wide, but
`entity_prices_daily` was never re-materialized after that retirement --
it is a derived/cached table ("Derived, fully recomputed each run... not
append-only facts", per the module's own docstring), and nothing re-ran
`materialize_entity_panel()` since the holdout's retirement.

This is **not** a data-loss problem (`prices_eod`, `isin_lineage`, and
`adjustment_factors` all still have the full current range -- confirmed:
`prices_eod` max is 2026-11-05) -- it is a **stale-cache** problem specific
to the one convenience read path (`read_entity_panel()`). The module itself
already provides the fix: `read_full_entity_panel_authorized(con,
authorize_holdout=True)` bypasses `entity_prices_daily` entirely and
queries `prices_eod` + `isin_lineage` + `adjustment_factors` directly,
unrestricted -- appropriate now that the holdout is retired project-wide.
**A lead-lag study must use `read_full_entity_panel_authorized(...,
authorize_holdout=True)` or query `prices_eod` directly, never the bare
`read_entity_panel()`, or it will silently lose the most recent ~20 months
of data.** This is exactly the kind of silent-staleness defect the
project's own "a figure is not a fact until committed" and "reconcile stage
counts" standing rules exist to catch -- flagged here before any lead-lag
code is written, not after.

### Verdict for area 3

**PARTIAL**: the underlying daily-bar data (`prices_eod`) is complete and
current -- PASS on its own. The commonly-reused convenience read path
(`read_entity_panel()`) is stale by ~20 months -- would FAIL silently if
used naively. Net: usable for a daily-bar-only design with **no new
fetch**, provided the study's own data-loading code uses the
holdout-bypassing read path (or queries `prices_eod` directly) rather than
the default convenience function.

---

## 4. Sector-membership churn feasibility check

```
data/raw/sector/symbol_industry_map.csv       : 755 distinct symbols, 22 distinct industries
data/raw/sector/ind_nifty100list.csv          : 100 rows
data/raw/sector/ind_nifty200list.csv          : 200 rows
data/raw/sector/ind_nifty500list.csv          : 501 rows
data/raw/sector/ind_niftytotalmarket_list.csv : 755 rows
```

Industry breakdown (top entries): Financial Services 121, Capital Goods 114,
Healthcare 71, Automobile and Auto Components 48, FMCG 46, Consumer
Services 46, Chemicals 45, Consumer Durables 41, Information Technology 36,
... (22 industries total, long tail down to Utilities at 4).

All five files share the same fetch date (mtime 2026-09-20, per Phase 0
recon) and **none carries a date column, `known_date`, or `revision_seq`**.
Grepped the full repo again for any reference to a historical/point-in-time
version of sector or index-constituent membership: none exists.
`src/reports/fundamental_snapshot.py:53` is still the only code reference
to `symbol_industry_map.csv`, for a display/report, not a backtest.

### Verdict for area 4

**UNVERIFIABLE with current data, explicitly, not an estimate.** The repo
contains exactly one current-dated snapshot of symbol->industry mapping and
one current-dated snapshot each of the Nifty 100/200/500/total-market
constituent lists. There is no second, earlier snapshot anywhere in the
repo to diff against, no `known_date` field, and no corporate-action-style
historical reconstruction for sector/index membership (unlike prices, which
do have a full point-in-time lineage/adjustment system). **Sector or index
constituent churn across 2016-2026 literally cannot be measured from data
that exists in this repo today** -- not "probably small," not "probably
large," simply unmeasurable without a new data-collection effort (e.g.
scraping NSE's historical index-reconstitution announcements, which is out
of scope for a read-only Phase 1 audit and was not attempted here). Any
design decision resting on "sector membership doesn't churn much" would be
an unverified assumption, not a measured fact.

---

## 5. Angel One fetch feasibility arithmetic

**Documented limits** (`OPERATIONS.md`, "Angel One rate limiting" section,
confirmed live against Angel's own docs): `getCandleData` = 3 req/sec,
150 req/min, 5000 req/hour, no documented daily cap. Separately,
`getMarketData` (a *quote* call, not candles) hard-caps at 50 instruments
per call (error `AB4029` above that) -- this is a different endpoint from
the historical-candle fetch a lead-lag backfill would use, so the
50-instrument cap does not directly reduce the number of *candle* calls
needed; it would only matter if the design also needs live quote snapshots
across many names at once.

**What was actually observed in practice** (`OPERATIONS.md` lines 104-167):
the realized limits are *tighter* than the documented ones, twice: a
rate-limit-shaped error after only ~6 requests on 2026-10-09, and after
"502 successful requests in roughly 10 minutes" on 2026-09-30 during
`scripts/fibo_download_intraday_top200.py`'s run -- both well inside every
documented ceiling, attributed to an undocumented burst or cumulative/daily
quota. The project's own standing policy for the bulk backfill scripts is
"stop immediately on a rate-limit error, rely on resumability, never
retry-in-place" -- i.e. the realistic throughput is bursty and
operator-supervised, not a clean continuous rate.

**Empirical anchor**: the actual backfill that produced
`fibo_intraday.duckdb`'s current 386-entity, ~10-year coverage ran across
13 separate script invocations between 2026-09-28 and 2026-10-01
(`data/fibo_logs/download_*.log`, 13 files spanning ~4 calendar days) --
i.e. getting to the current ~386-name, 10-year 1-minute archive took
roughly **4 elapsed days of intermittent, restart-heavy fetching**, not one
unattended run, even though total CPU/network time was much smaller (502
requests in 10 minutes before one of the stops implies the actual
request-issuing time was a small fraction of the 4 elapsed days -- most of
the elapsed time was gaps between restarts/relogins, not throttled
waiting).

**Order-of-magnitude estimate for a fresh N=200, Y=10-year 1-minute fetch**,
stated with explicit assumptions:

- Assume `CHUNK_DAYS = 25` trading days per `getCandleData` call (the
  project's own existing convention, `src/fibo/download.py`).
- Assume ~2500 trading days in 10 years (≈ 250 trading days/year x 10).
- Chunks needed per name ≈ 2500 / 25 = 100 calls.
- Total calls for N=200 names ≈ 200 x 100 = **20,000 `getCandleData` calls**.
- At the *self-imposed* throttle actually coded into the existing backfill
  script (0.4s/request, i.e. 2.5 req/sec, with a 140-req/min rolling-window
  self-throttle) and ignoring any stops: 20,000 x 0.4s = 8,000s ≈ **2.2
  hours of pure request time** -- this is the optimistic floor.
- Given the *observed* reality (undocumented stops after as few as ~6 and
  as many as ~502 requests, each requiring manual/auto relogin and a fresh
  script invocation to resume), the realistic wall-clock is dominated by
  restart overhead, not throttle math -- the empirical anchor above
  (~4 elapsed days for a comparable-order-of-magnitude backfill, 386 names
  x ~10 years) is a more trustworthy estimate than the throttle arithmetic
  alone. **Order-of-magnitude: a few days to roughly a week of elapsed,
  supervised wall-clock time**, not minutes and not months, for a genuinely
  new N=200/Y=10yr fetch from zero.
- If the design can restrict itself to names/date ranges already inside
  `fibo_intraday.duckdb`'s existing 386-name, 2016-10-04-to-2026-09-18
  coverage (area 1), **this cost is entirely avoidable** -- zero new calls
  needed for any pair drawn from that set.

### Verdict for area 5

**PARTIAL / feasible but not cheap.** A full fresh N=200, Y=10-year fetch
is feasible in roughly a week of supervised elapsed time, based on this
project's own prior experience fetching a comparable-sized universe --
this is not a Liquidity-F-style infeasible (~45-50h unattended, structurally
confounded) case, but it is also not a "run it and walk away" case, given
the twice-observed undocumented rate-limit/quota stops. Reusing the
already-fetched 386-name universe avoids this cost entirely for any design
that can live inside that name set and date range.

---

## 6. Data integrity spot checks (`fibo_intraday.duckdb`, broadest store)

```sql
-- duplicate (entity_id, ts) rows (grouped):
SELECT COUNT(*) FROM (
  SELECT entity_id, ts, COUNT(*) c FROM bars_1min GROUP BY entity_id, ts HAVING COUNT(*) > 1
);
-- 0

SELECT COUNT(*) FROM bars_1min WHERE volume = 0;
-- 7,018   (out of 169,935,257 rows -> 0.0041%)

SELECT COUNT(*) FROM bars_1min WHERE high < low;
-- 0

SELECT COUNT(*) FROM bars_1min WHERE close > high OR close < low;
-- 1        (out of 169,935,257 -> negligible, single row)

SELECT COUNT(*) FROM bars_1min WHERE open > high OR open < low;
-- 54       (out of 169,935,257 -> 0.00003%)
```

### Verdict for area 6

**PASS.** No duplicate-key rows (the exact defect class the project's own
`read_latest()`/revision-dedup discipline exists to guard against, though
this table doesn't even need it empirically). No high<low inversions. A
single close-outside-range row and 54 open-outside-range rows out of 169.9M
are consistent with isolated feed glitches, not a systemic defect, and the
7,018 zero-volume bars (illiquid-minute, no trades that bar -- expected
behavior, not corruption) are a trivial fraction. This is a cheap
spot-check, not an exhaustive audit -- no attempt was made to check
cross-day continuity, corporate-action alignment inside the intraday store,
or token/symbol-remap correctness (Bug #18's price-scale class of defect
lives in a different code path, `fibo.scale_probe` vs `adjustment_factors`,
not checked here since it is outside this table's own schema).

---

## Implication for study design

**1. Daily-bar-only design (no new fetch): immediately feasible, with one
fix needed to the read path.** `prices_eod` is complete and current
(2016-01-01 to 2026-11-05, 4047 symbols). The study must call
`entity_panel.read_full_entity_panel_authorized(con, authorize_holdout=True)`
(or query `prices_eod`/`isin_lineage`/`adjustment_factors` directly) rather
than the stale `read_entity_panel()` convenience function, which is
truncated at 2025-03-18 and has not been re-materialized since the holdout
retirement. With that one adjustment, a daily-bar lead-lag design needs
**zero new data infrastructure.**

**2. Intraday (1-minute) design: feasible without a large new fetch, IF the
study scopes itself to the existing `fibo_intraday.duckdb` universe and
date range.** 386 entities, 2016-10-04 to 2026-09-18, already the project's
standard top-200-by-turnover annually-reconstituted universe, already
reused by five other families (Box Theory, FVG, POC, Liquidity A-D) with
zero reported data-availability problems. A design that needs names or
dates *outside* that set (e.g. extending past 2026-09-18 to the present, or
reaching below the historical top-200 cutoff) requires a new fetch on the
order of days to about a week of supervised wall-clock time per the area 5
arithmetic -- feasible, but a real cost to budget for, not a quick
addition. Recommendation: **design the intraday arm, if pursued, around the
existing 386-name/2016-10-04-2026-09-18 coverage first**, and treat any
extension beyond it as a separate, explicitly costed follow-up fetch rather
than an assumed-free addition.

**3. Sector-based grouping: not usable as a point-in-time mechanism; must
be sector-agnostic or explicitly flagged as a simplifying assumption.**
Two independent gaps compound here: (a) `index_eod` has no sectoral index
series at all, only NIFTY50 (area 2) -- there is no ready-made sector
benchmark return series to regress against; (b) the one sector/industry
mapping that exists is a current-only, non-point-in-time snapshot with no
historical version to diff against, so churn is UNVERIFIABLE, not merely
unmeasured-but-assumed-small (area 4). Combining these: a design that
groups stocks by sector for a leader/follower structure has no data-backed
way to know whether 2017's sector membership matched 2026's, and no sector
index to use as a benchmark even if membership were known. **Recommendation:
scope the lead-lag mechanism to something that does not require sector
labels at all** -- pure statistical pairs/clusters derived directly from
price/turnover co-movement, or index-co-membership (Nifty 50/100/200/500
tiers, which at least has a defined current snapshot and an implicit
turnover-based analogue already built into `fibo.universe.reconstitute_annually`
for point-in-time universe membership) -- rather than a sector-propagation
design that would need to either build a new point-in-time sector-history
reconstruction from scratch (real new engineering work, not a data-audit
finding) or proceed on an explicitly-flagged, unverifiable point-in-time-blind
assumption.

---

## Files referenced in this audit (absolute paths)

- `C:\projects\trade-new\lead_lag\LEAD_LAG_RECONNAISSANCE.md`
- `C:\projects\trade-new\data\fibo_intraday.duckdb`
- `C:\projects\trade-new\data\ipo_listing\ipo_intraday.duckdb`
- `C:\projects\trade-new\data\warehouse.duckdb`
- `C:\projects\trade-new\data\options_history\options_history.duckdb`
- `C:\projects\trade-new\src\fibo\intraday_db.py`
- `C:\projects\trade-new\src\ipo_listing\intraday_db.py`
- `C:\projects\trade-new\src\data_layer\db.py`
- `C:\projects\trade-new\src\data_layer\entity_panel.py`
- `C:\projects\trade-new\src\data_layer\holdout.py`
- `C:\projects\trade-new\src\fibo\download.py`
- `C:\projects\trade-new\scripts\fibo_download_intraday_top200.py`
- `C:\projects\trade-new\scripts\box_theory_dev_run.py`
- `C:\projects\trade-new\scripts\box_theory_v2_dev_run.py`
- `C:\projects\trade-new\scripts\liquidity_a_dev_run.py`
- `C:\projects\trade-new\scripts\liquidity_b_dev_run.py`
- `C:\projects\trade-new\scripts\liquidity_c_dev_run.py`
- `C:\projects\trade-new\scripts\liquidity_d_dev_run.py`
- `C:\projects\trade-new\scripts\liquidity_abc_horizon_diagnostic.py`
- `C:\projects\trade-new\scripts\liquidity_abc_mae_diagnostic.py`
- `C:\projects\trade-new\src\box_theory\universe_data.py`
- `C:\projects\trade-new\src\darvas\boxes.py`
- `C:\projects\trade-new\data\fibo_logs\` (13 `download*.log` files, 2026-09-28 to 2026-10-01)
- `C:\projects\trade-new\OPERATIONS.md` (Angel One rate limiting section, lines 104-167; `getMarketData` 50-token cap, lines 169-177)
- `C:\projects\trade-new\PROJECT_CONTEXT.md` (line ~83, documented Angel One limits; holdout-retired live-state table)
- `C:\projects\trade-new\data\raw\sector\symbol_industry_map.csv`
- `C:\projects\trade-new\data\raw\sector\ind_nifty100list.csv`
- `C:\projects\trade-new\data\raw\sector\ind_nifty200list.csv`
- `C:\projects\trade-new\data\raw\sector\ind_nifty500list.csv`
- `C:\projects\trade-new\data\raw\sector\ind_niftytotalmarket_list.csv`
- `C:\projects\trade-new\src\reports\fundamental_snapshot.py`
