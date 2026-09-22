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

**Status: identified and quantified, not fixed.** No new corporate-action
subject patterns have been added to the parser. The three defensible fixes
-- (a) extend the parser to more action types, (b) exclude entities with an
unexplained transition-boundary jump from magnitude-sensitive calculations,
(c) both -- are not decided here.

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
