# Combined Leader-Side + Follower-Side (70%) Feasibility Measurement

**Family**: Cross-Liquidity-Tier Return Propagation (lead-lag), Study V1
**Date**: 2026-11-10
**Type**: no-outcome feasibility measurement — sample availability and temporal coverage only
**Status**: measurement record. **Makes no decision, approves nothing, amends nothing.**

---

## 1. Purpose and explicit non-predictive scope

### Purpose

`lead_lag/DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` measured the
**follower** side alone across 11 candidate breadth thresholds, and recorded in
its own Section 11 item 3 that two Section-12 **leader-side** exclusions had
deliberately *not* been applied, so that "the counts in this document are upper
bounds on what a full pipeline would retain."

This document closes that stated gap for the single already-approved follower
threshold θ = 70% (with θ = 75% carried as context only). It answers one
question: **once the leader-side eligibility rules are combined with the 70%
follower-breadth threshold, how many scheduled observations survive, and over
what calendar span?**

### What this document is NOT

- It reads **no price, return, forward label, signal value, correlation,
  regression coefficient, beta, or any predictive or P&L statistic.** The only
  use of `open`/`high`/`low`/`close` anywhere in the code written for this task
  is inside a boolean structural-validity predicate evaluated in SQL (quoted
  verbatim in Section 3.4). No price is returned as a value, differenced,
  ratioed, or compared across timestamps. `S_leader(t)` is **never computed** —
  only the *breadth count* `n_t` that gates whether it would be computed.
- It establishes **no** claim that the retained sample is unbiased,
  representative, statistically independent, adequately powered, or predictive.
- It makes **no primary-gate eligibility determination**, registers no trial,
  and amends no preregistration or decision record.

### Status-label note

The decision table in `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
(Section 11, `:1592-1620`) still records Decisions 10/11/17/18/19 as OPEN. Per
the task brief, that label is stale relative to subsequent out-of-band human
approval, and Decision 17 (bar validity), Decision 18 (fixed monthly roster),
Decision 19 (Option 2 frozen-subset construction) and the 09:20/Decision-11
anchor were applied as approved and in force. **Nothing in this document should
be read as evidence that any of those decisions has been approved**; the
substantive rules were applied exactly as written in the documents, and the
status conflict is recorded here rather than resolved.

---

## 2. The exact leader-side rule text, quoted verbatim

Both passages were read directly from the committed file before any computation.

### 2.1 Section 12 — the whole-day leader exclusion

`PREREGISTRATION_LEAD_LAG_V1.md:512-522`, quoted in full:

> ## Section 12: exclusions
>
> Unchanged from the original version (pre-open/opening-auction bars;
> final-5-minutes-before-close signal-end minutes whose forward window
> would cross 15:30; <90%-bar-completeness entity-days; +/-1-trading-day
> corporate-action windows; **whole-day exclusion if <50% of that month's
> leader tier lacks a valid bar**). **New in this amendment, Section 8's
> per-minute breadth floor (`n_t >= 0.80 * leader-tier size`) is an
> additional, minute-level exclusion layered on top of the existing
> day-level 50% floor** -- the two operate at different granularities and
> both apply.

(Bold on the day-level clause added here for locating it; the amendment's own
bold on the second sentence is reproduced as written.)

**This sentence as literally written is logically inverted.** Taken word for
word, "whole-day exclusion if <50% of that month's leader tier **lacks** a
valid bar" would exclude a day precisely when *most* leaders *do* have valid
bars — i.e. it would exclude every normal day and retain only catastrophic
ones. That cannot be the intended rule, and the preregistration's own frozen
parameter table resolves it. `PREREGISTRATION_LEAD_LAG_V1.md:988` (Section 23):

> | Day-level leader breadth floor | >=50% of tier has a valid bar | Section 12 (original) |

**Implemented reading**: a trading day is **retained** iff
`n_day >= 0.50 * (that month's leader-tier size)`, where `n_day` counts leader-tier
members that have a valid bar that day; **excluded** iff `n_day < 0.50 * NL`.
This is Section 23's phrasing taken at face value and is the only reading under
which the two statements are consistent. The verbatim Section-12 wording is
flagged as a **drafting defect** in Section 7 below; it is not re-litigated
here, and no new rule was introduced.

### 2.2 Section 8 — the per-minute leader-breadth floor

`PREREGISTRATION_LEAD_LAG_V1.md:380-387` (the construction defining `n_t`):

> For each leader-tier entity `i` and each completed 1-minute bar `k`:
>
> ```
> B_follower_pool(k)  = equal-weighted mean of r(j,k) over ALL followers j in that month's follower tier
> AR_leader(i,k)      = r(i,k) - B_follower_pool(k)
> S_i(t)              = sum_{k=t-4}^{t} AR_leader(i,k)      [5-minute trailing cumulative, fixed in real minutes]
> S_leader(t)         = (1/n_t) * sum_i S_i(t)              [equal-weighted across leader-tier entities with a valid bar at t, subject to the breadth floor below]
> ```

`PREREGISTRATION_LEAD_LAG_V1.md:420-433` (the floor itself):

> **New: minimum per-minute breadth floor** (`lead_lag/LEAD_LAG_POWER_AND_BREADTH_REVISION.md`
> Task 2): `S_leader(t)` is **not computed** for a given minute unless
> `n_t >= 0.80 * (that month's leader-tier size)`. Evidence: pooled across
> an 11-month, 1-per-year sample (86,250 leader-tier minute-observations,
> post-open-auction-exclusion per Section 12), the frac-of-tier-present
> distribution is 0.825/0.875/0.875/0.95 at the 1st/10th/25th/50th
> percentiles -- leader-tier breadth is virtually always complete
> (pooled zero-volume-bar fraction across the sample: 3.1e-7). A 0.80
> floor excludes only the single genuine outlier minute found in the full
> sample (`2020-06-11 14:21:00`, 13/40 = 32.5% breadth) -- roughly 0.001%
> of minutes -- while a stricter floor (0.90+) would needlessly discard
> ~35.7% of minutes that are in fact fine (a handful of leaders missing a
> bar by routine, non-systemic chance). This floor is frozen now, per
> Section 23, not tuned after Phase 4 output exists.

And `PREREGISTRATION_LEAD_LAG_V1.md:987` (Section 23):

> | Per-minute leader breadth floor | `n_t >= 0.80 * tier size` | Section 8, this amendment, evidence-based (excludes ~0.001% of minutes) |

**Which minute(s) `t` the floor applies to — resolved.** The text ties the floor
to **`n_t`**, and `n_t` is defined in the construction block as the count of
"leader-tier entities with a valid bar **at `t`**" — a single-minute count at the
signal-completion minute, not a window-wide count. The cited evidence base
confirms this: `LEAD_LAG_POWER_AND_BREADTH_REVISION.md:189-198` (Task 2 method)
computed "`n_t` = count of valid-bar leader entities at each `(trade_date, ts)`",
a per-minute quantity, and the recommendation at `:245-256` is phrased per
minute ("excludes ~0.001% of minutes"). **Implemented reading: the floor is
evaluated at the signal-completion minute `t` only**, once per scheduled
observation. The alternative reading — the floor must hold at every minute of
the signal window `t-4 … t` — is measured as a sensitivity in Section 6.3 and
is reported there; it changes the result by 2 observations out of 153,016 and
changes the retained count by zero.

### 2.3 Comparison and rounding convention — verified moot

Both rules are written as plain real-number comparisons (`n_t >= 0.80 * tier
size`; `>=50% of tier has a valid bar`) with **no rounding convention stated**.
No rounding convention was invented. For integer `n` this is identical to the
`ceil` form, and the code asserts it for every leader-tier size actually
observed:

| `NL` observed | months | `0.50*NL` → smallest passing `n` | `ceil(0.50*NL)` | `0.80*NL` → smallest passing `n` | `ceil(0.80*NL)` |
|---:|---:|---:|---:|---:|---:|
| 40 | 105 | 20.0 → 20 | 20 | 32.0 → 32 | 32 |
| 39 | 6 | 19.5 → 20 | 20 | 31.2 → 32 | 32 |
| 38 | 7 | 19.0 → 19 | 19 | 30.4 → 31 | 31 |
| 37 | 2 | 18.5 → 19 | 19 | 29.6 → 30 | 30 |

`n >= f*N  ⟺  n >= ceil(f*N)` for every `(N, f)` pair in play — asserted in code,
**PASS**. The ambiguity is therefore immaterial. Both comparisons are `>=`
(retain), i.e. exclusion is strict `<`, exactly as both sections write it.

---

## 3. What was implemented, and from where

### 3.1 Files and code inspected (absolute paths)

| Component | Source | What was taken |
|---|---|---|
| Leader-side rules (the subject of this task) | `C:\projects\trade-new\PREREGISTRATION_LEAD_LAG_V1.md:374-441` (Section 8), `:502-522` (Sections 11-12), `:975-1013` (Section 23) | Quoted verbatim in Section 2 |
| Floor evidence base / `n_t` definition | `C:\projects\trade-new\lead_lag\LEAD_LAG_POWER_AND_BREADTH_REVISION.md:64-256` (Tasks 1 and 2) | Confirms `n_t` is a per-minute count; Task 1 per-month tier table used as Reconciliation 2 |
| Annual point-in-time universe | `C:\projects\trade-new\src\fibo\universe.py:78` (`reconstitute_annually`), `:155` (`effective_universe`) | Called unmodified, no extra year/date bound, `top_n=200`, `stub_year=2016` |
| Monthly tier split | `PREREGISTRATION_LEAD_LAG_V1.md:308` (Section 6), `:365` (Section 7) | First trading day of month; trailing-60-session median raw `prices_eod.turnover` (`EQ`, via `isin_lineage`), window inclusive, `>=60` sessions; top 20% `ceil(0.2*n_eligible)` = leaders, remainder = followers |
| Bar validity / endpoint rules (Decision 17) | `C:\projects\trade-new\lead_lag\DECISION_17_FINAL_POLICY_RECOMMENDATION.md:693-756` | PRESENT-VALID / FUNCTIONALLY ABSENT / GENUINE ABSENCE; exact-`EPOCH` 180-second forward-fill threshold |
| Regular-session scoping | `C:\projects\trade-new\lead_lag\DECISION_17_ZERO_VOLUME_INVESTIGATION.md:315-350` | `09:15`–`15:29` only; off-session rows never adjacent to a session bar |
| Schedule and anchor (Decision 11) | `C:\projects\trade-new\LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:965-1008` | One fixed anchor per horizon, `h+5` spacing, failed slots skipped never shifted |
| Follower Option 2 (Decision 19) | `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:426-468`, `:286-312` | Unified `(t-35, t-5, t)` pre-signal eligibility, frozen subset, θ at one step only, `t+h` check on the frozen subset, whole-observation discard |
| Prior follower-only measurement | `C:\projects\trade-new\lead_lag\DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` §2, §4, §7, §10.7, §11 | Reconciliation 1 target figures; the five-step filter order; the load-bearing SQL reused verbatim |
| Trial ledger | `C:\projects\trade-new\lead_lag\trial_ledger.json`, `lead_lag\ledger.py` | **Read only; untouched; no entry added** |

Data stores, both opened **read-only** (`ATTACH … (READ_ONLY)`):
`C:\projects\trade-new\data\fibo_intraday.duckdb` (`bars_1min`) and
`C:\projects\trade-new\data\warehouse.duckdb` (`prices_eod`, `isin_lineage`,
`corporate_actions`).

Scripts written for this task (scratchpad only, nothing in the repo):
`L1_roster.py` (both tiers + Reconciliation 2), `L2_eligibility.py` (Decision-17
validity and Section-12 gates for both tiers), `L3_combine.py` (schedule,
combination, Sections A–E, Reconciliations 1/3/4), `L4_diag.py` (confirmatory
diagnostics).

### 3.2 Measured population

| Item | Value |
|---|---|
| Date range | 2016-10-04 → 2026-09-18 |
| Trading dates | 2,468 |
| Analysis months | 120 (2016-10 … 2026-09) |
| Regular-session bar rows read (both tiers) | 169,838,139 |
| Monthly **leader** roster size `NL` | 37 – 40 (median 40; 105 of 120 months at exactly 40) |
| Monthly **follower** roster size `NF` | 144 – 160 (median 160; 91 of 120 months at exactly 160) |
| Distinct leader-roster entities across all months | 155 |
| Distinct follower-roster entities across all months | 416 |
| Leader-roster entity-days in scope | 98,184 |
| Follower-roster entity-days in scope | 391,501 |
| Within-month leader/follower overlap | **0** (asserted) |
| **Scheduled observations** | **153,016** = 2,468 days × 62 slots/day |
| Slots per day, re-derived | h=5: 33 (09:59…15:19) · h=15: 16 (09:59…14:59) · h=30: 9 (09:54…14:34) · h=60: 4 (10:24…13:39) |
| Follower target clock-minutes per day | 72 |
| Leader signal-window clock-minutes per day (`t-4…t`, all horizons) | 200 |

The schedule was re-derived from the Decision-11 rules (anchor `t0 = 09:19`,
spacing `h+5`, constraints `t-35 >= 09:15` and `t+h <= 15:29`, failing slots
`continue`d). The resulting 33/16/9/4 and 153,016 match the prior measurement's
figures exactly — used as a sanity check, not hardcoded.

### 3.3 Leader-side implementation, stated precisely

**Step L1 — whole-day leader exclusion.** For each trading day, `n_day` = the
number of that month's leader-roster members having a valid bar that day. The
day is excluded iff `n_day < 0.50 * NL`.

"Has a valid bar that day" is implemented **primarily** as: *the leader
entity-day survives Section 12's already-frozen entity-day gates* (the
`<90%`-of-375-present-valid rule, then the `+/-1`-trading-day corporate-action
window). Rationale: Section 12 lists the `<90%`-bar-completeness entity-day
exclusion **before** the leader day-level clause and restricts it to neither
tier, and the project's own frozen filter order
(`DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md:349-364`) applies entity-day
gates *before* any breadth count. An entity-day already excluded wholesale by
Section 12 has no bar available to any downstream computation, so it cannot
supply the "valid bar" the day-level clause counts. Since passing the 90% gate
implies `>=338` present-valid bars, this reading also automatically satisfies
any weaker "at least one valid bar" requirement.

The looser, more word-literal reading — *`>=1` present-valid regular-session bar,
entity-day gates ignored* — is measured as a sensitivity in Section 6.3. Both
readings produce the **identical retained observation set**; the ambiguity is
immaterial to every number in Sections A–E.

**Step L2 — per-minute leader-breadth floor.** For each scheduled observation at
signal-completion minute `t`:

```
n_t = (# leader-roster members whose entity-day survives the Section-12 gates)
      - (# of those that are INVALID at clock-minute t under Decision 17)
```

i.e. `n_t` counts leader-tier members **present-valid or forward-fillable** at
`t`, exactly as Decision 17 defines validity: present-valid (positive-volume
structurally valid, or zero-volume OHLC-flat); else genuine absence filled from
the nearest preceding present-valid bar in the same `(entity_id, trade_date)`
when exact elapsed `EPOCH` seconds `< 180`; else invalid and **not imputed**.
Functionally-absent bars (zero-volume non-flat, or structurally invalid) are not
usable and **do not reset a surrounding gap**. The observation is excluded iff
`n_t < 0.80 * NL`. Evaluated at minute `t` only (Section 2.2).

**Step L3 — leader-side eligibility** = L1 AND L2.

### 3.4 Load-bearing SQL (reused verbatim from the prior measurement)

PRESENT-VALID classification — the only place any OHLC field is touched, and it
is touched only as a boolean:

```sql
  (b.open IS NOT NULL AND b.high IS NOT NULL AND b.low IS NOT NULL AND b.close IS NOT NULL
   AND isfinite(b.open) AND isfinite(b.high) AND isfinite(b.low) AND isfinite(b.close)
   AND b.open > 0 AND b.high > 0 AND b.low > 0 AND b.close > 0
   AND b.volume IS NOT NULL AND b.volume >= 0
   AND b.high >= b.low AND b.open >= b.low AND b.open <= b.high
   AND b.close >= b.low AND b.close <= b.high
   AND (b.volume > 0 OR (b.open = b.high AND b.high = b.low AND b.low = b.close)))
```

Regular-session scoping; Section-12 90% rule; the exact-elapsed-seconds gap rule:

```sql
WHERE date_trunc('minute', b.ts)::TIME >= TIME '09:15:00'
  AND date_trunc('minute', b.ts)::TIME <= TIME '15:29:00'
```
```sql
(COALESCE(d.n_pv, 0) >= 0.9 * 375) AS pass90
```
```sql
WHERE NOT (a.p_ts IS NOT NULL AND (epoch(a.gm) - epoch(a.p_ts)) < 180 AND n.m IS NULL)
```

One **performance-only** change versus the prior run, mathematically identical
and stated for the record: the gap-detection machinery is restricted to
entity-days with `n_pv < 375`. The regular session 09:15–15:29 is exactly 375
minutes and minute buckets are unique per `(entity_id, trade_date)` (verified in
the prior measurement, §10.4/§10.5), so an entity-day with `n_pv = 375` has every
in-session minute present-valid and can contribute no gap minute. This changes
no output row — only the work done. It was needed because adding the leader tier
raised the bar-row count from 160.6M to 169.8M and exceeded the previous temp
budget.

### 3.5 Filter-application order (load-bearing for Section D)

```
1. Roster construction (identity only, both tiers; no availability input)
2. Section-12 entity-day gates  (<90%-of-375 rule, then +/-1-day CA window)   [both tiers]
3. Decision-17 endpoint validity  (leader: minute t;  follower: t-35, t-5, t)
4. L1  whole-day leader exclusion       n_day >= 0.50 * NL
5. L2  per-minute leader floor          n_t    >= 0.80 * NL
6. F1  follower pre-signal breadth      n_eligible >= ceil(theta * NF)
7. F2  follower forward-endpoint check  every frozen subset member valid at t+h
```

Steps 1–3 are **inputs** to the counts used in 4–7 and are never counted again as
observation-level categories. Steps 4→7 are applied in that order and an
observation is attributed to the **first** stage it fails, making the four
exclusion categories mutually exclusive and exhaustive against the scheduled
total by construction (Reconciliation 3). Where two stages could independently
exclude the same observation — and they very often can, see Section C — the
earlier stage in this order owns it, and that attribution is held fixed
throughout this document.

---

## 4. Section A — Overall sample, per horizon

### 4.1 θ = 70% (the approved follower threshold)

Never pooled across horizons except in the explicitly labelled `ALL` row.

| Stage | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| Scheduled observations | 81,444 | 39,488 | 22,212 | 9,872 | 153,016 |
| Surviving follower pre-signal breadth alone | 80,678 | 39,134 | 22,012 | 9,781 | 151,605 |
| Surviving **follower side alone** (breadth + forward) | 79,662 | 38,633 | 21,708 | 9,639 | 149,642 |
| Surviving leader whole-day rule alone | 80,883 | 39,216 | 22,059 | 9,804 | 151,962 |
| Surviving leader per-minute floor alone | 80,849 | 39,216 | 22,058 | 9,804 | 151,927 |
| Surviving **leader side alone** (both leader checks) | 80,849 | 39,216 | 22,058 | 9,804 | 151,927 |
| Surviving leader side **AND** follower pre-signal | 80,678 | 39,134 | 22,012 | 9,781 | 151,605 |
| **Retained after follower forward-endpoint check** | **79,662** | **38,633** | **21,708** | **9,639** | **149,642** |
| Retained % of that horizon's scheduled total | **97.812%** | **97.835%** | **97.731%** | **97.640%** | **97.795%** |

Exclusions by stage (attribution order of Section 3.5):

| Exclusion category | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| 1. Whole-day leader-tier exclusion | 561 | 272 | 153 | 68 | 1,054 |
| 2. Per-minute leader-breadth exclusion | 34 | 0 | 1 | 0 | 35 |
| 3. Follower pre-signal breadth (70%) | 171 | 82 | 46 | 23 | 322 |
| 4. Follower forward-endpoint missingness | 1,016 | 501 | 304 | 142 | 1,963 |
| **Total excluded** | 1,782 | 855 | 504 | 233 | 3,374 |

### 4.2 The headline result

**The leader-side rules remove no additional observations.** Retained is
identical, per horizon, to the follower-only retained count published in
`DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` §5:

| θ | h | follower-only retained | combined (leader + follower) retained | delta |
|---:|---:|---:|---:|---:|
| 70% | 5 | 79,662 | 79,662 | **0** |
| 70% | 15 | 38,633 | 38,633 | **0** |
| 70% | 30 | 21,708 | 21,708 | **0** |
| 70% | 60 | 9,639 | 9,639 | **0** |
| 70% | ALL | 149,642 | 149,642 | **0** |
| 75% | 5 | 77,038 | 77,038 | **0** |
| 75% | 15 | 37,362 | 37,362 | **0** |
| 75% | 30 | 20,989 | 20,989 | **0** |
| 75% | 60 | 9,327 | 9,327 | **0** |
| 75% | ALL | 144,716 | 144,716 | **0** |

Every one of the 1,089 observations that fails the leader side **already fails
the follower side**. Measured directly, not inferred:

- Of the 1,054 observations on leader-whole-day-excluded dates, **1,054** also
  fail the follower side at 70%; the maximum follower `n_eligible` anywhere on
  those dates is **25** against a requirement of 108–112.
- Of the 35 per-minute-floor exclusions, **35** also fail follower pre-signal
  breadth; follower `n_eligible` there is 23–26 (median 24) against a
  requirement of 112.

Consequence, stated plainly: the prior document's self-described "upper bound"
is, at θ = 70% and θ = 75%, **exactly attained** — the leader-side Section-12
exclusions are entirely nested inside the follower-side exclusions and are
non-binding. This is a measured property of this data, not a general claim: it
holds because the leader tier is the most liquid 20% of the universe and the
events that disable it (non-regular sessions, market-wide interruptions) disable
the much thinner follower tier at least as severely.

---

## 5. Section B — Temporal coverage, per horizon (θ = 70%)

| Metric | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| Retained observations | 79,662 | 38,633 | 21,708 | 9,639 | 149,642 |
| Distinct retained trading dates (of 2,468) | 2,446 | 2,446 | 2,446 | 2,446 | 2,446 |
| Retained calendar months (of 120) | 120 | 120 | 120 | 120 | 120 |
| Retained years (of 11) | 11 | 11 | 11 | 11 | 11 |
| First retained date | 2016-10-04 | 2016-10-04 | 2016-10-04 | 2016-10-04 | 2016-10-04 |
| Last retained date | 2026-09-18 | 2026-09-18 | 2026-09-18 | 2026-09-18 | 2026-09-18 |
| Trading dates with **zero** retained observations | 22 | 22 | 22 | 22 | 22 |
| Largest gap between consecutive retained dates | 5 calendar days | 5 | 5 | 5 | 5 |

The four horizons have identical date/month/year coverage: the 22 zero-retained
dates are whole-day failures (non-regular or interrupted sessions, or
market-wide breadth collapse), so they remove every slot of every horizon
together rather than biting at particular times of day.

### 5.1 Long gaps — there are none

The largest calendar gap between consecutive retained trading dates is **5
days**, and every such gap is an ordinary weekend-plus-holiday:

| Previous retained date | Next retained date | Gap (calendar days) |
|---|---|---:|
| 2017-04-13 | 2017-04-18 | 5 |
| 2017-10-18 | 2017-10-23 | 5 |
| 2018-03-28 | 2018-04-02 | 5 |
| 2021-01-22 | 2021-01-27 | 5 |
| 2021-11-03 | 2021-11-08 | 5 |
| 2022-04-13 | 2022-04-18 | 5 |

Measured in **trading** dates rather than calendar days, the 22 zero-retained
dates are all **isolated singletons**: the longest run of consecutive
zero-retained trading dates is **1**, with a run-length distribution of
`{1: 22}`. There is no multi-day, multi-week or multi-month hole anywhere in the
retained sample.

### 5.2 Year-by-year breakdown (θ = 70%)

| Year | trading dates in archive | retained dates | retained obs, h=5 | h=15 | h=30 | h=60 | all pooled |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 61 | 60 | 1,914 | 923 | 523 | 229 | 3,589 |
| 2017 | 248 | 241 | 7,721 | 3,738 | 2,102 | 931 | 14,492 |
| 2018 | 246 | 245 | 7,923 | 3,842 | 2,158 | 962 | 14,885 |
| 2019 | 244 | 244 | 7,843 | 3,806 | 2,127 | 948 | 14,724 |
| 2020 | 252 | 248 | 8,075 | 3,916 | 2,203 | 980 | 15,174 |
| 2021 | 248 | 245 | 8,024 | 3,886 | 2,187 | 967 | 15,064 |
| 2022 | 248 | 247 | 8,094 | 3,925 | 2,204 | 976 | 15,199 |
| 2023 | 246 | 245 | 8,038 | 3,894 | 2,193 | 976 | 15,101 |
| 2024 | 249 | 246 | 8,069 | 3,918 | 2,197 | 977 | 15,161 |
| 2025 | 249 | 248 | 8,162 | 3,957 | 2,222 | 986 | 15,327 |
| 2026 (to 09-18) | 177 | 177 | 5,799 | 2,828 | 1,592 | 707 | 10,926 |

### 5.3 Do 2016–2017 remain meaningfully represented? **Yes — checked directly**

- **2016**: the intraday archive contains only **61** trading dates in 2016
  (it begins 2016-10-04). **60 of those 61 dates are retained** — 98.4%. The
  single loss is 2016-10-30, a Sunday with off-session rows only. 3,589 retained
  observations, including **229 at the primary h=60 horizon**.
- **2017**: 248 trading dates, **241 retained** (97.2%), 14,492 retained
  observations, **931 at h=60** — statistically indistinguishable from 2018–2025
  (962 / 948 / 980 / 967 / 976 / 976 / 977 / 986 at h=60).
- Both years retain **all 12 (2017) and all 3 (2016-10/11/12) calendar months**.
  The 120-of-120-months figure is reached because no month anywhere loses all of
  its dates.

The combined pipeline therefore does **not** erode early-year coverage. 2016's
smaller absolute count is a property of the archive's 2016-10-04 start date, not
of these filters.

---

## 6. Section C — Leader/follower filter interaction

### 6.1 The cross-tabulation (θ = 70%, all 153,016 scheduled observations)

| | passes follower side | fails follower side | total |
|---|---:|---:|---:|
| **passes leader side** | **149,642** (retained) | 2,285 | 151,927 |
| **fails leader side** | **0** | 1,089 | 1,089 |
| total | 149,642 | 3,374 | 153,016 |

| Category | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| Excluded **only** by leader-side rules | **0** | **0** | **0** | **0** | **0** |
| Excluded **only** by follower-side rules | 1,187 | 583 | 350 | 165 | 2,285 |
| Excluded by **both** sides | 595 | 272 | 154 | 68 | 1,089 |
| Retained (excluded by neither) | 79,662 | 38,633 | 21,708 | 9,639 | 149,642 |

The leader-side exclusion set is a **strict subset** of the follower-side
exclusion set — the "only by leader-side" cell is empty at every horizon.

### 6.2 Correctness check — strict AND (Reconciliation 4)

| θ | passes leader side AND passes follower side AND **not** retained | retained AND **not** (passes both) |
|---:|---:|---:|
| 70% | **0** | **0** |
| 75% | **0** | **0** |

Verified in the data, not assumed: the combination is a strict conjunction in
both directions, with no observation retained that fails a side and none
discarded that passes both. **PASS.**

### 6.3 Do leader-side exclusions land disproportionately on weak-follower periods?

Reported from the data alone, with no inference beyond what the data shows.

**Leader-side exclusion rate by year** (θ-independent — the leader rules do not
involve θ):

| Year | scheduled obs | leader whole-day fails | leader minute-floor fails | leader-side fails | leader-side fail % | follower-side fail % (θ=70%) |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | 3,782 | 62 | 62 | 62 | 1.639% | 5.103% |
| 2017 | 15,376 | 124 | 124 | 124 | 0.806% | 5.749% |
| 2018 | 15,252 | 62 | 62 | 62 | 0.407% | 2.406% |
| 2019 | 15,128 | 0 | 0 | 0 | 0.000% | 2.671% |
| 2020 | 15,624 | 248 | 248 | 248 | 1.587% | 2.880% |
| 2021 | 15,376 | 186 | 187 | 187 | 1.216% | 2.029% |
| 2022 | 15,376 | 62 | 62 | 62 | 0.403% | 1.151% |
| 2023 | 15,252 | 62 | 62 | 62 | 0.407% | 0.990% |
| 2024 | 15,438 | 186 | 186 | 186 | 1.205% | 1.794% |
| 2025 | 15,438 | 62 | 62 | 62 | 0.402% | 0.719% |
| 2026 | 10,974 | 0 | 34 | 34 | 0.310% | 0.437% |

Direct period comparison, as required:

| Period | scheduled obs | leader-side excluded | rate | follower-side excluded | rate |
|---|---:|---:|---:|---:|---:|
| 2016–2017 | 19,158 | 186 | **0.971%** | 1,077 | 5.622% |
| 2018–2020 | 46,004 | 310 | 0.674% | 1,221 | 2.654% |
| **2021+** | 87,854 | 593 | **0.675%** | 1,076 | 1.225% |

**The answer from the data: no meaningful concentration.** The 2016–2017
leader-side exclusion rate (0.971%) is only ~1.4× the 2021+ rate (0.675%), and
2020 (1.587%), 2021 (1.216%) and 2024 (1.205%) each exceed the 2017 rate
(0.806%) outright. The follower side, by contrast, degrades ~4.6× from 2021+ to
2016–2017. Leader-side exclusions are driven by **isolated non-regular trading
sessions** (Muhurat-pattern dates, short sessions, market-wide interruptions)
which are spread roughly uniformly across the decade at 0–4 dates a year, not by
early-archive thinness. Where the two do coincide, the follower side is already
the binding constraint — which is why the "only by leader-side" count is zero.

**Note on the near-identity of the two leader columns.** In most years the
whole-day and per-minute counts coincide because, under the attribution order,
a day failing the whole-day rule is counted in column 1, and the same day's
minutes also fail the floor; the "leader-side fails" column is the union, not
the sum. 2026 is the one year with a minute-floor failure on a day that passes
the whole-day rule (34 observations, discussed in Section 7.4).

### 6.4 Ambiguity sensitivities — all four readings give the identical retained set

| Reading | retained | % | dates | months | years | attributed to whole-day | attributed to minute floor | leader-side union |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **PRIMARY**: gated day rule, floor at minute `t` | **149,642** | 97.80% | 2,446 | 120 | 11 | 1,054 | 35 | 1,089 |
| loose day rule (`>=1` present-valid bar), floor at `t` | 149,642 | 97.80% | 2,446 | 120 | 11 | 558 | 531 | 1,089 |
| gated day rule, floor at all 5 minutes `t-4…t` | 149,642 | 97.80% | 2,446 | 120 | 11 | 1,054 | 37 | 1,091 |
| loose day rule, floor at all 5 minutes | 149,642 | 97.80% | 2,446 | 120 | 11 | 558 | 533 | 1,091 |

Both unresolved readings are therefore **immaterial to every reported number**.
The looser day rule simply reclassifies 8 dates (496 observations) from category
1 to category 2 — they fail the per-minute floor anyway. Widening the floor from
minute `t` to all five signal-window minutes adds 2 observations to the
leader-side exclusion union, both of which the follower side already excludes.
The retained count, retained dates, retained months and retained years are
invariant across all four branches.

---

## 7. Section D — Exclusion diagnostics

### 7.1 The four categories and their reconciliation (Reconciliation 3)

Categories are defined by the **first** stage failed in the Section 3.5 order,
so they are non-overlapping and exhaustive by construction.

θ = 70%:

| Category | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| 1. Whole-day leader-tier exclusion | 561 | 272 | 153 | 68 | 1,054 |
| 2. Per-minute leader-breadth exclusion | 34 | 0 | 1 | 0 | 35 |
| 3. Follower pre-signal breadth (70%) | 171 | 82 | 46 | 23 | 322 |
| 4. Follower forward-endpoint missingness | 1,016 | 501 | 304 | 142 | 1,963 |
| Retained | 79,662 | 38,633 | 21,708 | 9,639 | 149,642 |
| **Sum** | **81,444** | **39,488** | **22,212** | **9,872** | **153,016** |
| Scheduled | 81,444 | 39,488 | 22,212 | 9,872 | 153,016 |
| Reconciles | ✓ | ✓ | ✓ | ✓ | ✓ |

θ = 75%:

| Category | h=5 | h=15 | h=30 | h=60 | ALL |
|---|---:|---:|---:|---:|---:|
| 1. Whole-day leader-tier exclusion | 561 | 272 | 153 | 68 | 1,054 |
| 2. Per-minute leader-breadth exclusion | 34 | 0 | 1 | 0 | 35 |
| 3. Follower pre-signal breadth (75%) | 2,892 | 1,402 | 791 | 351 | 5,436 |
| 4. Follower forward-endpoint missingness | 919 | 452 | 278 | 126 | 1,775 |
| Retained | 77,038 | 37,362 | 20,989 | 9,327 | 144,716 |
| **Sum** | **81,444** | **39,488** | **22,212** | **9,872** | **153,016** |
| Reconciles | ✓ | ✓ | ✓ | ✓ | ✓ |

**Why double-counting cannot occur.** The four stages are applied in the fixed
order of Section 3.5 and each observation is assigned to the first it fails.
Categories 1–4 and "retained" therefore partition the scheduled set exactly.
**Two categories can and frequently do independently exclude the same
observation** — Section 6.1 shows 1,089 observations fail both a leader-side and
a follower-side stage. Those are attributed to the earlier (leader-side) stage,
and the same attribution is used in every table in this document. Changing the
order would move counts between categories 1/2 and 3/4 but cannot change the
retained set, which is a strict AND (Section 6.2). There is **no residual,
unknown or unattributed category**: `1+2+3+4+retained = 153,016` exactly, for
every horizon and both θ.

### 7.2 Leader-side entity-day accounting (inputs feeding categories 1 and 2)

| Stage | leader entity-days | % of scope |
|---|---:|---:|
| Leader-roster entity-days in scope | 98,184 | 100.00% |
| — removed: zero present-valid bars that day (archive-absent or no session) | 5,620 | 5.72% |
| — removed: partial data but `<90%` of 375 bars present-valid | 316 | 0.32% |
| — removed: `+/-1`-trading-day corporate-action window | 98 | 0.10% |
| **Surviving leader entity-days** | **92,150** | **93.85%** |

Leader Section-12 90%-rule failure rate by year (entity-days): 11.73% (2016),
10.54% (2017), 13.15% (2018), 9.77% (2019), 7.05% (2020), 4.70% (2021), 3.54%
(2022), 3.72% (2023), 3.77% (2024), 0.44% (2025), 0.83% (2026). Comparable to
the follower tier's published profile but roughly half the early-year rate
(24.7% / 24.4% for followers in 2016/2017). 13 of the 155 distinct
leader-roster entities have **zero rows in `bars_1min` ever** (vs 41 of 416 on
the follower side).

### 7.3 The 17 dates excluded by the whole-day leader rule

All 17 are also zero-retained dates on the follower side alone (verified: the
leader-excluded date set is a strict subset of the 22 zero-retained dates, and
the 22-date zero-retained set is **identical** with and without the leader
rules).

| Date | `NL` | `n_day` (gated) | `n_day` (loose, `>=1` PV bar) | `nF_ok` | max follower `n_eligible` | req@70% |
|---|---:|---:|---:|---:|---:|---:|
| 2016-10-30 (Sun) | 39 | 0 | 35 | 0 | 0 | 108 |
| 2017-07-10 | 40 | 0 | 34 | 0 | 0 | 112 |
| 2017-10-19 | 40 | 0 | 0 | 0 | 0 | 112 |
| 2018-11-07 | 40 | 0 | 0 | 0 | 0 | 112 |
| 2020-03-13 | 40 | 0 | 37 | 0 | 0 | 111 |
| 2020-03-23 | 40 | 0 | 37 | 0 | 0 | 111 |
| 2020-11-10 | 40 | 6 | 6 | 25 | 25 | 112 |
| 2020-11-14 (Sat) | 40 | 0 | 0 | 0 | 0 | 112 |
| 2021-01-25 | 39 | 2 | 2 | 17 | 17 | 109 |
| 2021-02-24 | 40 | 0 | 38 | 0 | 0 | 110 |
| 2021-11-04 | 40 | 0 | 0 | 0 | 0 | 112 |
| 2022-10-24 | 40 | 0 | 0 | 0 | 0 | 112 |
| 2023-11-12 (Sun) | 40 | 0 | 0 | 0 | 0 | 112 |
| 2024-03-02 (Sat) | 39 | 0 | 38 | 0 | 0 | 108 |
| 2024-05-18 (Sat) | 40 | 0 | 39 | 0 | 0 | 112 |
| 2024-11-01 | 40 | 0 | 0 | 0 | 0 | 112 |
| 2025-10-21 | 40 | 0 | 40 | 0 | 0 | 112 |

Fifteen of these 17 appear in the prior measurement's own table of fifteen
`n_eligible = 0` dates (Muhurat-pattern sessions with no regular session; short
or interrupted sessions). The two additional leader-excluded dates —
**2020-11-10** and **2021-01-25** — are not in that fifteen because the follower
tier retained a nonzero but far-insufficient `n_eligible` there (25 and 17
against requirements of 112 and 109). The remaining five of the 22 zero-retained
dates (2017-01-02, 2017-01-10, 2017-01-16, 2017-04-17, 2017-05-09) **pass** the
leader whole-day rule (`n_day = 37`) and fail only on follower breadth
(`n_eligible` 108–111 vs. required 110–112) — further confirmation that the
leader tier is the stronger side.

### 7.4 The per-minute leader floor: `n_t` distribution and the 35 exclusions

Over the 151,962 observations surviving the whole-day rule:

| statistic | `n_t` | `n_t / NL` |
|---|---:|---:|
| min | 1 | 0.0250 |
| 0.01st percentile | 2 | 0.0500 |
| 0.1st percentile | 32 | 0.8000 |
| 1st percentile | 33 | 0.8250 |
| 5th percentile | 34 | 0.8718 |
| 10th percentile | — | 0.8750 |
| 25th percentile | 36 | 0.9231 |
| median | 38 | 0.9500 |
| max | 40 | 1.0000 |
| mean (sd) | 37.585 (1.866) | — |

The 1st/10th/25th/50th percentiles of `n_t / NL` — **0.825 / 0.875 / 0.923 /
0.950** — reproduce the preregistration's cited Task 2 figures
(0.825 / 0.875 / 0.875 / 0.95) closely over the full 10-year population rather
than the 11-month pilot, confirming the 0.80 floor's stated evidence base out of
sample. The floor excludes **35 of 151,962** day-rule-surviving observations
(**0.023%**), consistent with the preregistration's "~0.001% of minutes" claim
once the different denominators are noted: the floor bites on 35 distinct
`(date, t)` minutes, not 35 of all 375-minute-days.

All 35 are concentrated in exactly two places:

| Occurrence | observations | detail |
|---|---:|---|
| `2021-01-19` at `t = 09:54` (h=30) | 1 | `n_t = 3` of `NL = 39` (`nL_ok = 37`) — isolated early-session minute |
| `t = 15:19` (h=5), every trading date 2026-08-03 → 2026-09-18 | 34 | `n_t = 2` (August) then `1` (September) of `NL = 40` |

The second cluster is **not leader-specific** and not a liquidity phenomenon: at
the same `15:19` minute in those months the follower tier's median `n_eligible`
also collapses to **24–25 of 160**, against 152–156 in every prior month.

| Month | `t=15:19` slots | leader `n_t` min / median | follower `n_eligible` median | `NF` |
|---|---:|---:|---:|---:|
| 2026-05 | 19 | 40 / 40 | 156 | 160 |
| 2026-06 | 21 | 40 / 40 | 155 | 160 |
| 2026-07 | 23 | 39 / 39 | 156 | 160 |
| **2026-08** | 21 | **2 / 2** | **24** | 160 |
| **2026-09** | 13 | **1 / 1** | **25** | 160 |

This is an **archive-truncation artifact at the end of the trading day in the
final two months of the intraday store** (which ends 2026-09-18), affecting both
tiers simultaneously. It is reported as observed; its cause is not investigated
here and no rule was added to handle it. Because the follower side excludes all
34 observations independently, it has no effect on any retained count — but it
would matter to any future measurement that reads the leader side alone, and is
flagged for that reason.

---

## 8. Section E — Comparison with 75% (context only)

No sweep was reopened and no new threshold is proposed. The identical leader-side
rules were applied to the 75% follower candidate.

| Quantity | θ = 70% | θ = 75% | 70% advantage |
|---|---:|---:|---:|
| Retained observations, h=5 | 79,662 | 77,038 | **+2,624** |
| Retained observations, h=15 | 38,633 | 37,362 | **+1,271** |
| Retained observations, h=30 | 21,708 | 20,989 | **+719** |
| Retained observations, h=60 | 9,639 | 9,327 | **+312** |
| Retained observations, all pooled | 149,642 | 144,716 | **+4,926** |
| Retained % of scheduled | 97.795% | 94.576% | +3.219 pp |
| Distinct retained trading dates | 2,446 | 2,366 | **+80** |
| Retained calendar months | 120 | 120 | **+0** |
| Retained years | 11 | 11 | **+0** |
| First → last retained date | 2016-10-04 → 2026-09-18 | 2016-10-04 → 2026-09-18 | unchanged |

Monotonicity verified: **0** observations are retained at 75% but not at 70%, so
the 70% set strictly contains the 75% set and the 4,926 difference is a clean
margin.

### 8.1 Is the marginal difference concentrated in 2016–2017? **Yes — checked directly**

Marginal observations (retained at 70%, not at 75%), by year:

| Year | marginal observations | % of the 4,926 | additional distinct dates |
|---|---:|---:|---:|
| 2016 | 1,267 | 25.7% | 21 |
| 2017 | 3,650 | 74.1% | 59 |
| 2019 | 9 | 0.2% | 0 |
| all other years | 0 | 0.0% | 0 |

**4,917 of 4,926 (99.82%) of the marginal observations fall in 2016–2017**, and
**all 80 additional distinct dates are in 2016 (21) and 2017 (59)**. The
remaining 9 observations are a single 2019 date that is retained at both
thresholds. By horizon the margin splits 2,624 / 1,271 / 719 / 312 for
h=5/15/30/60 — the same ~53/26/15/6 proportions as the slot counts, so the
concentration is temporal, not horizon-specific.

Concretely, moving 70% → 75% costs 2016 **21 of its 60** retained dates (35%)
and 2017 **59 of its 241** (24%), while costing 2018 and every later year
**nothing at all** (2018: 14,885 observations at both; 2019: 14,724 vs 14,715).

Reported as context. **No threshold recommendation is made or implied.**

---

## 9. The four required reconciliation checks

| # | Check | Result |
|---|---|---|
| **1** | Recomputed follower-only figures match `DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` §4 | **PASS** |
| **2** | Leader/follower tier reconstruction matches `LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1 | **PASS** |
| **3** | Four exclusion categories sum to the scheduled total, every horizon | **PASS** |
| **4** | "Passes each side independently but fails combined" = 0 under strict AND | **PASS** |

### Reconciliation 1 — follower-only recomputation (detail)

Recomputed independently in this task before combining with the leader rules:

| θ | quantity | published | recomputed | match |
|---:|---|---:|---:|:---:|
| 70% | pre-signal-eligible | 151,605 (99.08%) | 151,605 (99.080%) | ✓ |
| 70% | retained after forward check | 149,642 (97.80%) | 149,642 (97.795%) | ✓ |
| 70% | distinct qualifying dates | 2,446 | 2,446 | ✓ |
| 70% | calendar months / years | 120 / 11 | 120 / 11 | ✓ |
| 70% | first → last | 2016-10-04 → 2026-09-18 | 2016-10-04 → 2026-09-18 | ✓ |
| 75% | pre-signal-eligible | 146,491 (95.74%) | 146,491 (95.736%) | ✓ |
| 75% | retained after forward check | 144,716 (94.58%) | 144,716 (94.576%) | ✓ |
| 75% | distinct qualifying dates | 2,366 | 2,366 | ✓ |
| 75% | calendar months / years | 120 / 11 | 120 / 11 | ✓ |
| 75% | first → last | 2016-10-04 → 2026-09-18 | 2016-10-04 → 2026-09-18 | ✓ |

Per-horizon §5 figures also reproduce exactly (70%: 80,678/79,662 · 39,134/38,633
· 22,012/21,708 · 9,781/9,639; 75%: 77,957/77,038 · 37,814/37,362 ·
21,267/20,989 · 9,453/9,327). Two further independent anchors reproduced:
scheduled total **153,016** with 33/16/9/4 slots per day, and the follower
invalid-`(entity, day, target-minute)`-triple count **11,491** over the 72
follower target minutes. Follower entity-day accounting also matches: 391,501
in scope, 349,859 surviving the day-level gates.

**No discrepancy was found, so nothing was adjusted.** See limitation 10.1 on
what this check does and does not establish.

### Reconciliation 2 — tier reconstruction (detail)

`reconstitute_annually(con, top_n=200)` called with no bound returned
**2016–2027** (12 years), confirming directly that it mints a year beyond the
analysis window because `prices_eod` extends past the intraday cutoff.
Downstream analysis was restricted independently to the 120-month window derived
from `bars_1min`'s own `trade_date` calendar: **2,468 dates, 2016-10-04 →
2026-09-18, exactly 120 distinct months** — verified, not assumed.

Against Task 1's published table: **0 mismatches across all 120 months.** All 29
published sub-200-eligible months match exactly on
`(n_eligible, n_leaders, n_followers)`; the remaining 91 are exactly
`200 / 40 / 160`, matching the published "91 of 120 months (76%)"; the worst
month reproduces exactly (**2025-01 → 181 / 37 / 144**). Leader tier sizes:
40 (105 months), 39 (6), 38 (7), 37 (2) — min 37, median 40, max 40. Leader and
follower rosters are disjoint within every month (asserted: 0 overlaps).

### Reconciliation 3 — category sum (detail)

Verified for all 10 `(θ, horizon)` cells including the pooled row; see the two
tables in Section 7.1. Worked example, θ=70%, h=60:
`68 + 0 + 23 + 142 + 9,639 = 9,872` ✓. There is no residual category and no
unattributed observation.

### Reconciliation 4 — strict AND (detail)

Computed as a data check in both directions, at both thresholds, over all
153,016 observations: `Lok & Fok & ¬retained = 0` and
`retained & ¬(Lok & Fok) = 0`. See Section 6.2. This is a **measured
correctness result, not an assumption**.

---

## 10. Limitations, assumptions and ambiguities

### 10.1 This is a reproduction, not an independent reimplementation

Reconciliation 1 was computed by re-running the **same** implementation approach
as the prior measurement — the load-bearing SQL predicates in Section 3.4 were
reused verbatim from `DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` §10.7 and
the prior task's scratchpad scripts, extended to carry a second tier. The check
therefore establishes **exact reproducibility** of the published figures from
the same rules and data; it does **not** constitute an independent
reimplementation that would catch a shared logic error present in both runs.
Stated so the strength of the check is not overread.

### 10.2 Section 12's day-level clause is a drafting defect (ambiguity, flagged)

As quoted in Section 2.1, `PREREGISTRATION_LEAD_LAG_V1.md:517-518` reads
"whole-day exclusion if **<50%** of that month's leader tier **lacks** a valid
bar", which is logically inverted and, taken literally, would exclude nearly
every trading day. It is irreconcilable with Section 23's own entry at `:988`
("`>=50%` of tier has a valid bar"). **The Section 23 reading was implemented**
as the only one under which the document is self-consistent. This is reported
here as an ambiguity requiring a human-owned textual correction in the
preregistration; it was **not** corrected, amended or re-litigated by this
measurement. No count in this document depends on the resolution (the
alternative literal reading is not implementable as a coherent rule).

### 10.3 "Has a valid bar that day" is not defined; two readings measured

The day-level clause does not say what "has a valid bar" means. Both defensible
readings were implemented (Section 3.3): the **primary** gated reading (the
leader entity-day survives Section 12's own `<90%`-completeness and CA-window
exclusions) and a **looser** reading (`>=1` present-valid regular-session bar,
gates ignored). They reclassify 496 observations between exclusion categories 1
and 2 but produce the **identical retained set** (Section 6.3). No preference
between them is established here.

### 10.4 Which minute the per-minute floor applies to — resolved, with a sensitivity

Section 2.2 gives the textual and evidential basis for applying the floor at the
signal-completion minute `t` only. The alternative (all five minutes `t-4…t`) is
reported as a sensitivity and differs by 2 observations in the leader-side
exclusion union and **0** in the retained set. Note that the preregistration
specifies no per-entity requirement that a leader have valid bars at *all* of
`t-4…t` for its `S_i(t)` to be computable — only the aggregate `n_t` floor. That
gap is a genuine gap in the written rules; **no per-entity window-completeness
rule was invented** to fill it, and the consequence is that `n_t` as implemented
counts leaders valid at `t` without asserting their full 5-minute window is
complete.

### 10.5 Leader-side forward check: absent by design, confirmed

There is no leader-side forward-endpoint check in this measurement, because
leaders never appear on the forward/outcome side of this family's estimand (the
`t+h` endpoint is a follower-portfolio quantity only). This matches Decision 19
as written and was not an omission.

### 10.6 Inherited limitations, unchanged by this task

- **Decision 11's exact anchor remains genuinely unresolved.**
  `LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md:973-986` names two
  candidates (`09:20` if `09:15` is a valid regular-session bar, else `09:21`).
  The `09:20` branch was used as briefed; the targeted per-day `MIN(ts)` check
  was not performed. If the `09:21` branch is confirmed, slot counts (33/16/9/4)
  are unaffected but every target minute shifts and all counts here would need
  re-running. A dependency, stated — not a re-derivation.
- **The corporate-action window's portfolio-level meaning is ambiguous
  (Decision 20 OPEN).** The single-entity `+/-1`-trading-day rule was applied at
  the entity-day level to both tiers, as originally written; no portfolio-level
  CA rule was invented. Effect on the leader tier: 98 of 98,184 entity-days
  (0.10%). Ten ex-dates fall on non-trading days; for those the window was taken
  as the two trading days bracketing the ex-date.
- **The `09:14` boundary interacts with one jittered entity** (`INE628A01036`,
  408,297 jittered rows, 2016-10 → 2021-03), whose 09:15 bar buckets to `09:14`
  and is therefore outside the regular session. Reported, not corrected —
  correcting it would require a jitter-tolerant session-boundary rule no
  approved document contains.
- **Seven of the zero-retained dates have unverified causes** (short, partial or
  interrupted regular sessions). Decision 21 remains open; this measurement
  neither resolves it nor depends on its resolution.
- **Decision 12 (bootstrap block length, run length, series, switch-over) is
  open.** No count in this document is a count of **independent** observations,
  and none should be read as one.
- **Section 17's power calculation cannot be completed** from this measurement;
  the missing preregistered inputs are those named in
  `DECISION_10_BREADTH_FEASIBILITY_MEASUREMENT.md` §9.
- **Approval-status conflict**, per Section 1: the decisions applied here as
  approved are still recorded OPEN in the project's own decision table.

### 10.7 One new observation worth a separate look

The `t = 15:19` collapse across **both** tiers for every trading date from
2026-08-03 to 2026-09-18 (Section 7.4) is a data-quality signal about the final
weeks of the intraday archive, not a market phenomenon. It is non-binding at
θ=70% and θ=75% only because the follower breadth rule independently excludes
the same 34 observations. Reported as observed; cause not investigated, no rule
added.

### 10.8 Determinism and read-only confirmation

No RNG, no sampling, no seed, no iteration-order dependence; re-running the four
scripts reproduces every figure exactly. Both DuckDB files were opened
read-only throughout (`duckdb.connect(..., read_only=True)` and
`ATTACH … (READ_ONLY)`); all intermediates were written to the session
scratchpad. **This Markdown file is the only file created or modified in the
repository.** `git status --short` and `git diff --stat` were captured before
and after the measurement and show no change to any tracked or previously
untracked file, including `PREREGISTRATION_LEAD_LAG_V1.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`, every Decision 17/19
document, `lead_lag/trial_ledger.json` and `PROJECT_CONTEXT.md`. No commit was
made. No trial was registered or backdated.

---

## 11. Conclusion and explicit scope statement

Over 153,016 scheduled observations across 4 horizons, 2,468 trading dates and
120 monthly rosters (leader tier 37–40 names, follower tier 144–160 names),
combining the already-approved leader-side eligibility rules (Section 12's
whole-day `>=50%` leader-breadth floor and Section 8's per-minute
`n_t >= 0.80 * NL` floor) with the already-approved 70% follower-breadth
threshold and the Decision-19 forward-endpoint check:

- **149,642 observations are retained (97.795%)** — 79,662 / 38,633 / 21,708 /
  9,639 for h = 5 / 15 / 30 / 60.
- Coverage spans **2,446 of 2,468 trading dates, all 120 months, all 11 years**,
  2016-10-04 → 2026-09-18, with no gap larger than one trading date anywhere.
- **2016 and 2017 remain fully represented**: 60 of 61 and 241 of 248 trading
  dates retained, 3,589 and 14,492 observations, 229 and 931 at the primary
  h=60 horizon.
- **The leader-side rules are non-binding at this threshold.** They exclude
  1,089 observations, every one of which the follower side already excludes;
  "excluded only by leader-side" is **0** at every horizon, and retained is
  identical to the follower-only figure to the observation.
- The 70% vs 75% margin is **4,926 observations and 80 distinct dates**, of
  which **99.82% and 100%** respectively fall in 2016–2017.
- All four reconciliation checks **PASS**.

**Explicit scope statement.** This measurement establishes **sample availability
and temporal coverage ONLY**. It does **not** establish that the retained sample
is unbiased, representative, statistically independent, adequately powered, or
predictive of anything. It computes no price, return, forward label, signal
value, correlation, coefficient or P&L statistic, and it makes **no primary-gate
eligibility determination**. It freezes, amends and approves nothing: the
preregistration, the methodology proposal, every Decision record and the trial
ledger are unchanged, and no trial has been registered. Any decision about
whether this retained sample is adequate for the study remains open and
human-owned.
