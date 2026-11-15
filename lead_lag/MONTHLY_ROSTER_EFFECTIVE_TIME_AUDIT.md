# Monthly Roster Effective-Time Audit (Read-Only)

**Task scope**: resolve the point-in-time ambiguity in when the monthly
leader/follower roster becomes effective and which trailing-60-session
turnover window is legitimately available at the first trading day's
`09:20` signal. **This document does not decide Option 2's Stage-A
threshold and does not approve anything.** Read-only with respect to all
existing source, strategy, preregistration, proposal, master spec, trial
ledger, and prior audit files. No `src/`, data, roster artifact, or trial
ledger file was modified. No Phase 4 code was written or run.

---

## 1. The actual timing requirement, as existing documents state it

### 1.1 The ambiguous phrase, located and quoted exactly

`PREREGISTRATION_LEAD_LAG_V1.md` Section 6 (line ~1101-1110):

> "within each year's point-in-time top-200-by-turnover annual universe
> (Section 4), on the first trading day of each calendar month, rank
> eligible entities by trailing-60-trading-session median daily rupee
> turnover (raw, from `prices_eod`, point-in-time -- **no bar after the
> ranking date is used**). Top 20% of that month's eligible pool =
> leaders; held fixed for the month. An entity with fewer than 60
> trailing sessions of history as of the ranking date is excluded from
> that month's eligible pool."

Per the task's own framing, **"no bar after the ranking date is used" is
not sufficient proof of whether the ranking date itself is included or
excluded** -- it rules out future dates (`trade_date > ranking_date`) but
says nothing about `trade_date = ranking_date`. This is a genuine textual
gap, not a resolved question being re-litigated.

`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` Section 3A adds no
further precision: "the roster is the full set of entities assigned to
the leader or follower tier that month by the existing point-in-time
construction (Section 6/7 of `9f71b65`)" -- it defers entirely to Section
6's own (ambiguous) wording and adds nothing about effective-time.

`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1's Method section
(the only place this construction was actually executed and measured)
states: "every entity in that year's annual universe is ranked by
trailing-60-trading-session median daily rupee turnover... **as of the
ranking date**" -- again, "as of" does not pin down inclusivity. **The
script that produced Task 1's table (`task1_monthly_tiers.py`) is
referenced by name but is not present anywhere in this repository** --
confirmed by a repository-wide file search (`Glob` for the filename,
zero matches) -- so its exact `WHERE` clause cannot be inspected to
settle this empirically from that artifact.

### 1.2 No committed code implements this step

A targeted search of `src/` found no module that performs the monthly
leader/follower ranking. `src/fibo/universe.py` implements only the
**annual** top-N-by-turnover reconstitution (`reconstitute_annually`,
`effective_universe`) -- a separate, upstream step, as the task itself
states. There is no `src/lead_lag/` package. **No committed code
establishes the intended monthly-ranking-date convention.**

### 1.3 One existing script DOES exist, and it silently chose a convention

This session's own prior work (Frozen-Roster Endpoint Coverage Audit,
earlier in this conversation) wrote a read-only reconstruction script,
`roster_reconstruct.py` (scratchpad only, never committed, not part of
the repository), to rebuild August/September 2026 rosters. Its query:

```sql
WHERE p.trade_date <= ?        -- ranking_date, passed as a parameter
  AND l.entity_id IN (...)
QUALIFY ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) <= 60
```

This used `<=` -- **ranking-date-inclusive (Convention B)** -- without
flagging the ambiguity at the time. This is reported here as a finding,
not defended: **it is evidence of an unexamined default choice made
during this family's own prior audit work, not evidence of an intended
or approved convention.** The Frozen-Roster audit's own substantive
findings (archive-coverage collapse on specific 2026 dates) are unaffected
by which turnover convention was used, because that audit examined
15:29 bar coverage against an already-fixed roster, not the roster
construction itself -- but the roster it reconstructed should not be
read as having resolved this question.

### 1.4 A real, existing precedent: the annual step's own convention

`src/fibo/universe.py` (committed, lines 7-25, re-read directly) states
its own reconstitution rule explicitly:

> "Membership for calendar year Y = the top 50 entities by MEDIAN DAILY
> TURNOVER over calendar year **Y-1** ... That membership is held FIXED
> for every trading date in year Y."

This is the project's own existing point-in-time discipline for the
analogous **annual** step: year Y's membership uses **zero** rows from
year Y itself -- not merely rows before some date within year Y, but the
entire preceding calendar year, with a full buffer. This is a real
**precedent**, not proof of the intended monthly convention (the annual
step's boundary is calendar-year-level, a coarser granularity, and the
module's docstring is explicit that a different window form was
considered and rejected for a different reason -- see Section 1.1 of
`src/fibo/universe.py`'s own docstring, "if a trailing-N-trading-day
window anchored at each Jan 1 was intended instead"). It is cited here as
supporting evidence for which convention is more consistent with this
project's own established habits, not as a documented decision that
already settles the monthly question.

### 1.5 Conclusion of Section 1

**No existing document, script, or committed code explicitly and
unambiguously states whether the monthly ranking date's own turnover is
included or excluded.** The preregistration's phrasing is genuinely
silent on this exact point. One prior, uncommitted scratchpad script
assumed inclusion without flagging it. The project's own analogous
annual-step precedent uses full prior-period exclusion. This is a real
gap requiring the comparison in Section 2 and the explicit user decision
requested in Section 5.

---

## 2. The two conventions, defined precisely

**Convention A -- prior-session cutoff.** Trailing-60-session median
uses the entity's own last 60 `prices_eod` trading-day observations with
`trade_date < ranking_date`. By construction, this window is fully
determined using data available as of the **close of the trading day
before** the ranking date -- i.e., it is computable, and could be frozen,
before the ranking date's market open. **This roster can legitimately be
used at the ranking date's own `09:20` signal**, because nothing in its
construction requires any information from the ranking date itself.

**Convention B -- ranking-date-inclusive cutoff.** Trailing-60-session
median uses the entity's own last 60 observations with `trade_date <=
ranking_date`, i.e., including the ranking date's own turnover. **This
creates a genuine availability problem, distinguished explicitly, per the
task's instruction:**

- `prices_eod.turnover` is an end-of-day, full-session aggregate (raw
  rupee turnover for that trading date). It is not, and cannot be, known
  at `09:20` on the ranking date itself -- it only exists once that
  day's regular session has closed (~15:30) and the day's EOD feed is
  produced. **Using Convention B's roster during the ranking date's own
  `09:20` signal would require the day's own closing turnover before
  that day has closed -- a look-ahead violation, not a timing nuance.**
- A B-roster could instead be defined to become effective only **after**
  that date's close, or from the **next** trading session onward. This
  would be point-in-time valid, but it is a materially different rule
  from "the roster is formed on the first trading day of each month" --
  it would mean the first trading day of the month is governed by the
  *prior* month's roster for its own `09:20` signal, contradicting
  Section 6's "held fixed for the month" language, which this audit reads
  as including that very first day. **This document does not silently
  adopt the closing-turnover-available reading; it states it explicitly
  here because the task requires that distinction, and leaves the choice
  to the user (Section 5).**

---

## 3. Practical difference, reconstructed over the documented range

### 3.1 Method

Script: `roster_effective_time_audit.py` (scratchpad, read-only, not
committed; full path reported in Section 6). Connects to
`data/warehouse.duckdb` **read-only**. Reuses, unmodified:
`fibo.universe.reconstitute_annually(con, top_n=200)` (the lead-lag
family's own documented top-200, explicitly overriding the module's
`TOP_N=50` default) and `fibo.universe.effective_universe(universe,
stub_year=2016)` -- both committed, both read-only calls, no source
touched.

For each calendar month's first `prices_eod` EQ trading day ("ranking
date"), and for each entity in that year's annual top-200 universe, two
turnover windows were computed with **identical ranking and tie-break
rules in both conventions** (median descending, then `entity_id`
ascending; `ceil(0.2 * n_eligible)` = leaders; no new eligibility rule
introduced; `>=60` qualifying trailing observations required for
eligibility in both conventions, per Section 6's existing rule):

```sql
SELECT l.entity_id, p.trade_date, p.turnover
FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
WHERE p.series='EQ' AND p.turnover IS NOT NULL AND p.turnover > 0
  AND p.trade_date {< or <=} ?          -- the only difference between A and B
  AND l.entity_id IN (...)
QUALIFY ROW_NUMBER() OVER (PARTITION BY l.entity_id ORDER BY p.trade_date DESC) <= 60
```

**Scope**: restricted to the documented 120-month study range already
used by Section 6's own table and `LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
Task 1 (`2016-10` through `2026-09`, matching `fibo_intraday.duckdb`'s own
archive span) -- not the full `prices_eod` history, which extends earlier
(to 2016-01) and later (to 2026-11). Months outside this range cannot
host a real signal observation (no `bars_1min` data exists for them) and
are excluded from the primary comparison, reported rather than silently
dropped (Section 3.2).

### 3.2 Reconstruction counts and exclusions

- **131** calendar months have a first `prices_eod` EQ trading day in the
  full warehouse history.
- **120** months reconstructed (both conventions), matching the
  documented study range exactly.
- **11** months excluded, all for the single stated reason (outside the
  `bars_1min` archive span): `2016-01` through `2016-09` (9 months,
  before the archive's `2016-10-04` start) and `2026-10`, `2026-11` (2
  months, after the archive's `2026-09-18` end).
- **0** months excluded for any other reason (e.g., missing annual
  universe) -- every one of the 120 in-scope months has a valid annual-
  universe mapping via `effective_universe(stub_year=2016)`.

### 3.3 Window boundaries, confirmed by direct inspection

Example (first and last in-scope month):

| Month | Convention | Window start | Window end |
|---|---|---|---|
| 2016-10 (ranking `2016-10-03`) | A | 2016-07-05 | 2016-09-30 |
| 2016-10 (ranking `2016-10-03`) | B | 2016-07-07 | 2016-10-03 |
| 2026-09 (ranking `2026-09-01`) | A | 2025-03-05 | 2026-08-31 |
| 2026-09 (ranking `2026-09-01`) | B | 2025-03-05 | 2026-09-01 |

Convention A's window end is always strictly before the ranking date;
Convention B's window end is always exactly the ranking date (when the
entity traded that day). **No future observation (`trade_date >
ranking_date`) entered either window, in any of the 120 months** --
confirmed directly from the recorded `MAX(trade_date)` of every window.

### 3.4 Entity-level and count-level differences

- **Eligible-entity counts (`n_eligible`) identical in 119 / 120 months.**
  The one exception, `2025-04`, differs by exactly one entity (200 under
  B vs. 199 under A) -- see Section 3.5.
- **Leader counts (`n_leaders`) identical in all 120 / 120 months.** The
  `ceil(0.2 * n_eligible)` split is robust to the single-entity
  eligible-count difference in `2025-04`.
- **Follower counts**: identical in all 120 months, by the same
  arithmetic (follower count = eligible count − leader count).
- **Months with at least one entity's leader/follower tier assignment
  changed between conventions: 47 of 120 (39.2%).**
- **Total entity-month tier reassignments: 103.**
- **Distinct entities ever affected across the 10-year span: 58.**

### 3.5 Representative months with the largest differences

| Month | Ranking date | `n_eligible` A/B | Entities changed | Example flips |
|---|---|---|---|---|
| 2017-06 | 2017-06-01 | 200 / 200 | 4 | `INE129A01019` leader→follower; `INE522F01014` follower→leader |
| 2021-02 | 2021-02-01 | 196 / 196 | 4 | `INE205A01025` leader→follower; `INE271C01023` follower→leader |
| 2024-06 | 2024-06-03 | 200 / 200 | 4 | `INE860A01027` leader→follower; `INE423A01024` follower→leader |
| 2023-10 | 2023-10-03 | 200 / 200 | 4 | `INE021A01026` follower→leader; `INE752E01010` leader→follower |
| 2025-04 | 2025-04-01 | 199 / 200 | 3 | `INE0W2G01015` ineligible→follower (the one eligibility-count exception) |

### 3.6 What causes the differences -- directly verified, not assumed

**102 of 103 reassignments (99%) are leader↔follower boundary flips**
(an entity already eligible under both conventions moves across the
top-20% rank cutoff). **Exactly 1 of 103** is an eligibility-count change
(`INE0W2G01015`, 2025-04: `ineligible` under A, `follower` under B --
this entity reaches exactly 60 qualifying trailing observations only when
the ranking date's own row is counted; a genuine one-day boundary case of
the existing `>=60`-session rule, not a data defect).

**Verified directly, not inferred, that boundary flips are genuine median
shifts, not literal ties or a tie-break artifact.** Example, `2017-06-01`
(re-queried directly against `prices_eod`):

| Entity | Median turnover, Convention A | Median turnover, Convention B |
|---|---:|---:|
| `INE129A01019` | 1,186,069,030.68 | 1,149,414,769.85 |
| `INE669E01016` | 1,182,806,420.78 | 1,134,607,305.93 |
| `INE522F01014` | 1,153,839,202.18 | 1,153,839,202.18 |
| `INE213A01029` | 1,148,755,410.15 | 1,157,353,463.45 |

Swapping which 60 trading days are included (dropping the oldest day,
adding the ranking date) shifts each entity's median by a real amount;
`INE213A01029` rises just enough, and `INE129A01019`/`INE669E01016` fall
just enough, to cross the rank-40 cutoff. **No two entities show
identical median values in either convention in this example** -- the
tie-break rule (entity_id ascending) was not invoked to produce any of
these flips.

**Not caused by missing turnover**: every flip entity had its own full
60 qualifying observations in both conventions (the single exception,
`INE0W2G01015`, is the one eligibility-threshold case, explicitly
separated above, not a "missing data" defect).

**Not caused by entity/ISIN resolution**: both conventions use the
identical `prices_eod JOIN isin_lineage` identity-resolution query,
differing only in the `WHERE p.trade_date` comparator -- no
identity-handling difference exists between A and B by construction.

**Not concentrated in a particular period.** Affected months per year:
2016: 6, 2017: 14, 2018: 8, 2019: 6, 2020: 10, 2021: 10, 2022: 6, 2023:
12, 2024: 14, 2025: 7, 2026: 10 -- roughly proportional to each year's
month count (10-12/year), with no outlier year or multi-year run. This is
a **generic, recurring rank-boundary sensitivity**, not a data-quality
artifact or regime-specific effect.

### 3.7 The annual top-200 universe is verified unaffected

The task asked this to be verified, not assumed. `src/fibo/universe.py`
`reconstitute_annually` (re-read directly, Section 1.4 above) computes
year Y's membership exclusively from calendar year Y-1's `prices_eod`
rows -- **zero rows from year Y itself** are used, by construction, for
every year, independent of any monthly ranking-date question. This audit
ran the identical `reconstitute_annually(con, top_n=200)` call for both
conventions (Section 3.1) and it is, trivially and by inspection of the
function's own source, **the same call, unaffected by Convention A vs.
B** -- there is no analogous ranking-date-inclusivity question at the
annual level to begin with, because the annual step's own boundary (a
full prior calendar year) is already far coarser than, and already
excludes, the current year entirely. **Confirmed, not merely assumed.**

---

## 4. Point-in-time and source-integrity checks

- **Turnover source**: `prices_eod.turnover` exclusively, in every query
  in this audit -- never `bars_1min`, never close×volume, never an
  adjusted-price-derived figure. Confirmed by direct inspection of the
  SQL in Section 3.1 (the only turnover-reading query used throughout).
- **Trading-session calendar used for "first trading day of month"**:
  `prices_eod`'s own `series='EQ'` calendar (`MIN(trade_date)` per
  calendar month) -- **not** the governing 2,457-date `bars_1min`
  calendar established in prior audits (Decision 10's amendment,
  `AMENDMENT 2 LOG`). **This is a limitation, flagged explicitly, not
  silently assumed equivalent**: a direct comparison (Section 4.1 below)
  found these two calendars' "first trading day of month" **differ in 4
  of 120 months**, including 3 cases where `bars_1min` has data on a
  genuine weekend special-trading session (`2020-02-01`, `2025-02-01`,
  `2026-02-01` -- the same dates already verified as bucket-E weekend
  special sessions in the governing calendar work) that `prices_eod`
  does not record as that month's first EQ trading day. **This audit
  does not resolve which calendar should govern "first trading day of
  month" for roster-ranking purposes -- it is a separate, newly surfaced
  ambiguity, reported here because the source-integrity check required
  by this task surfaced it, not because this task asked it to be
  resolved.**
- **No future turnover observation enters either window**: verified
  directly (Section 3.3) -- `MAX(trade_date)` of every constructed window
  is `< ranking_date` (Convention A) or `<= ranking_date` (Convention B),
  in all 120 months, with zero exceptions.
- **Entity identity / ISIN lineage**: handled identically in both
  conventions (Section 3.6) -- the same `isin_lineage` join, differing
  only in the date comparator.
- **Missing turnover / insufficient history**: reported, not imputed.
  The one eligibility-boundary case (`INE0W2G01015`, 2025-04) is surfaced
  explicitly (Section 3.5), not silently smoothed over; no entity was
  given a substitute or forward-filled turnover value anywhere in this
  audit.
- **Same-day availability assumption, explicitly identified**: Convention
  B assumes the ranking date's own EOD turnover is available at that
  date's `09:20` signal. **This audit finds no basis for that assumption
  in the data**: `prices_eod` is an end-of-day feed: there is no
  mechanism, in this project's schema or any document read for this
  audit, by which a trading date's own turnover could be known before
  that date's session closes. This assumption, if adopted, would need to
  be stated and defended on its own terms, not inherited silently from
  Convention B's mechanics.

### 4.1 Calendar-source comparison detail

| Month | `prices_eod` first EQ day | `bars_1min` first day | Cause |
|---|---|---|---|
| 2016-10 | 2016-10-03 | 2016-10-04 | `bars_1min` archive literally starts 2016-10-04 (known archive-start artifact, not a session-calendar disagreement) |
| 2020-02 | 2020-02-03 | 2020-02-01 | Verified weekend special session (bucket E); `prices_eod` has no EQ row for 2020-02-01 |
| 2025-02 | 2025-02-03 | 2025-02-01 | Same as above, verified weekend special session |
| 2026-02 | 2026-02-02 | 2026-02-01 | Same as above, verified weekend special session |

---

## 5. Required conclusion

**This audit does not approve any convention. The user makes the final
choice.** Separated exactly as the task requires:

### What existing documents already specify
Section 6's exact text ("no bar after the ranking date is used") and
nothing more precise. This phrasing does not resolve ranking-date
inclusivity (Section 1.1-1.5). No document states an explicit
effective-time rule ("the roster becomes effective at open," "turnover
through the prior close only," or equivalent).

### What existing code or data establish
- No committed code implements the monthly ranking step at all (Section
  1.2).
- One prior, uncommitted scratchpad script assumed Convention B without
  flagging it (Section 1.3) -- evidence of an unexamined default, not an
  intended convention.
- The project's own committed annual-reconstitution code uses a full
  prior-period exclusion with no current-year lookback at all (Section
  1.4) -- a real precedent for the family's general point-in-time
  discipline, though at a different (annual, not monthly) granularity.
- `prices_eod.turnover` is an end-of-day aggregate with no mechanism for
  same-day availability before that day's close (Section 2, Section
  4, item "same-day availability assumption").
- The reconstruction in Section 3 establishes, as fact: 120/120 months
  reproducible under both conventions; identical leader/follower counts
  in all 120 months; 47/120 months (39.2%) with at least one changed
  entity-tier assignment; 103 total reassignments, 58 distinct entities;
  differences driven by genuine rank-boundary median shifts (verified,
  Section 3.6), not by ties, missing data, or identity-resolution
  inconsistency; not concentrated in any period; the annual top-200
  universe step is unaffected (verified, Section 3.7); and the
  calendar-source choice for "first trading day" itself introduces a
  separate, smaller (4/120 months) ambiguity (Section 4.1).

### Methodological recommendation (not a decision)
1. **Convention A (prior-session cutoff) should govern** the roster used
   at the first trading day's `09:20` signal.
2. **The roster becomes effective at the open of its ranking date's
   trading session** -- i.e., it is available, as a matter of
   construction, before that date's `09:20` signal, because nothing in
   its calculation depends on same-day information.
3. **The exact 60-session window boundary**: the entity's own last 60
   `prices_eod` trading-day observations with `trade_date < ranking_date`
   (strict inequality) -- fully determined as of the close of the
   trading session immediately preceding the ranking date.
4. **Convention B is not point-in-time valid for use at the ranking
   date's own `09:20` signal**, because it requires that date's own
   closing turnover, which cannot exist until after that date's session
   closes (Section 2) -- this is a look-ahead, not a stylistic
   preference. A same-session-excluded variant of Convention B (roster
   effective only from the next trading session) would be point-in-time
   valid, but is a different rule than "formed on the first trading day
   of each month," requiring its own explicit statement and approval,
   not an assumed equivalence with the documented construction.
5. **The membership-impact measurement does not change this
   recommendation.** If anything, it reinforces it: the empirical
   difference between conventions is real but modest (no change to
   leader/follower counts in any month; entity-level reassignment in
   47/120 months, nearly always a single-entity boundary flip, never a
   wholesale reshuffling) and is driven by ordinary rank-boundary
   sensitivity, not a data problem that would argue against either
   convention on its own terms. Adopting the point-in-time-valid
   convention (A) therefore carries low practical cost relative to the
   alternative's availability problem.

### What still requires explicit user approval
- Whether Convention A is adopted as the frozen construction (this
  audit's recommendation, not a decision).
- Whether the `bars_1min`-vs-`prices_eod` calendar-source discrepancy
  (Section 4.1, 4 of 120 months) needs its own resolution, or whether
  `prices_eod`'s own calendar is accepted as sufficient for ranking-date
  determination specifically (a narrower, separate question from the
  governing 2,457-date calendar used elsewhere in this family).
- Option 2's own Stage-A threshold form, value, and denominator --
  explicitly **not** addressed by this audit, per the task's own
  instruction.

---

## 6. Final verification

### Files created or modified
- **Created**: `lead_lag/MONTHLY_ROSTER_EFFECTIVE_TIME_AUDIT.md` (this
  file) -- the only new file.
- **Modified**: none. No existing document was edited.

### Exact commands/scripts/queries used
- `C:\Users\ARJUNK~1\AppData\Local\Temp\claude\C--projects-trade-new\9226b9f3-0dbb-437d-8061-7ca8712366b0\scratchpad\roster_effective_time_audit.py`
  -- the full reconstruction (Section 3), reading `data/warehouse.duckdb`
  read-only, calling `fibo.universe.reconstitute_annually` and
  `fibo.universe.effective_universe` (both `src/fibo/universe.py`,
  unmodified) and running the per-entity trailing-60-observation query
  quoted in Section 3.1, once per (month, convention) pair.
- Two ad hoc, one-shot read-only Python snippets (not saved as separate
  files, run directly via the Bash tool): (a) the median-value
  verification for `2017-06-01`'s four boundary entities (Section 3.6
  table), and (b) the `prices_eod`-vs-`bars_1min` first-trading-day
  comparison (Section 4.1 table).
- Source files read, not modified: `src/fibo/universe.py`,
  `PREREGISTRATION_LEAD_LAG_V1.md` (Sections 4, 6, 7), 
  `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md` (Section 3A),
  `lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md` (Task 1),
  `lead_lag/MONTHLY_ROSTER_TURNOVER_SCALE_AUDIT.md`.
- Repository-wide search confirming `task1_monthly_tiers.py` is absent:
  `Glob` for the filename, zero matches.

### Data tables and date ranges used
- `data/warehouse.duckdb`: `prices_eod` (`series='EQ'`, `turnover`
  column), `isin_lineage`. Date range queried: full history for
  calendar-month boundary determination (2016-01 through 2026-11);
  turnover windows themselves reach back to `2014-xx` for the earliest
  120-month-window entities (not separately bounded, by construction of
  the trailing-60-observation query).
- `data/fibo_intraday.duckdb`: `bars_1min` (`trade_date` column only, for
  the Section 4.1 calendar comparison) -- no bar-level price/volume data
  read in this audit.
- Primary reconstruction scope: 120 calendar months, `2016-10` through
  `2026-09`.

### Reproduction counts and denominators
- 120 / 120 months reconstructed successfully under both conventions;
  11 / 131 months excluded (outside the documented `bars_1min` archive
  span), 0 excluded for any other reason.
- Annual universe: 2,400 (year, entity) rows across years 2016-2027 (the
  2027 row is a byproduct of `reconstitute_annually`'s own forward
  mapping and is never used, since no 2027 ranking month falls in scope).
- Eligible-count agreement: 119 / 120 months identical, 1 / 120 differs
  by exactly 1 entity.
- Leader-count agreement: 120 / 120 months identical.
- Entity-tier-assignment agreement: 73 / 120 months identical (zero
  changed entities); 47 / 120 months with >=1 changed entity; 103 total
  entity-month changes across 58 distinct entities.

### Verification commands

```
git diff --check
git diff --stat
git status --short
git rev-parse HEAD
```

Run after writing this report. Output:

- `git diff --check`: clean except the pre-existing, unrelated CRLF
  advisory warning on `PREREGISTRATION_LEAD_LAG_V1.md` (a prior task's
  change, not this one; no new whitespace errors).
- `git diff --stat`: unchanged from before this task -- this task
  modified no tracked file (`PREREGISTRATION_LEAD_LAG_V1.md`'s diff stat
  is identical to its state before this task began).
- `git status --short`: the new report appears as an additional `??`
  untracked file; every other entry (modified/untracked) is identical to
  the state before this task began.
- `git rev-parse HEAD`: unchanged, `9f71b65e006f937760e39a9f65035c69a1ef8df9`.
- Nothing staged, committed, or pushed.

### Limitations and failed checks
- `task1_monthly_tiers.py`'s exact original query could not be inspected
  (absent from the repository) -- Section 1.1's conclusion that it does
  not resolve the ambiguity rests on the surrounding document's prose,
  not on reading that script directly.
- The calendar-source question raised in Section 4.1 is a genuine,
  newly-found ambiguity that this audit surfaces but does not resolve --
  flagged for the user, not silently absorbed into either convention.
- This audit's reconstruction uses `prices_eod`'s own EQ calendar for
  "first trading day of month" throughout (consistent with turnover being
  sourced from `prices_eod`), which is itself a choice with a small
  (4/120 months) footprint relative to the governing `bars_1min` calendar
  -- stated as a limitation, not hidden inside the headline counts.
