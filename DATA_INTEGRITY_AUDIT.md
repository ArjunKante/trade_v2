# Data integrity audit: Fibo intraday, options history, options depth, events.jsonl

Produced by `scripts/run_data_integrity_audit.py` (re-runnable, strictly
read-only -- see that script's own docstring for how read-only is
enforced, not just claimed). This document is the dated snapshot of its
2026-11-18 run plus a hand investigation of the four most consequential
findings, done before this document was written, per instruction.

**Scope**: `data/fibo_intraday.duckdb`, `data/options_history/options_history.duckdb`,
`data/options_depth/v1/`, `data/fibo_live/v1/events.jsonl`.

**Nothing in this document has been fixed.** Every finding below is
classified EXPECTED (cites a BUGS.md bug, a FIBO_FINDINGS.md section, or
an `invalidated_snapshots.csv` row) or UNEXPLAINED (new, needs a decision).

## 0. The checker was wrong twice on its own first run -- on the record, not buried

Two bugs in `scripts/run_data_integrity_audit.py` itself were caught and
fixed between its first and second run, both false positives:

1. **B.8e (options depth symbol-vs-column consistency)**: the first
   version used a loose regex to parse the `symbol` field back into
   expiry/strike/option_type and compared against the row's own columns.
   The regex was ambiguous between the expiry's trailing year digits and
   the strike's leading digits (`...2026` next to `22700...`) and
   silently mis-parsed every row. Fixed by reconstructing the expected
   symbol from the row's own columns instead of parsing the symbol with
   a regex -- see Section 4 below for what this check actually found
   once fixed (a real, 100%-reproducible finding, just not a parser bug).
2. **D.12b (unguarded readers of the options-depth log)**: the first
   version flagged `src/spread_monitor/summary.py` and
   `scripts/spread_summary.py` as readers of the options-depth log that
   don't honor its invalidation file. They don't read it at all --
   they reference a same-named `DEFAULT_LOG_PATH` constant belonging to
   the unrelated equity spread-monitor package. Fixed by requiring
   `"options_depth"` to co-occur with the generic constant name before
   counting a match.

Both fixes are in the script as committed; this is the output of the
corrected version.

## 1. Summary table (2026-11-18 run)

| Check | Count | Classification |
|---|---|---|
| A.1 Fibo intraday: interior entity-day gaps (within entity's own range) | 397 | UNEXPLAINED |
| A.1b Universe (year,entity) pairs with zero overlap vs entity's own range | 181 | UNEXPLAINED |
| A.1c Universe members never fetched at all | 61 | UNEXPLAINED |
| A.1d Entity-days unverifiable (holiday master gap) | 0 | N/A |
| A.2 Entity-days materially short of ~375 bars (<330) | 11,629 / 459,318 (2.53%) | UNEXPLAINED |
| A.3 Options depth: missing (day,slot) snapshots vs 10:30/12:30/14:30 | 58 / 75 (77.3%) | UNEXPLAINED |
| A.4a Options history: expiries with <10 strikes | 0 | N/A |
| A.4b Options history: expiry not a trading day | 0 | N/A |
| A.4c Options history: >10-day gaps between expiries | 50 | UNEXPLAINED (regime-dependent) |
| A.5a events.jsonl: evenings with no watchlist_run | 7 unexplained of 11 | PARTIALLY EXPECTED (Bug #19) |
| A.5b events.jsonl: days with no morning evidence at all | 3 | UNEXPLAINED |
| A.5c Reconciliation vs FIBO_FINDINGS.md Section 14 | loose=15, strict=8 | EXPECTED (by design) |
| B.6a OHLC: high < low | 0 | N/A |
| B.6b OHLC: high < max(open,close) | 16 | UNEXPLAINED |
| B.6c OHLC: low > min(open,close) | 39 | UNEXPLAINED |
| B.6d Negative volume | 560 | UNEXPLAINED |
| B.6e Null required fields | 0 | N/A |
| B.7a Bars outside 09:15-15:29 IST | 97,119 | UNEXPLAINED |
| B.7b ts date != trade_date | 0 | N/A |
| B.7c Duplicate (entity_id, ts) | 0 | N/A |
| B.8a Options history: negative premium/vol/OI | 0 | N/A |
| B.8b Options depth: negative LTP/bid/ask | 0 | N/A |
| B.8c Options depth: crossed book | 0 | N/A |
| B.8d Options depth: LTP outside [bid1,ask1] by >1% | 679 / 3,972 | UNEXPLAINED |
| B.8e Options depth: symbol inconsistent with its own columns | 3,972 / 3,972 | UNEXPLAINED (see Section 4) |
| C.9 Intraday session OHLC vs bhavcopy, >0.5% (Bug #18's shape) | 81,801 new / 81,812 total / 419,379 (19.51%) | EXPECTED, confirmed resolved for the 54 checked TEST trades -- see Section 4 |
| D.10 Frozen consecutive depth snapshots | 0 new / 368 total | PARTIALLY EXPECTED (all already in invalidated_snapshots.csv) |
| D.11 Depth snapshots off-hours/non-trading-day | 0 new / 3 total | PARTIALLY EXPECTED (all already flagged) |
| D.12a Invalidated rows with no matching real snapshot | 0 | N/A |
| D.12b Unguarded readers of the depth log | 0 | N/A |
| E.13 events.jsonl duplicate event_ids | 0 | N/A |
| E.14a events.jsonl future-dated events | 0 | N/A |
| E.14b File-order timestamp inversions per kind | 0 | N/A |
| E.15 Signal's commit predates outcome-knowable moment | 1 | UNEXPLAINED (see Section 5) |
| E.16 Working tree matches git HEAD | matches | N/A |
| F.17a Watchlist entities beyond archive's own coverage | 3,600 | EXPECTED (archive staleness) |
| F.17b Watchlist entities missing bars within covered range | 0 | N/A |
| F.18 Trigger events needing bar coverage | 0 (none exist) | N/A (vacuous) |
| F.19 Options depth vs history: overlapping dates agree | no overlap exists | UNEXPLAINED (structural) |

## 2. Section walkthroughs (bad result first)

**A. Completeness.** 397 interior entity-day gaps exist in the top-200
intraday universe, plus 181 universe-years an entity's own archive never
reaches at all and 61 universe members never fetched -- none cross-checked
against a specific known cause, all UNEXPLAINED pending a decision. 2.53%
of entity-days are materially short of a full session, the signature of
previously-documented silent API truncation, concentrated partly on
2016-10-30 (1-bar days, likely Diwali Muhurat trading -- not confirmed).
Options-depth snapshot coverage is poor: 77.3% of the 3-times-daily
schedule is missing since the collector started (2026-10-12). events.jsonl
reconciles against FIBO_FINDINGS.md Section 14's valid-observation-day
counter (8) by design -- the loose count (15) counts REPLAY/out-of-window
runs the strict counter deliberately excludes.

**B. Validity.** 560 bars have negative volume (all 2024-03-02), 55 bars
violate basic OHLC ordering (all 2023-03-03), and 97,119 bars (0.06% of
the table) fall outside the 09:15-15:29 session window, including several
clearly-wrong clock entries (18:21-18:31 IST on 2017-10-19). None of these
touch any trade, watchlist row, or the live window -- see Section 6.
Options depth has 679 LTP-outside-quote rows (last-traded-price lagging a
moving quote, plausible) and -- once the checker's own regex bug was
fixed -- 100% of rows show the `symbol` field encoding expiry with a
2-digit year while the dedicated `expiry` column uses 4 digits (e.g.
symbol `...13OCT26...` vs column `13OCT2026`): a real, universal
representation inconsistency, not a parsing error, and not necessarily a
correctness defect (strike and option_type match exactly in every row
checked) -- needs a decision on whether to normalize.

**C. Scale reconciliation (Bug #18's shape).** 19.51% of entity-days
where both sources exist disagree by more than 0.5% on session
high/low/close vs. the daily bhavcopy bar -- see Section 4, this is the
headline finding of this audit.

**D. Staleness.** Every frozen-tick and off-hours snapshot found (368 and
3 respectively) is already covered by `invalidated_snapshots.csv` --- no
new staleness issue. `exchFeedTime` is not persisted in
`nifty_depth_log.csv` at all (confirmed by reading `src/options_depth/
quotes.py`'s `DepthRow`), so the spec's literal "identical exchFeedTime"
sub-check cannot be run against stored data; full-payload identity was
used instead. The invalidation mechanism is honored by its only current
reader and has no orphaned rows.

**E. Provenance.** events.jsonl has no duplicate event_ids, no
future-dated events, and matches git HEAD exactly. One signal/outcome
pair exists in the whole log (AXISBANK, 2026-10-19) and it violates the
ordering check -- see Section 5.

**F. Cross-source.** 3,600 watchlist rows reference a target date beyond
`bars_1min`'s own archive coverage (which stopped 2026-09-18, before the
forward test even started) -- structural staleness, not a per-entity gap;
0 genuine misses once that's accounted for. No trigger event has ever
been logged, so F.18 is vacuous. Options depth and options history have
never had an overlapping date to cross-validate against each other.

## 3. Checker bugs vs. real findings -- which is which

Every count above is from the corrected checker. The two bugs described
in Section 0 were caught by inspecting their output, not by a second
independent review -- worth stating plainly rather than implying this
list is exhaustively verified.

## 4. Deep dive: the 19.51% scale disagreement (Section C.9)

### 4a. The question that decides this: does the mitigation actually fire? Yes, for all 54 checked.

For every one of the 54 TEST trades with a genuine (not close-only)
high/low raw disagreement, `fibo.scale_probe.decide_scale_for_day` was
run exactly as `src/fibo/backtest.py` calls it -- D-1's own bhav-vs-Angel
high/low ratio -- and the resulting scale was applied to day D's own
session high/low, then re-compared against bhavcopy D directly:

- **54/54 resolved to `SCALED`** (a real, non-identity factor, range
  1.03x-3.00x). None returned `UNRESOLVED`, `GAP_GUARD_SKIP`, or
  `EX_DATE_SKIP`, and none silently fell back to an identity (1.0)
  conversion.
- **Post-conversion deviation: 0/54 still exceed 0.5%.** Max residual
  0.31%, mean 0.03%, median 0.005% -- noise, not a mismatch.

**Conclusion: the raw sources diverge exactly as documented, and the
mitigation the live backtest actually applies resolves every single one
of these 54 cases correctly.** This is not "the mitigation didn't fire" --
it is "the raw-vs-raw check in Section C.9 is deliberately measuring the
exact population `scale_probe` exists to correct, and correctly
measuring that it IS corrected before the 216-trade result was produced."
The earlier framing of this as live financial risk to the 216-trade
result was wrong; corrected below and in Section 7.

### 4b. Generalizing the BSE finding -- the fetch-time theory was wrong, checked and replaced

The original explanation offered in chat ("Angel's historical API
auto-adjusts for corporate actions known at fetch time, so the same
dates return different numbers depending on when they were pulled") does
**not** hold up: BSE's entire archive, both the 1/3-ratio and 1/9-ratio
segments alike, was fetched within one ~90-second window on
2026-09-28/30 -- long after both real bonuses (2022-03-21, 2025-05-23)
had already occurred. A single fetch, well after all relevant actions,
cannot produce two different adjustment states by a "known at fetch
time" mechanism; that explanation is retracted.

**What the data actually shows**: the ratio is a function of how many
corporate actions fall between a bar's own `trade_date` and the present
(or the archive's own effective "now"), not of when it was fetched --
the standard "continuously back-adjusted" charting convention. BSE's
dates before the first bonus absorb both subsequent bonuses (1/9 = 1/3 x
1/3); dates between the two bonuses absorb only the second (1/3); dates
after the second need no adjustment (1.0). `bars_1min` is not raw
Angel-as-traded data for any entity that has had a corporate action since
its earliest archived bar -- it is back-adjusted to a moving present,
while `prices_eod` (bhavcopy) is raw, as-traded-that-day. This is a
structural property of the data source, not a transient fetch artifact,
and it is exactly the condition `scale_probe` was built to detect and
correct per-day (Section 4a confirms it does, for the checked sample).

**Scope, measured directly** (joining `corporate_actions` to
`bars_1min` via `isin_lineage`, the same join `scale_probe.is_ex_date`
uses):

- Literal fetch-time question as originally framed (an entity with a
  `corporate_actions.ex_date` *after* its own bars' `fetched_at`): **0
  entities**. Confirms the fetch-time theory is categorically wrong, not
  just wrong for BSE.
- Corrected scope (an entity whose own `bars_1min` date range *spans* at
  least one corporate-action `ex_date`): **80 of 386 entities (20.7%)**
  that have any intraday data at all.
- Of the 216 TEST trades: **64 (29.6%, across 33 distinct entities)**
  sit on such an entity. This is close to, but not identical with,
  Section 4a's 54/65 raw-disagreement counts -- expected, since not every
  pre-action day's disagreement crosses the 0.5% flag threshold, and
  `scale_probe`'s own `EX_DATE_SKIP` already excludes the ex_date itself.

BSE specifically: touches **0** of the 216 trades (never appears there)
and **324** `setup_off` rejections -- whether any of those were wrongly
rejected is not verified here (Section 4a's clean result was checked
against the 54 *selected* trades, not the rejected population).

## 5. Deep dive: the one signal/outcome ordering violation (Section E.15)

The only outcome event ever logged (AXISBANK, `INE238A01034`,
2026-10-19, `triggered=False`, `run_mode=REPLAY`) fails the check: its
matching `SETUP_ON` signal event was committed to git at 15:02:35 IST,
after 11:30 IST, the entry-window close that made the no-trigger outcome
knowable. This reproduces an already-documented fact, not a new
discovery -- `FIBO_FINDINGS.md` Section 14/15 already records this exact
case (SETUP_ON logged 3.5 hours after the window closed, excluded from
the valid-observation-day counter for exactly this reason). It is
recorded here as a formal provenance violation anyway, per instruction to
report every violation individually: this day's REPLAY classification
alone does not retroactively make its signal "known before the outcome"
in the git-commit-timestamp sense this check is built to verify.

## 6. Deep dive: OHLC violations and negative volume -- do they touch anything real

246 distinct entity-days carry an OHLC-ordering violation or negative
volume (16+39 high/low violations, all dated 2023-03-03; 560 negative-
volume bars, all dated 2024-03-02; one earlier 2017-10-06 case). Checked
directly against all four populations that could matter:

| Population | Overlap |
|---|---|
| 216 TEST trades | 0 |
| 48,608 setup_off rejected candidates | 0 |
| Live forward-test window (>=2026-10-08) | 0 |
| Any watchlist row (entity, target_trade_date) | 0 |

These are real data defects -- almost certainly a provider-side glitch on
two specific dates -- but have never fed a published result, a candidate
pool, or the live system.

## 7. Open decisions (not resolved by this document)

- **Resolved, not open**: whether the 216-trade result needed re-running
  through a `scale_probe`-based reconciliation -- no. Section 4a checked
  this directly: `scale_probe` is already applied, already resolves all
  54 affected trades to <0.31% residual, and no fix or re-run is needed
  on the selected side.
- Whether `setup_off`'s 6,635-row exposure (13.6%) and BSE's 324
  rejections hide any wrongly-rejected candidate -- Section 4a's clean
  result was checked only against the *selected* 54, not the rejected
  population; not rebuilt or re-evaluated here. This is the "other
  direction" PROJECT_CONTEXT.md finding #9 (as amended 2026-11-18) warns
  is structurally unable to be inferred from the selected side alone.
- Whether the B.8e symbol/expiry year-digit inconsistency needs
  normalizing anywhere downstream, or is cosmetic.
- Whether the 2023-03-03 and 2024-03-02 clusters warrant a source-side
  re-fetch, given they currently touch nothing real.
- Whether the 11,629 materially-short entity-days should be
  cross-referenced against a Muhurat-trading/special-session calendar
  before being treated as truncation.
- Whether options-depth's 77.3% missed-snapshot rate is within the
  collector's own documented loss tolerance or needs the Task Scheduler
  job investigated.

## 7a. Corrections made to this document after its first version (2026-11-18, same day)

Section 4's original text claimed two things that follow-up investigation
disproved before they could be acted on:

1. It framed the 25% TEST-trade exposure as an open risk to the published
   result. Directly checking whether `scale_probe`'s actual mitigation
   resolves it (Section 4a) shows it does, cleanly, for every one of the
   54 checked trades -- no re-run is needed.
2. It asserted BSE's 1/9 ratio came from Angel adjusting historical
   candles based on corporate actions known *at fetch time*. BSE's own
   `fetched_at` timestamps contradict this (the whole archive was pulled
   in one narrow window, after both bonuses) -- replaced with the
   correct mechanism (continuous back-adjustment to the present) in
   Section 4b, and the literal fetch-time claim was re-tested across the
   whole archive and found to apply to **zero** entities.

Left here rather than silently edited away, for the same reason Section 0
exists: a checker (or a chat answer) that was wrong should have its own
correction on the record, not just a replaced conclusion.

## 8. Script

`scripts/run_data_integrity_audit.py` -- read-only (DuckDB `read_only=True`
throughout, file fingerprinting asserts nothing it touches changed),
re-runnable, intended for the weekly job once reviewed. Takes under two
minutes against the full 170M-row intraday table.
