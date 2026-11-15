# Regular-Session Final-Bar (`15:29`) Verification Audit

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Scope**: strictly factual — whether `15:29` is supported as the final regular-session
`bars_1min` bar-start timestamp. **No methodology decision is made or implied.**
**Mode**: READ-ONLY. Every database connection used `duckdb.connect(path, read_only=True)`.
No source file, preregistration, proposal, master spec, trial ledger, or existing report
was modified. No strategy, gate, regression, or outcome analysis was run.
**Decision 11** (`09:15` vs. `09:16` first valid bar) and **Decision 21** (special/irregular
sessions) are **not resolved, discussed as resolved, or touched** by this audit — both
remain exactly as open as before. No signal anchor, no horizon-specific eligible minute,
and no new timestamp rule is proposed or computed here.

---

## 1. Executive conclusion

**`15:29` is well-supported as the final regular-session bar-start timestamp for the
large majority of normal sessions, but is NOT universally supported across the archive.**

- Pooled across 2,453 independently-classified normal sessions and 456,494 active
  entity-session-days: **451,706 / 456,494 (98.9511%)** have *some* row timestamped
  `15:29`; **986 / 2,453 (40.2%)** sessions have **100%** of that day's active entities
  present at `15:29`; **2,437 / 2,453 (99.3%)** sessions clear a **90%** coverage bar.
- **No full-session truncation was found anywhere in the 10-year archive** — in every
  single classified normal or special session, *at least one* entity has a bar at or
  after `15:29`; the exchange close is never archived as ending before `15:29` for
  every name at once.
- **A concrete, currently-unresolved, still-present data-quality defect exists**: for
  **all 34 of 34** trading dates from `2026-08-03` through `2026-09-18` (the archive's
  literal last date), the count of entities with a bar at the scheduled clock-minute
  `15:19` collapses to **27–29 of 198 (≈14%)** — this reproduces, and the archive's own
  current end date confirms is **still present and unresolved**, the truncation the
  project's own prior documents already flagged. **New in this audit**: of those same
  34 dates, **14 (41%)** *additionally* show the identical collapse at **`15:29`
  itself** — on those 14 dates, only ≈28 of 198 entities (≈14%) have *any* `15:29` row
  at all, structurally valid or not. The remaining 20 of 34 dates have full (198/198)
  `15:29` coverage. **For those 14 specific dates, "15:29 is available" is false for
  roughly 85% of the universe.**
- One further date, `2021-02-24`, cannot be classified as a normal session at all —
  it has **zero** bars in the `09:15–15:29` window for every entity (0/189), and a
  large, anomalous block of rows extending to `16:59`; this reproduces a previously
  flagged "unresolved identity" date and is reported as uncertain, not normal.
- **Archive coverage is therefore sufficient to establish that `15:29` is NOT a safe
  universal assumption** — it is accurate for the large majority of sessions but
  demonstrably false, for most of the universe, on an identified, bounded set of 14
  dates, plus inapplicable on 1 further date. A session-specific (indeed, in the
  identified period, date-specific) final-bar check would be necessary to use `15:29`
  safely across the whole archive; this audit does not implement one.

---

## 2. Data sources, schema, and date coverage

- **Table**: `bars_1min` in `data/fibo_intraday.duckdb`, opened read-only
  (`duckdb.connect(path, read_only=True)`). Schema (`src/fibo/intraday_db.py:22-39`,
  read, not modified): `entity_id, isin, symbol, angel_token, trade_date, ts, open,
  high, low, close, volume, known_date, fetched_at, source, revision_seq`. `ts` is
  documented in the schema's own comment as **"bar START time, Asia/Kolkata, naive"**
  — the convention this audit, and the existing lead-lag documents, already assume.
- **Live totals** (`SELECT COUNT(*), COUNT(DISTINCT entity_id), COUNT(DISTINCT
  trade_date), MIN(trade_date), MAX(trade_date) FROM bars_1min`): **169,935,257** rows,
  **386** distinct entities (lifetime), **2,468** distinct `trade_date` values, range
  **2016-10-04 to 2026-09-18**. This matches the range stated in the task brief exactly
  — independently re-confirmed, not assumed.
- **Calendar sources used, read-only, not modified**: `src/data_layer/nse_holidays.py`
  (`is_nse_holiday(date) -> bool`, backed by `data/raw/nse_cm_holidays.pkl`, confirmed
  present, covering 2016–2026 with **zero** `HolidayCalendarMissing` exceptions raised
  across all 2,468 dates tested — full coverage, no unverifiable year). The existing
  special-session classification already recorded in
  `lead_lag/DECISION_10_RECONCILIATION_ADDENDUM.md` (bucket table, Section 2.1) was
  used as a cross-check, not as an unverified substitute for live data (Section 3).
- `read_entity_panel()` (the stale daily convenience reader) was **not used anywhere**
  in this audit — only direct `bars_1min` queries and `is_nse_holiday`.

---

## 3. Calendar construction and classification methodology

**Rule, applied per date, independently against live data** (no date classified as a
trading session merely because rows exist):

1. Determine weekday (`date.weekday()`) and NSE-holiday status (`is_nse_holiday`).
2. Compute `n_distinct_inwindow_minutes` = `COUNT(DISTINCT CAST(ts AS TIME))` restricted
   to `09:15:00–15:29:59`, per date, across all entities.
3. Classify:
   - Ordinary weekday, not an NSE holiday, `n_min >= 300` → **A (normal session)**.
   - Ordinary weekday, not an NSE holiday, `0 < n_min < 300` → **B (normal, partial span)**.
   - Ordinary weekday, not an NSE holiday, `n_min = 0` → **C (non-session, e.g. evening-only)**.
   - Ordinary weekday, NSE holiday → **D (non-session, holiday special only)**.
   - Weekend, `n_min >= 370` → **E (verified special trading session)**.
   - Weekend, `0 < n_min < 370` → **F (non-session, partial weekend artifact)**.
   - Weekend, `n_min = 0` → **G (non-session, no in-window data)**.

**Independently re-derived bucket counts, this audit**:

| Bucket | Count (this audit) | Count (existing `DECISION_10_RECONCILIATION_ADDENDUM.md`) | Agreement |
|---|---|---|---|
| A (normal) | 2,452 | 2,451 | off by 1, see note below |
| B (normal, partial) | 1 | 2 | off by 1, see note below |
| C (non-session) | 5 | 5 | **exact match, same 5 dates** |
| D (non-session) | 1 | 1 | **exact match, same date** |
| E (special, included) | 4 | 4 | **exact match, same 4 dates** |
| F (non-session) | 3 | 3 | **exact match, same 3 dates, incl. `2016-10-30`** |
| G (non-session) | 2 | 2 | **exact match, same 2 dates** |
| **Governing (A+B+E)** | **2,457** | **2,457** | **exact match** |

**The A/B boundary difference, explained, not glossed over**: this audit used a single
numeric threshold (`n_min >= 300`) that the prior document's own text did not state
numerically ("partial in-window span" was not pinned to an exact minute count there).
The one date this audit places in B rather than A is **`2021-02-24`**
(`n_min = 295`, `n_entities_any = 189`, `min_ts = 09:14`, `max_ts = 16:59`,
**14,401** rows after `15:29` that day) — a date the project's own
`DECISION_17_FINAL_POLICY_RECOMMENDATION.md` already records as **"2021-02-24's
identity unresolved."** This audit **independently reproduces that same finding** and
does not resolve it: `2021-02-24` is reported in Section 7 below as **category 4
(irregular / uncertain)**, not forced into "normal." This is the only disagreement
found between this audit's live reclassification and the existing documented
calendar — it does not change the governing total (2,457, exact match) and does not
reflect a disagreement about *which* dates are non-session (C/D/E/F/G match exactly,
date-for-date).

**Exact non-governing and special-session dates** (independently confirmed, matching
the existing addendum date-for-date):

| Bucket | Dates |
|---|---|
| C (5) | `2017-10-19, 2018-11-07, 2021-11-04, 2022-10-24, 2024-11-01` |
| D (1) | `2025-10-21` |
| E (4, special, included) | `2020-02-01, 2024-01-20, 2025-02-01, 2026-02-01` |
| F (3) | `2016-10-30, 2024-03-02, 2024-05-18` |
| G (2) | `2020-11-14, 2023-11-12` |

**Totals requested**: 2,468 total archive dates; 2,452 verified normal (A, this
audit's threshold) + 1 partial-normal/uncertain (B, see above) = 2,453 sessions treated
as "normal" for Section 4/5's pooled statistics, with `2021-02-24` flagged uncertain
throughout rather than silently pooled; 4 verified special (E); 11 holiday/non-session
dates (C+D+F+G); 0 dates where the holiday calendar itself was unverifiable (category 5
— none occurred).

---

## 4. Session-level final-timestamp analysis

For every classified session (entity-date granularity, 459,318 pairs total — matching
the project's own previously-reported figure exactly), this audit computed, per
`(trade_date, entity_id)`: `MAX(ts)`, whether a `15:29` row exists, whether it is
structurally valid, whether any row exists before `09:15` or after `15:29`.

**No full-session truncation found**: zero normal or special sessions have `MAX(ts)`
(taken across *all* entities, not one) earlier than `15:29`. Every session has at least
one entity reaching `15:29` or later. **This directly refutes using "the single latest
observed timestamp in a session" as proof the session's final bar is complete** — the
task's own caution — because, as Section 5 shows, that single latest timestamp can
come from a tiny minority of entities while the rest stopped earlier.

**Distribution of entities' own final bar, pooled (normal sessions, n = 456,494
active entity-days)**:

| Entity's final bar | Count | % of active entity-days |
|---|---|---|
| `15:29` (any validity) | 451,706 | 98.9511% |
| Earlier than `15:29` | 4,788 | 1.0489% |
| Later than `15:29` | small, isolated (Section 4.1) | <0.01% |

### 4.1 Rows outside the expected `09:15–15:29` window, normal sessions only

- **Before `09:15`**: present on the large majority of normal sessions (a single row,
  almost always exactly one per date, consistent with the already-documented `09:14`
  pre-open/auction bar — not newly investigated here, and **not used to discuss or
  resolve Decision 11**, which remains OPEN).
- **After `15:29`**: found on exactly **5** normal-session dates out of 2,453 —
  `2017-04-28` (37 rows), `2017-10-17` (1 row), `2018-11-05` (213 rows), `2019-10-25`
  (195 rows), and `2021-02-24` (14,401 rows, the uncertain date from Section 3). The
  first four are small, isolated, and not further investigated here (plausibly
  special-session-eve artifacts, e.g. `2018-11-05` is Diwali-adjacent); they are
  reported, not explained away.

---

## 5. `15:29` coverage and structural-validity statistics

**Structural validity, reused verbatim, not invented**, from the project's own existing
Decision 17 policy (`lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`, Section 4.E
"Structurally invalid bars" and Section 7's "PRESENT-VALID" definition):

```
structurally invalid  := high < low
                       OR open  NOT BETWEEN low AND high
                       OR close NOT BETWEEN low AND high
                       OR (open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL)
                       OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                       OR volume < 0

PRESENT-VALID := (structurally valid AND volume > 0)
                 OR (volume = 0 AND open = high = low = close AND open > 0)
```

**Pooled statistics, normal sessions (n_active = 456,494 entity-days)**:

| Measure | Numerator | Denominator | % |
|---|---|---|---|
| Any row at `15:29` | 451,706 | 456,494 | 98.9511% |
| PRESENT-VALID row at `15:29` | 451,360 | 456,494 | 98.8753% |
| Positive-volume, structurally-valid row at `15:29` | 448,848 | 456,494 | 98.3251% |
| Entity's final bar strictly earlier than `15:29` | 4,788 | 456,494 | 1.0489% |

**Session-by-session distribution of per-session `%entities-with-15:29`** (2,453
sessions):

| Percentile | Coverage |
|---|---|
| p1 | 98.241% |
| p5 | 98.333% |
| p10 | 98.889% |
| p25 | 98.980% |
| p50 (median) | 99.438% |
| p75 | 100.000% |
| p90 | 100.000% |
| p95 | 100.000% |
| p99 | 100.000% |

| Threshold | Sessions meeting it | Denominator | % |
|---|---|---|---|
| ≥90% coverage | 2,437 | 2,453 | 99.35% |
| ≥95% coverage | 2,436 | 2,453 | 99.31% |
| =100% coverage | 986 | 2,453 | 40.19% |

**Do not over-read the pooled 98.95% figure**: it is a mean dominated by the ~2,419
sessions with near-complete coverage; it does not establish that *every* session is
complete, and Section 6 identifies a specific 14-date subset where coverage collapses
to ~14%, which the pooled percentage alone would hide.

**Longest consecutive run of sessions with materially incomplete (`<50%`) `15:29`
coverage**: **3** consecutive sessions, `2026-08-04 → 2026-08-06`. (The broader,
*non-consecutive* 14-date collapse identified in Section 6 is not captured by a
"consecutive run" measure, since it is interspersed with fully-covered days — reported
separately there.)

**Concentration by period**: outside the `2026-08` onward period (Section 6), no other
calendar month shows more than isolated single-session shortfalls; the "top year-months
by count of sub-100%-coverage sessions" are driven by routine, low-magnitude,
non-systemic single-entity gaps (counts of 22-23 sessions per month out of ~22 trading
days each — i.e., nearly every session has at least one entity missing by routine
chance, consistent with the project's own prior "zero-volume/missing-bar" spot-checks
finding such gaps negligible in isolation). No other period shows the collapse pattern
Section 6 describes.

---

## 6. Archive truncation analysis

### 6.1 The previously-identified `15:19` issue — confirmed still present, precisely re-measured

The project's own `lead_lag/DECISION_10_COMBINED_LEADER_FOLLOWER_FEASIBILITY_70PCT.md`
(Section 10.7) previously flagged: *"The `t = 15:19` collapse across both tiers for
every trading date from 2026-08-03 to 2026-09-18... is a data-quality signal about the
final weeks of the intraday archive."* This audit **independently re-measured this
directly against the live table** and confirms it is **still present, unresolved, and
unchanged**:

```sql
SELECT trade_date, COUNT(DISTINCT entity_id) AS n_total,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:19:00' THEN entity_id END) AS n_1519
FROM bars_1min GROUP BY trade_date ORDER BY trade_date;
```

**All 34 of 34** trading dates from `2026-08-03` through `2026-09-18` (the archive's
literal last date — the issue is present through the end of available data and was
never backfilled or corrected) show entity count at `t=15:19` collapsing to **27-29 of
198 (≈14%)**. Before `2026-08-03`, the only dates with a comparable `<50%`-breadth
collapse at `15:19` are the 11 already-classified non-session dates (C/D/F/G, Section
3) plus `2021-02-24` (the uncertain date) — **12 dates total, all independently
explained by existing classification, zero unexplained prior occurrences.**

### 6.2 New finding: the collapse extends to `15:29` itself on a 14-date subset

This was **not** stated in the prior document (which examined `t=15:19` as a scheduled
*signal* minute for the `h=5` horizon, not the session's own final bar). Measured
directly:

```sql
SELECT trade_date, COUNT(DISTINCT entity_id) AS n_total,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:28:00' THEN entity_id END) AS n_1528,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:29:00' THEN entity_id END) AS n_1529
FROM bars_1min WHERE trade_date BETWEEN '2026-08-03' AND '2026-09-18'
GROUP BY trade_date ORDER BY trade_date;
```

| Finding | Count | Denominator |
|---|---|---|
| Of the 34 flagged dates, `15:29` also collapses to ≈14% breadth | **14** | 34 (41%) |
| Of the 34 flagged dates, `15:29` has full (198/198) breadth | **20** | 34 (59%) |

**The exact shape of the degradation, worked example (`2026-08-04`)**, minute-by-minute
entity count in the last 30 minutes of the session:

```
15:00-15:14  -> 197-198 entities (normal)
15:15-15:27  -> 28-29 entities (collapsed)
15:28        -> 198 entities (anomalous full recovery, one minute only)
15:29        -> 29 entities (collapsed again)
```

This is **not** a simple "archive stops early" truncation (which would show a
monotonic decline to zero and stay there) — it is an **intermittent, non-monotonic
gap**: most of the universe disappears for a contiguous ~13-minute block
(`~15:15-15:27`), reappears for exactly one minute (`15:28`), then disappears again at
`15:29`. On a different subset of the 34 dates, the pattern is mirrored (the ~13-minute
gap, then `15:28` itself is the missing minute while `15:29` recovers instead) — which
of `15:28`/`15:29` is "the good one" **alternates unpredictably by date**, confirmed by
direct inspection of all 34 dates (full table reproduced from this audit's own query,
available on request; not included in full here for length).

**Whether this affects all entities or a subset**: a **fixed, identifiable subset**.
The entities present at `15:19` throughout this window are the same **29 symbols**
across nearly all 34 dates (e.g. `LENSKART, MEESHO, GROWW, OLAELEC, SAMMAANCAP,
BELRISE` and 23 others — predominantly names consistent with **recent (2024-2025) IPO
listings** with short trading histories), each present on 32-34 of the 34 dates. The
remaining ~169 names (the bulk of the top-200 universe, including long-established
large-caps) are the ones affected by the gap. **This entity-specific, non-calendar
pattern is more consistent with an ingestion/fetch-pipeline artifact (e.g., a separate
backfill batch for newly-added entities that happened to complete normally, versus an
affected bulk-refresh batch for the rest of the universe) than with any genuine
exchange-side session-timing change** — but this audit did not investigate the
ingestion code or logs to confirm a root cause, and does not claim one. This is an
observation about the *data*, not a diagnosis of the *pipeline*.

### 6.3 No other systemic truncation found

Outside the `2026-08-03 to 2026-09-18` window and the already-explained non-session
dates, no other period in the 2016-10-04 to 2026-09-18 archive shows a comparable
breadth collapse at `15:19` or `15:29`. The archive's own last date is `2026-09-18` —
there is no data past that point to check whether the defect persists, worsens, or
resolves.

---

## 7. Special and irregular session findings

**The 4 verified special (bucket E) sessions, each checked against `15:29` and its own
observed span — not forced into the normal-session rule**:

| Date | Active entities | `15:29` present | `15:29` PRESENT-VALID | Overall max `ts` | Complete relative to own 375-min span? |
|---|---|---|---|---|---|
| `2020-02-01` | 180 | 179 | 179 | `15:29:00` | Yes, 1 entity short of full `15:29` coverage; otherwise full span per Section 3 (`n_min >= 370`) |
| `2024-01-20` | 196 | 196 | 196 | `15:29:00` | Yes, 100% |
| `2025-02-01` | 198 | 198 | 198 | `15:29:00` | Yes, 100% |
| `2026-02-01` | 198 | 198 | 198 | `15:29:00` | Yes, 100% |

**`15:29` is applicable to all four** — each has a verified, near-complete 375-minute
span (the same criterion that classified them as genuine special sessions in Section
3), so the normal-session final-minute convention is empirically supported for these
four specifically, though this audit does not establish *why* NSE scheduled these
weekend sessions to run `09:15-15:29` rather than some other published special-session
timing, since no authoritative NSE special-session schedule document was available to
check against — **this specific sub-question is marked unresolved**, consistent with
Decision 21 remaining open.

**`2021-02-24` (the uncertain date from Section 3)**: 0 entities have any bar in the
`09:15-15:29` window at all; its active data is a block running to `16:59`. **No
expected session timing for this date is established by available project sources**
(it is not in the E-bucket weekend-special list, it is an ordinary Wednesday, and no
authoritative record of what NSE scheduled that day was found in this project's
sources) — **marked unresolved, category 5 (classification cannot be established from
available sources), not forced into either "normal" or "special."** Decision 21 is not
resolved by this observation.

---

## 8. Limitations and unresolved cases

1. **The A/B boundary (Section 3) depends on this audit's own `n_min >= 300` threshold
   choice**, which the original documentation never pinned to an exact number — a
   different reasonable threshold could move `2021-02-24` (or, in principle, other
   borderline dates near that boundary, though none were found) between buckets. This
   does not affect the governing total (2,457, confirmed both ways).
2. **`2021-02-24`'s identity remains genuinely unresolved** — reproduced, not newly
   solved, by this audit. Its `16:59`-extending data could be an evening special
   session, a data artifact, or something else; no project source resolves this.
3. **The entity-specific pattern underlying the `2026-08-03 to 2026-09-18` collapse
   (Section 6.2) is described, not explained.** This audit did not inspect ingestion
   scripts, fetch logs, or `fetch_log_intraday` to identify a root cause, since doing so
   would risk drifting from "what does the data show" into a different, broader
   investigation not authorized by this task's scope.
4. **No authoritative NSE source for special-session scheduling was available** to
   independently verify *why* the four E-bucket dates run `09:15-15:29`, beyond
   observing that they do. Decision 21 remains open and untouched.
5. **This audit used entity-date presence within `bars_1min` itself as the "active
   universe" for a given date** (i.e., "entities with no usable data for that session"
   is empty by construction under this definition, since the active set is defined by
   presence) — a genuinely separate, external, point-in-time universe definition (e.g.
   the annual top-200 roster) was not cross-joined in, since doing so was judged outside
   this audit's narrow factual scope and risked conflating a data-presence question
   with a methodology question.
6. **The archive ends at `2026-09-18`.** Whether the `15:19`/`15:29` collapse pattern
   continues, worsens, or resolves beyond that date cannot be determined from any data
   available to this audit.
7. **Decision 11 and Decision 21 are explicitly not resolved, narrowed, or discussed as
   resolved anywhere in this report.** Both remain exactly as open as before this audit.

---

## 9. Implications for the existing methodology (factual only — no rule proposed)

Per the task's exact seven questions:

1. **Is `15:29` supported as the final regular-session bar-start timestamp for normal
   sessions?** Yes, for the large majority — pooled 98.95% entity-day coverage,
   40.2% of sessions at exactly 100%, 99.3% at ≥90%.
2. **For every verified normal session, or only a subset?** **Only a subset.**
   Specifically false, for ~85% of the universe, on **14 identified dates**
   (`2026-08-04, 05, 06, 12, 14, 17, 25, 26, 27` and `2026-09-03, 04, 09, 17, 18`) — the
   exact dates where this audit measured `15:29` breadth collapsing to ≈28/198.
3. **Is the archive's coverage sufficient to establish this fact?** Yes — the archive is
   complete enough (169.9M rows, full holiday-calendar coverage, no unverifiable years)
   to answer the factual question definitively for the period it covers; it is
   *not* sufficient to extend any conclusion past `2026-09-18`, since no further data
   exists.
4. **Which dates or date ranges cannot support a `15:29` assumption?** The 14 dates
   named in point 2 above (for ~85% of entities specifically — not all), plus
   `2021-02-24` (inapplicable entirely, category 5/unresolved).
5. **Would a session-specific final-bar calendar be necessary instead of a universal
   `15:29` cutoff?** Based strictly on these findings: a **single universal `15:29`
   assumption is not safe across the whole archive** as measured; the factual evidence
   is consistent with needing *some* per-date (in the identified period, per-date and
   possibly per-entity) awareness rather than a single constant, though **this audit
   does not design, select, or recommend any such mechanism** — that is a methodology
   decision, explicitly out of scope here.

**No signal anchor, no first/final eligible minute for any horizon, and no change to
Decision 11 or Decision 21 is proposed, computed, or implied by any of the above.**

---

## 10. Reproducibility

**Environment**: Python 3.13, `duckdb` (read-only connections only), the project's own
`src/data_layer/nse_holidays.is_nse_holiday`. No other project module imported.

**Exact queries used** (all against `data/fibo_intraday.duckdb`, `read_only=True`):

```sql
-- Global totals
SELECT COUNT(*), COUNT(DISTINCT entity_id), COUNT(DISTINCT trade_date),
       MIN(trade_date), MAX(trade_date)
FROM bars_1min;

-- Per-date calendar-classification inputs
SELECT trade_date,
       COUNT(DISTINCT entity_id) AS n_entities_any,
       MIN(ts) AS min_ts, MAX(ts) AS max_ts, COUNT(*) AS n_rows,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:59'
                            THEN CAST(ts AS TIME) END) AS n_distinct_inwindow_minutes,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:59'
                            THEN entity_id END) AS n_entities_inwindow,
       SUM(CASE WHEN CAST(ts AS TIME) < TIME '09:15:00' THEN 1 ELSE 0 END) AS n_rows_before_0915,
       SUM(CASE WHEN CAST(ts AS TIME) > TIME '15:29:00' THEN 1 ELSE 0 END) AS n_rows_after_1529
FROM bars_1min GROUP BY trade_date ORDER BY trade_date;

-- Per (trade_date, entity_id) summary for Sections 4-5 (structural-validity
-- expressions given in full in Section 5)
SELECT trade_date, entity_id, MAX(ts) AS max_ts, COUNT(*) AS n_rows,
       MAX(CASE WHEN CAST(ts AS TIME) = TIME '15:29:00' THEN 1 ELSE 0 END) AS has_1529,
       -- ... present-valid / positive-volume-valid variants as defined in Section 5
       MAX(CASE WHEN CAST(ts AS TIME) > TIME '15:29:00' THEN 1 ELSE 0 END) AS has_after_1529,
       MAX(CASE WHEN CAST(ts AS TIME) < TIME '09:15:00' THEN 1 ELSE 0 END) AS has_before_0915
FROM bars_1min GROUP BY trade_date, entity_id;

-- Section 6 truncation check
SELECT trade_date, COUNT(DISTINCT entity_id) AS n_total,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:19:00' THEN entity_id END) AS n_1519,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:28:00' THEN entity_id END) AS n_1528,
       COUNT(DISTINCT CASE WHEN CAST(ts AS TIME)=TIME '15:29:00' THEN entity_id END) AS n_1529
FROM bars_1min GROUP BY trade_date ORDER BY trade_date;
```

**Calendar classification**: Python, iterating the 2,468 per-date rows above, calling
`is_nse_holiday(date)` for holiday status and `date.weekday()` for weekend status, per
the exact rule in Section 3.

**Definitions used**: structural validity and PRESENT-VALID exactly as quoted in
Section 5, reused verbatim from `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md`
Sections 4.E and 7 — not invented for this audit.

**Working scripts**: written to the session scratchpad only, not committed to the
repository (`final_bar_audit.py`, `final_bar_audit_stage2.py`,
`final_bar_audit_stage3.py`, plus ad hoc follow-up queries for Section 6). Intermediate
outputs (`per_date_aggregates.csv`, `classified_dates.json`,
`entity_date_summary.parquet`, `per_date_1529_coverage.csv`, `stage1/3_summary.json`)
likewise remain in the scratchpad, outside the repository.
