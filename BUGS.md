# Bugs found during this project

Every one of these produced a plausible, not-obviously-wrong number -- never
a crash. Format follows `trade-info/FINDINGS.md`'s own convention (mechanism,
evidence, before -> after), since these are the same class of failure the
prior project catalogued and several are the same failure recurring here in
different clothing, exactly as expected going in.

## Bug #1: lineage correctly links, adjustment silently doesn't -- unparsed corporate-action types fabricate returns at a linkage boundary

**Mechanism**: `isin_lineage`'s NSDL structural rule (issuer+type+serial,
non-overlapping dates) correctly identifies that two ISINs belong to the
same company -- that part of the design is sound and was independently
verified against BAJFINANCE's real chain. But the corporate-actions parser
only extracts Bonus and Face-Value-Split events from free-text subjects
(a deliberate, documented scope choice, matching the prior project's own
exclusion of "Capital Reduction" as unparseable). When the actual event
driving a lineage transition is a capital reduction, scheme of arrangement,
or similar restructuring -- a real corporate action, just not one either
project's parser attempts -- `adjustment_factors` has no entry to correct
for it. The combination (correct lineage link + silently-absent adjustment)
fabricates a return exactly at the boundary.

**Evidence**: entity `INE234I01010` (symbol KAUSHALYA). Lineage correctly
links it to `INE234I01028` (same symbol, deterministic NSDL match,
transition dated 2024-03-04). Raw close: 9.85 (last trade under the old
ISIN, 2024-01-11) -> 988.30 (first trade under the new ISIN, 2024-02-06) --
a ~100x jump. NSE's corporate-actions feed shows nothing for this symbol in
that window except annual AGM notices; no bonus, split, or any other parsed
event exists to explain it. Quantified across the full panel: **14 of 318
lineage transitions (4.4%)** show a >1.5x or <0.67x adjusted-price jump at
the boundary (worst: 89.8x). The 90th percentile of all 318 transition
ratios is 1.14x; the 99th is 3.0x -- this is a small, bounded, identifiable
population, not a pervasive one.

**Effect measured, not assumed**: rank IC is essentially untouched by these
14 entities (momentum_12_1: 0.0714 -> 0.0713 excluding them) -- Spearman IC
is magnitude-robust by construction. The cost-hurdle calculation, which
uses cross-sectional standard deviation (a magnitude statistic), is not:
mean daily x-sec std of forward 63d return fell from 43.5% to 34.3% when
just these 14 entities were excluded, and to 28.1% when measured via the
median instead of the mean.

**Status: built, currently redundant, retained deliberately.** A legitimate
outcome, not a wasted effort: Bug #2's fix already neutralized all 14
known cases before this fix was written, and the measurement below
confirms that rather than assuming it. Two follow-up questions, both
resolved directly rather than argued:

**(a) Can the parser be extended to these action types?** No -- checked
against the cached raw feed (22,514 records, not just the ones the bonus/
split regex matched): all 14 unexplained transitions have **zero** feed
records of ANY type within +-10 days of the transition date. This is not
a parser gap, it's a feed coverage gap -- NSE's `corporates-corporateActions`
endpoint simply never published anything for these events (capital
reductions/schemes of arrangement approved via NCLT/court order evidently
route through a different announcement channel this project hasn't
ingested). No regex extension can parse a record that was never fetched.

**(b) Structural fallback, built and tested**: `src/data_layer/
lineage_jump_guard.py` detects a lineage transition with a boundary ratio
outside [0.67, 1.5] and no nearby corporate-actions record, independent of
calendar gap size (the case Bug #2's calendar-gap check *cannot* catch: a
fabricated jump with no real trading halt). `factors/momentum.py`,
`factors/lowvol.py`, and `factors/target.py` all take an optional
`unexplained_jump_dates` parameter that NaNs only the single boundary
observation, not the whole entity -- verified against a synthetic
fixture with a ~90x jump and zero calendar gap (`tests/
test_lineage_jump_guard.py`, 5/5 passing, all opt-in and backward
compatible: 94/94 project tests still pass with the parameter omitted).

**Then measured against the real 14, and the measurement changed the
conclusion**: every one of the 14 turns out to have a calendar gap of
29 to 2,622 days between the last trade under the old ISIN and the first
under the new one (measured directly, not assumed) -- comfortably past
`STALE_GAP_DAYS=5`. Bug #2's existing gap-fix was already NaN-ing every
one of these 14 boundary returns, in production, before this investigation
started. The new surgical-NaN mechanism therefore makes **zero** measured
difference on top of Bug #2 for the current dataset (confirmed: momentum_12_1
rank IC and daily cross-sectional std of forward 63d return are bit-for-bit
identical with and without `unexplained_jump_dates` passed). It is kept
anyway, as defense-in-depth for a future capital reduction/scheme that
happens *without* a coincident extended halt -- a real possibility this
dataset's 14-for-14 pattern does not rule out, just hasn't produced yet.

**One number in the original write-up needs correcting as a result**: the
43.5%->34.3% cross-sectional-std swing was measured before Bug #2's fix
existed. On today's production code (Bug #2 applied, nothing entity-excluded),
the mean daily x-sec std of forward 63d return is already 36.9% (median
27.6%), not 43.5% -- most of the original contamination this bug described
is gone as a side effect of an unrelated later fix. Full-entity exclusion
still pulls it down further, to 33.6% (median 28.0%) -- but that residual
~3 points comes from removing these 14 (evidently distressed/restructuring)
companies' entire return histories from the sample, a universe-composition
choice, not a correction of the fabricated-jump mechanism this bug is
about. Excluding them outright remains undecided and is not done by
default.

## Bug #2: row-based shift() treats a stale trading gap as one ordinary trading day

**Mechanism**: every return-based computation in `factors/` (momentum's
lookback ratio, trailing volatility's chained daily log returns, the
forward-return target itself) used `groupby().shift(n)` -- moving `n` ROWS
back/forward per entity, not `n` CALENDAR days. For a name that stopped
trading for months (illiquidity, suspension, awaiting resolution) and then
resumed, the very next row's "1-day" return actually spans however long the
halt lasted. This is the same failure mode `trade-info/DESIGN.md` documents
fixing in its own outlier detector (`STALE_GAP_DAYS`-gated
`classify_discontinuity`) -- reading that finding did not, on its own,
prevent writing the same bug into three different factor computations here.

**Evidence**: of the panel's 50 largest single-row "daily" returns, **47 had
zero corporate action within +-5 days and a >5-calendar-day gap to the prior
row** (median 195 days, max 2,127 days / ~5.8 years). Only 3 of the 50
coincided with a lineage transition at all -- this is a distinct,
independent, and more pervasive failure mode than Bug #1, not the same bug
reappearing.

**Effect measured, not assumed, and asymmetric in an instructive way**:
- `trailing_vol_252`'s decile-mean table for forward return was *increasing*
  in the highest-vol decile (10.96%, above every other decile) despite a
  negative rank IC -- a decile table contradicting its own IC sign, which is
  structurally impossible for genuinely clean data. After gap-awareness
  (NaN-ing any daily return spanning a >5-day gap before rolling the 252-day
  window), the D9 decile fell from 10.96% to 4.98% -- no longer the extreme
  of the range -- while IC held (-0.073 -> -0.080). The contamination
  inflated vol AND correlated it with the genuine subsequent recovery
  rallies of newly-resumed names, in the wrong direction for the anomaly.
- `momentum_12_1` moved the OPPOSITE way: excluding the 16.8% of
  observations with a gap inside their 273-row lookback window *raised* IC
  (0.0714 -> 0.0867) and cleaned up the decile gradient. Same root cause,
  opposite symptom, because vol chains returns multiplicatively across the
  gap (fabricating an extreme value) while momentum only compares two
  endpoint prices (a stale gap just adds noise, diluting rather than
  inverting the signal).

**Status: fixed.** `factors/lowvol.py`, `factors/momentum.py`, and
`factors/target.py` all NaN out any observation whose relevant window
(trailing for vol/momentum, forward for the target) contains a
>`STALE_GAP_DAYS` (5) gap, rather than silently computing across it.
Regression tests: `tests/test_gap_awareness.py`, 5/5 passing.

## Bug #3: consolidated-vs-standalone pick logic silently preferred standalone

**Mechanism**: `factors/fundamentals_factors.py`'s first `_pick_pit_series`
implementation encoded consolidated-preferred as `_pref=0` (consolidated)
vs `_pref=1` (standalone), sorted ascending by `_pref`, then called
`.groupby(...).last()` to collapse duplicates. `.last()` returns the row at
the END of the sort order -- which, sorted ascending, is the HIGHEST
`_pref` value, i.e. standalone. The encoding and the aggregation disagreed
about which end of the sort "preferred" sat at; the result was the exact
opposite of the intended pick, silently, on every (isin, period_end) where
both types existed.

**Why this one is more consequential than it looks**: TTM (trailing
twelve months) is the shared foundation for the entire testable factor set
-- earnings yield, P/E, P/S, earnings growth, revenue growth, margin
trend, and accruals all sum trailing quarters through this same pick
logic. A silent standalone/consolidated mix-up here does not fail loudly;
it produces a plausible, wrong TTM value that would have propagated into
every one of those factors' IC calculations without any single number
looking obviously broken.

**Found by**: a synthetic unit test
(`tests/test_fundamentals_factors_ttm.py::test_ttm_prefers_consolidated_over_standalone_per_quarter`)
written and run BEFORE the real quarterly extraction had any meaningful
data in it -- caught on a two-row synthetic fixture, not on real numbers.
This is the shape of catch this project has been trying to build toward
since the momentum-holdout diagnostics: verify the mechanism on a case
small enough to reason about by hand, before it has the chance to hide
inside a real, large, plausible-looking result.

**Status: fixed.** Rewritten as an explicit two-step selection (filter to
consolidated rows where any exist for that quarter, standalone only as a
true fallback; then pick the latest `known_date` within the winning type
for restatement-awareness) rather than a single sort-and-aggregate whose
correctness depended on getting an ascending/descending convention right
by inspection. 5/5 tests passing, including the one that caught the bug.

## Bug #4: two compounding performance bugs made a ~4-hour job estimate into a real ~30-hour job

**Mechanism, part one**: `load_facts_to_duckdb`'s existence check
(`SELECT DISTINCT seq_number FROM fundamentals_xbrl_facts WHERE seq_number
= ?`) has no index to use -- `fundamentals_xbrl_facts` had no index on
`seq_number` at all -- so every call is a full table scan. The table
already held 2.5M+ rows from the Phase B annual extraction before this
quarterly run even started, so every single document paid that scan cost
from the first row, not as a gradually-worsening slowdown. The check
itself is also redundant for this workflow: the extraction script already
maintains its own in-memory `already_done` set and skips known documents
before ever calling this function.

**Mechanism, part two, found while investigating why the index fix alone
didn't close the gap**: the extraction script made every HTTP request with
a bare `requests.get()` call, never a reused `requests.Session()` -- so
every document paid a fresh TCP+TLS handshake to the same host. Measured
directly, back to back, same 20 URLs: bare `get()` averaged 0.484s/request;
a reused session averaged 0.075s/request. A 6.4x difference, invisible in
isolated single-request tests (which is exactly what the original ETA
calculation implicitly relied on) and only visible once measured as a
sustained batch against the same host.

**Combined effect, measured, not estimated twice more**: real observed
throughput before either fix, ~6-8s/document against an intended 0.33s
throttle. After the index alone, still ~2.48s/document -- proof the index
was necessary but not sufficient, and a reminder not to declare a fix
"working" from the first plausible-looking number. After both fixes
together, measured on two independent fresh 30-50 document batches:
~0.487s/document, consistently. The original "~4 hour" ETA for this job
had implicitly assumed the throttle sleep WAS the per-document cost,
with no allowance for real request latency at all -- an estimation
mistake, found by measuring rather than re-deriving the number a third
time from theory.

**Status: fixed.** `fundamentals_xbrl_facts` now has an index on
`seq_number` (kept, not removed, as defense-in-depth for any future caller
that doesn't pre-check). The extraction script uses one `requests.Session()`
for its entire run. Corrected ETA reported before relaunching, not after.

## Bug #5: two-source seq_number collision risk, and a live-mutating list API's totalCount is not a trustworthy pagination bound

**Mechanism, part one**: `load_facts_to_duckdb`'s existence check matched
on bare `seq_number`, with no `source` filter. This was harmless while only
one source (`corporates-financial-results`, IDs observed 11 to ~1.2M) ever
wrote to `fundamentals_xbrl_facts`. Building the Integrated Filing fetcher
introduced a second source with its own independent ID space (`seq_Id`,
observed ~190k-545k) that numerically overlaps the first source's range.
No live collision was found in a spot check, but the ranges overlapping at
all meant a real one was a matter of when, not if -- fixed before it could
silently skip a genuine new fact (mistaken for a duplicate of an unrelated
row from the other source) or conflate two unrelated filings on read.

**Mechanism, part two, found on the very first real run**: the Integrated
Filing list API (`api/integrated-filing-results`) is paginated, and its
`totalCount` field was used as the stopping bound for that pagination. Four
consecutive calls to page 1, seconds apart, returned `totalCount` values of
26765, 26765, 26765, then 26829 -- the dataset is live and mutating (new
filings and revisions arrive continuously), so `totalCount` is not a fixed
property of "the data" the way it would be for a static archive. The first
real backfill run stopped at exactly 3,000 of ~26,800 records, silently,
with no error -- some earlier page's response evidently reported a
`totalCount` at or below whatever `all_rows` had accumulated to at that
moment, and the loop treated that as "done."

**Status: fixed.** `load_facts_to_duckdb`'s existence check is now scoped
by `(source, seq_number)` together (new composite index added, old
single-column index kept). `fetch_all_integrated_filing_metadata`'s
stopping condition no longer trusts any single page's `totalCount` --  it
stops only when a page returns fewer rows than requested (the dataset
actually exhausted), with the largest `totalCount` ever observed kept only
as a 2x-margin runaway-loop safety net, not the primary signal. Both fixes
covered by regression tests (`tests/test_xbrl_parser_taxonomies.py`,
`tests/test_integrated_filing_nse.py`) before the real backfill was
re-run.

## Bug #6: a reused requests.Session can wedge solid after hundreds of successful requests, and only ConnectionError was ever treated as retryable

**Mechanism**: after the pagination fix (Bug #5), the real backfill ran
cleanly for 574 successful documents, then every single subsequent request
through that same `requests.Session` timed out (`ReadTimeout`, 20s) --  59
consecutive failures, zero successes, until the process was stopped. A
brand-new, session-less request to the exact same URL immediately
afterward succeeded in 0.4 seconds. This points at one dead connection
stuck in the session's connection pool (a keep-alive socket the remote
server silently closed, that `requests` kept trying to reuse rather than
detecting as dead), not a server-side block or rate limit -- confirmed,
not assumed, by the fresh request succeeding instantly against the same
host. Compounding this: the extraction script's exception handler only
special-cased `requests.exceptions.ConnectionError` for backoff; a
`ReadTimeout` (a different exception class) fell into the generic
`except Exception` branch, which logged it but never slowed the throttle
or took any recovery action -- so the script kept hammering the same
wedged session at full speed for the entire failure streak.

**General lesson, not just this instance**: this class of bug -- a pooled
connection or other reused stateful resource going silently bad after
sustained use -- is invisible at small scale. A five- or ten-request smoke
test of the fetcher passed cleanly every time this was tried; the wedge
only ever appeared after several hundred real requests in a row. "Worked
in the smoke test" was never going to be evidence this mechanism was
robust for a run of tens of thousands of requests, and it wasn't treated
as such after the fact -- but it's worth stating as a standing caution for
any future long-running script that reuses a connection, session, or
similar resource across many iterations.

**Status: fixed, and proven at scale, not just applied and hoped.** First
fix: `fundamentals_nse._session()` (shared by both the old and new
fetchers) mounts a `urllib3.Retry`-backed `HTTPAdapter` on both `http://`
and `https://`, so a connect/read failure drops the bad connection and
retries on a fresh one automatically; the backfill script's exception
handling was widened from `ConnectionError` to the broader
`requests.exceptions.RequestException` (covers timeouts too), plus a
session-rebuild safety net after consecutive failures. That first fix's
own retry settings (3 internal retries x 20s timeout) turned out to cost
~45s per failed attempt -- measured live after the wedge recurred, this
compounded to ~7.5 minutes of dead time per episode against a 10-failure
rebuild threshold, which projected to blow the run's completion-time
estimate. Tuned down to a single fast retry, a 10s timeout, and a 3-failure
rebuild threshold. The wedge recurred roughly a dozen more times over the
remainder of the ~26,700-document backfill; every recurrence resolved in
seconds via the tuned session rebuild, and the run completed cleanly
(26,598 of 26,690 scoped documents loaded, 99.66%). Confirmed fixed by
observed outcome across the full run, not just by the fix being applied.

## Bug #7: the fundamentals feed has the SAME stale-ISIN defect corporate_actions.py already fixed -- and the fix was never propagated

**This is, per this project's own count across it and its predecessor, the
FOURTH occurrence of the same meta-pattern: a fix applied where the bug was
first noticed, not everywhere the same pattern occurs.** Bug #2 already
needed its own gap-awareness fix applied independently to three different
factor modules rather than shared once. This is the same lesson one layer
up: `corporate_actions.py` established, and tested, that NSE's corporate-
actions feed's `isin` field cannot be trusted (`resolve_isin_for_actions`,
matching by symbol against this project's own price observations instead).
Nobody checked whether the OTHER NSE feed built around the same `isin`
field -- `corporates-financial-results`, i.e. every fundamentals fact in
this warehouse -- had the identical defect. It did.

**Mechanism**: confirmed live against NSE's API (2026-09-24). BHEL's
FY2024 annual filing (broadcast 2024-05-21) is tagged `isin=INE257A01018`
by the feed. This warehouse's own price data has never seen that ISIN
trade at all; BHEL's actual, currently-trading ISIN (the one in
`prices_eod`) is `INE257A01026` -- one NSDL serial ahead. Same pattern,
confirmed independently, for NATIONALUM, GRANULES, and AUROPHARMA. Since
`fundamentals_nse.py`'s `to_filings_df` trusted the feed's raw `isin`
field with no cross-check, every one of these companies' fundamentals
facts were ingested, correctly parsed, and then silently orphaned under an
ISIN that `isin_lineage`/`prices_eod` had no way to link -- not a lineage
transition (no predecessor/successor relationship exists; the old ISIN
simply never appears in this warehouse's price history at all, likely
predating 2016).

**Scope, measured directly, not assumed**: 200 of 2,487 distinct ISINs in
`fundamentals_filings` never matched `prices_eod` at all. 166 of those 200
(83%) resolve to a symbol that trades in this warehouse under a different
ISIN -- systemic, not a handful of edge cases. **Every fundamental factor
computed in Phase E (`run_phase_e_factors.py`) had been silently measured
on a universe missing these 166 companies** -- earnings_yield, P/E, P/S,
growth, margins, accruals, market_cap, and all five untestable
balance-sheet factors. Momentum was unaffected (price-only, never touches
this feed). The remaining 34 orphaned ISINs are genuinely unresolvable --
their symbol never appears in `prices_eod` at all (delisted pre-2016 or
otherwise out of this project's price universe), confirmed by the same
resolution attempt finding no observation to resolve against, not assumed
absent.

**Status: fixed, applied going forward, and retroactively corrected.**
`resolve_isin_for_filings` (`src/data_layer/fundamentals_nse.py`) ports
`resolve_isin_for_actions`'s exact mechanism -- point-in-time by (symbol,
known_date), never "symbol's current ISIN" (11.1% of symbols in this
project's own `isin_lineage` have mapped to more than one ISIN over time;
a naive current-ISIN join would misattribute an older filing to a
company's newer ISIN, the exact cross-period contamination this
document-parsing discipline exists to prevent elsewhere). Wired into both
backfill scripts (`backfill_fundamentals_quarterly.py`,
`backfill_fundamentals_annual.py`) as an opt-in parameter (`symbol_obs`,
default `None` preserves the old passthrough behavior so existing tests
that predate this fix are unaffected). Already-ingested data was corrected
in place by `scripts/fix_fundamentals_isin_resolution.py` -- a one-time
key-correction migration (UPDATE, not a new append-only row: this fixes
this project's own ingestion join key, not a company's disclosed number,
so the append-only philosophy protecting real-world restatements does not
apply here), scoped to the two legacy fact sources only. 12,255
`fundamentals_filings` rows and 226,715 `fundamentals_xbrl_facts` rows
corrected; verified afterward that exactly the 34 genuinely-unresolvable
ISINs remain orphaned, no more, no fewer.

**A second, distinct bug was caught before it reached the database**: the
migration script's first draft resolved isins correctly but then
reattached `seq_number` from the pre-resolution frame by positional
`.values` assignment -- since `resolve_isin_for_filings` sorts internally
by `known_date`, this silently misaligned rows once more than one symbol
was involved (a dry run surfaced it immediately: CLCIND's filings appeared
to "resolve" to BHEL's ISIN). Fixed by carrying every passenger column
(`seq_number`, a copy of the original isin) through the SAME function call
rather than reattaching them afterward by position -- a regression test
(`test_passenger_columns_stay_aligned_across_multiple_symbols`) locks this
in. Caught by dry-running against a read-only connection and sanity-checking
the output before any UPDATE touched the real database, not by inspecting
the code a second time and trusting it.

**Effect measured, not assumed** (`scripts/run_phase_e_factors.py`, full
old-vs-new comparison, pre-holdout only): every factor's `n_obs` and
per-date coverage increased (~30-43 more names per rebalance date on
average); `earnings_yield`'s raw t-stat moved from **+2.861 to +2.746** --
down, not up, and still SUGGESTIVE not established either way (Bonferroni/
BH threshold 0.00625 at m=8 tests; 0/8 factors survive correction before
and after this fix). This is a correction of the same already-reported
measurement, not a new finding, and does not change FINDINGS.md's
conclusion in either direction. Full comparison logged in `experiments.csv`.
