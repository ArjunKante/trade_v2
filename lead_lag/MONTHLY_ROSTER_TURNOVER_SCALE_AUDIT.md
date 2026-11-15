# Monthly Liquidity Roster / Trailing-Turnover Price-Scale Exposure Audit

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Scope**: Whether the monthly fixed liquidity-tier roster and its trailing-turnover
ranking are exposed to the `bars_1min` mixed price-scale convention established by
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`.
**Mode**: READ-ONLY. All database connections used `duckdb.connect(path, read_only=True)`.
No source file, test, config, database, ledger, preregistration, or proposal was
modified. No Phase 4 regression, gate, null, backtest, or outcome analysis was run.
No new market data was fetched. No alternative roster was computed.

---

## 1. Executive conclusion

### **UNAFFECTED BY DECISION 14 SCALE FINDINGS**

Every piece of code and documentation that defines the monthly liquidity roster's
turnover ranking — the one committed function (`fibo.universe.reconstitute_annually`),
the preregistration (original and amendment), the master spec, and the one
independently-executed empirical run of the monthly split
(`LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1) — agree on a single turnover
source: `prices_eod.turnover`, NSE's own pre-computed daily traded-value field,
loaded with no price arithmetic. `bars_1min` is never read for price, volume, or
turnover anywhere in this construction. Turnover is rupee-denominated and
split/bonus-invariant by definition (price divides, volume multiplies, by the same
factor), so even if it *had* used `bars_1min`, Decision 14's finding would not
necessarily move the rupee turnover total — but that question does not arise here,
because the input is categorically a different table.

This conclusion is qualified, not absolute, by one verification gap stated plainly
in Section 5: **the production code for the monthly leader/follower split (Section 6
of the preregistration) has not been committed to this repository.** It exists only
as (a) documented methodology, consistent across three independent documents, and
(b) one uncommitted scratchpad script whose *method description* — not its literal
source — is readable in `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`. The conclusion
rests on triangulating documentation plus one confirmed, committed, lower-layer
function, not on reading a single authoritative source file end to end. This is
disclosed, not glossed over.

---

## 2. Roster construction lineage

### 2.1 Two layers, only one of which is committed code

The monthly roster has two nested layers, per the preregistration and master spec:

1. **Annual point-in-time universe** (Section 4): top-200-by-trailing-turnover,
   reconstituted every January 1. **This layer is committed, executable code.**
2. **Monthly leader/follower split** (Section 6): within that year's annual
   universe, on the first trading day of each month, rank by trailing-60-session
   median turnover; top 20% = leaders, rest = followers (eligibility: >=60 trailing
   sessions of turnover history). **This layer is NOT committed code** — it is
   documented methodology, executed once as a throwaway, uncommitted script for a
   feasibility amendment, but no `lead_lag/` or `src/lead_lag/` source module exists
   in this repository implementing it. Confirmed by exhaustive search (Section 2.4
   below).

### 2.2 Layer 1 — `fibo.universe.reconstitute_annually`, read in full

File: `src/fibo/universe.py` (211 lines, read in full).

- **Entry point**: `reconstitute_annually(con, top_n=200)` (lines 78-113).
- **Turnover source**: `_entity_daily_turnover(con)` (lines 62-75):
  ```sql
  SELECT l.entity_id, p.trade_date, p.turnover
  FROM prices_eod p
  JOIN isin_lineage l ON p.isin = l.isin
  WHERE p.series = 'EQ' AND p.turnover IS NOT NULL AND p.turnover > 0
  ```
  Reads **only** `prices_eod.turnover` and `isin_lineage` for entity resolution.
  **No `bars_1min` reference anywhere in this file** (confirmed by reading all 211
  lines — the file's own module docstring, lines 27-32, states explicitly:
  *"TURNOVER, not adjusted price, is the ranking quantity — deliberately read
  straight from `prices_eod` (RAW close x volume, in rupees), not through
  `entity_panel`/`adjustment_factors`. Turnover in rupee terms is invariant to a
  split... so no split adjustment applies here at all."*
- **Aggregation**: median of daily turnover per `(entity_id, calendar_year)`
  (line 86), ranked descending with `entity_id` ascending as a deterministic
  tiebreak (lines 103-105).
- **Lookback**: a full prior calendar year (Y-1), not a trailing N-session rolling
  window — explicitly chosen over the continuously-rolling convention used
  elsewhere in the repo (`src/swing/universe.py`'s `historical_liquidity_tercile`,
  cited at line 19, for a different purpose).
- **Eligibility / point-in-time control**: a year only counts as a valid ranking
  base once its own data reaches November (lines 90-94, `complete_years`); the
  first year (2016) is dropped, not backfilled (lines 41-44 of the docstring).
  Membership for year Y is decided using only Y-1 data, no lookahead
  (`is_member`, lines 133-137).
- **Entity/ISIN resolution**: `isin_lineage` join (line 70), the same join pattern
  used project-wide for entity-level daily reads.
- **Caching**: `reconstitute_annually` recomputes from `prices_eod` on every call —
  no persisted/materialized roster table. It is called fresh each time a consuming
  script runs it (confirmed: no `CREATE TABLE`, no write statement anywhere in the
  file).
- **This is the identical function already reused by five other families**
  (Box Theory, FVG, POC, Liquidity A-D), per the project's own
  `lead_lag/DATA_AUDIT_LEAD_LAG.md` Section 1, and the lead-lag master spec Section 4
  states it is reused unchanged here too.

### 2.3 Layer 2 — monthly leader/follower split, documented but not committed

Three independent sources describe the identical construction:

- **`PREREGISTRATION_LEAD_LAG_V1.md` lines 459-466** (Section 6): *"within each
  year's point-in-time top-200-by-turnover annual universe (Section 4), on the
  first trading day of each calendar month, rank eligible entities by
  trailing-60-trading-session median daily rupee turnover (raw, from `prices_eod`,
  point-in-time — no bar after the ranking date is used). Top 20% of that month's
  eligible pool = leaders; held fixed for the month. An entity with fewer than 60
  trailing sessions of history as of the ranking date is excluded."*
- **`lead_lag/MASTER_SPEC_LEAD_LAG.md` Section 3, lines 426-435**: states Phase 4
  implementation should use *"the lighter direct `prices_eod` + `isin_lineage` join
  for turnover-ranking purposes specifically (turnover is split-invariant, so
  adjustment factors are not needed for that one purpose), reserving the full
  adjusted panel for where split/bonus-adjusted prices are actually required
  (return computation on intraday bars, which uses `bars_1min` directly, not
  `entity_panel` at all)."* This is the clearest statement in the repository that
  **turnover ranking and intraday return computation are deliberately kept on
  separate data paths** — `bars_1min` is reserved for the signal/response
  computation (a different part of the family, outside this audit's scope), never
  for roster construction.
- **`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1 "Method", lines
  66-82**: the one place this construction was actually *run* (read-only, against
  live data, in an uncommitted scratchpad script `task1_monthly_tiers.py`, per the
  document's own header, lines 6-9). Verbatim: *"every entity in that year's annual
  universe is ranked by trailing-60-trading-session median daily rupee turnover
  (`prices_eod.turnover`, raw, via a direct `prices_eod` + `isin_lineage` join —
  the full adjusted entity panel via `read_full_entity_panel_authorized` triggered
  a `MemoryError`... the lighter direct-turnover query, which needs no adjustment
  factors since turnover is split-invariant, was used throughout for reliability
  and speed)."*

All three agree: turnover source is `prices_eod.turnover`, raw, direct join with
`isin_lineage`, no `bars_1min`, no `adjustment_factors`, no `entity_panel`.

**One secondary, non-price detail surfaced in the Task 1 method description that
does touch `bars_1min` indirectly**: the ranking date itself — "the first trading
day of each calendar month" — is anchored *"per the intraday store's own
trading-day calendar"* (line 74 of the breadth-revision document). This means the
monthly scan iterates calendar months using `fibo_intraday.duckdb`'s own trading-day
list, not `prices_eod`'s. This is a **calendar-alignment dependency, not a
price-scale dependency** — it could in principle shift which exact date is used as
the ranking anchor if the two tables' trading-day calendars ever disagree, but it
has no mechanism to alter a turnover *value*, since `bars_1min` contributes no price
or volume to the ranking itself. Flagged for completeness in Section 7; it is
outside Decision 14's price-scale finding and not further investigated here per the
instruction against unnecessary analysis.

### 2.4 Confirmed: no committed roster/turnover module exists

Repository-wide search for `lead_lag`-specific implementation code:

```
Glob **/lead_lag*/**/*.py            -> lead_lag/ledger.py, lead_lag/test_ledger.py  (trial-ledger tooling only)
Glob src/lead_lag/**                 -> no matches
find src -iname '*turnover*'         -> no matches outside src/fibo/universe.py and src/swing/universe.py
find . -iname '*roster*'             -> no matches
```

`src/swing/universe.py::historical_liquidity_tercile` exists but is explicitly a
different, continuously-rolling construction for an unrelated 5-day-horizon swing
study (cited only as a contrast in `fibo/universe.py`'s own docstring, line 19) —
not part of the lead-lag call chain. `scripts/run_study2_largecap.py` (the only
other turnover/roster hit in the repo) is Study 2 of an unrelated large-cap
momentum replication, not the lead-lag family — verified by reading its docstring
("STUDY 2 — large-cap replication... momentum_12_1, long-only") and excluded per
the task's own warning not to confuse unrelated strategy universes.

**Conclusion of Section 2**: the lead-lag monthly roster's Phase 4 implementation
does not yet exist as a committed source file. What exists is (a) one confirmed,
read-in-full, committed function for the outer annual-universe layer, with zero
`bars_1min` involvement, and (b) consistent, triangulated documentation plus one
independently-executed (but uncommitted) empirical run for the inner monthly-split
layer, likewise with zero `bars_1min` involvement for the turnover value itself.

---

## 3. Input data conventions

| Input | Source | Table.column | Status | Evidence |
|---|---|---|---|---|
| Annual-universe turnover | `prices_eod.turnover` | NSE bhavcopy `TtlTrfVal`/`TOTTRDVAL` field | **RAW** | `src/data_layer/prices_nse.py` lines 54-74 (column mapping); Decision 14 Section 2.6 (prices_eod lineage, re-confirmed below) |
| Monthly-split turnover | `prices_eod.turnover` (documented identical source) | same | **RAW** (by documentation; code not committed) | Section 2.3 above |
| Entity resolution | `isin_lineage` | `isin -> entity_id` | not a price/volume input | `src/fibo/universe.py` line 70 |
| Any `bars_1min` price/volume | **none used** | n/a | n/a | Confirmed by full-file read of `universe.py`, and by the explicit disclaimer in master spec Section 3 |

### 3.1 `turnover` is not a computed `price x volume` product — it is NSE's own reported field

The task asks, if the calculation is `price x volume`, to identify exactly which
observations are multiplied. **It is not.** Verified against the live schema and
ingestion code:

```sql
-- data/warehouse.duckdb, live schema
SELECT column_name, data_type FROM information_schema.columns WHERE table_name='prices_eod';
-- ... open, high, low, close, last, prev_close DOUBLE; volume BIGINT; turnover DOUBLE; n_trades BIGINT ...
```

`src/data_layer/prices_nse.py` lines 54-74 map bhavcopy's own `TtlTrfVal` (UDIFF
format) / `TOTTRDVAL` (legacy format) columns directly to `turnover` — this is
NSE's own reported total traded value for the day, exactly as published in the
bhavcopy file, not a quantity this project derives by multiplying `close` and
`volume`. No `close * volume` or equivalent arithmetic exists anywhere in
`prices_nse.py` (grepped for `turnover`, `TtlTrfVal`, `TOTTRDVAL`, `close * volume`,
`price * volume` — only the direct column-rename mappings matched). Confirmed
re-reading Decision 14 Section 2.6: `prices_eod` is loaded "with no price
arithmetic" and "is never modified" — this audit's own check corroborates that for
the specific `turnover` field.

**Consequence**: because turnover is a single already-computed rupee-value field
from one raw source, the task's concern about mismatched price/volume scales
multiplying together does not apply — there are not two separately-sourced factors
to be scale-incompatible with each other.

### 3.2 Volume

`prices_eod.volume` (`TtlTradgVol`/`TOTTRDQTY`) is likewise loaded with no
arithmetic, from the same raw bhavcopy row as `turnover`. It is not separately
read or combined with any `bars_1min` volume anywhere in the traced call chain.
Per Decision 14 and this audit's own confirmation, volume's adjustment status is
not assumed from price's status (per the task's own caution) — it is independently
established here as raw, directly from the bhavcopy ingestion code, with no
transform step between parse and `INSERT`.

---

## 4. Scale-exposure analysis

**Turnover uses `prices_eod` exclusively** (Section 2). Per the task's own
decision tree:

> *"If turnover uses daily `prices_eod`: establish whether it uses raw daily price
> and raw volume. Determine whether any intraday price data enters the roster
> indirectly. Explain whether Decision 14's Angel One scale findings can affect
> this calculation."*

- **Raw daily price and raw volume**: established in Section 3 — `turnover` is
  NSE's own raw reported field, not derived from `close`/`volume` by this project,
  and both of its underlying bhavcopy inputs are loaded with no arithmetic.
- **Does any intraday price data enter the roster indirectly?** No price or volume
  data from `bars_1min` enters the turnover calculation at any traced step, in
  either the committed annual-universe code or the documented/executed monthly-split
  construction. The one `bars_1min` touchpoint identified (Section 2.3's calendar-
  anchoring note) affects only which *date* is used as a ranking snapshot, never a
  turnover *value* — it carries no price-scale information at all.
- **Can Decision 14's Angel One scale findings affect this calculation?**
  **No mechanism exists for them to do so.** Decision 14 found that `bars_1min`
  price *levels* are piecewise back-adjusted by the vendor. The roster's turnover
  ranking never reads a `bars_1min` price or volume column, so a scale change in a
  table that is never queried cannot alter a computation performed entirely on a
  different table. This is not a near-miss or a small-effect finding — it is an
  absence of a data-flow edge between the two.

### 4.1 Why the within-session-invariance context given in the task does not change this answer

The task's context notes that *"within-session endpoint returns are invariant to a
constant multiplicative scale factor, provided the relevant prices share that
factor."* That property is relevant to the family's **return/signal computation**
(`S_leader`, `AR_follower`), which does read `bars_1min` directly (master spec
Section 3, quoted in Section 2.3 above) — but it is not invoked here because this
audit's finding is stronger for the roster specifically: the roster's turnover
input never touches `bars_1min` at all, so the invariance property is not even
needed to neutralize an exposure — there is no exposure to neutralize in the first
place. (This audit does not re-examine the signal/response computation's own
scale-invariance; that is Decision 14's and the preregistration's territory, not
this roster-scoped audit's.)

### 4.2 Corporate-action boundaries and the lookback window

The task asks whether corporate-action boundaries "can affect the lookback window
and monthly membership" when turnover uses `bars_1min`. **This branch of the
decision tree does not apply**, since turnover does not use `bars_1min`. For
completeness: `prices_eod.turnover` is itself unaffected by a split/bonus's price
rescaling, because rupee turnover is invariant to a price/volume split by
definition (the module docstring's own stated reasoning, Section 2.2) — a named
corporate action changes `close` and `volume` oppositely and leaves `close *
true_volume` (= turnover) unchanged. This applies regardless of which archive the
price came from, so even under a hypothetical where turnover were computed as
`price x volume` from a mixed-scale source, a *clean* multiplicative rescale alone
would not move the product — though this audit does not rely on that argument,
since the actual input, `prices_eod.turnover`, is not computed from `price x
volume` at all (Section 3.1) and is independently established raw.

---

## 5. Demonstrated impact vs. theoretical exposure

**What the code proves, with certainty, from a fully-read committed source file**:
`fibo.universe.reconstitute_annually` and its helper `_entity_daily_turnover`
(`src/fibo/universe.py`, 211 lines, read in full) read only `prices_eod.turnover`
and `isin_lineage`. Zero `bars_1min` references. This is a code fact, not an
inference.

**What is established from consistent, triangulated documentation plus one
independently-executed (uncommitted) analysis, not from reading a single committed
production source file**: the monthly leader/follower split (preregistration
Section 6) also uses only `prices_eod.turnover`, identically sourced. Three
independent documents (preregistration, master spec, breadth-revision run)
describe/report the same construction with no divergence found between them.

**What is NOT established, and is explicitly not claimed**:
- No committed `lead_lag` roster source module exists to read end-to-end for the
  monthly-split layer; this audit cannot point to a single file and line range for
  that layer the way it can for the annual-universe layer.
- No roster membership change was computed, demonstrated, or even checked for,
  because the established data-flow finding (zero `bars_1min` input) makes such a
  check unnecessary — per the task's own instruction not to perform analysis the
  source path already makes unambiguous. **This audit does not claim that
  membership would or would not change under some alternative turnover
  definition; it establishes that the current definition has no path by which
  Decision 14's findings could reach it.**
- This audit did not re-verify that the uncommitted `task1_monthly_tiers.py`
  script, as actually run for the breadth revision, matches its own written method
  description byte-for-byte — that script is not present in this repository to
  read (confirmed by the search in Section 2.4). The conclusion rests on the
  method description and the one piece of code it explicitly reuses
  (`reconstitute_annually`), not on an independent re-execution.

---

## 6. Documentation consistency

No discrepancy was found between the preregistration, the master spec, and the
breadth-revision's executed-method description regarding the turnover source
itself — all three state `prices_eod.turnover`, raw, direct join, no adjustment
factors, consistently.

**One discrepancy found, unrelated to turnover but directly relevant to this
family's `bars_1min` documentation generally**: `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
(untracked, present in the working tree) still carries the **pre-Decision-14**
framing in two places:

- Line 806: *"unchanged conclusion... no adjustment column or code anywhere in
  `bars_1min`'s schema or read path... not a positive proof."*
- Line 1647 (open-items table): *"`bars_1min` adjustment status (raw vs. adjusted)
  | **OPEN** (schema-level evidence found, not a full confirmation) | Confirm via a
  targeted historical-split data check before Phase 4..."*

Decision 14 has since run exactly the "targeted historical-split data check" this
table calls for, and found **MIXED CONVENTION**, not raw. This proposal document
has not been updated to reflect that resolution — it still describes Decision 14's
question as open and still carries the schema-level "likely raw" framing that
Decision 14's own Section 9 explicitly identified as a refuted inference. **This is
a reported discrepancy, not resolved or corrected here** (read-only; the task
explicitly prohibits modifying the proposal). It has no bearing on this audit's
roster/turnover conclusion, since the roster never reads `bars_1min` regardless of
that table's adjustment status — but it is a live inconsistency the family's own
documents should reconcile before Phase 4, since it affects the signal/response
computation that *does* read `bars_1min` (outside this audit's scope).

---

## 7. Limitations and unresolved questions

1. **No committed source file implements the monthly leader/follower split.** This
   audit's conclusion for that layer rests on triangulated documentation and one
   described-but-not-present script, not a direct code read. If a future Phase 4
   implementation diverges from the documented construction (e.g., by reading
   `bars_1min` turnover instead of `prices_eod.turnover`, or by computing turnover
   as `close * volume` from a different table), this audit's conclusion would need
   to be re-run against that actual code — it is not a standing guarantee about
   code that does not yet exist.
2. **The ranking-anchor-date calendar dependency on `bars_1min`** (Section 2.3) is
   noted but not investigated further — it is a date-alignment question, not a
   price-scale question, and therefore outside Decision 14's finding and this
   audit's price-scale mandate. Whether `fibo_intraday.duckdb`'s trading-day
   calendar ever disagrees with `prices_eod`'s own calendar in a way that shifts a
   ranking date was not checked.
3. **This audit did not attempt to locate or re-run `task1_monthly_tiers.py`**
   (the uncommitted scratchpad script referenced in the breadth-revision document)
   because it is not part of this repository and reconstructing it would risk
   drifting from "trace the actual implementation" into "build a new one," which is
   out of scope.
4. **The documentation discrepancy in Section 6** is reported but not reconciled;
   whether `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`'s stale Decision 14
   framing is corrected is a decision for the methodology owner, not this audit.
5. **This audit does not address whether the signal/response computation
   (`S_leader`, `AR_follower`), which does read `bars_1min` directly per master
   spec Section 3, is exposed to Decision 14's findings.** That is a materially
   different question from the roster/turnover question this audit was scoped to,
   and the task's own context notes a candidate mitigating property
   (within-session endpoint invariance) that would need its own dedicated audit,
   not an incidental note here.

---

## 8. Recommended next action

**Narrowly scoped, not implemented here**: when Phase 4 roster-construction code is
actually written and committed, add a one-line structural assertion (in the spirit
of `fibo.universe.assert_universe_membership`, `src/fibo/universe.py` lines
189-210) that the turnover-ranking query's `FROM`/`JOIN` clause set contains
`prices_eod` and does not contain `bars_1min`, so that a future refactor cannot
silently reroute turnover ranking onto the mixed-scale intraday archive without a
loud failure. This is a suggestion for that future implementation step, not an
action taken by this read-only audit.

---

## 9. Final verification

**Files**: exactly one new file created, `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`
(confirmed non-existent before writing). No existing tracked or untracked file was
modified — `PREREGISTRATION_LEAD_LAG_V1.md`, `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
`lead_lag/MASTER_SPEC_LEAD_LAG.md`, `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md`,
`lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md`, `src/fibo/universe.py`,
`src/data_layer/prices_nse.py`, `lead_lag/trial_ledger.json`, and all other source
code were read only.

**Databases**: the one live query issued (`information_schema.columns` for
`prices_eod`) used `duckdb.connect('data/warehouse.duckdb', read_only=True)`. No
`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, or `ATTACH` was issued.

**New data**: none fetched. No new data source introduced.

**Prohibited analysis**: no strategy, regression, gate, null test, backtest, or
outcome analysis was run. No alternative roster, turnover definition, or ranking
was computed. No roster membership change was claimed or demonstrated — only the
absence of a data-flow mechanism was established.

**Git status** (`git status --short`, run after writing this report):
```
 M PREREGISTRATION_LEAD_LAG_V1.md          <- pre-existing modification, not made by this audit
?? LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md
?? lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md
?? lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md
?? lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md
?? lead_lag/DECISION_14_PRICE_ADJUSTMENT_AUDIT.md
?? lead_lag/DECISION_16_PREREGISTRATION_EXPOSURE_LOG.md
?? lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md
?? lead_lag/DECISION_17_REPRODUCIBILITY_AUDIT.md
?? lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md
?? lead_lag/METHODOLOGY_PROPOSAL_2026-11-08_PORTFOLIO_LEVEL_ESTIMAND.md
?? lead_lag/METHODOLOGY_REVIEW_2026-11-08_ESTIMAND_AND_NULL.md
?? lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md   <- this report, the only new file added by this audit
```
`git diff --check`: clean except a pre-existing LF/CRLF line-ending warning on
`PREREGISTRATION_LEAD_LAG_V1.md` (not introduced by this audit).

`git rev-parse HEAD`: `9f71b65e006f937760e39a9f65035c69a1ef8df9` — unchanged.

No staging, commit, branch, push, or amend occurred.
