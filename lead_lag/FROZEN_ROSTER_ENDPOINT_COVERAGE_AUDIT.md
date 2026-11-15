# Frozen-Roster Endpoint Coverage Audit — `15:29` Collapse vs. Actual Leader/Follower Baskets

**Date**: 2026-11-14
**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag)
**Scope**: whether the `15:29` coverage collapse identified in
`lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` actually reaches the frozen monthly
leader/follower baskets, and how it interacts with the already-approved frozen-subset
endpoint-validity rules. **No methodology decision is made, proposed, or implied.**
**Mode**: READ-ONLY. All database access via `duckdb.connect(path, read_only=True)`
against `data/warehouse.duckdb` (for roster reconstruction, via `prices_eod` +
`isin_lineage` + the committed `fibo.universe.reconstitute_annually`) and
`data/fibo_intraday.duckdb` (for coverage counts). No write, no fetch, no Phase 4 code,
no gate, no outcome, regression, or performance statistic was run or inspected.
Decisions 11, 15, 17, 20, and 21 are not touched, resolved, or discussed as resolved.

---

## 1. Executive conclusion

**The `15:29` collapse reaches the frozen rosters directly and decisively, but its
practical severity depends entirely on which of two readings of the "frozen-subset
completeness" rule governs** — a genuine ambiguity this audit surfaces rather than
resolves (Section 8).

- On the **14 dates** where archive-wide `15:29` coverage collapsed (prior audit):
  the frozen **leader** roster (40 entities) has only **1-2 of 40 (2.5%-5%)** present
  at `15:29`; the frozen **follower** roster (160 entities) has only **26-27 of 160
  (16.25%-16.9%)** present. **Both tiers fail the existing, already-approved breadth
  floors by a wide margin** (leader floor `0.80`, Section 8; follower floor `0.70`,
  Decision 10) — not a borderline case.
- On the **other 20 dates** in the same `2026-08-03 to 2026-09-18` window (where
  archive-wide `15:29` looked complete): the frozen rosters are **39/40 leaders
  (97.5%) and 159/160 followers (99.375%)** present at `15:29` — **above** both
  breadth floors, but **never literally 100%**, because of a separate, unrelated,
  chronic single-entity gap (Section 6).
- **A separate, independent, pre-existing finding, not caused by the Aug-Sep
  collapse**: exactly **one leader-tier entity (HFCL, `INE548A01028`) and one
  follower-tier entity (RELINFRA, `INE036A01016`)** are members of the reconstructed
  August/September 2026 rosters by turnover rank, but have **zero rows in
  `bars_1min` anywhere in the entire archive** — not just on the 34 flagged dates.
  This single pre-existing gap, by itself, makes literal 100% full-roster completeness
  structurally impossible for as long as either entity holds its tier membership,
  **independent of the `15:19`/`15:29` collapse entirely.**
- **Under the existing numeric breadth floors (0.80 leader / 0.70 follower), the
  mechanical verdict is clean and sharp**: the 14 collapse dates fail outright; the
  other 20 pass (comfortably, 97.5%/99.375% vs 80%/70% floors), the one chronic
  missing name notwithstanding.
- **Observation-level (per-signal-minute, per-horizon) quantification is not
  computable from existing sources without implementing Phase 4 logic that does not
  exist in this repository** (confirmed, not re-derived, from
  `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md`) — this audit stops
  at date-level feasibility, per its own instructions, and does not invent observation
  counts.

---

## 2. Governing roster methodology and source provenance

Reused exactly, not reinterpreted, from the committed preregistration and the already-
completed `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`:

1. **Annual universe**: `fibo.universe.reconstitute_annually(con, top_n=200)` —
   committed, read-only Python function, `src/fibo/universe.py`. **Note**: this
   module's own default parameter is `TOP_N = 50` (the unrelated Fibonacci/ORB study's
   own universe size); the lead-lag family's Section 4 explicitly calls for
   **top-200**, so `top_n=200` was passed explicitly — using the module's bare default
   would have silently reconstructed the wrong (50-name) universe. This is flagged
   because it is an easy, consequential mistake to make, not because it occurred
   uncorrected here.
2. **Monthly leader/follower split** (`PREREGISTRATION_LEAD_LAG_V1.md` Section 6): on
   the first trading day of each month, rank entities in that year's annual universe
   by trailing-60-session median daily `prices_eod.turnover` (raw), joined through
   `isin_lineage` to `entity_id`; require ≥60 trailing sessions for eligibility; top
   20% (`ceil(0.2 * n_eligible)`) = leaders; remainder = followers.
3. **No committed source file implements step 2** — reconfirmed, not re-derived, from
   `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 2 and
   `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`. This audit reconstructs it by
   **directly implementing the fully and deterministically specified rule above**,
   exactly as `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1 already did for
   its own breadth measurement — this is reconstruction of an exact, pre-specified,
   deterministic formula, not an invented or approximated methodology.

---

## 3. Historical roster reconstruction and verification

**Ranking dates, confirmed from `prices_eod`'s own trading-day calendar (not assumed)**:

```sql
SELECT strftime(trade_date, '%Y-%m') AS ym, MIN(trade_date)
FROM prices_eod WHERE series='EQ' AND trade_date BETWEEN '2026-07-01' AND '2026-09-30'
GROUP BY 1;
```
→ July 2026: `2026-07-01`; August 2026: `2026-08-03`; September 2026: `2026-09-01`.

**Annual 2026 universe**: 200 entities (ranked off 2025 median turnover, per the
committed function).

**Monthly rosters reconstructed** (window = 60 most recent `prices_eod` EQ sessions
with `trade_date <= ranking_date`; all 200 annual-universe entities had the required
≥60 trailing sessions — **0 ineligible** in every month checked):

| Ranking month | Ranking date | Eligible | Leaders (top 20%) | Followers |
|---|---|---|---|---|
| July 2026 | 2026-07-01 | 200 | 40 | 160 |
| **August 2026** | **2026-08-03** | **200** | **40** | **160** |
| **September 2026** | **2026-09-01** | **200** | **40** | **160** |

This matches the preregistration's own previously-reported steady-state figure
(~40 leaders / ~160 followers for a full, non-dip month, Section 6) exactly.

**Provenance of each roster**: reconstructed, not retrieved from a pre-existing saved
artifact (none exists — no committed roster table or file). Fully reproducible from
the query in Section 12. **Every entity's eligibility and tier assignment used only
`prices_eod` data with `trade_date <= ranking_date` — no `bars_1min` price, volume, or
availability was used to construct or filter the roster**, consistent with the
family's own stated design.

---

## 4. Identity and ISIN matching methodology

`entity_id` (the project-wide stable identity key, already used as the join key in both
`bars_1min` and `prices_eod`/`isin_lineage`) was used throughout as the primary
identity — **not** `symbol`, which is not treated as a stable historical key anywhere
in this project. For disclosure, each roster entity's recorded ISIN(s) were pulled from
`isin_lineage` (240 ISIN rows for 200 distinct entities across the Aug/Sep rosters —
some entities have more than one historical ISIN on file, consistent with the
project's own ISIN-lineage-chain convention documented elsewhere). The two entities at
the center of this audit's chronic-gap finding (Section 6) were identified by
`entity_id` and independently confirmed against `prices_eod`'s own `symbol` field:
`INE548A01028` = **HFCL** (leader tier); `INE036A01016` = **RELINFRA** (follower tier).

---

## 5. Leader/follower membership and endpoint coverage, 14 affected dates

**Pooled percentages, with exact numerator/denominator, `15:29`, PRESENT-VALID
(Decision 17 definition, Section 6 below)**:

| Tier | Numerator | Denominator | % |
|---|---|---|---|
| Leader | 23 (sum across 14 dates, see per-date table) | 560 (40 × 14) | 4.11% |
| Follower | 376 (sum across 14 dates) | 2,240 (160 × 14) | 16.79% |

**Per-date table (all 14 dates, both tiers, `15:29` only — full `15:19`/`15:28`/`15:29`
comparison in Section 6)**:

| Date | Leader present / 40 | Leader % | Follower present / 160 | Follower % |
|---|---|---|---|---|
| 2026-08-04 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-05 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-06 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-12 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-14 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-17 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-25 | 2/40 | 5.0% | 27/160 | 16.88% |
| 2026-08-26 | 2/40 | 5.0% | 26/160 | 16.25% |
| 2026-08-27 | 2/40 | 5.0% | 26/160 | 16.25% |
| 2026-09-03 | 1/40 | 2.5% | 27/160 | 16.88% |
| 2026-09-04 | 1/40 | 2.5% | 27/160 | 16.88% |
| 2026-09-09 | 1/40 | 2.5% | 27/160 | 16.88% |
| 2026-09-17 | 1/40 | 2.5% | 27/160 | 16.88% |
| 2026-09-18 | 1/40 | 2.5% | 27/160 | 16.88% |

(Structurally-valid and PRESENT-VALID counts are identical to "any row" at `15:29` on
every one of these 14 dates — **zero** of the present rows are structurally invalid or
zero-volume-flat; every present row is a genuine, clean trade. The shortfall is pure
absence, not corrupted presence.)

**Not all archive-wide-missing entities are roster members, and not all roster
members are archive-wide-missing** — explicitly checked, not assumed: the ~169-171
archive-wide entities missing at `15:29` on these dates (prior audit, out of the
386-entity lifetime archive) include names outside the current annual top-200
universe entirely (names that are leaders/followers in *other* years, or never in this
family's universe at all); conversely, the frozen Aug/Sep roster (200 names, a subset
of the 198 entities active in the archive that month) is almost entirely contained
within the affected cohort — **38 of 40 leaders and 133-134 of 160 followers are
within the missing cohort on the 14 dates**, confirming the collapse is not merely
incidental to the roster but overwhelmingly engulfs it.

---

## 6. `15:28` vs. `15:29` vs. `15:19` — roster-level comparison, all 34 dates

**Exact query** (repeated for each tier, each date, each of the three timestamps):

```sql
WITH roster AS (SELECT UNNEST(?::VARCHAR[]) AS entity_id),
bar AS (SELECT entity_id, open, high, low, close, volume FROM bars_1min
        WHERE trade_date = ? AND CAST(ts AS TIME) = TIME '<HH:MM:00>')
SELECT COUNT(*) AS n_roster, COUNT(bar.entity_id) AS n_any_row,
       SUM(CASE WHEN <structurally-valid> THEN 1 ELSE 0 END) AS n_structvalid,
       SUM(CASE WHEN <present-valid> THEN 1 ELSE 0 END) AS n_presentvalid
FROM roster LEFT JOIN bar ON roster.entity_id = bar.entity_id;
```

**Finding, not previously stated this precisely**: across **all 34 of 34** dates in
the window, leader-roster coverage at `15:19` is **1-2 of 40 (2.5-5%)** on *every
single date, with no exception* — `15:19` is uniformly collapsed, not intermittent.
Separately, on each date **exactly one** of `{15:28, 15:29}` is also collapsed to the
same ~2.5-5%/16-17% level, while the *other* is at its normal, near-complete level —
and **which one is collapsed alternates by date, unpredictably from this audit's
evidence**:

| Group (by which minute is bad) | Dates | Leader @ bad minute | Leader @ good minute | Follower @ bad minute | Follower @ good minute |
|---|---|---|---|---|---|
| `15:29` bad, `15:28` good (14 dates) | the 14 listed in Section 5 | 1-2/40 | 39/40 | 26-27/160 | 159/160 |
| `15:28` bad, `15:29` good (20 dates) | all other dates in the 34-date window | 1-2/40 | 39/40 | 26-27/160 | 159/160 |

**`15:28` is reported here only as the diagnostic the prior audit's task required — it
is not treated anywhere in this report as an approved substitute endpoint, and no
return or alternative construction is computed from it.**

**`15:19` diagnostic, roster-level, consistency check against the prior archive-wide
finding**: the prior audit found archive-wide `15:19` breadth at ≈14% (27-29 of 198)
on all 34 dates. The roster-level figure is **more severe**: 1-2 of 40 leaders
(2.5-5%) and 26-27 of 160 followers (16-17%) — i.e. the ~27-29 archive-wide "safe"
entities (identified in the prior audit as mostly recent 2024-2025 IPO listings) are
**overwhelmingly not members of the current top-200 turnover-ranked universe**, so the
roster sees almost none of that residual safety margin.

---

## 7. Application of the existing frozen-subset completeness rule

**Two distinct readings of the rule as stated in this task, reported separately, per
Section 8's own instruction not to silently pick one**:

**Reading 1 — literal, zero-tolerance ("every constituent... if any fails, discard")**:
under this reading, **all 34 of 34 dates fail** at `15:29`, because even the 20
"good" dates are missing exactly one chronic entity each (Section 6, below) — never a
literal 40/40 or 160/160. Under this reading, the 14-vs-20 distinction collapses to
"severely fails" vs. "fails by exactly one name" — both are failures.

**Reading 2 — the actual, already-approved numeric breadth floors** (leader `0.80`,
`PREREGISTRATION_LEAD_LAG_V1.md` Section 8; follower `0.70`, Decision 10,
`AMENDMENT 5 LOG` Section 1): under this reading, which this audit believes is the
operative one given it is the one actually frozen with a specific number, rather than
a prose paraphrase:

| Date group | Leader coverage | vs. 0.80 floor | Follower coverage | vs. 0.70 floor | Date-level feasible? |
|---|---|---|---|---|---|
| 14 collapse dates | 2.5-5.0% | **FAILS** | 16.25-16.88% | **FAILS** | **No** |
| 20 other dates in window | 97.5% | **PASSES** | 99.375% | **PASSES** | **Yes** |

**This audit does not resolve which reading governs** — that is a methodology
question (bearing on the same territory as the proposal's decision item 19, Option 1
vs. Option 2, already OPEN) and is explicitly not decided here. **No endpoint
timestamp, roster, or threshold is changed, proposed, or recommended by this report.**

**DATED CLARIFICATION NOTE (2026-11-14, added by a later documentation-correction
task).** The sentence above describes "Option 1 vs. Option 2" as "already OPEN." **A
subsequent reconciliation**, `lead_lag/PRE_SIGNAL_VS_FORWARD_ENDPOINT_RECONCILIATION.md`,
traced this to `PREREGISTRATION_LEAD_LAG_V1.md` AMENDMENT 3 LOG item 3 and found that
**Option 1 vs. Option 2 selection is in fact already RESOLVED (Option 2 selected) by
an existing human decision record** — not open, as this audit's own Reading-2 passage
assumed. This does **not** change this audit's underlying raw-data findings (the 14-
and 20-date coverage figures above are unaffected) and does **not** establish that
Reading 2's specific numeric comparison (raw full-roster presence at `15:29` against
the `0.80`/`0.70` floors) is the literal, correct implementation of Option 2's own
Stage-A procedure — that distinction (raw roster vs. the properly-constructed frozen
eligible subset) is exactly what the later reconciliation report's Section 6
separately addresses, and remains accurate. What changes here is narrower: Decision 19
itself is not the open question; Option 2's own threshold form/value (and whether
Decision 10's `70%` is that value) is. This report (`FROZEN_ROSTER_ENDPOINT_COVERAGE_AUDIT.md`)
is not otherwise modified — no coverage figure, date, or table above is recalculated.

**Leader-side vs. follower-side, reported separately as required**: on the 14
collapse dates, the **leader side fails more severely in relative terms** (down to
2.5-5% vs. an 80% floor — a shortfall of 75-77.5 percentage points) than the follower
side (down to ~16.5% vs. a 70% floor — a shortfall of ~53.5 percentage points),
though both fail outright under either tier's own floor.

---

## 8. Mechanical observation-loss estimate

**Not computable from existing sources without implementing Phase 4 logic that does
not exist — this audit stops here, per its own instructions, rather than inventing a
number.** Specifically:

- The exact scheduled signal-minute grid (the non-overlapping `h+5`-spaced anchor
  schedule) depends on the **still-OPEN** Decision 11 (`09:15` vs. `09:16` first valid
  bar), which this audit does not resolve or assume a value for.
- No committed Phase 4 code exists anywhere in this repository to generate the actual
  per-`(entity, day, signal-minute)` observation rows that a horizon-by-horizon
  observation count would require (reconfirmed, not re-derived, from
  `lead_lag/DECISION_14_SIGNAL_RESPONSE_SCALE_EXPOSURE_AUDIT.md` Section 2).
- Per the task's own explicit prohibition, missing-entity percentages are **not**
  multiplied against a scheduled-observation count to manufacture an estimate.

**What is established at the date level, and is reported instead**: for horizons
reaching their forward endpoint at `15:29` on signal-minutes near the close, the 14
dates in Section 5/7 are the exact set of trading dates on which the frozen leader and
follower breadth floors would both fail if the forward (or signal-window) endpoint
fell at `15:29` specifically; the 20 other dates in the window would not fail on that
basis. This is a date-level fact, not an observation count, and horizon-specific
eligible-minute selection is explicitly not performed here (per the task's own
prohibition on calculating final eligible signal anchors).

---

## 9. Nearby unaffected-session comparison

**5 verified normal sessions immediately before the affected window**
(`2026-07-27` to `2026-07-31`, same identity-matching methodology, **July 2026
roster** — ranking date `2026-07-01`, 40 leaders / 160 followers, reconstructed
identically to Section 3):

| Date | Leader @15:19 | Leader @15:28 | Leader @15:29 | Follower @15:19 | Follower @15:28 | Follower @15:29 |
|---|---|---|---|---|---|---|
| 2026-07-27 | 39/40 | 39/40 | 39/40 | 159/160 | 159/160 | 159/160 |
| 2026-07-28 | 39/40 | 39/40 | 39/40 | 159/160 | 159/160 | 159/160 |
| 2026-07-29 | 39/40 | 39/40 | 39/40 | 158/160 | 159/160 | 159/160 |
| 2026-07-30 | 39/40 | 39/40 | 39/40 | 159/160 | 159/160 | 159/160 |
| 2026-07-31 | 39/40 | 39/40 | 39/40 | 159/160 | 159/160 | 159/160 |

**Sharp, clean contrast**: before `2026-08-03`, all three timestamps are uniformly
near-complete (39/40 leaders every day — the one chronic HFCL gap, Section 6 — and
159/160 followers, the one chronic RELINFRA gap, plus one routine extra miss on
07-29). **There is no `15:19`-specific degradation at all before `2026-08-03`** — it
is identical to `15:28` and `15:29` in this comparison window, confirming
`2026-08-03` as a sharp, clean regime-change boundary, not a gradual drift.

**5 verified normal sessions immediately after the affected window**: **not
available.** The archive's last date is `2026-09-18` (confirmed,
`lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md` Section 2) — there is no data beyond
that point to check. This limitation is reported, not worked around.

**Concentration**: the missing cohort (Section 6) is **not concentrated in leaders or
followers disproportionately relative to their size** — both tiers lose essentially
the same proportion of their roster to the Aug-Sep collapse. The two **chronic,
archive-wide, pre-existing** gaps (HFCL, RELINFRA) are **one per tier**, also not
concentrated. This audit checked only the August and September 2026 roster vintages
(the two vintages the 14 affected dates fall into); no claim is made about any other
monthly vintage's exposure.

---

## 10. Limitations and unresolved questions

1. **The frozen-subset completeness rule's exact governing reading (Section 7) is
   not resolved by this audit** — both a literal zero-tolerance reading and the
   actual numeric 0.80/0.70 breadth-floor reading are reported, with different
   verdicts for the 20 "good" dates (fail vs. pass respectively); only the 14 collapse
   dates fail under both readings.
2. **The root cause of the alternating `15:28`/`15:29` collapse pattern is not
   investigated** — no ingestion script, fetch log, or `fetch_log_intraday` record
   was inspected; this audit describes the data pattern, not its origin.
3. **HFCL's and RELINFRA's absence from `bars_1min` is reported as a fact, not
   explained** — whether either was ever attempted in a fetch run, failed, or was
   never scheduled is not established here.
4. **No "after" comparison window exists** — the archive ends exactly at the end of
   the affected period.
5. **Observation-level eligibility (Section 8) is explicitly not computed** — stated
   as unavailable, not approximated.
6. **This audit checked only entity_id-level identity** via `isin_lineage`; it did not
   independently re-verify that `isin_lineage`'s own chain-resolution logic is free of
   the kind of errors Decision 14's price-adjustment audit found elsewhere in this
   project (e.g. Angel-vs-bhavcopy scale breaks) — that is outside this audit's scope
   and belongs to the already-closed Decision 14 work.
7. **Decisions 11, 15, 17, 20, and 21 are unaffected and unchanged** — none was
   touched, narrowed, or resolved by this audit, consistent with the task's explicit
   instruction.

---

## 11. (Interpretation note, per task Section 8's explicit instruction)

This audit does **not** conclude the study is unaffected because the missing cohort
includes names outside the top-200 roster — Section 5 shows the opposite is also true:
the roster itself is overwhelmingly engulfed on the 14 collapse dates. Nor does it
conclude the study is invalid merely because archive entities are missing — Section 7
shows the existing numeric breadth floors already tolerate the chronic one-name-per-
tier gap, and cleanly distinguish the 14 failing dates from the 20 passing ones. No
recommendation to exclude dates, change the roster, change the endpoint, relax a
threshold, substitute `15:28` for `15:29`, or alter the primary sample is made —
any such step would require a separate, explicit methodology decision, which this
audit does not take.

---

## 12. Reproducibility

**Roster reconstruction** (`data/warehouse.duckdb`, read-only):

```python
from fibo.universe import reconstitute_annually
universe = reconstitute_annually(con, top_n=200)   # NOT the module's own default (50)
u2026 = universe[universe["year"] == 2026]
```
```sql
-- ranking date
SELECT strftime(trade_date,'%Y-%m'), MIN(trade_date) FROM prices_eod
WHERE series='EQ' AND trade_date BETWEEN '2026-07-01' AND '2026-09-30' GROUP BY 1;

-- trailing-60-session turnover, eligibility, ranking
SELECT l.entity_id, p.trade_date, p.turnover
FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
WHERE p.series='EQ' AND p.turnover IS NOT NULL AND p.turnover > 0
  AND p.trade_date <= :ranking_date AND l.entity_id IN :annual_universe
QUALIFY ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) <= 60;
-- eligible iff >=60 rows per entity_id; median(turnover) per eligible entity_id;
-- sort desc by median, entity_id asc tiebreak; top ceil(0.2*n_eligible) = leaders.
```

**Coverage cross-reference** (`data/fibo_intraday.duckdb`, read-only): the exact
`WITH roster AS (SELECT UNNEST(...))` query in Section 6, run once per
`(date, tier, timestamp)` combination, for all 34 affected-window dates and the 5
July comparison dates. Structural-validity and PRESENT-VALID expressions reused
verbatim from `lead_lag/DECISION_17_FINAL_POLICY_RECOMMENDATION.md` Sections 4.E/7,
identical to the definitions already used in
`lead_lag/REGULAR_SESSION_FINAL_BAR_AUDIT.md`.

**Working scripts and intermediate outputs**: written to the session scratchpad only
(`roster_reconstruct.py`, `roster_coverage.py`, `roster_2026-07/08/09.csv`,
`roster_coverage_34dates.csv`, `isin_lineage_for_roster_entities.csv`), not committed
to the repository.

---

## 13. Final verification

- All database access used `duckdb.connect(path, read_only=True)` against
  `data/warehouse.duckdb` and `data/fibo_intraday.duckdb`. No `INSERT`, `UPDATE`,
  `DELETE`, `CREATE`, or `DROP` was issued against either file.
- No source file, preregistration, proposal, master specification, decision log,
  trial ledger, or existing report was modified.
- No new market data was fetched.
- No Phase 4 implementation or gate execution occurred.
- No outcome, return, regression, IC, or performance statistic was computed or
  inspected anywhere in this audit.
- Decisions 11, 15, 17, 20, and 21 remain exactly as open/closed as before this audit.
