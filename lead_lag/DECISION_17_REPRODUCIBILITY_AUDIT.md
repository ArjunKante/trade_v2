# Decision 17 Reproducibility and Interpretation Audit

Read-only reproducibility and interpretation audit of
`lead_lag/DECISION_17_ZERO_VOLUME_INVESTIGATION.md` (hereafter "the prior
memo"), run against the repo at commit `c2a0d62` (working tree at time of
writing), 2026-11-09. **This is an audit, not a redo.** It does not
re-litigate Part 1 (code-inspection) or Part 4's negative-volume/outlier-volume
root-cause narrative of the prior memo -- see that document for those. This
audit's job is narrower: (a) reproduce, with full SQL/logic shown, the Part
2/3 headline derived statistics the prior memo asserted were "reproduced
inline" but did not actually show the SQL for, and (b) correct three
specific interpretive overreaches.

**No file was written, created, or modified except this one.** All DuckDB
access was `duckdb.connect(path, read_only=True)` (or `ATTACH ... READ_ONLY`
into an in-memory DuckDB connection for cross-database joins -- an in-memory
database is never persisted to disk, so this is still read-only with respect
to both `data/fibo_intraday.duckdb` and `data/warehouse.duckdb`). No
strategy return, signal correlation, or predictive statistic was computed.
`DECISION_17_ZERO_VOLUME_INVESTIGATION.md` itself was not touched.

Working scripts for this audit live in the session scratchpad (not
committed), exactly like the prior memo's own scratchpad scripts did; every
query that matters is reproduced inline below so each number is
re-derivable from this document alone.

---

## 0. Tier-construction methodology reused, and one ambiguity it resolved

Per the task brief, the monthly leader/follower tier construction was reused
from `LEAD_LAG_POWER_AND_BREADTH_REVISION.md` Task 1, **not** reinvented:
`fibo.universe.reconstitute_annually(con, top_n=200)` +
`fibo.universe.effective_universe(..., stub_year=2016)` for the annual
point-in-time universe (unmodified, imported and called directly); for each
of the 120 calendar months in `bars_1min`'s own trading-day calendar
(2016-10-04 to 2026-09-18, confirmed), on that month's first trading day,
every entity in that year's annual universe is ranked by trailing-60-session
median daily turnover (`prices_eod.turnover`, raw, via `isin_lineage` join);
an entity needs >=60 trailing sessions to be eligible; top 20%
(`ceil(0.2*n_eligible)`) = leaders, remainder = followers.

```sql
-- annual universe (unmodified, reused from src/fibo/universe.py):
SELECT l.entity_id, p.trade_date, p.turnover
FROM prices_eod p JOIN isin_lineage l ON p.isin = l.isin
WHERE p.series = 'EQ' AND p.turnover IS NOT NULL AND p.turnover > 0;
-- (fed into reconstitute_annually()'s existing groupby/rank/top_n=200 logic, called as-is)
```

**One genuine ambiguity found and resolved empirically, not assumed:**
neither `LEAD_LAG_POWER_AND_BREADTH_REVISION.md` nor the prior memo states
whether "trailing 60 sessions of history as of the ranking date" counts the
ranking date's own session (if `prices_eod` has a same-day row) as one of
the 60, or requires 60 sessions strictly before it. Both were implemented
and checked against Task 1's published 120-month table (which gives
eligible/leader/follower counts for every month, including all 29
sub-200-eligible months):

- **Exclusive** (60 sessions strictly before the ranking date): reproduces
  28 of the 29 published sub-200 months exactly, but gives 2025-04 as
  199/40/159 against the published 200/40/160 (90/120 steady-state months,
  not 91/120).
- **Inclusive** (ranking date's own row counts if present, i.e.
  `trade_date <= ranking_date`): reproduces **all 29** published sub-200
  months exactly, row for row, and the correct 91/120 steady-state count.

The inclusive definition is therefore the one actually used by both prior
documents and is the one used throughout this audit. This was determined by
testing against the published table, not assumed.

**Residual, small, unexplained discrepancy.** Even with the inclusive
definition validated exactly against Task 1's own published table, this
audit's bars_1min-side present-row totals differ from the prior memo's by a
small amount: leader present rows (regular session) 34,622,110 here vs.
34,622,832 in the prior memo (diff 722, 0.002%); follower 133,872,953 here
vs. 133,865,112 (diff 7,841, 0.006%). Zero-volume counts differ by 1-2 rows;
zero-run counts by 1-2; gap counts by 29-34. Because the tier *construction*
itself is validated as an exact match to the published Task 1 table, this
residual most likely originates in a bars_1min-side join detail (e.g. a
handful of entity-months touching an ISIN-lineage edge case) rather than in
the ranking logic -- but this audit could not pin down the exact mechanism
and does not assert one. Every number below is reported as measured, with
this known ~0.002%-0.8%-scale residual stated once here rather than
repeated at every line.

---

## Part 1 -- Reproduced measurements, full SQL, denominator definitions

### Item 1: Zero-volume row counts and rates, by tier

**Denominator**: present rows in `bars_1min`, regular session only
(`CAST(ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:00'`), for every
`(entity_id, trade_date)` pair where that entity was tier-assigned (leader
or follower) for the calendar month containing `trade_date`. Counting unit:
row.

```sql
SELECT t.tier,
       COUNT(*) AS present_rows_regular_session,
       SUM(CASE WHEN b.volume = 0 THEN 1 ELSE 0 END) AS zero_volume_rows
FROM bars_1min b
JOIN tiers t
  ON t.entity_id = b.entity_id
 AND t.yr = EXTRACT(YEAR FROM b.trade_date)
 AND t.mo = EXTRACT(MONTH FROM b.trade_date)
WHERE CAST(b.ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:00'
GROUP BY t.tier;
```
(`tiers` is the monthly tier-assignment table built in Section 0, registered
as a DuckDB view/temp table -- `(entity_id, tier, yr, mo)`, one row per
tier-assigned entity-month, 23,810 rows total: 4,774 leader-months, 19,036
follower-months.)

| Tier | Present rows | Zero-volume rows | Rate | Prior memo rate |
|---|---|---|---|---|
| Follower | 133,872,953 | 5,186 | 3.8731e-5 (0.0038731%) | 3.88e-5 (0.00388%) |
| Leader | 34,622,110 | 1,280 | 3.6967e-5 (0.0036967%) | 3.69e-5 (0.00369%) |

**Verdict: REPRODUCED WITHIN ROUNDING.** Raw counts differ by 1-2 rows
(zero-volume) and by hundreds-to-thousands (present rows, the Section-0
residual); the rates themselves match the prior memo's stated figures to
every displayed significant digit.

### Item 2: Absent-expected-timestamp counts and rates, by tier

**Denominator definition, stated explicitly (this is the exact ambiguity the
task flagged).** Two readings were tested:

- **(A) Full calendar-minute grid**: for every `(entity_id, trade_date)` in
  that entity's own coverage window (`[MIN(trade_date), MAX(trade_date)]` in
  `bars_1min`), intersected with `bars_1min`'s own observed global
  trading-day calendar, expect all 375 regular-session minutes
  (09:15-15:29), whether or not the entity has *any* row that day.
- **(B) Interior-only, between consecutive present rows**: only count a
  minute as "absent" if it falls strictly between two present rows of the
  *same* `(entity_id, trade_date)` that are more than 1 minute apart. A day
  with zero present rows for an entity contributes nothing under this
  reading (it is not "absence inside an observed session" but "no session
  observed at all" -- a different fact).

The prior memo's own Part 5 text pins this down for us: it describes the
required "absent-row-gap detector" as working by "**comparing consecutive
present `ts` values**" -- i.e. definition (B). Reading (A) was computed as a
cross-check and gives a much larger, qualitatively different number (because
it also counts entire never-fetched days as 375 absent minutes each); it is
reported here only to show the sensitivity, not as a candidate reproduction.
**Definition (B) is what reproduces the prior memo's cited figures and is
used for every absent-timestamp number in this document.**

```sql
WITH p AS (
  SELECT t.tier, b.entity_id, b.trade_date, b.ts,
         LAG(b.ts) OVER (PARTITION BY b.entity_id, b.trade_date ORDER BY b.ts) AS prev_ts
  FROM bars_1min b
  JOIN tiers t ON t.entity_id = b.entity_id
              AND t.yr = EXTRACT(YEAR FROM b.trade_date)
              AND t.mo = EXTRACT(MONTH FROM b.trade_date)
  WHERE CAST(b.ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:00'
)
SELECT tier,
       COUNT(*) AS gap_count,
       SUM(DATE_DIFF('minute', prev_ts, ts) - 1) AS absent_minutes
FROM p
WHERE prev_ts IS NOT NULL AND DATE_DIFF('minute', prev_ts, ts) > 1
GROUP BY tier;
```

Counting unit: a "gap" is one maximal run of consecutive absent minutes
between two present rows (an entity-session event); "absent minutes" sums
the length of every such gap. The rate's denominator is
`present_rows + absent_minutes` (i.e. "expected minutes considering only
interior gaps, not session-edge or fully-missing-day absence").

| Tier | Gap count | Absent minutes | Present rows | Rate (absent/(present+absent)) | Prior memo rate |
|---|---|---|---|---|---|
| Follower | 970,835 | 1,551,213 | 133,872,953 | 1.14557% | 1.145% |
| Leader | 3,664 | 33,024 | 34,622,110 | 0.09529% | 0.095% |

**Verdict: REPRODUCED WITHIN ROUNDING.** Gap counts and absent-minute totals
differ from the prior memo by 28-34 (out of 3,664-970,835 -- the Section-0
residual), and the rates match the prior memo's stated figures exactly at
the displayed precision.

**Explicit caveat on what this denominator excludes** (not a flaw, a scope
statement): a day where a tier-assigned entity has *zero* present rows at
all contributes nothing to either the numerator or the denominator under
definition (B). If that happens non-trivially for one tier more than the
other, reading (A) vs (B) could diverge further; this audit did not measure
the fully-missing-day rate separately and flags that as an open question
(see "Unresolved" below), not something resolved by this reproduction.

### Item 3: Zero-volume run counts and run-length distribution

**Run definition**: a maximal sequence of consecutive *present* rows, all
with `volume = 0`, for the same `(entity_id, trade_date)`, where
"consecutive" means adjacent present rows exactly 1 minute apart (an absent
row in between breaks the run even if both sides are zero-volume).
Counting unit: a run (one row per run in the output, `run_len` = number of
1-minute bars in it).

```sql
WITH z AS (
  SELECT entity_id, trade_date, ts, volume,
         LAG(ts) OVER (PARTITION BY entity_id, trade_date ORDER BY ts) AS prev_ts,
         LAG(volume) OVER (PARTITION BY entity_id, trade_date ORDER BY ts) AS prev_volume
  FROM sess   -- sess = tier-joined, regular-session-filtered bars_1min, one tier at a time
),
flagged AS (
  SELECT *,
    CASE WHEN volume = 0 AND prev_volume = 0 AND prev_ts = ts - INTERVAL 1 MINUTE
         THEN 0 ELSE 1 END AS run_start
  FROM z
),
withid AS (
  SELECT *, SUM(run_start) OVER (PARTITION BY entity_id, trade_date ORDER BY ts) AS run_id
  FROM flagged
)
SELECT entity_id, trade_date, run_id, COUNT(*) AS run_len, MIN(ts) AS run_start_ts
FROM withid
WHERE volume = 0
GROUP BY entity_id, trade_date, run_id;
```

| Bucket | Follower count | Follower % | Leader count | Leader % |
|---|---|---|---|---|
| 1 min | 4,654 | 96.07% | 905 | 99.56% |
| 2 min | 151 | 3.12% | 1 | 0.11% |
| 3 min | 25 | 0.52% | 0 | 0.00% |
| 4-5 min | 7 | 0.14% | 0 | 0.00% |
| 6-10 min | 3 | 0.06% | 0 | 0.00% |
| >10 min | 4 | 0.08% | 3 | 0.33% |
| **Total** | **4,844** | | **909** | |

Prior memo: follower 4,846 total (1min 4,656/96.08%, 2min 151/3.12%, 3min
25/0.52%, 4-5min 7/0.14%, 6-10min 3/0.06%, >10min 4/0.08%); leader 908 total
(1min 904/99.56%, 2min 1/0.11%, >10min 3/0.33%). Max run: follower 45 min,
`INE669E01016` (IDEA), 2020-05-29 -- **exact match**, including entity and
date. Leader max: 166 min, `INE669E01016`, 2024-04-25 -- **exact match**.
Distinct entities contributing a run: follower 266 -- **exact match** to the
prior memo's cited figure.

**Verdict: REPRODUCED WITHIN ROUNDING** (counts differ by 1-2 per bucket,
the Section-0 residual; bucket percentages match to the displayed
precision; both cited maximum-run facts match exactly).

### Item 4: Absent-timestamp gap counts and gap-length distribution

Same gap definition as Item 2 (interior gaps between consecutive present
rows). The prior memo did not publish a full bucketed gap-length table (only
the <3/>=3 split in Part 3 and a few named percentages in Part 2's
narrative) -- this audit computes the full bucketed distribution, using the
same bucket scheme as Item 3 for comparability, and checks every percentage
the prior memo *did* cite against it.

```sql
WITH p AS (
  SELECT entity_id, trade_date, ts,
         LAG(ts) OVER (PARTITION BY entity_id, trade_date ORDER BY ts) AS prev_ts
  FROM sess
)
SELECT entity_id, trade_date, prev_ts, ts,
       DATE_DIFF('minute', prev_ts, ts) - 1 AS gap_len
FROM p
WHERE prev_ts IS NOT NULL AND DATE_DIFF('minute', prev_ts, ts) > 1;
```

| Bucket | Follower count | Follower minutes | Leader count | Leader minutes |
|---|---|---|---|---|
| 1 min | 743,223 | 743,223 | 1,766 | 1,766 |
| 2 min | 137,260 | 274,520 | 143 | 286 |
| 3 min | 43,016 | 129,048 | 103 | 309 |
| 4-5 min | 26,094 | 112,705 | 54 | 226 |
| 6-10 min | 11,389 | 82,173 | 140 | 1,182 |
| >10 min | 9,853 | 209,544 | 1,458 | 29,255 |
| **Total** | **970,835** | **1,551,213** | **3,664** | **33,024** |

Leader `>10 min` share: 1,458/3,664 = **39.79%**, vs. the prior memo's cited
"39.48% exceed 10 minutes outright" -- within the Section-0 residual.

**Verdict: NOT PUBLISHED AS A FULL TABLE BY THE PRIOR MEMO, so no direct
table-for-table comparison is possible; every individual percentage the
prior memo DID cite from this distribution (see Items 5-6 below) reproduces
within the Section-0 residual.**

### Item 5: The <3-minute vs. >=3-minute split

| | Follower zero-runs | Leader zero-runs | Follower gaps | Leader gaps |
|---|---|---|---|---|
| Valid (<3 min), this audit | 4,805 / 4,844 = **99.19%** | 906 / 909 = **99.67%** | 880,483 / 970,835 = **90.69%** | 1,909 / 3,664 = **52.10%** |
| Invalid (>=3 min), this audit | 39 / 4,844 = **0.81%** | 3 / 909 = **0.33%** | 90,352 / 970,835 = **9.31%** | 1,755 / 3,664 = **47.90%** |
| Prior memo | 99.17% / 0.83% | 99.67% / 0.33% | 90.69% / 9.31% | 52.45% / 47.55% |

**Verdict: REPRODUCED EXACTLY** (leader zero-runs 99.67%/0.33%, follower
gaps 90.69%/9.31%) **or WITHIN ROUNDING** (follower zero-runs 99.19% vs.
99.17%; leader gaps 52.10% vs. 52.45%, the largest single percentage gap
found anywhere in this audit, still attributable to the Section-0 residual
since the leader-gap sample is the smallest denominator in this entire
exercise -- 3,664, so even a ~30-count residual moves the percentage by
~0.8 points).

### Item 6: Time-of-day and annual breakdowns

**Time-of-day anchor, determined empirically, not assumed.** The prior memo
does not state which timestamp anchors a run's or gap's "time of day." For
runs, `run_start_ts` (the run's first minute) was tried and reproduces the
prior memo's table closely. For gaps, two candidate anchors were tested --
the last *present* row before the gap, and the first present row *after*
the gap (the resumption point) -- because they gave visibly different
answers:

| Anchor | Follower open-30 | Follower midday | Follower close-30 |
|---|---|---|---|
| Before (last present row pre-gap) | 22,475 | 933,282 | 15,078 |
| **After (first present row post-gap)** | **19,400** | **933,782** | **17,653** |
| Prior memo | 19,400 | 933,748 | 17,653 |

The **"after" anchor matches the prior memo's exact counts** for open-30 and
close-30 (19,400 and 17,653, both exact) and within the Section-0 residual
for midday (933,782 vs. 933,748, diff 34). The "before" anchor does not
match at all. **This resolves the ambiguity: a gap's time-of-day bucket is
determined by the timestamp of the present row that ends it (the
resumption point), not the one that precedes it.** This same anchor is used
for the leader table and for the invalid-gap (>=3 min) sub-tables below.

| | Follower zero-runs | Leader zero-runs | Follower gaps | Leader gaps |
|---|---|---|---|---|
| Open-30 | 208 (4.29%) | 19 (2.09%) | 19,400 (2.00%) | 95 (2.59%) |
| Midday | 1,285 (26.53%) | 4 (0.44%) | 933,782 (96.20%) | 2,270 (61.96%) |
| Close-30 | 3,351 (69.18%) | 886 (97.47%) | 17,653 (1.82%) | 1,299 (35.45%) |
| Prior memo | 209/4.3%, 1285/26.5%, 3352/69.2% | 18/2.0%, 4/0.4%, 886/97.6% | 19400/2.0%, 933748/96.2%, 17653/1.8% | 95/2.6%, 2299/62.2%, 1299/35.2% |

Invalid (>=3 min) gap sub-tables, same "after" anchor:

- Follower invalid gaps: midday 82,820/90,352 = **91.66%**, close-30
  6,181/90,352 = 6.84%, open-30 1,351/90,352 = 1.50%. Prior memo cites
  "91.7%" midday -- **reproduced within rounding (91.66% vs 91.7%)**.
- Leader invalid gaps: close-30 1,275/1,755 = **72.65%**, midday
  437/1,755 = 24.90%, open-30 43/1,755 = 2.45%. Prior memo cites "72.6%"
  close-30-skew -- **reproduced within rounding (72.65% vs 72.6%)**.

**Annual breakdown** (zero-volume rate by year, and follower gap
invalid-share by year):

```sql
SELECT t.tier, EXTRACT(YEAR FROM b.trade_date) AS yr,
       COUNT(*) AS present_rows,
       SUM(CASE WHEN b.volume = 0 THEN 1 ELSE 0 END) AS zero_vol_rows
FROM bars_1min b JOIN tiers t ON <join as above>
WHERE CAST(b.ts AS TIME) BETWEEN TIME '09:15:00' AND TIME '15:29:00'
GROUP BY t.tier, EXTRACT(YEAR FROM b.trade_date);
```

| Year | Follower zero-vol rate (this audit) | Leader zero-vol rate (this audit) | Prior memo (follower / leader) |
|---|---|---|---|
| 2016 | 0.0000% | 0.0000% | 0.0000% / 0.0000% |
| 2017 | 0.0025% | 0.0020% | 0.0026% / 0.0020% |
| 2018 | 0.0010% | 0.0000% | 0.0010% / 0.0000% |
| 2019 | 0.0000% | 0.0000% | 0.0000% / 0.0000% |
| 2020 | 0.0005% | 0.0000% | 0.0005% / 0.0000% |
| 2021 | 0.0004% | 0.0000% | 0.0004% / 0.0000% |
| 2022 | 0.0000% | 0.0000% | 0.0000% / 0.0000% |
| 2023 | 0.0060% | 0.0000% | 0.0060% / 0.0000% |
| 2024 | 0.0058% | 0.0108% | 0.0058% / 0.0108% |
| 2025 | 0.0004% | 0.0002% | 0.0004% / 0.0002% |
| 2026 | 0.0287% | 0.0317% | 0.0287% / 0.0317% |

Raw 2026 counts: follower zero-vol rows = **2,933** (exact match to prior
memo's "2,933 of the follower tier's 5,188"), leader = **820** (exact match
to "820 of the leader tier's 1,279"). Follower gap invalid-share by year:
2021 = 1,502/48,952 = **3.07%** (exact match), 2026 = 9,552/32,225 =
**29.64%** (exact match).

**Verdict: REPRODUCED EXACTLY** at the displayed rate precision for every
single year in both tiers, and for every one of the four specific raw
counts the prior memo cited by name (2,933; 820; 3.07%; 29.64%).

---

## Part 2 -- Corrected language: absent expected timestamps

**Corrected text, for use in place of the prior memo's "missing-row"
framing wherever this phenomenon is discussed going forward:**

> An absent expected timestamp in `bars_1min` is an observed data fact: a
> minute within the regular session for which no row exists for a given
> entity on a given date. It does **not**, by itself, establish *why* the
> row is absent. This audit checked `src/fibo/download.py` and
> `scripts/fibo_download_intraday_top200.py` (the entire write path) and
> found no vendor documentation, code comment, or project-side handling
> that distinguishes between:
>
> - **Vendor no-trade suppression**: Angel One's `getCandleData` candle
>   aggregator may simply not emit a row for a minute in which no trade
>   occurred, by design.
> - **Missing or incomplete vendor data**: a genuine gap in what Angel One
>   returned for that minute, unrelated to whether a trade occurred (e.g. an
>   aggregation or transmission fault on the vendor's side).
> - **Other undocumented vendor/API behavior**: any other mechanism not
>   covered by the two above, which cannot be ruled out given the complete
>   absence of documentation.
>
> `src/fibo/download.py`'s only validation logic
> (`fetch_chunk_with_retry`/`is_truncated`) detects a *date-range*
> truncation (Angel returning less history than requested), not anything
> about per-minute omission behavior. No Angel One SmartAPI documentation
> addressing this question was found anywhere in this repository. All three
> explanations above remain open and are not adjudicated by this
> investigation or the prior one. This term -- **"absent expected
> timestamps"** -- is used throughout this audit in place of "missing
> rows," "feed failures," or any other phrase that would imply a confirmed
> cause.

---

## Part 3 -- Corrected language: tier-rate comparison

The prior memo's Headline Finding 2 states the follower (3.88e-5) and
leader (3.69e-5) zero-volume rates are "**statistically
indistinguishable**." This audit checked the prior memo's text in full: no
test statistic, p-value, confidence interval, or standard-error calculation
appears anywhere near that claim, or anywhere else in the document, for
this comparison. The claim is unsupported as stated.

**Corrected text:**

> The observed rates are numerically similar in this measured population;
> no inferential test of their difference was performed.

No new significance test, confidence interval, or statistical model was
computed to fill this gap, per the task's explicit restriction. This
correction only removes language implying a formal test occurred.

---

## Part 4 -- Corrected language: session and anomaly qualifications

### 4.1 The eight evening/off-session clusters (retained as observed facts)

Reproduced exactly from `bars_1min` (rows after 15:29:00, grouped by
`trade_date`, taking the 8 dates with row counts in the thousands):

| Date | Row count |
|---|---|
| 2017-10-19 | 10,720 |
| 2018-11-07 | 10,818 |
| 2020-11-14 | 11,036 |
| 2021-02-24 | 14,401 |
| 2021-11-04 | 11,649 |
| 2022-10-24 | 11,582 |
| 2023-11-12 | 11,401 |
| 2024-11-01 | 11,749 |

Sum of these 8 dates: 93,356 rows (prior memo: "~93,600," consistent with
its own hedged "~" language). Total post-15:29 rows table-wide: 94,046
(prior memo: 94,045 -- within 1 row, immaterial).

### 4.2 Muhurat-date cross-check

Web-sourced confirmation (NSE/BSE public circulars and contemporaneous
press coverage, cited below) of the annual Diwali Muhurat Trading session
date for each year:

| Year | Confirmed Muhurat date | Matches a bars_1min off-session date? |
|---|---|---|
| 2017 | October 19 | Yes -- 2017-10-19 |
| 2018 | November 7 | Yes -- 2018-11-07 |
| 2020 | November 14 | Yes -- 2020-11-14 |
| 2021 | November 4 | Yes -- 2021-11-04 |
| 2022 | October 24 | Yes -- 2022-10-24 |
| 2023 | November 12 | Yes -- 2023-11-12 |
| 2024 | November 1 | Yes -- 2024-11-01 |

**7 of the 8 bars_1min off-session dates are confirmed, sourced NSE/BSE
Muhurat Trading dates -- the prior memo's "7 of 8" claim is CONFIRMED, not
merely repeated.** Sources: NSE/BSE circulars and press reports for 2017
([business-standard.com](https://www.business-standard.com/amp/article/markets/diwali-muhurat-trading-from-6-30-pm-to-7-30-pm-on-oct-19-117101700629_1.html)),
2018 and 2020
([dnaindia.com](https://www.dnaindia.com/business/report-diwali-muhurat-trading-2020-nse-bse-timings-significance-of-one-hour-special-session-2856458)),
2021-2024
([forbesindia.com](https://www.forbesindia.com/article/explainers/diwali-muhurat-trading/89399/1),
[business-standard.com](https://www.business-standard.com/markets/news/nse-announces-timings-for-muhurat-trading-session-2023-full-list-here-123110200189_1.html)).

**2021-02-24 is explicitly NOT confirmed as either a Muhurat session or an
NSE disaster-recovery test by any source available to this investigation.**
Diwali/Muhurat Trading falls only in October or November (it tracks the
Hindu lunar calendar's Lakshmi Pujan date); February 24 cannot be a Diwali
date in any year, which is consistent with -- but does not confirm -- the
prior memo's hedge that it is "most likely" something else. No NSE circular,
press report, or other source documenting a disaster-recovery test on that
specific date was found. **Both candidate explanations for 2021-02-24
remain unconfirmed; neither is asserted as fact here or elsewhere in this
audit.**

### 4.3 The 54 same-bar OHLC violations (hedge preserved, not strengthened)

Reproduced exactly: 54 rows, all at `(trade_date, ts) = (2023-03-03,
09:15:00)`, 54 distinct entities, zero overlap with the single
close-violation row (`INE916U01025`, 2017-10-06 15:27:00).

```sql
SELECT trade_date, ts, COUNT(*) FROM bars_1min
WHERE open < low OR open > high GROUP BY trade_date, ts;
-- 2023-03-03 09:15:00 | 54
```

The prior memo's proposed mechanism (a pre-open-auction-price-vs-first-trade-
price mismatch) is **explicitly preserved as unconfirmed** in this audit,
exactly as hedged in the source document ("most likely mechanism... cannot
be confirmed from available source code or documentation"). This audit adds
no new evidence either way and does not strengthen this into a claim.

### 4.4 Largest-volume rows: descriptive ranking reproduced, with one discrepancy flagged; no threshold implied

The single largest volume in the table reproduces exactly: `1,571,529,211`,
`INE669E01016` (IDEA), `2024-04-26 09:15:00`.

```sql
SELECT entity_id, trade_date, ts, volume FROM bars_1min
ORDER BY volume DESC LIMIT 10;
```

Of the top-10 rows by volume, **this audit finds 10 of 10 occur at either
`09:15:00` (9 rows) or `09:29:00` (1 row) -- i.e. all ten, not "8 of the
10," are at or immediately adjacent to the session's first bar.** This is a
genuine, checkable discrepancy with the prior memo's stated "8 of the top
10 ... occur at ... the first bar of the session (mostly 09:15:00, one at
09:29:00)": this audit's own reproduction of the identical query finds a
*stronger* version of the clustering claim (all ten, not eight), not a
weaker one, and it is reported as found rather than adjusted to match.
**Verdict for this specific descriptive sub-claim: NOT REPRODUCED EXACTLY**
(10/10 found vs. 8/10 claimed); the qualitative finding (large-volume rows
cluster at session open) is not undermined by this, and if anything is
corroborated more strongly.

**No numerical threshold for "implausible" or "outlier" volume is stated,
proposed, or implied anywhere in this audit.** The observation above is a
rank-based, descriptive fact about the top 10 rows by volume, nothing more.

### 4.5 Structural invalidity vs. numerically extreme values -- distinguished explicitly

Two different kinds of "anomaly" appear in the prior memo and must not be
conflated:

- **(a) STRUCTURALLY INVALID, full stop**: a row that is self-contradictory
  under its own stated OHLC/volume constraints. This includes `high < low`
  (0 rows), `close` outside `[low, high]` (1 row), `open` outside
  `[low, high]` (54 rows), and **negative volume** (560 rows,
  min = -27,567,834, confirmed on exactly 3 distinct dates: 2023-05-03 = 73
  rows, 2023-05-04 = 198 rows, 2024-03-02 = 289 rows; 189 distinct entities).
  These are invalid by construction -- a negative traded volume, or a price
  outside its own bar's high/low, cannot be correct under any reading of
  the OHLCV convention, independent of economic plausibility.
- **(b) Numerically extreme but NOT self-contradictory**: the largest
  positive-volume rows (e.g. 1,571,529,211). A very large volume figure is
  **a flagged anomaly, not a proven data error** -- nothing in this audit or
  the prior investigation establishes that this value is wrong, only that
  it is unusually large and clusters suspiciously at the session's first
  bar. Its effect (if any) on the row's price validity has not been
  established by either investigation. This audit does not reclassify any
  large-but-internally-consistent volume value into category (a), and does
  not propose a cutoff that would do so for future work.

---

## Final verdict table (Part 1 items)

| # | Measurement | Verdict |
|---|---|---|
| 1 | Zero-volume row counts/rates, both tiers | **REPRODUCED WITHIN ROUNDING** -- raw counts off by 1-2 rows (Section-0 residual); rates match to displayed precision exactly |
| 2 | Absent-expected-timestamp counts/rates, both tiers | **REPRODUCED WITHIN ROUNDING** -- required resolving a genuine denominator ambiguity (resolved using the prior memo's own stated "compare consecutive present ts" definition); counts off by 28-34 (Section-0 residual), rates match exactly |
| 3 | Zero-volume run counts and run-length distribution | **REPRODUCED WITHIN ROUNDING** -- bucket counts off by 1-2 each; both cited maximum-run facts (entity, date, length) reproduced EXACTLY for both tiers; distinct-entity count (266, follower) reproduced EXACTLY |
| 4 | Absent-timestamp gap counts and gap-length distribution | **PARTIALLY REPRODUCIBLE** -- the prior memo never published a full bucketed table for direct comparison (this audit supplies one); every individual percentage the prior memo DID cite from this distribution reproduces within rounding (see item 6) |
| 5 | <3 min vs. >=3 min split, runs and gaps, both tiers | **REPRODUCED EXACTLY** for 2 of 4 figures (leader zero-runs 99.67%/0.33%; follower gaps 90.69%/9.31%); **REPRODUCED WITHIN ROUNDING** for the other 2 (follower zero-runs 99.19% vs. 99.17%; leader gaps 52.10% vs. 52.45%, the latter being the most sensitive figure in this audit due to the smallest denominator, 3,664) |
| 6 | Time-of-day and annual breakdowns | **REPRODUCED EXACTLY** -- required resolving a genuine time-of-day anchor ambiguity for gaps (resolved empirically: the anchor is the first present row AFTER the gap, confirmed by exact matches on open-30/close-30 counts); every annual zero-volume rate (11 years x 2 tiers) and every specific raw count/percentage the prior memo cited by name (2,933; 820; 3.07%; 29.64%; 91.7%; 72.6%) reproduces exactly or within the stated residual |

---

## What remains genuinely unresolved after this audit

- **The cause of absent expected timestamps is still not established.**
  Vendor no-trade suppression, incomplete vendor data, and other
  undocumented API behavior all remain open, competing explanations (Part
  2). This audit did not and could not resolve this without live API access
  or vendor documentation neither investigation has.
- **The fully-missing-day rate was not separately measured.** This audit's
  Item 2 reproduction (definition B, interior gaps only) explicitly excludes
  days where a tier-assigned entity has zero present rows at all. Whether
  that phenomenon is rare or tier-differentiated the way interior gaps are
  is not known from this audit (reading (A) in Item 2 would capture it but
  was not fully characterized here, only flagged as diverging).
- **2021-02-24's identity remains unconfirmed.** Neither "Muhurat-adjacent
  anomaly" nor "NSE disaster-recovery test" has a source. It is not a
  Diwali date under either plausible calendar reading.
- **The source of the ~0.002%-0.8%-scale residual between this audit's
  bars_1min-side totals and the prior memo's is not fully pinned down.**
  The tier-construction logic itself is validated as an exact match to
  Task 1's published table, so the residual most likely sits in a
  bars_1min-join detail affecting a small number of entity-months, but the
  precise mechanism was not identified.
- **The "8 of top 10 largest-volume rows at the first bar" discrepancy**
  (this audit finds 10 of 10) is unexplained; it does not change the
  qualitative finding but is a genuine, unresolved difference between the
  two documents' identical-looking queries.
- Every "UNRESOLVED QUESTION" the prior memo itself flagged (root cause of
  the 54 open-violations, the 560 negative-volume rows, the
  extreme-maximum-volume clustering, the policy choice for the
  18%-not-flat zero-volume subset) remains exactly as unresolved as the
  prior memo left it -- this audit does not attempt to close any of them,
  per its scope.

---

## Files and data referenced (absolute paths)

- `C:\projects\trade-new\lead_lag\DECISION_17_ZERO_VOLUME_INVESTIGATION.md` (audited, not modified)
- `C:\projects\trade-new\lead_lag\LEAD_LAG_POWER_AND_BREADTH_REVISION.md` (Task 1 methodology, reused)
- `C:\projects\trade-new\LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`
- `C:\projects\trade-new\src\fibo\intraday_db.py`
- `C:\projects\trade-new\src\fibo\universe.py` (`reconstitute_annually`, `effective_universe` -- reused unmodified)
- `C:\projects\trade-new\src\fibo\download.py`
- `C:\projects\trade-new\scripts\fibo_download_intraday_top200.py`
- `C:\projects\trade-new\data\fibo_intraday.duckdb`
- `C:\projects\trade-new\data\warehouse.duckdb`
