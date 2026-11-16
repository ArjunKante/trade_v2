# Post-earnings-drift: Phase 0 (feasibility and power only)

**This is NOT a preregistration and NOT a study.** No relationship between
announcement return and forward return is computed anywhere in this
document. That computation is the study itself, and per this project's own
rule (`PROJECT_CONTEXT.md` Section 3, "Pre-registration"), it needs a frozen,
committed preregistration before any such number exists. This document is
counting and power arithmetic only, on the unsealed portion of the data, to
decide whether a preregistration is even worth writing.

---

## 0. Sealed-window declaration (committed before anything else below)

**Earnings events with `known_date`/`broadcast_ts` on or after 2025-07-01
are SEALED for the post-earnings-drift hypothesis family, effective this
commit.**

Declared now, in its own commit, before any backfill script runs and before
any of the Phase 0 analyses below are computed — following this project's
own standing discipline (`PROJECT_CONTEXT.md` Section 3, "Sealed windows":
read once, after DEV passes and the human approves; declared before touched,
not after).

**Honest statement of contamination — partial, not zero:**

The *price* data for 2025-07-01 onward is not unknown. Daily and intraday
bars for this period were already loaded and used in the momentum holdout
evaluation (`FINDINGS.md` Section 7) and in the live Fibo/momentum forward
systems. Market conditions in this window — levels, volatility, the general
shape of the tape — have been seen, repeatedly, by other work in this
project.

What has genuinely never been loaded or examined, by any script, study, or
person, in this project, is the **earnings-event data itself**: which
companies filed on which dates, the `broadcast_ts`/`known_date` timestamps,
the financial content of those filings, or anything derived from joining
those events to subsequent price action. `fundamentals_filings` and
`fundamentals_xbrl_facts` rows with `known_date >= 2025-07-01` have not been
queried, joined, or aggregated anywhere before this document.

So: the environment the events sit in is known; the events themselves are
not. That is a weaker seal than the original historical holdout had (which
sealed both price and event data together), and this document says so
plainly rather than claiming an unseen window where only a partial one
exists.

**This is the only unseen data available to this hypothesis family, and it
stops being claimable as unseen the moment the fundamentals backfill is next
run and it pulls in rows past this date, or the moment any script queries
`fundamentals_filings`/`fundamentals_xbrl_facts` with `known_date >=
2025-07-01`.** Everything in this document (Sections 1-5 below) is computed
only against `known_date < 2025-07-01` (equivalently, the window 2016-01
through 2025-06), using data already resident in `data/warehouse.duckdb` as
of this commit. No backfill is run as part of this document.

Recorded in `data/holdout_access_log.txt` alongside the retired windows
(see entry timestamped at this commit).

---

## 1-5. Feasibility and power analyses (2016-01 through 2025-06 only)

Computed by `scripts/earnings_drift_phase0.py`, read-only, no backfill run.
All numbers below restrict to `known_date < 2025-07-01` (137,110 of the
137,228 total events ever loaded — 118 fall on/after the seal and are
excluded from every count in this section).

### 1. Join attrition

Of 137,110 events in the unsealed window:

| Stage | Count | % of 137,110 |
|---|---:|---:|
| No `isin_lineage` match at all | 1,097 | 0.8% |
| Matched, but nearest trade date >10 calendar days from announcement | 11,069 | 8.1% |
| Matched, but incomplete 60-trading-day forward window (panel ends 2025-03-18) | 4,368 | 3.2% |
| Matched, but no price row on/after the announcement at all | 3,855 | 2.8% |
| Matched, but gap before the event row >10 calendar days | 797 | 0.6% |
| Matched, but entity has no price rows at all | 55 | 0.0% |
| Matched, but entity history starts at/after the event | 52 | 0.0% |
| **Survives (complete 3-day-ish event window AND complete 60-day forward window)** | **115,817** | **84.5%** |

**A finding not asked for by name but structurally unavoidable here:**
`entity_prices_daily` — the point-in-time, split-adjusted panel this
project's backtests actually use — ends **2025-03-18**, not 2025-06-30.
That date is independently known in this repo as "the sealed-holdout
boundary" (comment in `scripts/run_survivorship_quantification.py`). It is
*not* the earnings seal declared in Section 0 above — it is simply how far
the adjusted price panel has been built — but it means the practically
complete-forward-window portion of the "unsealed" 2016-01–2025-06 range is,
under the data as it sits today, closer to 2016-01–2024-12-ish (60 trading
days ≈ 3 months short of 2025-03-18). The "incomplete forward window" row
above (4,368 events, 3.2%) is this effect, counted directly rather than
estimated. No backfill was run to extend the panel, consistent with
Section 0's "no new ingestion" instruction — extending it is a separate,
later decision, not part of this feasibility check.

Event-window definition used (stated plainly, provisional — see Section 3
below for why): day 0 = the first trading day on/after the calendar date of
`known_date`, admitting a match only within 10 calendar days (to catch
long trading halts/delistings rather than silently keeping them). This
ignores `broadcast_ts` time-of-day; Section 3 exists precisely to check
whether that is defensible before any real preregistration bakes it in.

### 2. The 1,097 unmatched rows — systematic, not random

| | Unmatched (1,097 rows / 59 ISINs) | Matched (136,013 rows / 2,441 ISINs) |
|---|---:|---:|
| Median daily turnover (₹, last-observed) | 11,552 | 10,280,101 |
| Median last close (price level — **not market cap**, see note) | ₹3.36 | ₹193.69 |
| % still trading within 90 cal. days of the raw price panel's own end (2026-11-05) | 10.2% | 71.6% |

**This is a survivorship-flavoured gap, stated before any result exists.**
The 59 unmatched ISINs are penny-priced (median ₹3.36 vs ₹193.69), roughly
900x less liquid by turnover, and nearly 90% of them are no longer trading
at all as of the most recent raw price data — versus under 30% attrition
for the matched universe. Dropping these 1,097 rows silently would bias any
later study toward survivors.

**Market cap note**: no warehouse-resident market-cap field exists.
Reconstructing one requires live-scraping individual XBRL filings for
paid-up share capital (`scripts/sample_shares_outstanding_coverage_v2.py` —
a network crawl, not a warehouse query), which is out of scope for a
feasibility/counting check. Price level is substituted above as a labelled,
weaker proxy rather than silently computing a misleading market-cap number.

### 3. Announcement timing distribution

Of 137,110 events (all have a non-null `broadcast_ts`):

| Window | Count | % |
|---|---:|---:|
| Before 09:15 (pre-market) | 1,873 | 1.4% |
| 09:15–15:30 (market hours) | 53,032 | 38.7% |
| After 15:30 (post-market) | 82,205 | 60.0% |

60% of announcements land after market close — day 0's natural definition
for the *majority* of events is "the next trading day," not the
announcement's own calendar date. But 38.7% land *during* market hours,
where same-day price action could already reflect the news before the
close — for those, "day 0 = next trading day" (used provisionally in
Section 1 above) would miss the first, and often largest, reaction. Any
real preregistration needs a day-0 rule that branches on this, not one
rule applied uniformly. Stated here, not fixed here — fixing it is part of
the study design, not this feasibility check.

### 4. Clustering — the item that matters most

| Year | Distinct dates | Events | Top-20-day share |
|---|---:|---:|---:|
| 2016 | 198 | 12,420 | 43.6% |
| 2017 | 190 | 14,625 | 43.8% |
| 2018 | 166 | 15,268 | 52.5% |
| 2019 | 228 | 12,947 | 41.9% |
| 2020 | 296 | 14,169 | 35.1% |
| 2021 | 276 | 14,446 | 39.6% |
| 2022 | 252 | 14,925 | 46.7% |
| 2023 | 246 | 16,491 | 44.1% |
| 2024 | 283 | 17,887 | 42.2% |
| 2025 (partial, through June) | 83 | 3,932 | 84.4% |

35–53% of each year's events land on just 20 days (results-season peaks).
Across the full 2016-01-08 to 2025-06-17 window:

- **Day-clusters**: 2,218 distinct announcement dates.
- **Quarter-clusters**: 38 distinct quarters.

These are the two candidate effective sample sizes for inference, not
137,110 (the event count) and not 2,441 (the entity count) — because
within a results-season day, and even more so within a quarter, events are
not independent draws; they share market-wide and sector-wide shocks.

### 5. MDE, computed both ways

**Quarter-clustered MDE (182.5%, or 30.8% on an outlier-robust sigma —
either way) vastly exceeds any plausible drift effect. The idea stops at
this step, the same way portfolio construction did (`PROJECT_CONTEXT.md`
Section 3, "Feasibility and power checks first").**

Cross-sectional SD of the 60-trading-day forward return, survivors only
(n=115,817; mean 7.24% — **not used for sizing**, variance only, per
`FINDINGS.md` Section 12's own discipline):

- Raw SD: **117.2%**. Driven heavily by a small number of extreme-tail
  returns (max observed: +18,939%, on 4 rows belonging to one entity — a
  corporate-action-scale artifact, not representative; min: -97.9%, genuine
  near-total losses). Median is only 1.8%; IQR is -9.9% to +16.8%.
- Outlier-robust SD (IQR/1.349, a standard normal-equivalent estimator):
  **19.8%**.

MDE (two-sample, top-decile-vs-rest, t-distribution, 80% power, α=0.05
two-sided, decile/rest split applied to the *effective cluster count*, not
the event count):

| Clustering | Effective n (clusters) | df | MDE (raw σ=117.2%) | MDE (robust σ=19.8%) |
|---|---:|---:|---:|---:|
| Day | 2,218 | 2,216 | 23.3% | 3.9% |
| Quarter | 38 | 36 | 182.5% | 30.8% |

Round-trip cost band for comparison: **0.20%–0.30%**.

**Which is honest**: quarter-clustering. Announcement dates cluster into
results seasons that repeat each quarter; the day-level count (2,218)
overstates independence the same way counting every trading day in a
single earnings season as a separate "cluster" would. Treating 2,218 days
as independent when 35–53% of each year's events fall on 20 of them is the
same mistake the project has already paid for once (day-clustered vs
quarter-clustered bootstrap CIs, `PROJECT_CONTEXT.md` Section 3, "Gates").

**Under the honest (quarter) clustering, the MDE is 30.8%–182.5% of
return, against a cost band of 0.2%–0.3% — roughly 100x to 900x too large
for any plausible drift effect to be detectable.** Even under the
optimistic, almost-certainly-wrong day-clustered assumption, the MDE
(3.9%–23.3%) still exceeds the cost band by 13x to 78x. The conclusion does
not depend on which sigma or which clustering is used. **This idea does not
clear even a generous feasibility bar. No preregistration should be
written for it as specified.**

---

## Separately: PROJECT_CONTEXT.md's stale balance-sheet-coverage claim

`PROJECT_CONTEXT.md` stated balance-sheet data "only reaches FY2022-23."
Directly counted: `fundamentals_xbrl_facts` rows with
`source = 'NSE_XBRL_ANNUAL_BALANCE_SHEET'` reach `period_end = 2024-12-31`
(2,646,909 rows, 2,260 distinct ISIN). Corrected in that commit, swept
across the repo for the same stale claim — see that commit's message for
the specific sites found and fixed.

---

## Correction to Section 5's MDE (appended, Section 5 above left unedited)

**The original Section 5 computation measured the wrong quantity.** It
computed the cross-sectional standard deviation of the 60-day forward
return *level* and fed that into a two-sample MDE formula. The study this
family would eventually run tests a *difference* — top decile minus the
rest, within the same quarter. A market-wide shock inflates quarter-level
variance on a level; it mostly **cancels** in a within-quarter difference,
because both legs of the spread sit in the same quarter and share that
shock. Computing the level's variance when the test statistic is a spread
overstates the effective dispersion, and therefore overstates the MDE, by
construction — independent of what the actual numbers come out to.

**This was identifiable before the result existed, not after.**
`PROJECT_CONTEXT.md`'s own standing finding #3 reads, verbatim: *"Variance
of the difference, not effect size, is the binding constraint."* → *"compute
MDE before finalising any comparison study."* That finding already names
the exact failure mode — using the wrong variance in an MDE calculation —
as a recurring, previously-paid-for mistake (momentum+fundamentals needed
8–72 years; portfolio construction needed 10–20x). The original Section 5
computed a *level's* variance for a study whose binding statistic is a
*difference*. Checking the computation against finding #3's own title
would have caught this without running anything.

### The corrected computation

Per the pre-committed procedure: decile membership assigned **at random**
(never from the real announcement return — this measures the null, not
drift), the top-decile-minus-rest mean 60-day-return spread computed
within each quarter, the cross-quarter standard deviation of that spread
used as `sigma_period` in this project's own existing one-sample MDE
machinery (`src/portfolio/power.py::minimum_detectable_difference`, which
every prior power calc in this project already uses), repeated over 200
random assignments, raw and winsorized (clip at the 1st/99th percentile:
[-48.9%, +108.8%]). Script: `scripts/earnings_drift_phase0_mde_correction.py`.

Of the 115,817 survivors (unchanged from Section 1), 36 distinct quarters
have at least one surviving event (not 38 — two of the 38 calendar
quarters in the filings-only count have zero events that clear the
join), so `n=36`, `df=35`. ~322 events per quarter fall in the random
"top decile."

| | SD of quarterly null spread | MDE (80% power, quarter-clustered, df=35) |
|---|---|---|
| **Raw** | mean 3.71%, range 2.20%–15.11% across 200 draws (std-across-draws 1.54pp) | mean 1.78%, range 1.06%–7.26% |
| **Winsorized** | mean 1.39%, range 0.92%–1.93% across 200 draws (std-across-draws 0.18pp) | mean 0.67%, range 0.44%–0.93% |

**Which I would use, and why: winsorized.** Two reasons, not one:

1. **Stability.** The raw estimate swings 7x in MDE terms (1.06%–7.26%)
   depending on which draw happened to place a handful of extreme events
   in the random "top decile" versus "the rest" for a given quarter. A
   number that moves 7x based on the luck of a random split is not a
   number a go/no-go decision can be hung on, independent of which value
   in that range looks more convenient.
2. **Substantive, not just statistical.** Section 5's own original run
   already found the 60-day level distribution dominated by a handful of
   corporate-action-scale return artifacts (max observed: +18,939%, on 4
   rows belonging to a single entity — not a return any real strategy
   would hold into, and very likely a data artifact rather than genuine
   price action). Every surviving strategy in this project is built on
   bounded position sizing; winsorizing approximates what a real,
   risk-limited implementation would actually realize far better than the
   raw tail does.

### Verdict

**Plausible PEAD effect band: 1%–3% over 60 days. Round-trip cost band:
0.2%–0.3%.**

The winsorized MDE (mean 0.67%, range 0.44%–0.93%) sits **below the
entire plausible PEAD effect band**, not above it. The raw MDE (mean
1.78%, range 1.06%–7.26%) straddles the band depending on the draw, which
is itself the reason not to use it (above).

Under the methodology I would actually trust (winsorized), **this is not
"exceeds plausible effects"** (the Section 5 verdict, now retracted as
resting on the wrong variance) **and it is not "marginal, near the top of
the plausible range" either** — both of the user's own pre-stated closing
conditions. A PEAD-sized effect, if one exists, would be statistically
detectable at 80% power from the data already in hand. This does not mean
the effect exists, and it does not mean the idea is validated: it means
Phase 0's power objection to this family is **lifted**, which is the
opposite of what the uncorrected Section 5 concluded. Phase 0's own scope
limit still applies unchanged — this does not authorize running the study,
computing announcement-return-vs-forward-return, or writing anything
beyond a preregistration. If one is written, it still needs its own
power section, its own decision rule, and its own accounting for the
instability documented above (the raw/winsorized gap is itself a design
question that preregistration would have to resolve before any read,
not after).

**Trial count**: counted as **one trial** for the post-earnings-drift
family, per explicit user instruction, regardless of outcome — Section 5's
original (wrong-variance) computation and this correction are one Phase 0
feasibility episode, not two, since the correction was "one corrected
computation, not a search" rather than a second attempt at a different
configuration.

---

## Investigation: the +18,939% outlier, before relying on winsorization

Full bug writeup: `BUGS.md` Bug #26. Numbers recorded here per
instruction.

**The one row.** Entity `INE234I01010` (KAUSHALYA Infrastructure
Development Corp.), 4 filings broadcast 2023-05-30 -- Q4 Consolidated,
Q4 Non-Consolidated, Annual Consolidated, Annual Non-Consolidated.
**Genuinely distinct filings** (checked `period_end`, `reporting_quarter`,
`consolidated`, `seq_number`: 1150739-1150742, four different documents),
not a pipeline duplicate -- Indian companies routinely co-file all four
variants at FY-end; this project's event construction does not currently
deduplicate by announcement day, so this one day gets 4 votes instead
of 1 (noted, not fixed here). `t0` = 2023-05-30 (close ₹4.00), `tf` =
2024-04-30 (close ₹761.55) -- the 189.4x move (+18,939%).

**Root cause, traced, not assumed.** `prices_eod` has zero rows for
this ISIN between 2024-01-12 and 2024-05-10 -- the real feed went dark.
`entity_prices_daily` is nonetheless densely populated across exactly
that gap, because `isin_lineage` maps a second ISIN (`INE234I01028`,
transition `known_date` 2024-03-04) to the same `entity_id`, and the
materialize join stitches both ISINs' price series into one continuous
entity. `corporate_actions` has zero rows for either ISIN across the
transition; `adjustment_factors.factor` is 1.0 throughout (no correction
applied). `lineage_jump_guard.find_unexplained_jumps()` (Bug #1's own
detector) already flags this exact transition: `boundary_ratio=89.83`,
`has_nearby_ca_record=False` -- an ~90x unexplained jump, almost
certainly an uncaptured corporate restructuring or ISIN-reissue with a
share-count change.

**Class size: 51 of 115,817 survivors exceed a 500% 60-day return** (25
distinct entity/announcement-day pairs). **50 of 51 are flagged by an
existing jump guard** (`lineage_jump_guard` or the full `same_isin_
jump_guard` output, either one, any `gap_days`) -- a real, already-
instrumented class, not noise. The one unflagged row (`INE294G01026`/
ROML, +996%, 2020-11 to 2021-05) has no single-day ratio above 1.05
anywhere in its window -- checked directly, a genuine gradual COVID-era
microcap rally.

**Blast radius, measured, both directions.** Of the 115,817 survivors,
**1,519 (1.3%) have a 60-day window containing an unexplained jump**
under either guard: 18 events / 8 entities via `lineage_jump_guard`,
1,501 events / 476 entities via the full `same_isin_jump_guard` output
(the 78/82-entity canonical pin, `gap_days<=5`, catches almost none of
these -- KAUSHALYA's own flagged same-isin-adjacent jumps have
`gap_days` 61-146, all above that cutoff). Checked whether this
threatens the already-committed MDE above: of the 1,519 contaminated
events, 603 (40%) are already removed as a side effect of the frozen
within-quarter 1st/99th-percentile winsorization rule; **916 (60%) are
not** -- their net 60-day return is modest enough to pass through
winsorization untouched while still containing an unrelated price
discontinuity. Winsorization is not a substitute for excluding these.

**Winsorization is unchanged, per instruction** -- this investigation is
about knowing what it covers, not about changing it. The fix is a new
universe-construction exclusion, added to `PREREGISTRATION_EARNINGS_
DRIFT.md` as Amendment 2 before DEV runs: drop any event whose window
contains an unexplained jump under either guard, in addition to the
existing 78-entity pin.

---

## Hand-trace: five events, by hand, against raw data, before any aggregate

All five checked against the real NSE trading calendar (`index_eod`),
not `entity_prices_daily`'s own calendar (truncated at 2025-03-18, which
would misclassify real trading days near the end of DEV as holidays).

**1. Pre-15:30 announcement.** `INE614B01018`, known_date 2017-01-24,
broadcast 12:04:39. Day 0 = 2017-01-24 (the announcement's own session,
since before 15:30). Day 0+1 = 2017-01-25. Day 0+2 = 2017-01-27 --
correctly skips 2017-01-26 (Republic Day, an NSE holiday), not
misread as the next calendar day. Entry = 2017-01-30 (gap from day 0+2:
3 calendar days, an ordinary weekend). Exit (60 trading days later) =
2017-04-28. `p_entry`=₹105.82, `p_exit`=₹148.86, return = **+40.7%**.

**2. Post-15:30 announcement.** `INE628A01036`, known_date 2017-01-27,
broadcast 17:30:08. Day 0 = 2017-01-30 (the NEXT trading day, not the
announcement date, since broadcast after 15:30). Day 0+1 = 2017-01-31.
Day 0+2 = 2017-02-01. Entry = 2017-02-02 (1-day gap). Exit = 2017-05-04.
`p_entry`=₹493.40, `p_exit`=₹540.93, return = **+9.6%**.

**3. Non-trading-day announcement.** `INE617A01013`, known_date
2017-02-11 (a Saturday), broadcast 20:19:16. Day 0 = 2017-02-13 (the
next trading day -- the non-trading-day branch fires regardless of the
broadcast time-of-day on a Saturday). Day 0+1 = 2017-02-14. Day 0+2 =
2017-02-15. Entry = 2017-02-16 (1-day gap). Exit = 2017-05-18.
`p_entry`=₹810.70, `p_exit`=₹906.20, return = **+11.8%**.

**4. Entry lands after a holiday.** `INE858F01012`, known_date
2017-02-21, broadcast 15:29:17 (43 seconds before the 15:30 cutoff --
day 0 = the announcement's own session). Day 0+1 = 2017-02-22. Day 0+2
= 2017-02-23. The next calendar day, 2017-02-24 (Maha Shivaratri), is
NOT a trading day; entry correctly skips to 2017-02-27 -- a 4-calendar-
day gap, distinguishable from the 1-3 day gap a plain weekend would
produce, confirming the holiday is actually being skipped rather than
assumed away. Exit = 2017-05-26. `p_entry`=₹57.80, `p_exit`=₹64.60,
return = **+11.8%**.

**5. One of the 1,097 excluded rows.** `INE220001015` (Nova Iron & Steel
Ltd, symbol NOVAIRNSTL). Confirmed directly: **zero** `isin_lineage`
rows exist for this ISIN -- the exclusion fires at the join step, before
any ranking or return computation; this event never reaches the
universe. 59 distinct ISINs behind the full 1,097-row exclusion
(multiple filings per excluded ISIN); this is one of them, traced by
hand to confirm the mechanism, not merely asserted from the earlier
count.

