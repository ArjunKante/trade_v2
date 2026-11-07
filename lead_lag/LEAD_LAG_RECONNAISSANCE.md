# Lead-Lag Reconnaissance

Read-only recon for a brand-new research family: cross-stock lead-lag
propagation. **No strategy code written. No data touched beyond read-only
schema/metadata inspection.** Written 2026-11-07, against commit `c2a0d62`
(HEAD at time of writing; `git log --oneline -20` shows the Liquidity
family closure as the immediately preceding work).

---

## 1. Repository / project structure conventions

- Root is flat, not nested by family: every study gets `<NAME>.md` (design
  doc, book-sourced studies only), `PREREGISTRATION_<NAME>.md` (frozen
  before any result), `<NAME>_FINDINGS.md` (result record, append-only
  once closed — annotated, never edited), and sometimes
  `<NAME>_<FAMILY>_CLOSED.md` or `<NAME>_ABANDONED.md` for a family-level
  closure note (e.g. `LIQUIDITY_FAMILY_CLOSED.md`, `LIQUIDITY_F_ABANDONED.md`).
  A standalone measurement that isn't a full study gets `MEASUREMENT_<NAME>.md`
  (e.g. `MEASUREMENT_F_REJECTED_BUCKETS.md`).
- Strategy code lives under `src/<family_lowercase>/` (e.g. `src/liquidity/`,
  `src/darvas/`, `src/fvg/`, `src/box_theory/`, `src/poc/`, `src/swing/`,
  `src/per_stock/`, `src/ipo_listing/`), one module per concern inside
  (`backtest.py`, `nulls.py`, `costs.py`, `universe.py`/`universe_data.py`,
  `context.py`, `resolution.py`, `bars.py`/`intraday_db.py`). This project
  put `src/lead_lag/` as the natural home for new code — **not created by
  this recon**, per instructions.
- Driver scripts live in `scripts/` (`<name>_dev_run.py`, `<name>_handtrace.py`,
  `<name>_unit_test.py`), never inside `src/`.
- `PROJECT_CONTEXT.md` is the one living cross-session doc, appended to, never
  edited once a section closes; its own §7 is an append-only numbered
  "transferable findings" ledger (currently #1-15) and §3 holds the
  per-family trial-count table. Read this file first in any future session.
- `OPERATIONS.md` is the day-to-day operational log (97KB) — scheduler
  issues, rate limits, bug discoveries, and **STANDING RULE** blocks. Search
  it by grepping `STANDING RULE`, not by section, per its own rule (§6
  below).
- `BUGS.md` is the numbered bug ledger (~18 bugs as of now), referenced by
  number (`Bug #18`) everywhere else rather than re-described.

---

## 2. Reusable infrastructure inventory

### Data layer (`src/data_layer/`) — all REUSABLE (read-only reuse)

| File | Purpose |
|---|---|
| `db.py` | DuckDB connection helpers. `get_connection()` (write, ingestion-only), `get_read_connection()` (read-only, enforced at connection level — reports must use this), `read_latest()` (dedupe a fact table to one row per logical key by max `revision_seq` — **every reader must go through this**, per its own docstring and `tests/test_revision_dedup_canary.py`), `query_as_of()` (point-in-time query with a defense-in-depth assertion against leaking `known_date > as_of`), `HoldoutViolationError`. |
| `prices_nse.py` | NSE bhavcopy (UDiFF + legacy) fetch/parse/load for daily EOD prices. Column maps for both formats, legacy/UDiFF cutover dates (legacy through 2024-07-05, UDiFF from 2024-01-01, overlap window for cross-validation). |
| `isin_lineage.py` | `parse_isin()`, `build_lineage()`, `build_entity_resolver(con, as_of=None)` — isin → `entity_id` map, **point-in-time** (a link only applies after its own `known_date`). This is the canonical entity-resolution path; use it, don't re-derive. |
| `entity_panel.py` | `materialize_entity_panel()` (write), `read_entity_panel()` / `read_full_entity_panel_authorized()` (read) — the materialized entity-adjusted daily price panel (one row per entity_id × trade_date, split/bonus-adjusted, lineage-joined). This is almost certainly the base panel a lead-lag study would read from. |
| `adjustment.py` | `materialize_adjustment_factors()` (write-only, never call from a report), `read_adjusted_prices(con, entity_id)` (read path). Two independent implementations (SQL and pure-Python) kept in parallel as a cross-check. |
| `corporate_actions.py` | Bonus/split ingestion, ISIN resolution for actions via (symbol, ex_date) against own price observations (NSE's own ISIN field on actions is unreliable — Bug #7 class). |
| `index_nse.py` | `fetch_and_parse()`, `load_index_day()`, `backfill_index_range()` — NSE's own daily all-indices close file. **This is the real Nifty 50 (and presumably other published indices') level history** — the natural source for a market-wide benchmark return series, which a lead-lag study will need. Confirm which index codes are actually backfilled before assuming sector indices (NIFTYBANK, NIFTYIT, etc.) are populated — the table (`index_eod`) is generic, but population is backfill-script-dependent (`scripts/backfill_nifty_index.py` — name suggests Nifty 50 only; verify in Phase 1). |
| `holdout.py` | `guard_date_range()`, `clip_to_pre_holdout()` — the sealed-holdout guard. **Still live code, but the holdout itself is retired project-wide** (`PROJECT_CONTEXT.md` §2, §10) — a new lead-lag study is DEV-only by definition; this module is now mostly a historical/legacy guard, not an active constraint, but worth importing for discipline/consistency if any date-range clipping is needed. |
| `staleness.py` | `latest_trade_date()`, `assert_data_current()` — freshness guard so a stale warehouse read fails loudly. |
| `entity_features.py` | `trailing_return(con, entity_id, as_of, lookback_days)` — simple trailing N-trading-day return on entity-adjusted close. Explicitly a **minimal validation helper**, not a production feature pipeline, per its own docstring — but structurally exactly the building block a lead-lag design needs (entity A's own trailing return, computed point-in-time, feeding a prediction about entity B). |
| `fundamentals_*.py`, `xbrl_parser.py`, `integrated_filing_nse.py` | Fundamentals pipeline — NOT relevant to lead-lag price propagation, included for completeness only. |
| `nse_holidays.py` | Holiday calendar — relevant for any daily-bar date-alignment logic. |

### Factors (`src/factors/`) — REUSABLE

| File | Purpose |
|---|---|
| `momentum.py` | `compute_momentum(panel, window, skip)`, `compute_momentum_12_1`, `compute_momentum_6_1` — Jegadeesh-Titman construction with an "unexplained jump" guard (`_is_unexplained_jump_row`, Bug #1 class) that excludes windows crossing an unrecorded lineage/price-jump boundary. Not reusable as a factor for lead-lag, but the jump-guard pattern and panel-handling convention are worth copying. |
| `target.py` | `compute_forward_return(panel, horizon)` — forward N-day return per entity, trading-day-indexed, same jump guard. Directly reusable as the "forward return to be predicted" side of a lead-lag design. |
| `ic_eval.py` | `daily_rank_ic()` (cross-sectional Spearman IC per date), `purged_fold_assignments()` / `fold_level_ic_report()` (PurgedKFold-style CV, DEV-only use), `nonoverlapping_ic_report()` (direct significance test for a parameter-free factor, non-overlapping spacing), `benjamini_hochberg()` (own BH implementation, not statsmodels — worth reusing directly for multiple-testing correction rather than re-implementing), `ic_by_year()` (descriptive). **This is the most directly reusable file in the repo for a lead-lag significance/correction framework.** |
| `fundamentals_factors.py`, `lowvol.py` | Not relevant to cross-stock propagation; low-vol factor construction pattern could be referenced for style but isn't needed. |

**No "sector classification," "NIFTY constituent," or "leave-one-out
cross-sectional benchmark" code exists anywhere in `src/factors/` or
elsewhere in `src/`.** Grepped for `sector`, `leave_one_out`,
`benchmark_return`, `equal_weight`, `cross_sectional_mean` across `src/` —
only `sector` hits are in fundamentals-screener/report code (see §4). A
leave-one-out market or sector benchmark (entity i's forward return vs. the
equal-weighted return of the OTHER entities, excluding i) would need to be
built fresh for this study — not a large build, but not already sitting
anywhere to import.

### Cost model code — PARTIALLY REUSABLE, none generic

There is no single shared `cost_model.py`. Every strategy family ported and
re-specified its own cost module from the sibling `trade-info` project's
ground-truth measurement, adjusted for its own holding structure:

- `src/swing/costs.py` — Groww-specific INTRADAY/DELIVERY cost model (STT,
  stamp duty, exchange charge, SEBI fee, GST, brokerage formula
  `min(Rs20, 0.1%)` floored at Rs5, DP charge Rs23.60/sell-day delivery-only),
  spread+impact range 6.0-19.0bps round-trip, **explicitly flagged in its
  own docstring as NOT validated for this project's universe** (ported from
  a 5-name, 2-reading, one-afternoon measurement in the sibling project).
  This is the most complete, best-documented cost model in the repo and the
  one most likely to be portable to a lead-lag study if the study trades at
  delivery/multi-day horizons — but it is a DELIVERY/INTRADAY retail-equity
  model, not calibrated for anything resembling a cross-stock pairs or
  basket structure.
- `src/darvas/costs.py`, `src/per_stock/costs.py` — same lineage, same
  caveats, each re-specified per study, not a shared import.
- `src/liquidity/*.py`, `src/spread_validation/estimators.py` — spread
  estimator implementations (Corwin-Schultz, Roll) — see §5 below, these
  are known to be badly wrong for NSE and should NOT be trusted directly.
- `src/options_history/fetch.py` — options-specific, not relevant.

**Verdict: reuse the cost-model PATTERN (statutory components stated
explicitly, spread/impact flagged as the least-certain input) but do not
import any existing cost module as-is; a lead-lag study's own trade
structure (number of legs, holding period, position count per signal) is
different enough from every existing family that a fresh, explicitly-flagged
cost model is warranted, same discipline as `swing/costs.py`'s own
docstring models.**

### Universe construction — REUSABLE PATTERN, NOT a single shared function

No single `universe.py` is shared; each family built its own point-in-time
top-N-by-turnover construction, same underlying idea, different window
convention:

- `src/fibo/universe.py` — top-50-by-turnover, **annually reconstituted**
  (membership for year Y = top 50 by median daily turnover over year Y-1,
  held fixed all of year Y), explicit survivorship-bias discussion in its
  own docstring (today's Nifty 50 membership would silently drop
  since-delisted/failed names), explicit 2016-first-year gap (no prior year
  to rank against, year dropped rather than proxied) and last-year gap
  (in-progress year excluded from ranking). Ranks by RAW turnover (price ×
  volume, unadjusted — correct, since rupee turnover is split-invariant).
- `src/swing/universe.py` — `historical_liquidity_tercile`, a
  **continuously-rolling** N-trading-day window (different convention,
  different purpose — a 5-day-horizon rule needs a rolling tercile, not a
  stable annual list).
- `src/box_theory/backtest.py`, `src/darvas/backtest.py`,
  `src/fvg/backtest.py` — all state "point-in-time top-200 universe, stub
  year 2016 filled from 2017" (same construction family as Fibo's, reused
  across studies via `fibo.universe`, per `darvas/backtest.py`'s own
  comment: "point-in-time top-200-by-turnover universe (`fibo.universe`,
  unchanged)").
- `src/per_stock/universe.py` — its own stock-selection logic for the
  per-stock weekly-rules study (42 trials, 0 survivors).

**PROJECT_CONTEXT.md §1 states the 1-minute intraday data is "top-200
universe" project-wide — but this is NOT one single always-current top-200
list; it is reconstructed per-study, annually, from `fibo.universe`'s
convention when reused, or redefined per family. A lead-lag study needs to
decide and preregister its own universe-construction convention explicitly
(annual reconstitution vs rolling, N=50 vs 200, ranking basis) rather than
assuming a single canonical "the top-200 universe" object exists to import.**
No existing survivorship-bias quantification doc was found beyond the
docstring-level discussion in `fibo/universe.py` itself, though
`scripts/run_survivorship_quantification.py` exists (not read in depth here
— flagged for Phase 1 follow-up if cross-stock survivorship matters, e.g. a
lead-lag pair where one leg later delists).

### Entity/ISIN resolution and corporate-action handling — REUSABLE

Covered under data_layer above: `isin_lineage.build_entity_resolver` for
ISIN→entity_id mapping, `corporate_actions.py` + `adjustment.py` for
split/bonus-adjusted prices. Both carry known, documented bug history (Bug
#7 ISIN mismatch — 166 orphaned companies; Bug #11 same-ISIN uncorrected
corporate actions — 78 entities) that is **already fixed in the current
code path**, per `PROJECT_CONTEXT.md` §6, but the general lesson ("a fix
applied only where the bug was noticed, not everywhere the same pattern
recurs" — finding #4, 7 known instances) means any new lead-lag-specific
price-reading code should go through `entity_panel.read_entity_panel` /
`adjustment.read_adjusted_prices` rather than re-deriving a price join, to
inherit the existing fixes rather than risk reintroducing the pattern.

### `src/liquidity/` — CONFIRMED CLOSED, NOT REUSABLE

`src/liquidity/{a,b,c,d}.py` exist (no `e.py`/`f.py` — both abandoned at
Phase 1 before implementation). Family status per `LIQUIDITY_FAMILY_CLOSED.md`:
4 DEV failures (A-D, all passing both nulls at the 100th percentile and
still losing money), 2 Phase 1 abandonments (E, F — both on timeframe/candle
width design flaws, not returns), 1 withdrawn measurement. **CLOSED
2026-11-07, no Study G.** Confirmed per instructions — not inspected for
entry-detector reuse, and explicitly not recommended for reuse: its
mechanism (multi-timeframe confluence sweep-and-reclaim) is single-stock,
not cross-stock, and the family's own closure reasoning is that filtering
the same mechanism further is not expected to behave differently (four
filter attempts, four null results).

---

## 3. Data storage mechanism

**No Postgres. No SQL server. Local DuckDB files, each a standalone
`.duckdb` on disk, opened via `duckdb.connect()`.** Confirmed via
`.env.example` (no DB_* vars at all — only `ANGEL_API_KEY` / Angel One
SmartAPI credentials and Gmail SMTP creds for Fibo's live alerting) and
`src/data_layer/db.py`'s own module docstring ("DuckDB connection and
append-only schema for the point-in-time warehouse").

Storage is **fragmented across multiple DuckDB files, not one unified
warehouse**:

| File | Size (as observed) | Contents |
|---|---|---|
| `data/warehouse.duckdb` | ~1.65GB | The main point-in-time warehouse: `prices_eod` (daily bhavcopy), `fundamentals_filings`/`fundamentals_xbrl_facts`, `corporate_actions`, `index_eod`, `entity_prices_daily`, `isin_lineage`(+ `_ambiguous`), `adjustment_factors`, `fetch_log`. Schema in `src/data_layer/db.py` lines 16-171. |
| `data/fibo_intraday.duckdb` | ~5.1GB | Fibo study's OWN 1-minute bars (`bars_1min` table, schema in `src/fibo/intraday_db.py`), fetched from Angel One for its own top-50-by-turnover universe only — **not a project-wide 1-minute archive**, scoped to the Fibo study's own universe/date range. |
| `data/ipo_listing/ipo_intraday.duckdb` | — | IPO listing-day 1-minute bars, 498 listings, its own separate file. |
| `data/options_history/options_history.duckdb` | — | NIFTY options EOD, unrelated to equities lead-lag. |

**Critical implication for a lead-lag study**: PROJECT_CONTEXT.md §1 states
"1-minute intraday bars, 2016-10-04 onward (Angel One's archive floor),
top-200 universe" as a project-wide data fact, but no single file or table
actually holds that — each intraday-consuming study (Fibo, box theory,
Darvas, FVG, IPO, POC, Liquidity) fetched and stored its OWN 1-minute bars
into its OWN DuckDB file for its OWN universe and date range (see
`src/fibo/intraday_db.py`'s own docstring: "deliberately its own file...
never sharing data/warehouse.duckdb", and `src/box_theory/bars.py`,
`src/darvas/boxes.py`, `src/fvg/bars.py`, `src/ipo_listing/intraday_db.py`
as separate per-study intraday-bar modules). **A cross-stock lead-lag study
needs synchronized 1-minute bars across MANY names on the SAME days — this
is exactly the shape of query none of the existing per-study intraday
stores were built for (each is single-study-scoped).** This is the single
largest open infrastructure question — see §8.

**Design conventions, all enforced project-wide and worth inheriting
unchanged**:
- Every fact table carries `known_date` (when knowable), `fetched_at`,
  `source`, `revision_seq` — append-only, corrections are new rows, never
  UPDATE/DELETE (`db.py` module docstring).
- `get_connection()` = write (ingestion scripts only); `get_read_connection()`
  = read-only, enforced at the connection level by DuckDB itself, specifically
  so a report script cannot accidentally hold a write lock or trigger
  materialization as a side effect (this exact bug cost the prior project a
  33-minute report run, per the docstring).
- `read_latest()` must be used for any fact-table read, to dedupe to one row
  per logical key by highest `revision_seq` — a bare `SELECT *` risks
  silently doubled rows the first time any key gets a second revision
  (`tests/test_revision_dedup_canary.py` is the regression guard).
- `query_as_of(con, table, as_of, ...)` — point-in-time query with an
  in-code assertion against leaking data past `as_of`, defense-in-depth
  against a future refactor dropping the WHERE clause.

**Daily bars**: `prices_eod` in `data/warehouse.duckdb`, read via
`entity_panel.read_entity_panel()` for the adjusted panel, or
`adjustment.read_adjusted_prices(con, entity_id)` for one entity.

**Sector/industry classification**: see §4 below — exists, but as a
current-only snapshot, not point-in-time.

---

## 4. Sector/industry classification availability: **UNVERIFIED-AS-POINT-IN-TIME (data exists, historical versioning does not)**

Found: `data/raw/sector/symbol_industry_map.csv` (756 lines, columns
`Symbol,Industry` — e.g. `360ONE,Financial Services`; `ABB,Capital Goods`;
`ACC,Construction Materials`), plus `ind_nifty100list.csv`,
`ind_nifty200list.csv`, `ind_nifty500list.csv`,
`ind_niftytotalmarket_list.csv` in the same directory (index-constituent
snapshot lists, same directory, fetched same day — Sep 20).

- **PASS**: the raw data for a CURRENT symbol→industry mapping and current
  Nifty 100/200/500/total-market constituent lists exists in the repo
  already, no new fetch needed to get *a* mapping.
- **FAIL / UNVERIFIED for historical use**: this file has no date column
  and no `known_date`/`revision_seq` — it is a single current-as-of-fetch
  snapshot (fetched 2026-09-20, per file mtime), not a point-in-time series.
  It is used in exactly one place in the codebase —
  `src/reports/fundamental_snapshot.py:53` (`SECTOR_MAP_CSV = ... /
  "symbol_industry_map.csv"`) — for a display/report, not for any backtest.
  **No other code references it.** This is the identical defect shape to
  **Bug #12** ("the fundamentals screener is current-state only... any
  screener-based historical variant is uncomputable," `PROJECT_CONTEXT.md`
  §6) and to the gap `NEW_RESEARCH_DIRECTION.md` Hypothesis C was deferred
  on (the fundamental screener needing to be made point-in-time before any
  historical use). Applying today's sector label to a 2017 trading day
  would be the same silent error class Bug #12 and the swing V5/V6 block
  already cost this project real design time to notice.
- A lead-lag study that wants to group stocks by sector (for a
  sector-propagation or leader-follower-within-sector design) **must either
  (a) treat sector membership as a point-in-time-blind simplifying
  assumption and say so explicitly in the preregistration, or (b) build a
  point-in-time sector-history reconstruction first** (there is no existing
  reconstruction to reuse — this would be new work, same shape as the
  still-not-built point-in-time fundamentals screener). No evidence either
  reconstruction has been attempted anywhere in this repo's history.
- No NIFTYBANK/NIFTYIT/NIFTYAUTO-style sector *index level* history was
  found (only the broad-market Nifty 50/100/200/500/total-market
  constituent *lists*, and `index_nse.py`'s generic `index_eod` table,
  whose actual population is Nifty-50-only per the backfill script name
  `backfill_nifty_index.py` — not verified further in this recon; check in
  Phase 1 whether any sectoral index was ever backfilled into `index_eod`
  before assuming it has more than the one series).

---

## 5. Spread/cost model validation status: **STILL PENDING, confirmed current as of this recon**

`PROJECT_CONTEXT.md` §2 (current live state table, written 2026-11-06) and
§10 state it explicitly: **"Specified, 24 names selected, awaiting
market-hours collection."** Confirmed by reading `SPREAD_ESTIMATOR_VALIDATION.md`'s
own closing "Status" section: *"Specification complete. Sample built and
written to `config/spread_validation_symbols.txt`... no live data
collected. Next: commit, report the hash, and wait for the user to start
live collection during market hours."* The document's stratified 24-name
sample, protocol, and refutation criteria are frozen (`PREREGISTRATION`-style
discipline applied to a measurement study, not a strategy), but **zero
days of live collection exist yet** — nothing has changed on this front
since PROJECT_CONTEXT.md was last written.

Separately, and already proven (not pending): `PROJECT_CONTEXT.md` §7
finding #2 — **Corwin-Schultz and Roll overstate Indian spreads by
12-31x** on normally-traded EQ names (accurate, ~1x, only on
trade-to-trade names). This finding predates and motivates the pending
validation study; it is itself not yet independently re-validated at
scale, only observed once (5 names, one afternoon, per `swing/costs.py`'s
own docstring describing the source measurement it ported).

**Implication for lead-lag**: any cost model for this new family cannot
lean on CS/Roll-derived spread estimates without the same 12-31x-overstatement
caveat attached, and cannot yet lean on the pending validation study either
(it has no results yet). The only grounded cost inputs available today are
the exact statutory components (STT, stamp duty, exchange charge, SEBI fee,
GST, brokerage) and the explicitly-flagged, not-yet-validated-for-any-new-universe
spread/impact range ported into `swing/costs.py` et al.

---

## 6. Standing rules from `OPERATIONS.md` directly relevant to a lead-lag study

All quoted verbatim, with their line numbers in `OPERATIONS.md` as read.

**Candle-count vs. minutes (line 1401, rule text at 1424-1435)**:
> "STANDING RULE: a rule expressed in CANDLES silently changes its real-time
> meaning when candle size is the variable under test... before finalizing
> any study that varies candle width (or any other time-bucketing
> granularity) as the independent variable, every OTHER rule in that study
> expressed as a candle count ('N candles,' 'within 3 bars,' a lookback of
> 'K candles') must be re-stated in real time (minutes) and held constant
> across arms — or the preregistration must say explicitly that it is
> deliberately letting that window vary too, and interpret any result
> accordingly."

**Directly on point for lead-lag**: a lead-lag study is *inherently* a
timeframe/lag comparison (does stock A's move N minutes ago predict stock
B's move now, and does that lag's *width* matter) — exactly the design
shape that broke Liquidity Study E and F. Any lag window (e.g. "the leader's
move in the prior 3 bars") must be specified in minutes and held constant
if bar size (1-min vs 5-min vs daily) is ever varied, or the study must
explicitly declare it is varying both at once. Window WIDTH and window
START are separate parameters (`PROJECT_CONTEXT.md` §7 finding #13) — a
slower/coarser bar's signal is only knowable at that bar's own close, so
comparing a 1-minute-lag design against a 1-hour-lag design is not just a
width question, it is also a *start-time* question, and Liquidity Study F
found this specific confound to be unidentifiable, not merely confounded,
when actionability welds the window's start to the slower timeframe.

**Power/MDE requirement (line 1327, rule text at 1345-1362)**:
> "STANDING RULE: any study comparing two or more configurations must
> compute the minimum detectable difference BEFORE the preregistration is
> finalized... compute the minimum detectable difference from the DATA'S
> OWN OBSERVED VARIANCE first — before the set of configurations to test,
> the significance threshold, or the decision rule is finalized... compute
> this from VARIANCE ONLY, never from a mean or an already-observed effect."

Directly applicable: a lead-lag study will almost certainly compare
multiple lag windows, multiple leader/follower universes, or multiple
lead-lag mechanisms (sector-pair, index-constituent, liquidity-tiered) —
each such comparison is a "configuration A vs B" case requiring an MDE
computed from variance alone, before the configuration grid or threshold is
fixed. Two prior studies (Portfolio construction, Combination) and two
Phase-1 abandonments (Liquidity E, F) were all closed or never run because
this was skipped or caught only incidentally.

**Multiple-testing / trial ledger convention (`PROJECT_CONTEXT.md` §3,
lines 132-164)**: *"Trial, defined: any configuration that reached a
pre-registered gate OR was killed at a Phase 1 feasibility check. Both
carry selection pressure."* Every lag window, every universe definition,
every leader/follower pairing rule tried — even if killed at a cheap Phase 1
check before a full DEV run — counts as a trial requiring Bonferroni/BH
correction across the family. The per-family trial-count table in
`PROJECT_CONTEXT.md` §3 is the format to follow: state the family's own
trial count and its own correction denominator explicitly in the
preregistration, not retroactively (this is exactly where the POC family's
stale-Bonferroni defect — finding #15 — went wrong: a flag written in a
per-study doc that never escalated).

**Liquidity family's "stage-reconciliation" standing rule (`OPERATIONS.md`
line 1481, text at 1483-1498)**:
> "STANDING RULE: reconcile stage counts before interpreting any result...
> Before reading the numbers from any stage, check its row counts against
> the prior stage's counts, unscaling where a sample fraction was applied,
> and check that the buckets sum to their parent. A mismatch is a defect
> until explained."

This caught the withdrawn Study F rejected-buckets measurement — a
selected bucket reconciled cleanly, two rejected buckets were short by
~15x, produced a plausible-looking but wrong result. Directly relevant to
lead-lag: any staged pipeline (e.g. "candidate leader-follower pairs" →
"pairs with sufficient co-occurrence" → "pairs passing a correlation
threshold" → "trades taken") must have its bucket counts reconciled against
the parent stage at every step before the final numbers are trusted.

**Counterfactual/null reuse rule (`PROJECT_CONTEXT.md` §7 finding #14,
`OPERATIONS.md` context around line 1500)**: *"A counterfactual must reuse
the original setup, not re-derive it... Any counterfactual, null or bucket
comparison must be constructed by reusing the recorded setup (extreme,
level, timestamp) from the stage under study, never by re-running a
detector."* For lead-lag's TIMING and SELECTION nulls, this means: when
building the matched-random-entry null, reuse the exact recorded
leader-event timestamps/levels from the stage that selected them, never
re-run the leader-detection logic from scratch on the null's own
(randomized) population — re-detection on a different population silently
changes what fraction passes a downstream filter, biasing the comparison
exactly as it did for the withdrawn Study F measurement.

**Checkpointing (`PROJECT_CONTEXT.md` §2, §11 rule 9)**: *"Long unattended
runs get killed by the environment frequently... Long runs must checkpoint
mid-stage."* A cross-stock lead-lag scan is likely to be the most
computationally expensive study attempted yet (pairwise or N-way
cross-correlation across a universe of ~50-200 names, potentially at
1-minute granularity) — checkpoint per stage AND per unit of work within a
stage (the Box Theory DEV run cost ~17 hours of wall clock for ~4 hours of
actual work specifically because Stage 3 had no mid-stage checkpoint,
`OPERATIONS.md` lines 965-1033) — plan this before the first full run, not
after a kill.

**Figures-are-not-facts-until-committed (`OPERATIONS.md` line 1533)**:
> "A FIGURE IS NOT A PROJECT FACT UNTIL IT IS COMMITTED. Statements made in
> conversation... are not records. If a figure cannot be traced to a
> committed file, it is UNVERIFIED regardless of who stated it or how
> confidently."

Applies directly to this recon document itself: nothing here should be
treated as settled design until it is itself committed and cross-checked
the way this rule demands.

**Bug #18 (price-scale, `PROJECT_CONTEXT.md` §6, lines 402-408)**: two
unreconciled price scales existed in the codebase (`scale_probe`, validated,
used for ORB/entry vs. `adjustment_factors`, blind to unrecorded corporate
actions, used for zone/swing) — disagreed on ~15-18% of days, changed WHICH
stocks were selected, inflated the Fibo result by adding false positives
while also wrongly rejecting many more true ones (found via the "measure
blast radius in both directions" rule, §7 finding #9). **Relevant to
lead-lag directly**: any lead-lag design reading prices through two
different code paths for two different purposes (e.g. a fast "is this a
leader event" scan on one price series and a slower "what's the follower's
actual tradeable fill" computation on another) must verify both paths
resolve to the same adjusted-price convention before trusting any
cross-stock timing result — this exact two-scale-divergence pattern is
what produced Bug #18 and it is a plausible shape for a lead-lag study to
reintroduce independently if it builds its own fast intraday scan path.

---

## 7. Prior-failure lessons bearing specifically on cross-stock propagation

- **No prior sector-momentum, sector-rotation, or cross-stock propagation
  study has been attempted in this project.** `NEW_RESEARCH_DIRECTION.md`
  (55KB, last substantive edit 2026-10-24) proposes exactly three
  candidates — A) a momentum-persistence stability *monitor* (descriptive,
  asserts nothing), B) loss-avoidance portfolio construction (bottom-decile
  exclusion), C) a fundamentals-based concentration/crash-risk filter on
  momentum — **none of which is cross-stock lead-lag or sector
  propagation.** Grepped the full document for `lead-lag`, `cross-stock`,
  `propagation`, `spillover`, `Granger`, `sector momentum`, `sector
  rotation` — zero matches. This is a genuinely new family, not a revival
  or variant of anything already designed, let alone tried.
- **The structural finding (`PROJECT_CONTEXT.md` §8)**: eleven intraday
  strategies with completely different logic (Darvas, Fibo zones, volume
  profile, FVG, IPO openings, liquidity sweeps) all landed in the same
  -0.1% to -0.3% per-trade band. The project's own reading is that this is
  "one constant seen through eleven lenses" — fixed per-trade costs against
  a shrinking available move at short horizons, not eleven unrelated bad
  ideas. **A lead-lag study that trades on an intraday or few-day horizon
  inherits the same prior skepticism** stated in `PROJECT_CONTEXT.md` §11
  rule 2: "Any intraday mean-reversion or level-bounce idea has a very poor
  prior." Lead-lag propagation is a different causal mechanism (information
  diffusion across related names, not level-bounce), so it is not
  automatically subject to the same closed-class reasoning — but the cost
  arithmetic (fixed per-trade cost vs. available move) applies regardless
  of mechanism, and should be gated with an MDE/cost check (§6 above)
  before any signal work starts, exactly as Swing's own Phase 1 cost gate
  did (break-even at 5 days needed IC≈0.05, exceeding every factor either
  project has ever measured at any horizon).
- **Momentum's one clean pass is at 63 trading days, cross-sectional,
  rank-based** (`PROJECT_CONTEXT.md` §4) — the only strategy in the whole
  project where the available move clearly exceeds fixed costs. A
  short-horizon (intraday or few-day) lead-lag design sits on the wrong
  side of the project's own single clearest lesson (§8: "costs are fixed
  per trade, the available move shrinks with the horizon") unless the
  study can argue, and ideally cheaply pre-check, that cross-stock
  information diffusion produces a materially larger available move than
  the single-stock mean-reversion/breakout mechanisms that have
  consistently failed at short horizons.
- **The calibration record (`PROJECT_CONTEXT.md` §9)**: Claude's own
  mechanism predictions have been wrong in the Liquidity family 5 times out
  of 5 (verdict right, mechanism wrong), and twice wrong on *count
  direction* specifically for a timeframe/coarseness manipulation (predicted
  fewer setups on the coarser grid in both Liquidity E and F Phase 1; both
  times there were more, because the conversion-rate effect dominated the
  level-count effect). **A lead-lag study is exactly this shape of
  manipulation** (coarser lag window / bar size vs finer) — treat any
  advance intuition about which lag window will show "more" or "cleaner"
  propagation as a hypothesis to falsify, not an assumption to design
  around, per this project's own explicit, repeated track record.
- **Confirmation/retest-style filters discard the winners** (finding #6,
  narrowed): any lead-lag design that requires a "confirmation" step
  (follower must retest a level, must show a minimum lagged correlation
  before counted) risks the same structural bias — a filter's condition
  determines which subsequent behavior it cannot select, and two
  independent studies (Liquidity C, D) measured this directly (discarded
  buckets averaging +0.87% to +1.0%, i.e. the filter was discarding
  winners). If a lead-lag design uses any confirmation/retest-style gate
  on the follower leg, measure what it discards, not just what it keeps.

---

## 8. Risks / gaps specific to the lead-lag study

1. **No unified 1-minute cross-stock data store exists.** Every prior
   intraday study fetched and stored its own 1-minute bars for its own
   (generally single-digit-to-200-name) universe into its own DuckDB file.
   A lead-lag study needs *synchronized* 1-minute bars across potentially
   the full universe, on the same trading days, which is a different shape
   of query from anything built so far. Phase 1 must determine: (a) which
   existing per-study intraday DB (if any) has the broadest universe/date
   coverage worth reusing as a seed, (b) how much new Angel One fetching
   this requires, and (c) Angel One's own rate limits (~3 req/sec, 50
   instruments/quote call, undocumented daily quota — `PROJECT_CONTEXT.md`
   §2) against the likely much larger fetch volume a many-name cross-stock
   study implies.
2. **No point-in-time sector/industry classification exists.** The one
   sector mapping file in the repo (`data/raw/sector/symbol_industry_map.csv`)
   is a current-only snapshot with no historical versioning, used nowhere
   in any backtest today. Any lead-lag design organized around sector pairs
   or within-sector leader/follower structure needs this gap closed first,
   or must explicitly flag the point-in-time-blindness as an assumption
   (same open problem that deferred `NEW_RESEARCH_DIRECTION.md` Hypothesis C).
3. **No reusable sector/market benchmark or leave-one-out cross-sectional
   construction exists.** Would need to be built fresh; `factors/ic_eval.py`'s
   `daily_rank_ic` and `benjamini_hochberg` are reusable for the statistics
   layer once the benchmark itself exists.
4. **Spread/cost model validation is still pending (zero days of live
   collection).** Any cost gate for a lead-lag study currently has to lean
   on the same not-yet-validated-for-this-universe statutory+ported-spread
   model every other family used, with the same explicit caveats — there is
   no better-grounded number to use today, and the one empirical spread
   finding available (CS/Roll overstate by 12-31x) argues for skepticism of
   any spread estimator rather than confidence in one.
5. **Universe/survivorship convention must be chosen and preregistered
   explicitly**, not assumed from "the top-200 universe" language in
   `PROJECT_CONTEXT.md` §1 — no single canonical, always-current top-200
   object exists; every family built its own annual or rolling
   reconstruction. A cross-stock study additionally needs to decide how to
   handle a pair where one leg enters/exits the universe or delists
   mid-study — not addressed by any existing universe module, since no
   prior family needed cross-entity survivorship coherence (each entity was
   evaluated independently).
6. **This is a fundamentally multi-entity design in a project whose
   entire null/correction/MDE framework was built for single-entity,
   single-trigger strategies.** The TIMING and SELECTION nulls
   (`PROJECT_CONTEXT.md` §3) are defined as "same stock-days, random entry
   time" and "random stock-days from the same universe" — a lead-lag null
   needs an additional axis (random LEADER-FOLLOWER pairing, not just
   random day/time) that has no precedent in this project to borrow from;
   designing this correctly is probably the single most novel
   methodological piece of this study, not a parameter choice.
7. **Angel One intraday data floor is 2016-10-04** (`PROJECT_CONTEXT.md`
   §1) — any lead-lag design needing intraday granularity is bounded to
   ~10 years, smaller still once a DEV-only (no holdout) carve-out and
   enough independent lag-events for power are considered; compute the MDE
   (§6 above) against this realistic sample ceiling before committing to
   an intraday-granularity design rather than a daily-bar one.

---

## 9. Open questions for Phase 1 (data audit) before design can proceed

1. Does ANY existing per-study intraday DuckDB (`fibo_intraday.duckdb`,
   `ipo_intraday.duckdb`) already cover a broad enough universe and date
   range to seed a cross-stock lead-lag Phase 1 sample cheaply, or does
   this require a fresh, large Angel One fetch from scratch? (Query each
   file's own `bars_1min` table for `COUNT(DISTINCT entity_id)`,
   `MIN(trade_date)`, `MAX(trade_date)` — the mechanism is a plain
   `duckdb.connect(path, read_only=True)` + SQL, no new script needed, but
   this recon deliberately did not run that query, per instructions to
   note the mechanism rather than execute a full audit.)
2. What is `index_eod`'s actual population — Nifty 50 only, or does it
   include any sectoral index (NIFTYBANK, NIFTYIT, etc.)? (`SELECT DISTINCT
   index_name FROM index_eod` against `data/warehouse.duckdb` via
   `get_read_connection` — same deliberately-not-run caveat.)
3. Is a daily-bar-only lead-lag design (using the already-complete,
   already-point-in-time `entity_panel`/`prices_eod` data, no new intraday
   fetch at all) sufficient to test the core hypothesis, or does the
   mechanism require intraday granularity to be meaningful? This decision
   alone determines whether any new data infrastructure is needed before
   Phase 1 can even run a feasibility check.
4. What is the actual minimum detectable propagation effect, computed from
   the OBSERVED VARIANCE of candidate follower-leg returns, before any
   universe/lag-window grid is finalized — per the MDE standing rule (§6).
   This is the single highest-priority Phase 1 deliverable, following the
   same discipline that closed Portfolio Construction and the
   momentum+fundamentals Combination before any compute was spent on an
   unanswerable comparison.
5. If sector/industry grouping is part of the design at all: is a
   point-in-time reconstruction of sector membership worth building (how
   much does membership actually churn across 2016-2026 — a cheap,
   measurable question before committing engineering time), or should the
   study explicitly scope itself to pairs/baskets that don't require sector
   labels at all (e.g. index-co-membership, supply-chain pairs specified by
   hand, or a sector-agnostic statistical lead-lag scan)?
6. What does Angel One's real fetch capacity look like for a many-name,
   multi-year 1-minute pull, given the already-documented ~3 req/sec, 50
   instruments/quote-call, and undocumented daily quota constraints — is a
   full cross-sectional 1-minute fetch even feasible in reasonable wall-clock
   time, or does the design need to fall back to daily bars or a reduced
   universe for this reason alone? (This is the same class of question that
   closed Liquidity F before any preregistration — a cheap feasibility
   estimate, not a full run, is the right first move.)

---

## Files referenced in this recon (absolute paths)

- `C:\projects\trade-new\PROJECT_CONTEXT.md`
- `C:\projects\trade-new\OPERATIONS.md`
- `C:\projects\trade-new\NEW_RESEARCH_DIRECTION.md`
- `C:\projects\trade-new\LIQUIDITY_FAMILY_CLOSED.md`
- `C:\projects\trade-new\LIQUIDITY_E_FINDINGS.md`
- `C:\projects\trade-new\LIQUIDITY_F_ABANDONED.md`
- `C:\projects\trade-new\LIQUIDITY_D_FINDINGS.md`
- `C:\projects\trade-new\SPREAD_ESTIMATOR_VALIDATION.md`
- `C:\projects\trade-new\.env.example`
- `C:\projects\trade-new\config\config.yaml`
- `C:\projects\trade-new\data\raw\sector\symbol_industry_map.csv`
- `C:\projects\trade-new\src\data_layer\db.py`
- `C:\projects\trade-new\src\data_layer\entity_panel.py`
- `C:\projects\trade-new\src\data_layer\adjustment.py`
- `C:\projects\trade-new\src\data_layer\isin_lineage.py`
- `C:\projects\trade-new\src\data_layer\corporate_actions.py`
- `C:\projects\trade-new\src\data_layer\index_nse.py`
- `C:\projects\trade-new\src\data_layer\holdout.py`
- `C:\projects\trade-new\src\data_layer\staleness.py`
- `C:\projects\trade-new\src\data_layer\entity_features.py`
- `C:\projects\trade-new\src\factors\momentum.py`
- `C:\projects\trade-new\src\factors\target.py`
- `C:\projects\trade-new\src\factors\ic_eval.py`
- `C:\projects\trade-new\src\fibo\universe.py`
- `C:\projects\trade-new\src\fibo\intraday_db.py`
- `C:\projects\trade-new\src\swing\costs.py`
- `C:\projects\trade-new\src\reports\fundamental_snapshot.py`
- `C:\projects\trade-new\src\liquidity\{a,b,c,d}.py`
- `C:\projects\trade-new\tests\test_isin_lineage.py`
