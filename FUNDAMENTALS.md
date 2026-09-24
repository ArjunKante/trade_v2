# Fundamentals data layer: build record

Infrastructure record, not a study — nothing here spends a pre-registered
study slot. Companion to `FINDINGS.md` (the momentum studies) and `BUGS.md`
(bugs found in the price/lineage layer).

## Correction: the VSTTILLERS case was mischaracterized in Phase 1

Phase 1's report described VSTTILLERS as "a single 19-month-late filing"
(period_end 2024-12-31, "announced" 2026-07-30, 576-day gap) and used that
framing as the canonical example of announcement-lag risk. **That
characterization was wrong, found and corrected during the Phase A full
backfill, not assumed correct going forward.**

The Phase 1 finding came from a partial pull (the financial-results API's
no-date-range default, which returns a rolling snapshot of the current
reporting quarter) that happened to surface only the *restated* version of
this filing. The full date-ranged backfill shows the real sequence:

| event | date | lag from period_end |
|---|---|---|
| original filing | 2025-02-11 | 42 days (on time, inside the 45-day SEBI window) |
| restatement | 2026-07-30 | 576 days |

VSTTILLERS filed on time. It was restated 536 days later. Both are real,
independently dated announcements with their own `seq_number`. The
corrected version is a **better** fixture than the original, because it
exercises two invariants in one real case instead of one: (1) the
announcement-lag invariant (period_end must never stand in for known_date),
and (2) the restatement-visibility invariant (a point-in-time query must
return the version knowable at as_of, never a later restatement). Both are
tested directly against these exact rows in
`tests/test_fundamentals_point_in_time.py`.

**Lesson recorded, not just the corrected fact**: a "no date filter" API
default that looks like a convenient full-history shortcut can silently
return a rolling snapshot instead, and a single-pull sanity check is not
enough to characterize a filing's true history — only a genuine
date-ranged backfill exposed the original filing at all. Fetching from an
endpoint whose date-filtering behavior hasn't been independently verified
gets treated as suspect by default from here on, not assumed convenient.

## Phase A: quarterly financial results (P&L) backfill

Full report already delivered; summarized here for the permanent record.

- 108,996 rows, 2,486 distinct companies, 2016-01 through 2025-03 usable
  (see the hard ceiling below for what "usable" excludes).
- Lag distribution: median 44 days, p90 108 days, p99 466 days, max 3,060
  days (BHARATIDIL, a real multi-year catch-up filing dump). 8.06% exceed
  180 days.
- 0.000% of rows required the 45-day period_end fallback — broadCastDate
  was present on every row from this endpoint. Precisely because this path
  never executes on real data, it is now covered by a synthetic test
  (`tests/test_fundamentals_fallback.py`) rather than left untested.
- Consolidated 39,439 / Non-Consolidated 69,557 rows; 57.6% of
  company-periods file both (pick-consolidated-else-standalone logic
  built, tracked per row).
- Restatements: **5.89% of (isin, period_end, consolidated) keys have more
  than one filing** (max 4). Roughly one in seventeen company-periods would
  silently serve figures that did not exist yet at a plausible historical
  as_of date without point-in-time revision selection
  (`src/data_layer/fundamentals_pit.py`). Tested against the real
  VSTTILLERS case above, not a synthetic stand-in, and separately against
  BHARATIDIL's real catch-up-filing rows
  (`tests/test_catchup_filing_visibility.py`).
- 3.90% of companies (97 of 2,486) use a non-March fiscal year end --
  TTM computation must sum trailing quarters by each company's own
  `period_end` sequence, never assume calendar-quarter alignment.

## Hard ceiling: price+fundamentals strategies cannot be holdout-tested at all, right now

Stated in the strong form, not softened to "a gap" or "a follow-up item":

SEBI mandated NSE's "Integrated Filing-Financial" XBRL format from
**April 1, 2025**, replacing the legacy financial-results filing category
this project's fetcher reads. Confirmed against NSE's own circulars, and
independently confirmed live: monthly filing counts collapse from a normal
500-3,000 to single digits starting April 2025 (cross-checked against the
equivalent months in 2023, which show the normal pattern, ruling out a
seasonal explanation).

**The sealed price holdout begins 2025-03-19. The fundamentals coverage
gap begins 2025-04. These two boundaries are 12 days apart.**

## Phase B: balance sheet extraction

Balance-sheet fields live inside Annual-period "Financial Results" XBRL,
not a separate endpoint -- confirmed by inspecting RELIANCE's real annual
XBRL after a smaller company's filing (SEJAL GLASS) turned out to have no
balance-sheet tags at all and nearly sent this down a wrong path (a
same-named "Annual Reports" NSE endpoint that turned out to serve PDFs
only, not XBRL).

**Operational note, for the permanent record**: the extraction job (12,308
documents) was killed once by the environment mid-run, at 8,813 of 12,308
processed. Incremental per-document commits meant zero work was lost --
resumed cleanly by re-checking which `seq_number`s already existed in
`fundamentals_xbrl_facts`. See `OPERATIONS.md` for the logging-visibility
lesson this also surfaced (unflushed first line + coarse checkpoints made
early progress briefly indistinguishable from a hang).

### Result: 12,144 of 12,308 documents extracted (98.7%), 164 failed (1.3%)

All 164 failures are genuine HTTP 404s from NSE's own archive -- confirmed
by direct request, not inferred. Clustering, precisely:

| | count | % of failures |
|---|---|---|
| period_end year 2019 | 115 | 70.1% |
| period_end year 2018 | 32 | 19.5% |
| `_WEB_2`-suffixed URL (a superseded/resubmission naming pattern) | 117 | 71.3% |
| `BANKING_`-prefixed URL (bank-specific taxonomy) | 33 | 20.1% |

Reads as one real phenomenon, not several: NSE's own metadata references a
specific historical XBRL file revision (`_WEB_2`) for a cluster of
2018-2019 filings, and that specific file no longer resolves -- the
company's underlying filing likely still exists under a different revision
number, just not linkable from the metadata this project reads. Not
pursued further; 1.3% failure with a known, explained cause is not worth
chasing file-by-file.

### A third, distinct XBRL taxonomy boundary

Not the 2018 "no real XBRL at all" boundary (Phase A) and not the 2025
Integrated Filing transition (above) -- a third one, found by looking at
field coverage rather than filing counts:

| period_end year | filings extracted | have `Assets` tag | coverage |
|---|---|---|---|
| 2017 | 567 | 0 | 0.0% |
| 2018 | 1,377 | 1 | 0.1% |
| 2019 | 1,281 | 4 | 0.3% |
| 2020 | 1,627 | 6 | 0.4% |
| 2021 | 1,618 | 10 | 0.6% |
| 2022 | 1,784 | 47 | 2.6% |
| **2023** | **1,879** | **1,852** | **98.6%** |
| 2024 | 2,011 | 2,011 | 100.0% |

Verified this is a real taxonomy-content change, not a parsing gap: pulled
every tag from a real 2021 annual filing and confirmed it has a full cash
flow statement (`CashFlowsFromUsedInOperatingActivities` present, hence
that field's much higher coverage in 2020-2022 than the others) but
genuinely no `Assets`/`Equity`/`CurrentAssets`/`CurrentLiabilities`/
`BorrowingsCurrent`/`BorrowingsNoncurrent` tags -- only segment-level
asset/liability breakdowns (`SegmentAssets`, `UnAllocableAssets`), which
are not the primary balance sheet. **A usable, near-universal balance
sheet only exists in this data from fiscal year 2022-23 onward.** Value
and quality factors needing book value, leverage, or any balance-sheet
ratio are only reliably computable from ~2023 forward, roughly two years
of history, not the full 2016-2025 window the price layer supports.

### Coverage by field (2023-2024, the usable window)

| field | tag | 2023 coverage | 2024 coverage |
|---|---|---|---|
| total assets | `Assets` | 1,852 | 2,011 |
| total equity | `Equity` | 1,850 | 1,969 |
| current assets | `CurrentAssets` | 1,729 | 1,836 |
| current liabilities | `CurrentLiabilities` | 1,729 | 1,836 |
| cash | `CashAndCashEquivalents` | 1,852 | 1,970 |
| operating cash flow | `CashFlowsFromUsedInOperatingActivities` | 1,877 | 2,011 |
| borrowings (current) | `BorrowingsCurrent` | 1,727 | 1,835 |
| borrowings (non-current) | `BorrowingsNoncurrent` | 1,727 | 1,835 |

Total debt = borrowings current + non-current (no single "total debt" tag
exists in this taxonomy). Gross profit has no direct tag at all in any
year -- computed from P&L components already extracted in Phase A
(Revenue from Operations minus Cost of Materials Consumed, Purchases of
Stock-in-Trade, and the change in inventories), Novy-Marx style.

### Companies with no balance sheet at all

**426 of 2,487 companies (17.1%) have zero balance-sheet extraction across
the entire 2016-2025 window** -- no `Assets` tag on any filing, at any
point. Given the coverage-by-year finding above, this is dominated by
companies whose most recent annual filing predates FY2022-23 (delisted,
suspended, or simply not yet re-filed under the newer taxonomy as of this
backfill), not necessarily companies that will never have one.

### Consolidated vs standalone -- confirmed different from the P&L split, as expected

| | balance-sheet filings (`Assets` tag) | P&L filings (Phase A) |
|---|---|---|
| Consolidated | 2,880 | 39,439 |
| Non-Consolidated | 1,051 | 69,557 |
| **Consolidated share** | **73.3%** | **36.2%** |

The ratio flips. Companies that file a full balance sheet skew heavily
toward filing it on a consolidated basis -- consistent with fuller-taxonomy
compliance being more common among larger, group-structured companies (the
same population more likely to have a subsidiary structure requiring
consolidation in the first place). Confirms the pick-consolidated-else-
standalone logic must be applied independently to the balance-sheet series,
never inherited from whichever type a company's P&L happened to use --
mixing them here would silently combine two different bases far more often
than the P&L series would.

### Staleness distribution -- sawtooth, not a fixed number, and the "typical date" answer depends on where in the annual cycle you ask

Balance sheet refreshes once a year per company (unlike P&L's quarterly
cadence), so its staleness necessarily saws from near-zero right after the
annual filing rush to nearly a full year just before the next one. Reporting
across the 2024 cycle rather than one arbitrarily chosen date:

| as_of date | companies visible | median staleness | p90 |
|---|---|---|---|
| 2024-01-15 | 1,849 | 236 days | 261 days |
| 2024-04-01 | 1,852 | 313 days | 335 days |
| 2024-06-01 | 2,035 | 11 days | 37 days |
| 2024-08-01 | 2,047 | 71 days | 97 days |
| 2024-10-01 | 2,051 | 132 days | 158 days |
| 2024-12-01 | 2,053 | 193 days | 218 days |
| 2025-02-01 | 2,053 | 255 days | 280 days |

Average across these seven evenly-spread sample dates: **~173 days** --
close to the ~182 days a perfectly uniform annual refresh would predict,
slightly lower because filings cluster somewhat around the SEBI deadline
rather than spreading evenly. **The single-number answer to "how stale is
the median company's balance sheet" is misleading on its own** -- it is 11
days in June and 313 days in April, and any factor built on this data must
carry `as_of_staleness` per observation (as specified) rather than being
described by one typical value.

## Consequence of the Phase B coverage finding, stated in the arithmetic, not softened

Balance-sheet data starts being usable at FY2022-23 (period_end in calendar
2023). The price layer's pre-holdout window ends at the sealed boundary,
2025-03-18. That overlap is:

- 2023-01 through 2025-03 ~= **26 months ~= 2.15 years**
- at a 63-trading-day rebalance (~4 periods/year): **2.15 x 4 ~= ~8
  non-overlapping periods**

The momentum work (Study 1) used **31 periods** to get a fold-level t-stat
of 2.66-3.53 -- readable, if still a thin sample by this project's own
standing admission. Fold-level standard error scales as `1/sqrt(n)`, so
going from 31 periods to 8 multiplies SE by `sqrt(31/8) ~= 1.97` --
**roughly double**. Momentum's own measured SE at n=31 was ~0.027; at n=8
that scales to ~0.053. Clearing a conventional t~2 threshold at that SE
requires **|IC| ~= 0.10** -- five times the momentum factor's own
significant result (0.087), and well outside the 0.02-0.05 range typical
of published cross-sectional equity factors. A measured IC anywhere near
that bar, on 8 periods, is not evidence of an unusually strong factor; per
this project's own standing rule ("if a result looks too good, hunt for
leakage before believing it"), it is closer to a bug signature than a
finding.

**Consequence, stated as a hard limitation, not a caveat**: any factor
requiring book value or leverage -- P/B, ROCE, ROE, debt/equity, interest
coverage, Piotroski F-Score, Altman Z-Score -- **cannot be meaningfully
tested on this data.** Not "weakly tested," not "tested with wide
confidence intervals" -- the sample size at the only window where the data
even exists is too thin to distinguish a real effect from noise using this
project's own validation standard. Phase E computes these factors (the
infrastructure is real and correct) but reports them as **untestable, with
this reason stated explicitly**, not as a weak or inconclusive result.

**What survives**: every P&L-derived factor computed in Phase A, on the
full 2016-2025 window --earnings growth, revenue growth, margin trend (no
share count needed), and accruals in simplified form (net income minus
operating cash flow, both available from Phase A/B without needing a
balance sheet). Earnings yield, P/E, P/S, and any size factor additionally
need a share count -- Phase C, next, is the decision point for whether
that set is thin (growth/margin only) or real (adds a genuine value factor
set on the full window).

## Phase C: shares outstanding -- the decision point, resolved positively

**Good news, stated as plainly as the bad news elsewhere in this
document**: shares outstanding is obtainable from source #1
(`PaidUpValueOfEquityShareCapital` / `FaceValueOfEquityShareCapital`,
already present in the SAME quarterly XBRL used for P&L in Phase A -- no
separate fetch needed) at coverage that **tracks general XBRL
availability, not Phase B's FY2023 cliff.**

Validated in two passes, not assumed from the first promising spot check.
First pass (9 quarterly filings, one per year 2016-2024, hand-picked)
showed 9/9 with both tags and a plausible computed share count (e.g.
TATASTEEL 2021: paid-up capital / face value = ~1.20 billion shares,
matching its real share count at that time). Grouping that sample by
`period_end` year initially looked inconsistent with Phase A's known
2016-2017 no-real-XBRL boundary -- traced to a real methodological
mismatch (period_end year vs announcement/`known_date` year disagree often
enough to matter), corrected before trusting the result, then re-run
properly stratified by announcement year with a larger sample (40/year,
2018-2026, real-XBRL filings only):

| announce year | n sampled | has both tags | coverage |
|---|---|---|---|
| 2018 | 40 | 40 | 100.0% |
| 2019 | 40 | 39 | 97.5% |
| 2020 | 40 | 40 | 100.0% |
| 2021 | 40 | 40 | 100.0% |
| 2022 | 40 | 40 | 100.0% |
| 2023 | 40 | 39 | 97.5% |
| 2024 | 40 | 40 | 100.0% |
| 2025 | 40 | 40 | 100.0% |

**Consequence**: wherever real XBRL exists at all (Phase A's own boundary:
0% of filings announced 2016-2017, 54.5% announced 2018, 84.7% announced
2019, 98%+ from 2020 onward), the share-capital tags are present 97.5-100%
of the time. Shares outstanding is not a new, separate limitation on top
of Phase A's -- it inherits exactly Phase A's existing boundary and no
worse. **P/E, P/S, earnings yield, and market-cap-based size become
computable from ~2018-2019 onward** (partial 2018, near-complete
2019-2025) -- not the full 2016 start, but the same window the P&L factors
already use, not a new, narrower one.

**The 2016-2017 gap is real and not solved here.** No real XBRL exists for
filings announced in that window (Phase A's finding, confirmed again here,
not new). Two partial paths were checked and neither is pursued further
without direction: NSE's `corporate-share-holdings-master` endpoint has
records back to at least 2017, but reports promoter/public shareholding as
**percentages**, not an absolute share count -- useless alone without a
paid-up-capital anchor for that same date, which is exactly what's missing
pre-XBRL. Inferring backward from a post-2018 anchor using the
already-built `corporate_actions` (bonus/split) table is feasible in
principle but only accurate for companies with no equity issuance or
buyback in the gap window -- an approximation with a real, uncharacterized
error rate, not attempted here. **Explicitly not substituting today's (or
any single) share count backward across this gap** -- that is precisely
the lookahead this layer exists to prevent, and would have been the fourth
time a plausible shortcut in these projects produced a wrong number, after
(1) VSTTILLERS' single-filing mischaracterization, (2) the original
gap-unaware return computation, and (3) the near-miss on treating
`corporates-financial-results`'s no-date-range default as a full-history
shortcut.

## Phase D: sector classification -- timeboxed attempt, no improvement found

Two avenues tried, both dead ends, neither pursued further per the
timebox:

1. **NSE's per-symbol `quote-equity` API** (`industryInfo` field, which
   does carry full macro/sector/industry/basic-industry classification per
   company on the live site) -- blocked by bot protection (403) even after
   visiting the quote page first to pick up cookies, the pattern that
   works for every other endpoint this project uses. Not pursued further
   -- this would in any case require ~2,500 individual per-symbol calls,
   the least attractive option even if it worked.
2. **The `industry` field already present in the financial-results feed
   itself** -- checked directly against a real sample: **always the
   literal string `"-"`, never populated, across every record checked.**
   A structurally dead field, not an extraction gap.

Searched for a downloadable full-universe classification file (NSE
Indices does describe a formal structure -- 12 macro-sectors, 22 sectors,
59 industries, 197 basic industries, reviewed annually) but found no
accessible bulk download; the sectoral index constituent lists already
used for the existing 44.9% coverage are the only classification data
confirmed reachable.

**Coverage remains 44.9% (Nifty Total Market list, 755 names), unchanged.**
Per instruction: value factors proceed with this limitation stated
explicitly; sector-relative percentiles are uncomputable for the
uncovered ~55% of the universe, and Phase E reports coverage per factor
per date rather than assuming completeness.

**Known limitation, recorded rather than assumed away**: the Nifty Total
Market list is a **current-state** snapshot. A company's sector in 2026 is
not guaranteed to be its sector in 2018 (business model changes,
reclassifications, conglomerate restructuring). This is a real, if mild,
lookahead -- much weaker than a price or earnings lookahead, since sector
identity changes far less often and far less consequentially than a
financial figure -- but it is present and unresolved. No historical,
point-in-time sector classification source was found or built.

## Net effect on Phase E the full value-factor set (earnings yield, P/B,
P/E, P/S, EV/EBITDA, FCF yield) is only fully computable from FY2022-23
onward (Phase B's balance-sheet boundary governs, since P/B and EV/EBITDA
need book value); but P/E, P/S, and earnings yield specifically -- and any
size factor -- do not need a balance sheet, only price and share count,
and are computable from ~2018-2019 onward given this finding. That is a
real, usable value-factor subset on close to the full window, not just
growth/margin factors alone.

The consequence: **any strategy combining price and fundamentals factors
has zero fundamentals coverage across the entire sealed holdout window.**
This is not a data-quality nuisance to work around later -- it is a hard
ceiling on what this project can currently prove about such a strategy
out-of-sample. A price+fundamentals composite could be built and could
show a compelling pre-holdout backtest, and there would be no way to
holdout-test it at all until a fetcher for the Integrated Filing category
exists. That fetcher is not built. Until it is, any fundamentals-involving
study is CV-only by construction, permanently, not by choice of
methodology -- the same limitation `trade-info` recorded for its own spent
holdout, arrived at here for a different reason before any study has even
run.

## Phase E: per-factor rank IC results (no composite, no pre-registration)

### Design decision: direct SE, not purged-fold CV, for these factors -- decided before any significance number was seen

Momentum's own validation (Study 1/2) used purged fold-level standard error
because its panel was DAILY with a 63-day target -- consecutive days'
forward-return windows overlap by 62 of 63 days, so daily ICs are dependent
observations, and folds fix that. Phase E's rebalance dates are themselves
spaced 63 trading days apart (matching the horizon), so forward windows do
NOT overlap and each date's IC is already an independent draw; and every
factor tested here is a single parameter-free ratio (nothing fitted), so
there is no in-sample leakage channel for CV to guard against either --
point-in-time correctness via `known_date` is a separate, already-handled
concern. Applying the fold machinery anyway produced `0 folds used` (NaN
significance) on every one of 9 factors, because splitting ~22-26
independent dates into 10 folds starves each fold below the fold-report's
own 10-date trust threshold. **This design change was made after seeing
only the descriptive `ic_by_year` table (which had run successfully) and
before any significance number existed** -- the fold-based 0-result was a
plumbing failure, not a result, so switching methodology here is not
data-driven tuning. The direct calculation (mean IC over independent dates,
SE = std/sqrt(n_dates), t = mean/SE) is implemented in
`factors.ic_eval.nonoverlapping_ic_report`, gated by an explicit assertion
that the observed rebalance spacing is >= the target horizon (verified per
factor from the actual date list, never assumed from the grid design), and
unit-tested against a hand-computed synthetic case
(`tests/test_nonoverlapping_ic.py`). Fold-based CV remains the correct tool
and is unchanged (`fold_level_ic_report` untouched) for any future study
that fits a model or composite, where both overlap and fitting-leakage risk
return.

### Raw per-factor results (26 quarterly rebalance dates, 2018-2024, pre-holdout)

**Corrected 2026-09-24 (BUGS.md Bug #7).** The table below originally read
t=+2.86 for `earnings_yield` (and correspondingly for every other factor).
A fundamentals-feed ISIN-resolution bug -- the same stale-ISIN defect
`corporate_actions.py` had already fixed for the corporate-actions feed,
never checked against this one -- had silently excluded 166 companies
(83% of 200 orphaned ISINs) from every factor computed here. Fixing it
added ~30-43 names per rebalance date on average to every factor's
cross-section (n_dates itself is unchanged for every factor, verified
directly). This is a corrected remeasurement of the same result, not a
new finding -- reported as such, not as a discovery, and the headline
conclusion below (nothing survives multiple-comparisons correction) is
unchanged either way.

Verified spacing: every factor's used-date subset showed min=median=max=63
trading days between consecutive dates -- the non-overlap assumption held
exactly, zero violations.

| factor | n_dates | mean_ic | std_ic | se | t (raw, uncorrected) | t before Bug #7 fix |
|---|---|---|---|---|---|---|
| earnings_yield | 26 | +0.0393 | 0.0729 | 0.0143 | +2.75 | +2.86 |
| pe | 26 | -0.0431 | 0.0930 | 0.0182 | -2.36 | -2.47 |
| margin_trend | 22 | +0.0244 | 0.0520 | 0.0111 | +2.20 | +2.26 |
| earnings_growth | 22 | +0.0214 | 0.0610 | 0.0130 | +1.65 | +1.61 |
| revenue_growth | 22 | +0.0155 | 0.0559 | 0.0119 | +1.30 | +1.32 |
| accruals_simplified | 15 | -0.0170 | 0.0478 | 0.0123 | -1.38 | -1.23 |
| ps | 26 | -0.0259 | 0.1201 | 0.0236 | -1.10 | -1.20 |
| operating_margin | 26 | +0.0208 | 0.1010 | 0.0198 | +1.05 | +1.19 |
| market_cap | 26 | +0.0103 | 0.1778 | 0.0349 | +0.30 | +0.26 |

Untestable set (pb, roce, roe, de, interest_coverage), computed on only the
8 rebalances from 2023 onward where balance-sheet data exists: t ranges
-1.61 to +1.20 (was -1.66 to +1.17). **Reported as UNTESTED, not weak or
inconclusive** -- 8 periods cannot distinguish any of these from zero at
this project's own standard, exactly as predicted by the arithmetic
earlier in this document.

### Multiple-comparisons correction -- the raw t-stats above must never be cited without this

`earnings_yield` and `pe` are the same underlying value signal (EBIT/mktcap
vs mktcap/NI, opposite-signed by construction), not two independent tests
-- collapsed to **8 tests** for correction, using `earnings_yield` (cleaner
than `pe`, which drops 19.1% of observations to negative-earnings exclusion)
as the pair's representative.

- Bonferroni threshold at alpha=0.05, m=8: **0.05/8 = 0.00625**.
- `earnings_yield`: raw t=+2.75, p~0.011 -- **fails** Bonferroni (p > 0.00625).
- `margin_trend`: raw t=+2.20, p~0.039 -- fails Bonferroni.
- Benjamini-Hochberg: the smallest p-value must itself beat alpha/m for
  BH to reject anything -- since `earnings_yield`'s p (0.011) does not
  beat 0.00625, **BH rejects zero of 8 factors**, same as Bonferroni here.

**HEADLINE: no fundamental factor clears significance after correcting for
the number tested.** `earnings_yield` is the strongest candidate and is
**suggestive, not established**. Full corrected table (t, raw p, Bonferroni
threshold/reject, BH q-value/reject) is computed and printed by
`scripts/run_phase_e_factors.py` on every run and must accompany the raw
t-stat wherever it is cited, per instruction that the raw t=2.75 (formerly
2.86; see the correction note above) must not appear alone.

### Diagnostic: earnings_yield vs momentum_12_1 (no slot spent -- decides whether a combination is worth pre-registering, not itself a study)

Cross-sectional rank correlation between `earnings_yield` and
`momentum_12_1`, per rebalance date, 26 dates: **mean +0.0003, std 0.1501**
-- near zero, with real year-to-year swings (2019: -0.17, 2020: -0.21,
2021: +0.13, 2023: +0.14). **Verdict: NEAR ZERO -- earnings_yield appears
to carry information largely independent of momentum**, not a duplicate of
it and not a literature-typical negative correlation either. This is the
result the fundamentals layer was built to find.

**Observation, carefully scoped -- noticed after the fact, not evidence**:
2020 was momentum's crisis year (Study 1/2's own record shows momentum
underperforming sharply in 2020); in that same year the EY/momentum
correlation was -0.21, its most negative of the seven years measured. In
the one year momentum did badly, earnings_yield pointed the other way. This
is **one year, observed post hoc** -- it is the right *shape* for a
diversification benefit and nothing more. It is not a second test, not
corroboration, and must not be cited as if it independently supports the
near-zero-correlation finding above; it is the same finding's most visible
single data point, described in words instead of a number.

`earnings_yield`'s IC restricted to entities OUTSIDE momentum's top decile
per date: mean_ic=+0.0436, se=0.0141, t=+3.09, n_dates=26 (26,790 of 28,915
obs; 2,125 excluded as in-top-momentum). **This t=3.09 figure predates the
Bug #7 ISIN-resolution fix and has not been remeasured** -- `n_obs=28,915`
here matches the OLD (pre-fix) `earnings_yield` universe exactly, since
this is a separate diagnostic (`scripts/run_ey_momentum_diagnostic.py`),
not part of the Phase E rerun that produced the corrected 2.75 figure
above. Flagged rather than silently left stale or guessed at; rerunning it
is a follow-up, not done here. **Caution**: this is a test of
*independence* (does EY's signal survive when momentum's own top picks are
removed), and it supports independence, which is what it checked -- it is
**not evidence that EY "got stronger."** t=3.09 on a different
sub-population was never comparable to the full-universe raw t (now 2.75,
formerly 2.86) as a before/after improvement; they are two different tests
answering two different questions. **The corrected headline from the
multiple-comparisons section above stands regardless: earnings_yield alone
does not survive correction for the number of factors tested.** Both findings together
support pre-registering a future combination study as worthwhile, subject
to the constraint immediately below -- they do not upgrade earnings_yield's
own standalone significance.

### Constraint that bounds any future combination study

**Fundamentals have zero coverage in the sealed holdout window** (the April
2025 Integrated Filing format change documented above). Any
momentum+fundamentals combination that gets built and tested is **CV-only
on data already seen** in Study 1/Study 2 -- not a sealed test. No sealed
test is possible until an Integrated Filing fetcher is built. This must be
stated alongside any future combined-backtest result so it is never read as
validated out-of-sample.

### Stale-beats-fresh anomaly -- noted, not investigated

For both `earnings_yield` and `pe`, the staler half of the median-staleness
split is *more* significant than the fresher half (earnings_yield: t=2.50
stale vs 1.81 fresh; pe: t=-2.20 stale vs -1.71 fresh) -- the opposite of
the naive expectation that fresher fundamentals should be more predictive.
A post-earnings-announcement-drift (PEAD) mechanism is a plausible
candidate explanation, but splitting an already-small sample of 26
independent dates roughly in half leaves each half within noise at this
sample size. Recorded, not chased further, per instruction.

### Piotroski F-Score and Altman Z-Score: not implemented

A time-boxing choice, disclosed rather than silently dropped. Altman Z
specifically needs a `RetainedEarnings` tag that is not present in the
extracted balance-sheet set.

## Integrated Filing coverage report (reconnaissance only -- nothing built or ingested yet)

Investigated the format that replaced quarterly "Financial Results" filings
from April 2025 (the boundary behind the "hard ceiling" section above), to
determine whether and how it can be fetched before building anything on it.
No fetcher module, backfill script, or database ingestion was written --
this is findings only, gathered by locating the live endpoint and inspecting
real documents and metadata.

### Endpoint located

List metadata: `nseindia.com/api/integrated-filing-results?type=Integrated%20Filing-%20Financials&page=N&size=N`
(found via the public page `nseindia.com/companies-listing/corporate-integrated-filing`,
whose own network calls reveal it -- there is no separate developer-facing
API reference). Underlying documents: `nsearchives.nseindia.com/corporate/xbrl/*.xml`,
the same archive host already used for Phase A/B's XBRL, plus a bonus
`ixbrl` (inline-XBRL, human-readable HTML) rendering per document not
present in the old format.

### Licensing: no new question -- same NSE domain, same terms

Both hosts above are the same `nseindia.com` / `nsearchives.nseindia.com`
already cleared in `LICENSE_ASSESSMENT.md` (sections A/B) for the old
format. The new SEBI taxonomy (`in-capmkt`) is a different regulator-issued
XBRL schema, not a different data source -- addendum recorded in
`LICENSE_ASSESSMENT.md` section D.

### Tag mapping: the vocabulary carried over almost completely -- the namespace changed, the field names mostly didn't

The taxonomy changed from `in-bse-fin` to a new SEBI schema, `in-capmkt`
(`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`). Despite the namespace
change, inspecting one quarterly document (LUMINO, Q1 FY26) and one audited
annual document (a March-2026-year-end filer) by direct download shows
**every P&L and balance-sheet tag this project already uses is present
under the identical local tag name**: `RevenueFromOperations`,
`ProfitLossForPeriod`, `ProfitBeforeExceptionalItemsAndTax`, `FinanceCosts`,
`Assets`, `Equity`, `CurrentAssets`, `CurrentLiabilities`, `BorrowingsCurrent`,
`BorrowingsNoncurrent`, `CashFlowsFromUsedInOperatingActivities`,
`PaidUpValueOfEquityShareCapital`, `FaceValueOfEquityShareCapital` -- zero
renaming needed for the existing tag list. A fetcher for this format is a
new namespace prefix and a new `source` label in the existing schema, not a
new field-mapping exercise.

**Field that does not map: ISIN is not in the list-metadata API** (unlike
the old `corporates-financial-results` API, which carried `isin` directly).
It IS present as a tagged fact inside every document body (`ISIN` tag,
`OneD` context, e.g. `INE185Q01025` for LUMINO) -- resolvable by parsing
each document, the same per-document work the pipeline already does, not by
a separate lookup. Explicitly avoided: joining the list API's `symbol` to
our own most-recent-known ISIN, which would reopen exactly the symbol-reuse
risk the ISIN-first design exists to prevent -- **11.1% of all symbols ever
seen in `prices_eod` (440 of 3,971) have mapped to more than one ISIN across
this project's history**, a real, non-negligible rate, not a rounding
concern.

**New fields found, not required but useful**: `NatureOfReportStandaloneConsolidated`,
`WhetherResultsAreAuditedOrUnaudited`, `DateOfStartOfReportingPeriod`/`DateOfEndOfReportingPeriod`
tagged directly in-document (cross-check against the list API's own
`consolidated`/`audited`/`qe_Date` fields); and filer-computed
`DebtEquityRatio`, `NetWorth`, `InterestServiceCoverageRatio` tags -- not
used as inputs, but available to cross-validate this project's own computed
ratios against the filer's own disclosed figures if useful later.

### Context convention: same semantics, confirmed on real data, not assumed from the tag names alone

`OneD`/`OneI` (current-period duration/instant) are present and hold the
current quarter's own figures, exactly the old convention -- confirmed
against real numbers, not inferred: the annual sample's `RevenueFromOperations`
showed `OneD=147,282,000` vs `FourD=553,406,000` (~3.76x), the same
one-quarter-vs-YTD-cumulative ratio pattern found for VSTTILLERS in Phase A,
confirming `Four*` still means year-to-date cumulative here too. This
project only ever reads `One*` (see `load_quarterly_tag`/`load_annual_tag`),
so this is confirmation the existing context-filtering logic needs no
change, not merely a hopeful analogy. New contexts not present in the old
taxonomy (`PY_I`, `I_Audited`/`D_Audited`, `I_Adjusted`/`D_Adjusted`) exist
for prior-year and audit-qualification disclosures; not needed for the
current factor set, noted for completeness.

### known_date discipline: a new two-field split, verified total and unambiguous on the full current dataset

The list metadata carries `type_Sub` (`"Original"` or `"Revision"`),
`broadcast_Date`, and `revised_Date` instead of the old single `broadCastDate`.
Checked on all 26,829 currently-available records: **`broadcast_Date` is
populated for every `"Original"` row and null for every `"Revision"` row;
`revised_Date` is the exact complement** (null for Original, populated for
Revision) -- zero rows have both null, zero rows have both populated. The
rule is therefore total and exact, not a fallback for an edge case: `known_date
= broadcast_Date if type_Sub == "Original" else revised_Date`. `qe_Date`
(quarter-end) is the `period_end` analog and must never be used as
`known_date`, same discipline as every other source in this project.

### Restatement handling and consolidated preference: same pick logic, richer labeling

`type_Sub`/`revision_Remark` is a more explicit analog of the old model's
implicit multiple-seq_number-per-period restatement pattern -- it directly
labels which submissions are revisions and why (e.g. "Revised based on BSE
Query.", "Resubmission is made against BSE mail for Discrepancy found in
Standalone & Consolidated..."). Restatement rate in the current data: 3,059
of 26,829 (11.4%), higher than Phase A's 5.89% P&L restatement rate --
plausibly a newer, less mature filing process producing more corrections,
not investigated further here. `consolidated` carries the same
`"Consolidated"`/`"Standalone"` string values as before and is directly
cross-checkable against the in-document `NatureOfReportStandaloneConsolidated`
tag. The existing pick-latest-known-date-within-winning-type logic
(`fundamentals_pit.py`, `_pick_pit_series`) needs no redesign, only a
correctly-derived `known_date` per the rule above.

### Transition-boundary validation: checked directly against our own data, clean handoff confirmed

Sampled FIVESTAR and HGINFRA (both present in the new format's earliest
`qe_Date` bucket, 31-MAR-2025): the OLD-format `fundamentals_filings` table
has **zero rows for `period_end = 2025-03-31` across the entire universe**,
and both companies' last old-format quarter is `period_end = 2024-12-31`
(Q3 FY24-25). The new format's earliest quarter (31-MAR-2025, Q4 FY24-25) is
broadcast primarily in April-May 2025 (95.6% of that quarter's "Original"
filings), consistent with a normal 30-60 day filing lag after the April 1
2025 mandate took effect. **No overlap (no company double-counted for the
same quarter under both formats) and no gap (no quarter silently missing
between the two formats' coverage) in this sample.**

### Coverage from April 2025 onward

| metric | value |
|---|---|
| total Integrated Filing-Financials records (as of this check) | 26,829 |
| distinct quarter-ends covered | 6 (31-Mar-2025 through 30-Jun-2026, ongoing) |
| distinct symbols with >=1 filing | 2,381 |
| symbols actively trading in our price panel since 2025-04-01 | 3,139 |
| **coverage of the currently-active universe** | **75.8%** |
| Consolidated / Standalone split | 11,305 / 15,524 (42.1% consolidated) |
| Original / Revision split | 23,770 / 3,059 (11.4% revised) |

### Correction to the "hard ceiling" framing -- recorded as a correction, attributed accurately

The earlier framing in this document ("any strategy combining price and
fundamentals factors has zero fundamentals coverage across the entire
sealed holdout window... a hard ceiling") was written in that strong form
at the user's own push for plain, unsoftened language, applied here to a
claim that turned out to be wrong on the facts. **Correcting it explicitly,
not quietly loosening the wording**: fundamentals for the quarter ending
2025-03-31 (announced April-May 2025, squarely inside the sealed holdout
window that begins 2025-03-19) are NOT absent from existence -- they are
absent only from this project's OLD extractor, which reads an endpoint
that stopped receiving new filings after the mandate. A working Integrated
Filing fetcher recovers real coverage starting at the holdout's own start
date forward, not from some later, hypothetical quarter.

**This does NOT reopen the holdout, and stating why matters more than the
correction itself.** Study 1 already evaluated `momentum_12_1` on this
exact window and the result is known and recorded (`FINDINGS.md`: holdout
CAGR 14.72% vs benchmark 10.85%, margin +3.87pts, all three decision-rule
conditions passed). Any study combining momentum with `earnings_yield` on
that same window would therefore have one of its two legs already observed
to succeed there -- partial contamination, not a clean test, regardless of
whether the fundamentals data needed to compute the other leg physically
exists. **The data existing and the data being usable for a clean test are
different things**, and only the second one governs what a pre-registered
study is allowed to touch. The combination study's validation remains
forward-only, starting after pre-registration, on quarters that do not yet
exist at the time this document is written -- see
`PREREGISTRATION_COMBINATION.md`.

### Credit: parsing ISIN from the document body, not joining via symbol, was the correct call

Recorded with the reasoning, not just the choice, since the reasoning is
what makes it durable. NSE's Integrated Filing list-metadata API dropped
the `isin` field the old `corporates-financial-results` API carried,
leaving only `symbol`. The available shortcut -- join each filing's
`symbol` to this project's own most-recently-known ISIN for that symbol --
was rejected before building anything, in favor of parsing the `ISIN` tag
out of each document's own body. The reasoning: **11.1% of all symbols
ever seen in this project's price history (440 of 3,971) have mapped to
more than one ISIN over time.** A symbol-keyed join is not a rare-edge-case
risk at that rate; on a dataset this size it would have silently attached
some real, non-negligible number of companies' fundamentals to a
*different* company's prices, with no error, no warning, and no way to
detect it later except by re-deriving the whole feature from scratch. Per-
document ISIN parsing costs nothing extra (the document is fetched and
parsed regardless, to get the actual facts), so this was correctness
obtained for free, not a costly precaution -- confirmed practical, not just
theoretically preferable, once the fetcher below was actually built against
real documents.

## Integrated Filing fetcher: built, run, and validated against real data

`src/data_layer/integrated_filing_nse.py` (metadata fetch/parse) and
`scripts/backfill_integrated_filing.py` (per-document fetch, parse, load)
implement the design from the coverage report above, reusing the existing
`fundamentals_xbrl_facts` schema and the existing point-in-time/
consolidated-preference logic (`fundamentals_factors._pick_pit_series`,
`load_quarterly_tag`, `load_annual_tag`) completely unchanged --
source-agnostic by construction, so no new pick-logic was needed once facts
were loaded correctly under the `NSE_INTEGRATED_FILING_FINANCIALS` source
label.

### Two more bugs found building and running it, not left in

Both recorded in full in `BUGS.md` (#5, #6); summarized here for the
fundamentals-layer record:

- **Bug #5**: the list-metadata API's `totalCount` is not a stable
  pagination bound on this live-mutating dataset (four calls seconds apart
  returned 26765, 26765, 26765, then 26829) -- the first real run stopped
  silently at 3,000 of ~26,800 records before this was caught and fixed to
  stop only on a genuinely short page. Also: `load_facts_to_duckdb`'s
  existence check was scoped to bare `seq_number`, which is only unique
  within one source's own ID space -- fixed to scope by `(source,
  seq_number)` before a real cross-source collision could occur (none was
  found live, but the numeric ranges overlap enough that it was a real
  risk, not a theoretical one).
- **Bug #6**: a reused `requests.Session` wedged solid after ~574
  successful requests (every subsequent request timed out, 59 in a row)
  while a brand-new request to the same URL succeeded immediately -- a
  dead pooled connection, not a server-side block. Fixed with a retry
  adapter plus a session-rebuild safety net; then tuned live after
  measuring that the first fix's own retry settings cost ~45s per failed
  attempt (compounding to ~7.5 minutes per recurring episode, which
  projected to blow the completion-time estimate) -- cut to a single fast
  retry, a shorter per-request timeout, and a much lower failures-before-
  rebuild threshold, which held up cleanly for the rest of the run (recurred
  roughly a dozen more times over the full backfill, each resolved in
  seconds rather than minutes).
- The run was also killed once by the environment mid-flight (the same
  pattern seen repeatedly during the original quarterly XBRL extraction) --
  resumed cleanly with zero data loss, confirmed by re-checking the loaded
  document count before restarting, same established practice as every
  prior interruption in this project.

### Handoff validated on real data, not just asserted from design

`tests/test_integrated_filing_handoff.py` checks a specific real company
(ISIN `INE133A01011`, symbol `JSWDULUX` under the old format) against the
live warehouse: its 2025-03-31 quarter is present via the new source and
absent from the old one; its old-format last quarter (2024-12-31) is
exactly one quarter before its new-format first quarter (2025-03-31, a
3-month gap, not 6); and neither source has any row inside the other's
covered window for this entity. All four checks pass.

### Final coverage, after ingestion (supersedes the pre-ingestion recon estimate)

| metric | recon estimate | actual, post-ingestion |
|---|---|---|
| total documents | 26,829 (metadata only) | **26,598 loaded** (99.66% of the 26,690 scoped for fetch; 92 permanent failures, same genuine-404 class as Phase B's 1.3%, not chased further) |
| distinct entities (by ISIN) | 2,381 (by symbol, pre-parse) | **2,493** |
| coverage of actively-traded universe | 75.8% (symbol-based) | **79.4%** (2,493 of 3,139 ISINs actively trading since 2025-04-01) |

Coverage by quarter (period_end), documents and distinct entities:

| period_end | n_docs | n_entities |
|---|---|---|
| 2025-03-31 | 4,380 | 2,169 |
| 2025-06-30 | 4,015 | 2,172 |
| 2025-09-30 | 4,593 | 2,256 |
| 2025-12-31 | 4,406 | 2,285 |
| 2026-03-31 | 4,882 | 2,298 |
| 2026-06-30 | 4,322 | 2,315 |

Entity count rises steadily quarter over quarter (2,169 to 2,315) --
consistent with a still-maturing compliance process (more companies
catching up to the new filing system over time) rather than a data-quality
problem, and matching the higher restatement rate already noted (11.4% vs
Phase A's 5.89%).

## Momentum + earnings_yield combination: considered, power-analyzed, correctly not pursued

A pre-registration draft (`PREREGISTRATION_COMBINATION.md`) was written for
an equal-weight `momentum_12_1` + `earnings_yield` rank combination, using
the final study slot for this dataset. Before freezing it, a power analysis
was run on two different metrics -- top-decile portfolio-margin, then
paired rank-IC difference (the better of the two, since it uses the full
cross-section rather than collapsing ~1,200 stocks into one decile cut per
quarter) -- using historical variance only, never the historical mean, on
the 2018-2024 window where both factors exist. Both metrics found the same
thing: no practically reachable sample size would let this project
distinguish a real, economically plausible improvement from noise. The
best case on the better metric (a true 0.03 paired IC difference) needs 8
years of forward data; more realistic differences (0.01-0.02) need 18 to
72 years. **The pre-registration was withdrawn before approval. The final
study slot is held, not spent.** Full numbers and reasoning in
`PREREGISTRATION_COMBINATION.md`. This is not a finding against
`earnings_yield` itself -- the diagnostic results above (near-zero
momentum correlation, IC holding outside momentum's top decile) stand as
reported; it is a finding that this project's data is not large enough,
in either cross-section or history, to validate a combination of the two
even if a real effect exists.
