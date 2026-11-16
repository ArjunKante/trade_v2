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

**UPDATE, 2026-09-24: Bug #7 has a second face, confirmed but NOT YET
FIXED -- the fifth instance of the same meta-pattern, one layer earlier
than the first fix.** The stored-row correction above (`resolve_isin_for_
filings`, the retroactive migration) fixes facts that were fetched and
extracted under the wrong ISIN. It cannot create facts for documents that
were never fetched at all -- and `scripts/extract_quarterly_xbrl_facts.py`'s
own fetch list (`data/quarterly_xbrl_to_fetch_v2.csv`) was built by joining
fundamentals ISINs against `prices_eod` for a "price coverage only" scope
cut, the EXACT SAME join, using the EXACT SAME unreliable ISIN field, that
Bug #7's main fix already corrected for stored data. Confirmed directly:
of the 166 recovered companies' documents (5,596, one per (isin,
period_end), consolidated-preferred), 5,172 (92.5%) were never in either
fetch-scope CSV at all -- quarterly essentially 100% excluded (3,093 of
3,094), annual 67% excluded (871 of 1,294). As a fraction of the TOTAL
document universe Phase E's factors were actually computed on (56,485
fetched+extracted documents), this is **8.39% more that should exist and
doesn't** -- below the 15-20% threshold that would mandate a full
fundamentals-layer rerun, but well above "a few percent, cleanup only."
Verified this is fetch-scoping exclusion, not a separate extraction
failure: for every sampled company, whatever WAS in fetch scope was
extracted successfully (100% match, e.g. BHEL's 7 in-scope annual
documents = 7 extracted). Not fixed here -- re-fetching ~5,172 documents
from NSE is a real, multi-hour undertaking, and the decision of whether
it's worth it is not made in this entry. See `experiments.csv` for the
full verification.

**UPDATE, 2026-09-25: fixed, after one abandoned approach worth recording
in its own right.** First attempt: rebuild both fetch-scope CSVs from
scratch via `resolve_isin_for_filings`, on the theory that the whole
universe should simply be re-derived correctly. It produced ~27,000
"brand-new" documents across ~1,980 distinct ISINs -- an order of
magnitude more than the confirmed 166-company blast radius. Checked
against TCS, a company independently confirmed to have never had an ISIN
issue at all: **TCS still gained 2 phantom "new" periods under the
reconstruction.** That is a decisive signal, not noise to average away --
if a confirmed-clean company changes under the "fix," the fix does not
match the thing it replaces. The reason: this project never committed the
script that generated the original two CSVs (see the new entry below) --
only their output survived -- so there is no way to verify a full
reconstruction's exact boundary/tie-break behavior against 2,300+ companies
whose original inclusion decisions cannot be re-derived with confidence.

**The general lesson, not just this instance: a fix that cannot be
verified against the thing it replaces should be narrowed to the confirmed
blast radius, not generalised.** Reverted both CSVs from backup and took
the disciplined path instead -- `scripts/build_xbrl_fetch_scope.py` touches
*only* the 166 confirmed-affected ISINs (whose rows are proven entirely
absent from the existing CSVs, so there is no existing behavior to
diverge from), and leaves every other company's entries byte-for-byte
untouched. Added 5,424 documents (4,096 quarterly + 1,328 annual), 4,984
not yet extracted; a further 745 documents were already correctly in
scope but never fetched (a separate, pre-existing, unrelated backlog --
not part of this bug, refetched anyway since the marginal cost is small).

**ETA used the Bug #4 lesson, not the naive throttle arithmetic.** 5,729
documents at the 0.33s throttle alone suggests ~31 minutes; this project
already measured (Bug #4) that the throttle sleep is not the real
per-document cost -- with session reuse and the seq_number index, the
real rate is ~0.487s/document, giving ~46-50 minutes. Planned and reported
against the realistic number, not the optimistic one, before starting.

**A second, self-inflicted bug caught the first time the corrected CSVs
were actually run, not before.** `build_xbrl_fetch_scope.py`'s first
version wrote the newly-appended rows' `period_end`/`known_date` as full
timestamps ("2020-09-30 00:00:00") while every existing row in the CSV was
a plain date ("2020-09-30"). That mixed format made `pandas.read_csv(...,
parse_dates=[...])` silently fall back to leaving the WHOLE column as
strings rather than raising -- and `extract_quarterly_xbrl_facts.py`'s
`row["period_end"].date()` then failed with a bare `AttributeError`,
caught by the script's own blanket `except Exception: n_err += 1` with no
message at all. Observed live: 171 consecutive attempts, 0 successes,
before this was noticed and the run stopped. Fixed by writing both new and
old rows through the identical `%Y-%m-%d` string format, verified by
re-reading the CSV the same way the extraction scripts do and asserting a
real datetime dtype came back -- not by re-reading the code and trusting
it. Worth naming plainly: a broad `except Exception` with only a counter,
no captured message, turned a one-line formatting bug into a silent,
total failure that looked identical to a slow-but-working run for as long
as nobody stopped to look inside the CSV.

**UPDATE, 2026-09-25: refetch complete, both faces of Bug #7 now fixed.**
Quarterly 4,232 ok / 431 errors (of 4,663 attempted); annual 573 ok / 493
errors (of 1,066 attempted). Failures cluster cleanly: the 745-document
pre-existing backlog (unrelated to this bug) succeeded only 337 times
(45%) -- consistent with those being genuinely dead links, plausibly why
they were never fetched historically -- while the 166-company new-scope
block succeeded 4,475 of 4,984 times (89.8%), a normal-ish rate. Phase E
rerun: `earnings_yield`'s raw t moved from 2.746 to **2.833** (up, back
toward -- not past -- the original pre-Bug-7 value of 2.861), n_obs
29,745 -> 31,808. Multiple-comparisons conclusion unchanged: 0/8
Bonferroni, 0/8 BH survive. Screener funnel: 147->114->74->**47**
survivors (was 43); 9 of the 36 remaining INSUFFICIENT DATA names got a
real verdict (4 PASS, 5 FAIL). Full comparison table in `experiments.csv`
-- reported there deliberately without interpreting the direction of the
earnings_yield move, per instruction, since recovering 166 large,
established companies could plausibly move it either way and deserves
scrutiny before being read as a result.

**This is a recurrence of the same meta-pattern: a fix applied where the bug
was first noticed, not everywhere the same pattern occurs** (recurrence
count maintained in `OPERATIONS.md`'s own standing-rule entry; see Bugs #2,
#7, #9, #12, #18 -- *updated 2026-11-07; this previously hardcoded "FOURTH
occurrence," accurate when written, stale once Bugs #9/#12/#18 were later
found*). Bug #2 already
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

**A second, distinct bug was caught before it reached the database -- and
it is worth stating plainly what kind of bug it was: a fix can recreate
the bug it fixes.** The migration script's first draft resolved isins
correctly but then reattached `seq_number` from the pre-resolution frame
by positional `.values` assignment -- since `resolve_isin_for_filings`
sorts internally by `known_date`, this silently misaligned rows once more
than one symbol was involved (a dry run surfaced it immediately: CLCIND's
filings appeared to "resolve" to BHEL's ISIN). That is the precise
cross-company contamination the ISIN-from-document-body-parsing discipline
exists to prevent in the first place, reintroduced by a one-line alignment
error inside the very fix meant to eliminate it. Fixed by carrying every
passenger column (`seq_number`, a copy of the original isin) through the
SAME function call rather than reattaching them afterward by position -- a
regression test (`test_passenger_columns_stay_aligned_across_multiple_
symbols`) locks this in. Caught by dry-running against a read-only
connection and sanity-checking the output before any UPDATE touched the
real database, not by inspecting the code a second time and trusting it.

**Effect measured, not assumed** (`scripts/run_phase_e_factors.py`, full
old-vs-new comparison, pre-holdout only): every factor's `n_obs` and
per-date coverage increased (~30-43 more names per rebalance date on
average); `earnings_yield`'s raw t-stat moved from **+2.861 to +2.746** --
down, not up, and still SUGGESTIVE not established either way (Bonferroni/
BH threshold 0.00625 at m=8 tests; 0/8 factors survive correction before
and after this fix). This is a correction of the same already-reported
measurement, not a new finding, and does not change FINDINGS.md's
conclusion in either direction. Full comparison logged in `experiments.csv`.

## Bug #8: the fetch-scope generator scripts were never committed -- a reproducibility gap, not a data-correctness bug

**Mechanism**: `data/quarterly_xbrl_to_fetch_v2.csv` and `data/annual_xbrl_
to_fetch.csv` -- the documents this project decided were worth fetching,
the artifacts Bug #7's second face turned out to hinge on -- were produced
by a script that was run once, interactively, and never committed. Only
its output survived. Discovered while investigating Bug #7's fetch-scoping
face: there was no way to inspect, rerun, or verify the original scoping
logic against anything -- the only evidence of what it did was inference
from its output's behavior (confirmed via cross-referencing specific
companies), and even that inference was later shown to be incomplete when
a full reconstruction attempt diverged from the original for companies
with no known ISIN issue at all (see Bug #7's update above, the TCS check).

**Why this matters beyond the one incident**: this project's own stated
discipline is that every step should be re-derivable -- data is fetched by
committed scripts, facts are extracted by committed scripts, factors are
computed by committed scripts, every one of them checked into this
repository specifically so a decision or a number can be traced back to
the code that produced it. A step whose logic exists only as a historical
CSV breaks that chain silently: nothing failed loudly, nothing looked
wrong, until a different bug's investigation happened to need to inspect
this one step's exact behavior and found there was nothing to inspect.

**Status: the immediate instance is now moot** (the CSVs have been
superseded by `scripts/build_xbrl_fetch_scope.py`'s narrower, committed,
rerunnable addition -- see Bug #7), but the general defect is not
fixed: nothing currently prevents a future one-off script from being run
directly against the warehouse without being committed first. No
enforcement mechanism proposed here (this entry records the defect, not a
fix for the general case) -- worth deciding deliberately rather than
assuming committing every script is automatically enforced by habit alone,
since it evidently was not, at least once already.

## Bug #9: the annual dedup rule picked a registration without ever checking it resolves -- the same class of defect as Bug #7's ISIN join

**The defect is the selection rule itself, not the fetcher.** Diagnosing
the 493 annual extraction failures (experiments.csv, 2026-09-25) found
that `_pick_pit_series`' consolidated-preferred, latest-known_date
tie-break -- used unmodified by `build_xbrl_fetch_scope.py` to decide
which of several duplicate registrations to fetch for a given (isin,
period_end) -- has no way to know that its pick is a dead resubmission
until the fetch actually 404s. It selects on metadata (consolidated flag,
known_date) that was never checked against whether the URL it points to
still exists. That is structurally the same mistake as Bug #7: a decision
made by trusting a field's value instead of verifying it against reality
(there, the feed's isin; here, which duplicate registration is live).

**Mechanism, confirmed live**: NSE re-registered a batch of FY2018-2019
Consolidated annual filings under new seq_numbers (mostly `_WEB_2`-suffixed
URLs) at some point after original filing; the resubmission URLs are now
dead, while the ORIGINAL registration (frequently filed as Non-
Consolidated) remains live. The dedup rule, preferring Consolidated and
then latest known_date, reliably picked the dead resubmission every time
one existed, with no check that it actually resolved.

**The 2018-2019 clustering (95 of 96 flagged switches) has an external
explanation, not one in this project's own logic.** It lines up with a
real NSE-side event -- a batch re-registration of that vintage's
Consolidated annual filings -- not with anything specific to how this
project's dedup or extraction code behaves. Worth stating plainly rather
than leaving it looking like a pattern this project introduced: the
defect is that the dedup never checked its pick resolved, full stop; which
specific years got hit by that defect is downstream of NSE's own history,
not evidence of a second, separate problem in this code.

**Fixed, bounded to the 175 real-URL failures already identified** (the
other 318 of 493 are placeholder URLs with no document at all -- untouched,
correctly permanent) via `scripts/recover_annual_dead_duplicates.py`:
before giving up on a picked seq_number, try a live same-(isin,
period_end,consolidated) sibling first (no basis change); if none
resolves, try a live sibling of the OTHER consolidated type and flag the
substitution explicitly (`data/annual_basis_switch_log.csv`) -- never a
silent basis change, per instruction. Results: 1 recovered via a live
same-type sibling, 96 recovered via a flagged basis switch (95 of 96
Consolidated-dead/Non-Consolidated-live, 1 the reverse), 78 confirmed
genuinely dead under every variant tried (no fix possible). 91 distinct
companies now carry exactly one (86) or two (5) explicitly-flagged
single-period basis switches in their otherwise-Consolidated series --
accepted as-is, since a flagged single-period standalone is the stated
acceptable outcome; none are silent.

**Zero effect on Phase E or the screener, confirmed by rerunning both, not
assumed**: every one of the 97 recovered documents has `period_end` in
2018-2019 (96) or 2021 (1) -- none in FY2023+, the only window this
project's own balance-sheet analysis uses (`BS_START` in the screener,
the "2023 onward" filter in Phase E), because of the same coverage cliff
FUNDAMENTALS.md already documents. The fix is real and correctly scoped,
but it recovers a vintage of data nothing downstream currently reads. Both
reruns produced byte-identical output to the pre-fix run. This is not a
wasted fix -- the data is now correctly in the warehouse for any future
analysis that looks earlier than FY2023 -- but it settles nothing about
the current screener list or Phase E's numbers, and should not be
mistaken for having done so. "Byte-identical, confirmed by rerunning" and
"this shouldn't change anything" are different claims; this entry makes
the first one, not the second.

**The general shape, stated once so it is findable independent of either
instance: a scoping step that selects a registration without checking it
resolves is the same class of defect as an unresolved feed-identifier
join -- a selection made on metadata that was never validated against
reality.** Bug #7's ISIN join and this dedup rule are both instances of
that shape (recurrence count maintained in `OPERATIONS.md`'s own
standing-rule entry; see Bugs #2, #7, #9, #12, #18 -- *updated 2026-11-07;
this previously hardcoded "two instances... now," accurate at the time,
stale once Bugs #12/#18 were later found*), not two unrelated bugs that
happen to rhyme. Anywhere else
in this project a selection is made from several candidates by metadata
alone (a preference order, a recency rule, a type filter) is worth reading
with this shape in mind before the next one is found the hard way.

## Bug #10: resolve_isin_for_filings ported a direction preference that was correct in its source context and wrong in this one

**A different failure shape from the fix-not-propagated instances already
on record** (recurrence count maintained in `OPERATIONS.md`'s own
standing-rule entry; see Bugs #2, #7, #9, #12, #18 -- *updated 2026-11-07;
this previously hardcoded "five... already on record," accurate at the
time (and itself a useful later cross-check -- see Bug #7's own
annotation above), stale once Bugs #12/#18 were later found*) -- not "the
fix wasn't applied everywhere the bug
occurs," but "the fix was applied everywhere, and carried an unexamined
assumption into a place it didn't hold." `resolve_isin_for_filings`
(Bug #7) copied `resolve_isin_for_actions`' FORWARD-preferred merge_asof
direction wholesale. Forward-preference is correct for corporate actions
because an action's `ex_date` structurally anchors at the ISIN transition
-- the action *causes* the change, so searching forward from it naturally
lands on the post-action ISIN. A filing's `known_date` has no such
relationship to any ISIN change; it is just "when this became public."
Applying the same preference there meant: a filing whose `known_date`
falls inside the calendar gap between an old ISIN's last trade and a new
ISIN's first got resolved to the NEW isin -- an identity that did not
exist yet at the time the filing was made public.

**Confirmed live, not theorized**: BURNPUR's old ISIN last traded
2025-01-29; its new ISIN didn't start trading until 2026-08-11, a 559-day
gap. Two real filings (known 2025-02-10, 2025-03-11) and four of
SUMEETINDS' fall inside their respective gaps. Scanned all 390 lineage
transitions in `isin_lineage`; exactly these 6 filing rows, across these
2 symbols, were affected -- confirmed, not assumed, by an exhaustive
check, not a sample.

**The error direction this shipped with was conservative, and that was
luck, not design.** A misattributed filing vanished from every as-of
query for the gap window and reappeared late, rather than becoming
visible before it should have -- not a lookahead. The same directional
mismatch in a context where the wrong preference resolves a document
EARLY instead of late would have been a genuine leak, and nothing about
how this bug was written would have prevented that version of it.

**General lesson**: when porting logic between contexts, re-derive the
ASSUMPTIONS the logic depends on, not just the code that implements it.
An assumption that holds in the source context does not automatically
travel with the function.

**Fixed**: swapped to backward-preferred (resolve to whichever ISIN was
actually trading as of `known_date`), forward only as a fallback when no
prior observation exists at all (a company's very first filing, pre-dating
this warehouse's price history for it) -- matching every other
point-in-time convention already in this codebase (`known_date <= as_of`,
`build_entity_resolver`, `guard_date_range`). Two new regression tests
(BURNPUR's real case; the forward-fallback case), 8/8 pass in
`test_fundamentals_isin_resolution.py`, 118/118 project tests pass.
Re-scanned all 390 lineage transitions with the fixed function: **0
misattributions remain**, confirmed exhaustively.

**No retroactive data correction was needed**: BURNPUR's and SUMEETINDS'
stored `fundamentals_filings.isin` values were never actually corrupted --
neither symbol was among Bug #7's 166 orphaned companies, so neither the
migration script nor `build_xbrl_fetch_scope.py` ever passed their rows
through the buggy function. The bug was live only in the code path, not
yet in the database; the fix closes it before it could reach stored data
on a future backfill re-run.

**Screener output confirmed unchanged, not assumed**: reran
`run_fundamental_screener.py` after the fix; its output is **byte-for-byte
identical** to the pre-fix run (`diff`, zero output). Phase E was not
rerun, per instruction -- 6 observations against tens of thousands would
not move a reported number, and neither affected symbol reaches the
screener's universe.

## Bug #11: a same-ISIN corporate action is unguarded anywhere in this codebase -- a new bug shape, not another instance of Bug #1

**Found via the swing project's Phase 3 backtest** (a separate research
module, `src/swing/`), while sanity-checking the single worst trade in a
4,346-trade distribution, not by a test or a proactive audit.

**Mechanism, and why it is NOT Bug #1 recurring**: `lineage_jump_guard.py`
(Bug #1's fix) detects a large, unexplained price ratio at the boundary
between an ISIN and its LINEAGE SUCCESSOR -- it structurally cannot see a
jump that happens within a single ISIN's own continuous row sequence,
because that isn't a lineage transition at all. MAJESCO
(`INE898S01029`) collapsed from ~985 to ~12.2 between 2020-12-22 and
2020-12-23 -- the real December 2020 Majesco demerger -- on the SAME isin
throughout. `adjustment_factors.factor` stays flat 1.0 across the
collapse and `corporate_actions` has zero rows for this isin at all.
Same underlying mechanism as Bug #1 (a real corporate action the
bonus/split-only parser cannot capture), but a structurally different
gap in the DEFENSE, not a failure to propagate an existing one -- there
was never a guard checking within-ISIN consecutive-row jumps at all.

**Detector built and tested**: `src/data_layer/same_isin_jump_guard.py`
(`find_unexplained_same_isin_jumps`, `unexplained_same_isin_jump_entities`),
mirroring `lineage_jump_guard.py`'s own ratio/explanation-window
convention (RATIO_HIGH=1.5, EXPLANATION_WINDOW_DAYS=10) for consistency.
4 tests in `tests/test_same_isin_jump_guard.py`, all passing.

**Full-warehouse scan result, and the nuance that matters**: 1,345 rows
exceed the ratio threshold with no nearby `corporate_actions` record.
1,057 of those have a >5-day calendar gap to the prior row -- these are
NOT part of this bug's blast radius, because every factor computation in
this codebase (`factors.momentum`, `factors.lowvol`, `factors.target`)
already NaNs out any window containing a >`STALE_GAP_DAYS` gap; a jump
across a multi-month halt was already guarded, just for a different
reason (calendar-gap unreliability, not a missing-adjustment claim).

**The remaining 288 rows (gap <= 5 days, 78 distinct entities) are the
real, previously-unguarded blast radius -- and even within that set, not
all 78 are the same finding**: 5 symbols (VISESHINFO, UVSL, BIRLACOT,
VKSPL, KSERASERA) contribute 208 of the 288 rows via an exact-ratio
(2.0x / 0.5x) pattern repeating dozens of times each -- almost certainly a
thin/illiquid-pricing artifact, a DIFFERENT mechanism from a missed
corporate action, not individually diagnosed here. The remaining 73
entities have 1-2 flagged rows each, consistent with one-off events --
spot-checking a handful found a mix of (a) real, well-documented market
crashes needing no adjustment at all (YES Bank's March 2020 AT1
write-off crash, Jet Airways' 2019 insolvency slide -- a genuine crash is
not a data error), and (b) plausible missed splits/bonuses on names with
**zero** `corporate_actions` coverage at all (JSWSTEEL, GRASIM, TRENT,
KAJARIACER -- ratios close to common split factors like 1/2, 1/5, 1/10).
**Not individually verified one by one** -- reported as a structural
finding with this nuance stated, not as "78 confirmed bugs."

**Impact on the swing backtest this was found through**: excluding all 78
entities moved the strategy's own mean gross return from 0.792% to
0.793% and its percentile in a random-entry null distribution from 9.0 to
9.8 -- i.e., **this contamination was not material to that particular
finding**, checked directly rather than assumed. That does not make the
underlying gap unimportant: `adjustment_factors`/`corporate_actions`
coverage gaps of this shape would affect the MAIN momentum project's own
`momentum_12_1`, `trailing_vol_252`, and forward-return target computations
identically, for any of these same entities that entered THAT project's
universe at the wrong time -- not checked here, flagged for a decision.

**Not fixed.** This entry records the detector, the scan, and the
quantified impact on the one place it was found to matter; it does not
correct any stored data, thread the new detector through
`factors.momentum`/`factors.lowvol`/`factors.target` the way
`lineage_jump_guard` already is, or re-run the main project's Phase
E/Study 1/2 numbers.

**Correction to the initial plan for the sibling `trade-info` project**:
checked before writing anything there, per this project's own "verify
before act" discipline -- `trade-info` is NOT missing this defense.
`src/nsepit/quality.py`'s `PriceDiscontinuity` detector (classifications
`split_like` / `extreme_outlier` / `stale_resumed`) already exists there,
already uses the same `STALE_GAP_DAYS=5` convention, and its own
docstring cites the identical real case this session independently
re-found in `trade-new`'s data (`INE784B01035`/WINSOME, a multi-year gap
misread as a 38x single-day move) -- confirming this pattern was already
known and handled in that project before this session started. It is
referenced from `bulk_ingest.py`, `isin_lineage.py`, `analysis.py`, and
`fresh_data.py`, i.e. wired into the pipeline, not dead code -- not
independently confirmed whether every downstream computation there
actually excludes flagged rows the way `trade-new`'s factor modules
consume `unexplained_jump_dates`, but there is no unaddressed gap of the
kind assumed when this bug was first found. No entry was added to
`trade-info`'s `DESIGN.md`; reported to the user instead of guessing.

**UPDATE, 2026-09-27: grep-for-siblings, prompted by building the
momentum-persistence monitor (`src/monitor/persistence.py`).** The
monitor's own reference script (`scripts/run_momentum_persistence_regime_
count.py`) was found NOT applying this exclusion despite being asked to
apply it -- fixed there and in the monitor's other two entry points
(`scripts/run_momentum_persistence_monitor.py`, `src/monitor/web.py`),
now sharing one `same_isin_jump_excluded_entities()` helper. Checked
further, per instruction: **seven other scripts in this project compute
cross-sectional persistence or rank IC without this exclusion** --
`scripts/run_phase_e_factors.py`, `run_factor_ic_report.py`,
`run_phase2_diagnostics.py`, `run_ey_momentum_diagnostic.py`,
`run_combination_ic_power_analysis.py`, `run_concentration_diagnostic.py`,
`run_lineage_jump_fix_impact.py`. All predate this bug's discovery (found
later, via the swing project) and feed already-published results in
`FINDINGS.md`/`FUNDAMENTALS.md` -- **not retroactively recomputed here**,
consistent with this entry's own original "not fixed" scope (excluding
78 entities moved the one number checked, the swing backtest's headline
percentile, by 0.9 points; whether it would move any of these seven
scripts' own published numbers, and whether any of them are worth
re-running, is not decided by this update). Recorded so the blast radius
already anticipated in this entry's own text ("would affect the MAIN
momentum project's own... computations... not checked there") is now a
concrete, named list instead of a general worry.

**UPDATE, 2026-10-11: fixed in src/fibo/ -- the SIXTH instance of "fixed
where noticed, not everywhere the pattern recurs."** `src/fibo/` (the
Fibonacci/ORB intraday project, including the 188-trade sealed test) had
NEITHER this guard NOR Bug #1's (`lineage_jump_guard`) anywhere, and
`src/fibo/indicators.py:88`'s `true_range` used a raw, row-based
`prev_close = shift(1)` -- Bug #2's exact shape, also unguarded. All three
built on `prices_eod`/`adjustment_factors`, the same tables every other
instance of this meta-pattern touches.

Blast-radius check FIRST, per instruction, before any fix: ran both
detectors (full warehouse history) plus a new >5-calendar-day stale-gap
scan against all 130 entities traded across the 188 sealed-test + 67
dev-window trades. Coarse bound (entity has a flagged defect anywhere in
its history): 40 of 255 trades. Tight bound (the flagged date falls
inside THAT trade's own swing-low-to-swing-high computation window):
**0 of 255** -- checked directly, not estimated. This does not certify
the ATR series clean in general: the detectors only catch jumps outside
[0.667, 1.5] with no nearby corporate-action record, and gaps over 5
calendar days -- a smaller, unflagged distortion would not be caught by
this same check.

Fixed: `src/fibo/jump_guard.py` (new -- imports both existing detectors,
reimplements neither, merges their output into one `entity_id -> dates`
dict), threaded through `true_range`/`atr` (now gap-aware the same way
`factors/lowvol.py` already is, including a NaN-input carry-forward fix
to `_smma` so a flagged row pauses Wilder's recursive ATR for one step
instead of corrupting it forever) and `most_recent_confirmed_swing`, then
wired into every real caller: `scripts/fibo_test_backtest.py`,
`scripts/fibo_step5_backtest.py`, `scripts/fibo_open_diagnostic_backtest.py`,
and `src/fibo_live/watchlist.py` (the live paper-trading system).
Regression tests added to `tests/test_fibo_indicators.py` (4 new cases,
including a synthetic gap inside the ATR window asserting the fix does
not chain a NaN across it).

**Re-run and verified, per instruction, not assumed**: the sealed 188-trade
list is byte-identical, every column, confirming the blast-radius finding.
The live evening watchlist for 2026-10-08 (the basis for 2026-10-09's
morning run) reproduces the identical 6 qualifying stocks with identical
zone/ATR/swing values to full precision. The 67-trade dev-window list
could NOT be directly re-verified this way -- re-running it today returns
278 trades, not 67, because `fibo_intraday.duckdb`'s dev-window (2016-2022)
intraday coverage grew from 81 to 280 entities between the original
2026-09-29 run and now (`fetch_log_intraday` shows downloads continuing
through 2026-10-01, after that run), unrelated to this fix -- confirmed by
re-running with the fix OFF against today's same, grown archive: also 278
trades, identical set, zero difference attributable to the fix. The
sealed window's own intraday archive did not grow over the same period
(304 entities, unchanged). Flagged as a separate, pre-existing
reproducibility gap in `scripts/fibo_step5_backtest.py` (it reads
`bars_1min` live rather than from a frozen, versioned snapshot) --
not investigated or resolved here, and `data/fibo_step5_dev_results.pkl`
was restored to its original 67-trade state rather than left at the
newer, differently-sourced 278.

## Bug #12: the pre-registered fundamentals-screener risk filter was never applied in any swing candidate-count or backtest run -- the same class as Bug #7 (a spec assumed a capability the actual join/computation did not have)

**Found while specifying the Phase 3 decomposition diagnostic**, checking
`PREREGISTRATION_SWING.md`'s Universe section against what the code that
actually produced every reported swing number does -- not by a test or a
proactive audit.

**Confirmed directly, not assumed**: `PREREGISTRATION_SWING.md`'s
"Universe" section, condition 5, freezes `fundamental_screener.py`'s
verdict != FAIL as a risk filter, applied to every candidate before
conditions (a)-(c). Neither `scripts/run_swing_phase2_candidate_counts.py`
(the candidate-count funnel) nor `scripts/run_swing_phase3_backtest.py` /
`run_swing_phase3_clean_rerun.py` (the frozen-rule backtest, including the
headline 9.0th/9.8th-percentile finding) reference
`fundamental_screener` at all -- both funnels are built from exactly
`momentum ∩ liquidity → bottom-tercile-5d → volume + regime`, four
conditions, not the five the pre-registration document freezes. This is
not a silent omission at the code level: `src/swing/universe.py`'s module
docstring and the Phase 2 script's own header both state the condition is
"OMITTED" and explain why (see mechanism below) -- but that flag never
made it back into `PREREGISTRATION_SWING.md` itself or into `SWING.md`'s
Phase 2/Phase 3 narrative sections, so a reader of either of those two
documents' headline claims (the candidate-count table, the 9.8th-
percentile finding) would not know condition 5 never ran. Every
"the frozen rule" / "the full three-condition rule" claim in this
project's swing work to date is actually a four-condition rule.

**Mechanism, and why it is the same class as Bug #7**: Bug #7 was a spec
(the fetch-scope join) built on a field that was reliable in one context
and silently wrong in another. Here, the pre-registration named a
screener that exists and runs correctly for its own stated purpose (a
CURRENT, as-of-today shortlist tool -- see `fundamental_screener.py`'s own
docstring) but was never built to answer the question the swing rule
actually needs: a verdict AT EVERY HISTORICAL CANDIDATE DATE across nine
years. `compute_liquidity_tercile`/`load_current_price_panel`
(`fundamental_screener.py`) and the P&L/balance-sheet checks it calls are
all "as of the latest available date" by construction, not point-in-time
historical. The pre-registration document assumed a capability (a
historical, point-in-time screener series) that the named module does not
provide, the same shape of gap as Bug #7's join assuming a field was
point-in-time-reliable when it was not.

**Impact, scoped honestly**: this is an omitted RISK filter (per the
pre-registration, "never as ranking input, never as a substitute for
conditions (a)-(c)"), not a ranking or signal computation -- so it does
not by itself explain the headline worse-than-random finding (Phase 3's
9.8th percentile is measured on the four-condition rule against a
matched-random null drawn from the SAME four-condition candidate pool,
so the missing fifth condition is common to both the strategy and its
own benchmark and does not bias that specific comparison). Its actual
effect is unmeasured: adding it back would shrink the candidate pool by
however much the screener's cash-flow-quality checks remove (measured at
one point in time, `fundamental_screener.py`'s own diagnostics: funnel
147->119->81->43 on the 2026-09-23 run), and that could move the
backtest's result in either direction, not necessarily toward viability --
per that module's own docstring, the screen is untested in either
direction and is known to remove some historically-strong momentum
turnaround names along with the genuinely weak ones.

**Not fixed here.** Building a point-in-time historical version of
`fundamental_screener.py`'s checks (quarterly-lagged fiscal points,
known-date-gated, evaluated as of each of nine years of candidate dates
rather than once as-of-today) is a separate undertaking -- flagged as an
open item in `src/swing/universe.py`'s docstring before this bug was
logged, not attempted as a shortcut inside this diagnostic. This entry
exists so the gap is recorded in the same place every other spec-vs-
implementation gap in this project is recorded, rather than left as a
comment only the module's own docstring reader would find.

## Bug #13: daily ingestion silently stopped for 13 trading days -- a process failure, not a code defect

**This is NOT a code bug.** Every function involved -- the bhavcopy
fetcher, `factors.momentum`'s own internal gap guard, the Fibo evening
job's indicator computation -- behaved exactly as designed, on the inputs
it was actually given. The failure was that nobody, and nothing, was
watching whether those inputs were current.

**Mechanism**: `prices_eod` has zero rows, and `fetch_log` has zero
entries of ANY status, for 2026-09-19 through 2026-10-07 -- 13 NSE trading
days. Not "no_data" (a logged holiday check), not "error" -- simply never
attempted. This project has no scheduled ingestion runner of any kind
(checked: no cron entry, no Windows Task Scheduler entry, no CI workflow
anywhere in this repo) -- `RUNBOOK.md` documents ingestion/backfill as a
manual step, and it always has been. For three weeks, nobody ran it.

**How it surfaced**: a Fibo live paper-trading evening job run on
2026-10-08 fetched that one day's bhavcopy (the next day the pipeline
happened to be run again) and computed that night's watchlist from the
full daily panel, including the 13-day hole immediately before it. Separately,
`scripts/serve_screener.py` crashed starting the screener web app:
`compute_momentum_universe` returned zero rows, because
`factors.momentum`'s own `STALE_GAP_DAYS` guard correctly NaN's any
momentum value whose lookback window contains a >5-day gap -- and the
13-day hole sat inside *every* currently-active entity's window. The crash
was in a UI route several layers away from the actual problem; the gap
guard that caught it was never designed as a freshness alarm, it just
happened to trip one by coincidence.

**Effect measured, not assumed**: re-running the Fibo evening job after
backfilling the gap produced a DIFFERENT 6-stock watchlist than the one
computed on the gapped panel -- only 2 of the original 6 names
(MEESHO, LAURUSLABS) survived, and MEESHO's own golden zone moved from
[180.43, 186.59] to [200.71, 209.12], roughly an **11% shift**. Had the
Fibo evening job been the only thing run that night -- no screener, no
momentum, nothing to trip the coincidental NaN guard -- it would have
produced this same wrong, plausible-looking watchlist with no error
anywhere, and it would have been traded on the next morning.

**Status: fixed with a guard, not a scheduled job.** A scheduler can fail
silently too -- this one had no scheduler to fail, and still went
undetected for three weeks. `src/data_layer/staleness.py::
assert_data_current` is a single shared check (latest `prices_eod` trade
date within `max_staleness_days` (default 3, one trading day plus a long
weekend) of today) that every entry point reading the price panel now
calls before computing anything: the Fibo evening job
(`scripts/fibo_evening.py`, checked before its own fetch, and again inside
`src/fibo_live/watchlist.py::build_watchlist`), the momentum universe
(`src/reports/fundamental_snapshot.py::compute_momentum_universe`), the
screener (`src/reports/fundamental_screener.py::run_screener`), and the
persistence monitor (`src/monitor/web.py::build_monitor_payload`). A stale
panel now raises `StaleDataError` with the gap size stated in the message,
at the point where it would otherwise turn directly into a wrong result --
not fixed by remembering to run ingestion on time, which is exactly the
thing that already failed once. Regression test fixes this incident's own
13-day gap as the test fixture: `tests/test_staleness.py::
test_the_actual_13_day_gap_incident_is_refused`.

## Bug #14: Fibo backtest universe was defined by data availability, not specification -- the sealed test's 188 trades were stable by luck

**Found while verifying the Bug #11 propagation fix above**: re-running
`fibo_step5_backtest.py` (dev, pre-registered top-50 universe) returned 278
trades, not the documented 67. Root cause traced, not assumed: the script
built its entity list from `SELECT DISTINCT entity_id, trade_date FROM
bars_1min` -- whatever had been downloaded -- and never filtered it against
`reconstitute_annually`'s own declared top-50 membership. `universe` was
computed and saved to the output pickle, but used only for nothing; no
code path ever checked an evaluated entity against it. Separately,
`scripts/fibo_download_intraday_top200.py`'s download plan spans
`DEV_START` (2016-10-04) to `FULL_END` (2026-09-18) for the band-51-200
"additional universe" -- it backfilled band 101-200 names across the ENTIRE
history, including the dev window, even though those names were never part
of the dev backtest's own top-50 specification. That backfill (confirmed
via `fetch_log_intraday`, downloads continuing through 2026-10-01) is what
grew the dev script's candidate pool from 81 to 280 entities and silently
changed its trade count on any rerun.

**`fibo_test_backtest.py` (sealed, top-200) has the IDENTICAL shape** --
`entities` likewise came from `bars_1min`, not filtered against
`universe`. It does tag every trade with `rank`/`band` afterward
(`rank_lookup.get(...)`, defaulting to `"unranked"`), but a tag is not a
filter -- an out-of-universe entity would still generate a counted trade,
merely labeled differently. Checked directly: of the 785 distinct (year,
entity) combinations actually evaluated in the current 188-trade sealed
result, **zero** fall outside the declared top-200 roster for their year,
and zero trades are tagged `"unranked"`. **This means Section 9's 188
trades were never protected by an enforced universe -- they were stable
only because the sealed window's own intraday archive happened not to
grow the same way the dev window's did.** Had the top-200 widening
campaign's download plan been scoped as loosely for the sealed window as
it was for the dev window, the 188-trade sealed result could have
silently changed on any rerun the same way the dev result did. Recorded
here as fact, not hypothetical: the mechanism that would have caused it is
confirmed, only the specific trigger (archive growth) did not happen to
fire for this window.

**`src/fibo_live/watchlist.py` (the live paper-trading system) does NOT
have this defect** -- checked, not assumed: `build_watchlist` derives
`entity_ids` directly from that year's `universe` membership and calls
`build_daily_ohlc_panel(con, entity_ids=entity_ids)` with that explicit
list -- it starts from the specification and queries data for it, rather
than starting from whatever data exists. This is the correct pattern the
backtest scripts should have used from the start.

**The SEVENTH instance of "fixed where noticed, not everywhere the
pattern recurs,"** and a different shape from the first six: not a missing
exclusion on a known-bad data point, but a missing boundary on which data
points are even eligible to be evaluated at all. Universe must be defined
by specification, never by data availability.

**Fixed with a FILTER and a separate GUARD, not three local patches**:
`src/fibo/universe.py` gained `effective_universe()` (handles the
documented first-reconstituted-year gap -- e.g. 2016 has no preceding year
to rank against -- by reusing the next available year's membership, the
same convention `build_download_plan` already used for this exact gap, now
centralized instead of each caller re-deriving it), `restrict_to_universe()`
(an inner join restricting any entity/year table to declared members), and
`assert_universe_membership()` (an independent guard, raises `ValueError`
loudly if anything about to be evaluated is still outside the declared
universe after filtering -- protects a FUTURE script that builds its
entity list some other way and forgets to filter, not just the three
scripts fixed today). Wired into `fibo_test_backtest.py`,
`fibo_step5_backtest.py` (with the stub-year handling), and
`fibo_open_diagnostic_backtest.py` (restricted to the wider top-200 bound,
since that script computes both top-100 and top-200 by design). 6 new
tests in `tests/test_fibo_universe.py`.

**Not yet re-run** -- the filter and guard are in place and the full test
suite passes (322/322), but per instruction this is reported before any
backtest is re-executed. Expected effect: the sealed 188-trade list should
be unchanged (zero violations found on inspection); the dev-window list
should return to something close to its original 67 once restricted back
to the declared top-50, though the exact count is not yet confirmed by an
actual run.

## Bug #15: a fetch made before a day's bhavcopy could possibly be published was cached as a permanent confirmed holiday -- "could not check" recorded as "checked, nothing there"

**Same class as FETCH_FAILED vs SETUP_OFF** (the recurring shape where "we
could not determine the outcome" and "we determined the outcome was
negative" collapse into one status, and the second, much stronger claim is
what gets persisted): `src/data_layer/prices_nse.py`'s `fetch_raw_zip`
raised the same `NoDataForDate` for every 404 from NSE's archive --
genuine holiday, weekend, or simply "not published yet" -- and
`load_bhavcopy_to_duckdb` recorded ALL three as `fetch_log.status = 'no_data'`,
which its own idempotency check then treats as permanent: once written,
no later call ever retries that `(source, trade_date)` again.

**Mechanism, confirmed live, not inferred**: `fetch_log` held
`(NSE_BHAVCOPY_UDIFF, 2026-10-09, 'no_data', attempted_at=2026-10-09 00:23:00)`
-- 23 minutes after midnight, hours before that day's market opens, let
alone before NSE publishes that evening's bhavcopy. A 404 at that moment
proves nothing about whether the day is a holiday; the file simply cannot
exist yet. The likely origin: `scripts/backfill_prices.py` walking forward
through dates and crossing midnight mid-run, so "today" rolled over to
2026-10-09 while it was still fetching, and it immediately tried (and
necessarily failed to get) that still-nonexistent day's bar. Re-fetched
live on 2026-10-11: HTTP 200, Content-Length 206,974 bytes, a complete
valid bhavcopy ZIP, 3,687 real data rows, every row's `TradDt=2026-10-09`
-- including MEESHO's low of 224.31, which matches the live ORB low the
Fibo morning job itself recorded that same day in `events.jsonl`. Cross-
checked against `data/raw/nse_cm_holidays.pkl` (NSE's official CM-segment
holiday master, fetched directly from NSE in an earlier phase, covering
2016-2026): 2026-10-09 is not in it. The day traded normally; only the
EOD bhavcopy fetch for it failed, at a moment it was guaranteed to fail.

**Effect measured, not assumed**: this silently punched a one-day hole in
`prices_eod` at exactly the boundary `scripts/fibo_evening.py`'s backward
search for "the latest trading day with data" needed to cross. Every
manual evening-job run over the following weekend walked back from
2026-10-11 (Sun) through 2026-10-10 (Sat) and 2026-10-09 (Fri) -- all
hitting the cached `no_data` with no real network call made -- straight to
2026-10-08 (Thu), and computed the 2026-10-12 (Mon) watchlist from that
stale, Friday-less panel. The result was silently wrong in the same way
Bug #13 describes: not a crash, a plausible-looking watchlist (6
qualifying names) that happened to be byte-for-byte identical to
2026-10-08's own watchlist, because it was built on the exact same data.
Recomputing from the panel through the real 2026-10-09 close raised that
to **10 qualifying names** -- KOTAKBANK, RBLBANK, MOTILALOFS, and
AUROPHARMA newly qualify on Friday's bar; none of the original 6 dropped
out, and their golden zones were unchanged. Had this gone untraded Monday
morning, four real setups would have been invisible to the paper-trading
system for no reason it could have reported.

**Status: fixed, stale row corrected, superseded runs annotated, not just
patched.** `src/data_layer/nse_holidays.py` (new) loads the holiday master
and exposes `is_nse_holiday(date)`, raising `HolidayCalendarMissing` --
never silently `False` -- for a year the master doesn't cover, the same
fail-safe stance `src/spread_monitor/trading_day.py` already takes for the
live equivalent check. `load_bhavcopy_to_duckdb` now only writes a
permanent `'no_data'` when `is_nse_holiday` CONFIRMS the date; every other
404 (including an unverifiable year) is logged `'error'` instead, which is
always retried on the next call rather than cached forever. The one stale
row this bug had already written could not be "corrected by appending" --
`fetch_log` has `PRIMARY KEY(source, trade_date)`, a current-status table,
not an append-only log -- so it was deleted and re-fetched through the
now-fixed normal path (`ok`, 2938 rows), with the before/after and full
reasoning recorded as an append-only `data_correction` event in
`events.jsonl` instead, since that log format actually supports it.
`scripts/fibo_evening.py`'s `already_has_watchlist_run` idempotency guard
was extended to ignore runs marked superseded by a new
`watchlist_run_correction` event, so the correction could produce a fresh
run for the same `target_trade_date` (2026-10-12) rather than being
refused as a false duplicate of the run it was replacing; both the
`target=2026-10-09` artifact and the stale Friday-less `target=2026-10-12`
run were annotated superseded this way, not deleted.

**Open item, not investigated tonight**: the same audit (every weekday
`no_data` row in `fetch_log` cross-checked against the holiday master)
found one more suspicious row -- `2016-06-20` (a Monday), source
`NSE_INDEX_CLOSE_ALL`, attempted 2026-09-19 during what looks like a
historical index-data backfill. Different table, different ingestion path
(`src/data_layer/index_nse.py`) from the bhavcopy fix above -- plausibly
the same conflation, not confirmed. Not fixed or even fetched live here;
flagged for whoever next touches index ingestion.

## Bug #16: the evening job's staleness guard ran BEFORE the fetch that would cure it -- a single missed run could never recover on its own

**Mechanism**: `scripts/fibo_evening.py` called `assert_data_current(con)`
-- the Bug #13 guard -- as the very first thing in `main()`, before
attempting to fetch anything. That guard compares real wall-clock "today"
against whatever the warehouse's latest ingested date already was. Found
live, 2026-10-12: the scheduled 18:30 run never fired (Bug #17, below),
so nobody fetched Monday's bhavcopy that evening. By the time the job
was run manually just after midnight into Tuesday, the gap between real
"today" (Tuesday) and the warehouse's latest date (the preceding Friday)
had grown to 4 calendar days -- past the guard's 3-day tolerance -- and
the job refused immediately, **before ever trying to fetch Monday**, the
one day that would have closed the gap on its own. The job could not
self-heal from a single missed evening; it needed a human to manually
ingest the missing day first.

**This inverts what the guard is for.** Bug #13's whole point is to stop
a computation from running on data that is missing because ingestion
genuinely stalled -- not to block the one fetch that would prove
ingestion hadn't stalled at all. A guard checked before the fetch can
never tell "a stalled feed" apart from "one missed evening, cured by
trying again" -- it treats both identically, and only the second one is
actually fixable by the job itself.

**Status: fixed.** The fetch (the existing backward-walk loop that finds
the latest trading day with published data) now runs unconditionally,
first. Staleness is checked AFTER, against the warehouse's state once
the fetch has had its chance to cure an ordinary gap -- immediately
before the computation (`build_watchlist`) that guard exists to protect,
not before the fetch that might make the guard's concern moot. A
genuinely stalled feed (the fetch finds nothing new) is still refused,
unchanged -- regression-tested directly:
`tests/test_fibo_evening_staleness_ordering.py::
test_missed_monday_evening_run_still_produces_tuesdays_watchlist`
reproduces the exact live scenario (warehouse ends Friday, job runs the
following Tuesday, Monday is fetchable) and fails against the
pre-fix ordering (confirmed by reverting the fix and re-running it:
`AssertionError: Monday 2026-10-12 was never fetched`), passes against
the fix;
`test_still_refuses_when_no_fetch_can_cure_the_gap` confirms the fix did
not turn the guard into a no-op -- a fetch that finds nothing new still
refuses.

**Checked, not assumed: the morning job does NOT have this bug.**
`scripts/fibo_morning.py` opens the warehouse with `get_read_connection`
(read-only) and never fetches bhavcopy itself anywhere in the script --
it only reads whatever the evening job already ingested. There is no
fetch step to reorder around; its staleness check correctly guards
against computing from a warehouse it has no means to refresh on its
own. Its dependency on the evening job having run is real, but it is not
this same ordering bug.

## Bug #17: the FiboEvening scheduled task was specified on 2026-10-09 but never actually created -- a manual setup step that silently did not happen

**Mechanism**: a Windows Task Scheduler entry for `scripts/fibo_evening.py`
(weekdays 18:30) was specified in detail on 2026-10-09 -- name, trigger,
battery/wake conditions, working directory -- as instructions for a
manual setup step. **The task was never actually created.** Found live,
2026-10-12: `data/fibo_live/scheduler.log` has no entry at all for 18:30
that evening (not a refusal, not an error -- nothing), and
`Get-ScheduledTask` confirmed no task named anything like "fibo" existed
on this machine, despite `scripts/snapshot_options_depth.py`'s own task
(`TradeNew_OptionsDepthTest`) existing and working. Every run of the
evening/morning jobs, this entire project, has been triggered manually.

**The same meta-pattern as Bug #13, one layer up**: Bug #13 found this
project had no scheduled ingestion runner of any kind, and a 13-day gap
went unnoticed for exactly that reason. A set of instructions for a
manual setup step is not different in kind from a manual ingestion
step -- both depend on a human remembering to do something with no
guard watching whether they actually did. Specifying the schedule
clearly is not the same as the schedule existing; nothing here checked
that the gap between "specified" and "created" had actually closed
until a missed run exposed it.

**Compounding effect**: because nothing fetched Monday's bhavcopy that
evening, by the time the job was run by hand after midnight the gap had
grown past the staleness guard's tolerance, triggering Bug #16 above as
a second, independent consequence of this same missed run.

**Status: fixed.** `FiboEvening` now exists
(`schtasks /create /tn FiboEvening /xml scripts/_fibo_evening_task.xml`),
weekdays 18:30, runs only when logged on (no password), runs on battery,
does not wake the machine, starts in `C:\projects\trade-new` -- verified
directly against the task's own registered settings
(`schtasks /query /tn FiboEvening /xml`), not just the creation command's
exit status. No scheduled task exists yet for `fibo_morning.py`;
flagged, not fixed here -- not asked for, and that script's own 09:15
market-open timing is less tolerant of the same "specified but not
created" gap going unnoticed, since a missed morning run has no
after-midnight catch-up equivalent to what cured this one.

## Bug #18: two different price-scale methods, never cross-checked against each other, used on the same signal day across POC, Liquidity, and the Fibo sealed test -- the exact failure `fibo.scale_probe` was built to retire, recurring in the one place that was never migrated

**Mechanism**: `fibo.scale_probe.probe_scale` was built (2026-09-29) to replace
a table-based method (`fibo.price_scale.get_adjustment_factor` /
`_build_adjustment_factor_lookup_for_entity`, reading `adjustment_factors`
directly) specifically because that table-based method's own dev-window
report showed 14.90% UNRESOLVED, concentrated in a handful of entities with
corporate actions invisible to or mis-recorded in this project's own
`corporate_actions` table. `box_theory` and `darvas` were built on, or
migrated to, `scale_probe` throughout -- confirmed by import trace, neither
module references `fibo.price_scale` or `adjustment_factors` at all.
**`poc.v4`, `liquidity.a/b/c`, and `fibo.backtest` (the sealed Fibo test)
were not fully migrated**: each converts the day's own candles via
`scale_probe` (correct), but separately converts the REFERENCE LEVEL being
compared against those candles -- POC/Liquidity's confluence-zone inputs
(`lo_3m`/`lo_1w`/`lo_1d`/ATR), Fibo's `zone_low`/`zone_high`/`swing_high` --
via the older table method, with no cross-check that the two methods agree
for that day.

**Evidence**: on a 1,500-trade random sample from the real, already-published
Liquidity A/B/C trade population, comparing `scale_probe`'s scale for day D
(from D-1's own bhav-vs-Angel match) against `adjustment_factors.factor` for
the same day D: **233/1,500 (15.5%) disagree by >=0.5%**, consistent with
the 14.90% figure `scale_probe`'s own docstring already recorded for this
exact failure mode under the predecessor method. Entity-concentrated, not
random: 50 of 246 entities carry every mismatch, the top 10 account for 43%
of them, and for every entity with 2+ mismatches the ratio is constant
across all of that entity's dates (INE239A01016: exactly 0.1x across 14
dates; INE003A01024: exactly 2.011x across 11 dates; INE237A01028: exactly
5.0x across 7 dates) -- a few show a clean regime change mid-sample
(INE423A01024: 1.031 -> 1.648 -> 1.031), consistent with a real corporate
action partway through. 104 of 233 (45%) land within 2% of a simple
small-integer ratio. Checked `corporate_actions` directly for the five
largest-count entities: INE239A01016 and INE263A01016 have recorded
splits/bonuses consistent with the observed ratio being one missed leg of a
multi-step adjustment chain; **INE003A01024, INE237A01028, and
INE745G01035 have zero corporate actions recorded at all**, yet show
stable 2.011x/5.0x/5.0x mismatches -- the same "invisible corporate event"
failure `scale_probe`'s docstring names as its original motivation (there,
KOTAKBANK's pre-2016 merger), recurring in different entities that this
particular conversion path was never checked against. No correlation with
the 2024 bhavcopy format cutover -- structurally impossible to be the cause
here, since every affected date and its forward window falls entirely
before 2023.

**Effect, stated precisely, not assumed**: the realized entry/stop/target/
P&L of a specific already-published trade is not directly corrupted by
this -- those values come from the `scale_probe`-scaled candles directly
(confirmed via the Study C vs Study A hand-trace cross-check, where
`stop_price` tracked the candle-derived `final_sweep_low` exactly). What is
at risk is the SELECTION stage: whether a given entity-day is accepted as
having a valid confluence zone, or a sweep deep enough relative to ATR, on
the ~15-18% of days where the reference-level conversion disagrees with the
validated candle scale -- a false-positive-entry or false-negative-skip
risk, not a P&L-arithmetic risk, for whichever trades fall on a mismatching
day. Whether, or how much, this changes any specific published verdict has
not been measured and is not claimed here.

**Status: found, not fixed.** Affects `poc.v4` (hence POC V1-V5), all of
`liquidity.a`/`liquidity.b`/`liquidity.c`, and `fibo.backtest` (the sealed
Fibo test). Does not affect `box_theory` or `darvas`. No code changed by
this entry -- discovered as a side effect of building a new post-hoc
diagnostic over the closed Liquidity A/B/C trade population, reported
before proceeding with that diagnostic, and left for a deliberate decision
on whether/how to re-measure any of the affected studies' selection stage.

**Blast-radius measurement, Fibo sealed test and DEV window (requested
given the sealed test is the only strategy here with a pass)**: checked
`scale_probe` vs the table method directly on the signal day of every one
of the 188 TEST trades and 67 DEV trades (`scripts/fibo_bug18_blast_
radius.py`, read-only, no trades re-run).

**TEST: 11/188 (5.9%) disagree materially; 9/188 (4.8%) flip `zones_overlap`
from True to False** -- `INE647O01011` (2023-06-22, 2023-06-28),
`INE237A01028` (2025-01-15, 2025-10-01), `INE0J1Y01017` (2025-09-29),
`INE732I01013` (2025-04-17), `INE423A01024` (2024-10-08),
`INE849A01012` (2025-05-05), `INE774D01024` (2024-02-14) -- these 9 would
not have been selected as trades at all under the validated scale. The
other 2 mismatches (`INE423A01024`, 2024-06-14/06-20, ~3% ratio) do not
flip. **These 9 are not neutral**: their mean `net_r_amended` is 0.875 vs.
0.367 for the full 188 and 0.342 excluding them -- removing them would
lower the sealed test's own headline mean by roughly 7% relative. The
verdict itself was not re-run; this states the exposure, not a new result.

**DEV: 5/67 (7.5%) disagree materially, and all 5 flip** -- `INE205A01025`
(2021-11-22), `INE237A01028` (2016-11-09), `INE397D01024` (2017-05-10),
`INE628A01036` (2021-12-22), `INE239A01016` (2021-11-26). Here the effect
on the mean is negligible (0.364 full vs. 0.368 excluding the 5) -- the
same defect, opposite practical effect, in the two windows.

**Live forward system (`fibo_evening.py`/`fibo_morning.py`): structurally
immune to this specific mechanism, not merely clean so far.**
`adjustment_factors.factor(D)` is a product over every ex-date strictly
AFTER D -- for D = the most recent trading day that product is always
empty, so factor == 1.0 by construction, with no dependence on whether
`corporate_actions` is complete. Verified directly, not just derived:
every one of 175 qualifying watchlist rows logged 2026-10-08 through
2026-11-02 carries `scale_factor: 1.0`. `orb_high`/`orb_low` need no
conversion at all (live `getCandleData`, no historical reconstruction).
Separately flagged, not checked: whether the *adjusted* `golden_zone`/
`swing_high` inputs themselves, built from a historical lookback window
inside `fibo_evening.py`, could carry a stale-factor error from within
that window -- a different, earlier-pipeline question than the one
measured here. Live exposure to date is close to nil regardless: 87
`setup` events logged, exactly one `setup_on=True` (AXISBANK, 2026-10-19,
`run_mode: REPLAY`, never triggered), one `outcome` event, nothing live
has actually traded.

## Bug #19: `git pull --ff-only` encoded a single-writer assumption in what became a two-writer system -- blocked the evening job for 7 straight trading days

**Mechanism**: `src/fibo_live/git_sync.py`'s `pull_before_appending`
used `git pull --ff-only`, which only succeeds if the laptop's local
history is a strict subset of origin's. Its own docstring stated the
precondition explicitly: "fibo_morning.py must be the ONLY thing that
ever commits to this repo from anywhere else." That stopped being true
the day the morning job moved to GitHub Actions (2026-10-16, OPERATIONS.md)
-- GitHub Actions and this laptop became two independent writers to the
same `events.jsonl`, so a diverged history (each side has a commit the
other lacks) is the NORMAL state for that arrangement, not a failure
condition. `--ff-only` could not tell the two apart and refused every
time, with zero automatic recovery.

**Blast radius, found by a 2026-11-15 health check, not by design**: 7
straight trading days, 2026-11-06 through 2026-11-13, every scheduled
18:30 evening run aborted on this exact line (`fibo_live.git_sync.
GitPullError`) before touching anything else -- no watchlist produced,
cascading into the morning job REFUSING every one of those mornings
(`assert_watchlist_current`, working exactly as designed). Two earlier,
shorter instances of the identical error (2026-10-28, 2026-10-30) had
self-resolved only because the NEXT evening's run happened to find origin
back in a fast-forwardable state -- not because anything fixed the root
cause; the 2026-11-06 instance simply did not get that lucky before this
bug was found.

**Blast radius, the other direction (finding #9, `PROJECT_CONTEXT.md`
§7)**: checked whether any OTHER tracked file in this repo could hit the
same non-fast-forward wall via this same `pull_before_appending` call
(it pulls the whole repo, not just `events.jsonl`). None currently does
-- the evening job only ever writes `events.jsonl`, and no other
automated process commits to this repo from this laptop on a schedule
(`TradeNew_BoxTheoryDevRun` and `TradeNew_OptionsDepthTest` are one-shot,
non-recurring Task Scheduler entries, confirmed via `Get-ScheduledTask`
showing no `NextRunTime`; see OPERATIONS.md's "Options-depth collector
dead-man's switch" section for the full grep). The exposure is real only
for `events.jsonl`, which is exactly what the fix targets.

**Status: fixed, 2026-11-15.** `git pull --no-rebase` (never `--ff-only`,
never a rebase -- rebase rewrites committer timestamps, which this
project's provenance argument depends on being untouched) plus a new
`.gitattributes`: `data/fibo_live/v1/*.jsonl merge=union`, safe because
the file is append-only and line order is not semantically load-bearing.
A known, accepted limit of the union driver (a genuinely overlapping edit
can still duplicate a line in the raw merged file) is closed by
`fibo_live/eventlog.py`'s `read_events` now deduping by `event_id` --
every reader in this codebase goes through `read_events`, never a raw
file read. Regression-tested with real git subprocesses, not mocked:
`tests/test_git_sync_pull.py::
test_merges_cleanly_when_laptop_and_origin_have_both_diverged`
reproduces the literal historical failure and proves `pull_before_
appending` no longer raises; `tests/test_fibo_git_union_merge.py` (2
tests) proves the merge itself loses nothing and that the duplicate case
is real, not hypothetical; `tests/test_fibo_eventlog_dedupe.py` (4 tests)
covers the dedupe logic directly. Full detail, including the historical
timeline and the incidental merge commit that happened to unblock this
repo before the fix landed (luck, not a fix -- see OPERATIONS.md), is in
OPERATIONS.md's "git pull --ff-only was a single-writer assumption"
section.

## Bug #20: warehouse.duckdb lock conflict had no retry and no attribution -- cost 2 forward-test days

**Mechanism**: `scripts/fibo_evening.py` opened `warehouse.duckdb` with a
single, unretried `get_connection()` call. `duckdb.connect()` raises
`duckdb.IOException` INSTANTLY when any other process already holds the
file open on Windows (confirmed live with two concurrent Python
processes, byte-for-byte the same error text the production logs
showed) -- it never blocks and waits on its own. A transient hold by any
other process at exactly the wrong instant was therefore fatal with no
chance to recover.

**Blast radius**: 2 forward-test days, 2026-10-27 and 2026-11-03, the
evening job aborted immediately on this line, producing no watchlist for
the following trading day.

**Blast radius, the other direction (finding #9)**: checked which other
process could plausibly hold this exact file open. The options-depth
collector is structurally ruled out -- `src/options_depth/writer.py`
never imports `duckdb` or opens any `.duckdb` file, only a CSV.
`scripts/serve_screener.py` explicitly closes its read-only connection
before serving. The one long-lived process in this codebase that holds
`warehouse.duckdb` open indefinitely is `scripts/research_app.py`'s
Streamlit research browser (`@st.cache_resource`, never closed) -- the
leading candidate by elimination, not confirmed for the specific
historical dates (no process audit trail exists for those timestamps).

**Status: fixed, 2026-11-15.** `_open_warehouse_with_retry` -- 5 attempts,
exponential backoff (3/6/12/24s) -- added around the connection. On
exhaustion, `sys.exit(1)` (a deliberate `SystemExit`, not a raised
exception, so it survives `run_unattended`'s catch-all and actually
terminates the process non-zero, a second independent failure signal
alongside the dead-man's switch above going overdue). Regression-tested:
`tests/test_fibo_evening_duckdb_lock_retry.py` (4 tests, exact backoff
schedule and exit code asserted) and an upgraded
`tests/test_fibo_evening_heartbeat_wiring.py` case exercising the real
retry-then-exhaust path. Full detail in OPERATIONS.md's "warehouse.duckdb
lock conflict" section.

**UPDATE, 2026-11-15, same day**: `research_app.py`'s cached connections
were checked, not assumed -- both already used `read_only=True` before
any of this bug's own fix landed, and that was never going to help
anyway: DuckDB's local-file concurrency here is N-readers-XOR-1-writer,
so a read-only reader still blocks a writer. The actual gap was an
unbounded `@st.cache_resource` with no TTL. Added `ttl=900` (15 min) --
confirmed live that Streamlit evaluates this lazily (next-call, not a
background timer), so it bounds the realistic exposure window to "no
interaction with the app in the 15 minutes before the evening job runs,"
not an elimination. The retry above remains the backstop. Full detail,
including the live TTL-eviction test, in OPERATIONS.md's "research_app.py:
a 15-minute TTL added" section.

## Bug #21: test output was polluting the real scheduler.log

**Mechanism**: `src/fibo_live/scheduler_support.py`'s `make_logger()`
bound its default log path to the real `SCHEDULER_LOG` at the MODULE's
own import time, not at call time. `scripts/fibo_morning.py`'s module-
level `log = make_logger()` therefore always wrote to the real file
unless a caller explicitly overrode it. `tests/
test_fibo_morning_idempotency.py` (fake SYM1..SYM16 fixtures) correctly
monkeypatched `append_event`/`read_events` to a tmp_path but never `log`
-- every `log()` call reached during those tests wrote straight into
`data/fibo_live/scheduler.log`.

**Blast radius**: confirmed, not assumed, by reading the real log's
history -- SYM1..SYM16 fixture noise, a `RuntimeError: simulated
network-down failure`, and fake "Angel One login FAILED" lines, all
dated 2026-10-16 and 2026-10-27, cost audit time during the 2026-11-15
health check (each had to be individually checked and ruled out as test
noise, not a real incident, before the real failures that week could be
trusted).

**Blast radius, the other direction (finding #9)**: grepped the whole
`src/` tree for the same `make_logger` pattern. Exactly one other
instance exists, `src/options_depth/scheduler_support.py` (duplicated by
design, per that package's own decoupling convention) -- fixed in the
same pass, not left for later.

**Status: fixed, 2026-11-15, with a wrong first attempt corrected before
it shipped.** The default now resolves lazily, at call time, inside
`make_logger()`. The first version keyed this on `PYTEST_CURRENT_TEST` --
proven wrong LIVE by re-running the exact polluting test and watching the
real log grow by 29 lines anyway, not caught by reasoning about pytest's
internals: that env var is only set once pytest starts running an
individual test, after every test module (including the one whose import
already executed `log = make_logger()`) was imported during collection.
Replaced with `"pytest" in sys.modules`, true from pytest's own process
startup, before collection -- re-verified the same way (before/after line
count on the real log, not just a passing test). Regression-tested:
`tests/test_fibo_scheduler_log_test_isolation.py` and `tests/
test_options_depth_scheduler_log_test_isolation.py`. Full `fibo`/
`options_depth` selection (205 tests) confirmed the real log's line count
unchanged before and after. Historical pollution already in the file was
left as-is (gitignored, local-only; not silently edited). Full detail in
OPERATIONS.md's "Test output was polluting the real scheduler.log"
section.

## Bug #22: the evening job (and the options-depth collector) had no independent heartbeat -- a local log or a caught exception was the only failure signal

**Mechanism**: `scripts/fibo_evening.py` (Windows Task Scheduler, weekdays
18:30 IST) and `scripts/snapshot_options_depth.py` (same scheduler,
10:30/12:30/14:30 IST) each only ever recorded their own outcome locally
(`data/fibo_live/scheduler.log` / `data/options_depth/scheduler.log`) or
via a caught-and-swallowed exception (`run_unattended`, by design, so one
bad run never blocks the next). Neither had any independent, externally
monitored signal that a run happened at all. The morning job
(`fibo_morning.yml`) already had exactly this gap once, found and fixed
via a healthchecks.io heartbeat (OPERATIONS.md's "External pinger"
sections, live since 2026-10-23) -- `PROJECT_CONTEXT.md` Section 7
finding #4 ("fixed where noticed, not everywhere the pattern recurs")
named this defect shape explicitly; it had recurred, one layer up, in
both remaining scheduled jobs, undetected until the 2026-11-15 health
check went looking.

**Blast radius, direction one (jobs missing a heartbeat)**: found by
reading events.jsonl and scheduler.log directly, not assumed. 3 of 10
failure-days the health check examined (2026-10-29, 2026-11-11,
2026-11-12) have ZERO entries in `data/fibo_live/scheduler.log` -- Task
Scheduler never launched `python.exe` at all, a failure mode no local log
or exception handler inside that process could ever see. The evening job
was down for 7 straight trading days (2026-11-06 through 2026-11-13)
before this was noticed. The options-depth collector had the identical
gap, unnoticed because nothing was looking for it specifically (its only
indirect signal was `fibo_evening.py`'s own `snapshot_health` log line --
a check FROM a different job, not a check ON this one's own launch).

**Blast radius, direction two (checked, not assumed, per finding #9 --
a selection bug that wrongly includes also wrongly excludes): are there
scheduled jobs this grep could have wrongly waved through as "doesn't
need one"?** Enumerated every entry in this machine's actual live
`Get-ScheduledTask` list (not just the `*_task.xml` files committed to
this repo, which can go stale) and this repo's GitHub Actions workflows:

| job | recurring? | verdict |
|---|---|---|
| `FiboEvening` | yes, weekdays | **had the gap -- fixed** |
| `TradeNew_OptionsDepth` | yes, weekdays 10:30/12:30/14:30 | **had the gap -- fixed** |
| `TradeNew_BoxTheoryDevRun` | no -- one-shot `MSFT_TaskTimeTrigger`, already fired once (2026-10-17), no `NextRunTime` | correctly excluded: not a recurring job, box theory is closed (`PROJECT_CONTEXT.md` Section 5) |
| `TradeNew_OptionsDepthTest` | no -- one-shot, already fired once (2026-10-12, killed mid-run), no `NextRunTime` | correctly excluded: `test_options_depth.py` is an explicit one-off manual probe, not a build artifact |
| `nse-pit-bhavcopy-probe` | yes, daily | correctly excluded: runs `C:\projects\trade-info\ops\poll_bhavcopy.py`, a **different project's repository**, out of this codebase's scope |
| `fibo_morning.yml` (GitHub Actions) | yes, 4x/day via cron-job.org | already covered before this session (the original heartbeat this bug's shape was first found on) |
| `probe_github_actions.yml` (GitHub Actions) | no -- `workflow_dispatch` only, no `schedule:` | correctly excluded: manual-trigger probe, nobody expects it to fire unattended |

No recurring, in-scope job was wrongly excluded.

**Status: fixed, 2026-11-15.** `src/fibo_live/heartbeat.py` and
`src/options_depth/heartbeat.py` (duplicated, not imported, per that
package's own decoupling convention) -- each pings healthchecks.io only
on outcomes that represent correct, intended behavior (full success, or a
legitimate no-op: the evening job's idempotent-skip path, the
options-depth collector's correctly-recognized non-trading-window
refusal), never on a genuine failure. Both verified end-to-end, not just
by code review: a real success ping confirmed on each check's dashboard,
and a real forced failure signal confirmed BOTH an "up -> down" dashboard
transition AND an actual delivered email ("DOWN | Fibo evening job" at
19:11; "DOWN | Options depth collector" at 20:09), then restored to
"up" before this entry was written. Full detail, including the two
dead-man's-switch sections, the schedule-move rationale, and the
retracted ~11%-refusal-rate claim, is in OPERATIONS.md.

## Bug #23: an uncovered holiday-calendar year degraded silently instead of refusing

**Mechanism**: `scripts/fibo_evening.py`'s `next_trading_day` and
`scripts/fibo_morning.py`'s `previous_trading_day` both caught
`HolidayCalendarMissing` (no calendar entry for a candidate date's year)
and degraded to the old reactive, fetch_log-only heuristic -- logged as a
WARNING, but otherwise indistinguishable from a correct run to anything
not reading logs. 2027 is exactly such a year (confirmed unpublished by
NSE as of 2026-11-15, OPERATIONS.md's "2027 NSE holiday master" section).

**Why this is the same shape as finding #15, not a new class of
mistake**: a documented "recheck the calendar monthly" intention is not a
correction on its own -- nothing forces it to happen, and the first
version of this entry's own fix pass initially proposed exactly that as
the mitigation before being corrected to a code guard instead.

**Status: fixed, 2026-11-15.** Both functions now let
`HolidayCalendarMissing` propagate uncaught. `fibo_evening.py`'s `main()`
catches it, emails `notify_evening_skipped`, and returns before the
dead-man's-switch heartbeat call -- an uncovered year becomes a
healthchecks.io DOWN alert the same evening. `fibo_morning.py`'s `main()`
catches it and routes it through `log_refusal`, the same durable
`REFUSED` `session_status` path every other morning refusal already
uses. Regression-tested: 4 new tests in `tests/test_holiday_week_oct2026.py`
(replacing 2 that asserted the old degrade behavior) and an updated
assertion in `tests/test_fibo_morning_watchlist_freshness.py`. Full
detail in OPERATIONS.md's "Trading-day logic now refuses loudly on an
uncovered year" section.

## Bug #24: a test could write to the real events.jsonl -- one draft test actually did

**Mechanism**: 7 functions (`eventlog.append_event`, `eventlog.read_events`,
`fibo_morning.assert_watchlist_current`, `outcomes.record_outcome`,
`outcomes.evaluate`, `session_status.already_logged_session_status`,
`session_status.record_session_status`) all had a
`log_path: Path = EVENTS_LOG` default -- bound ONCE, at import time, to
the real `data/fibo_live/v1/events.jsonl`, the same stale-default shape
`scheduler_support.make_logger` had (fixed 2026-11-15, see that
function). Because Python binds a default argument once at function
definition, no later monkeypatch of the imported `EVENTS_LOG` name, or
of `fibo_morning.append_event`/`read_events` as names, could change what
`assert_watchlist_current` actually used UNLESS the test also rebound
`assert_watchlist_current` itself.

**THE NEAR MISS, 2026-11-13/14**: an in-progress draft test for
`fibo_morning.py`'s holiday-calendar-missing refusal called
`fibo_morning.main()` after monkeypatching `fibo_morning.append_event`,
`read_events`, and `record_session_status` to a `functools.partial`
bound to a tmp_path log -- but not `assert_watchlist_current`, which
still used its own stale `log_path=EVENTS_LOG` default. Worse: even the
functions that WERE rebound would not have helped here, because an
explicit `log_path=` keyword at a call site overrides a
`functools.partial`'s preset keyword (confirmed empirically) --
`assert_watchlist_current`'s own call to `read_events(kind=...,
log_path=log_path)` passed its own (real) `log_path` explicitly, which
always wins. The result: a fabricated `session_status` event
(`event_id: "0ac21757-d28d-4c84-8d7e-05fcc148ba3f"`, `trade_date:
"2027-01-04"`, `status: "REFUSED"`, `run_mode: "REPLAY"`) was appended to
the REAL `data/fibo_live/v1/events.jsonl`. Caught immediately via `git
diff` (this project's habitual before/after check around every test
run), reverted with `git checkout -- data/fibo_live/v1/events.jsonl`,
confirmed byte-identical to `HEAD` afterward, and re-verified clean
across every full-suite rerun since.

**Blast radius, both directions**:
- *What the fabricated event would have affected had it survived to the
  next real job run*: `sync_events_log_to_git` (git_sync.py) commits and
  pushes ANY diff in this file unconditionally, on every real morning or
  evening run -- so the very next scheduled run would have permanently
  committed and pushed the fabricated line to GitHub, requiring a manual
  revert commit rather than a quiet local `git checkout`. Separately,
  `already_logged_session_status`'s dedup key is
  `(trade_date, session, reason)` -- a genuine evening or morning refusal
  on 2027-01-04 with the same `reason` text as the fabricated event would
  have been silently treated as "already logged" and never written,
  which is exactly the failure this file exists to make impossible
  (git_sync.py's own module docstring: this file is the sole evidentiary
  record that a signal was logged before its outcome was known).
- *Whether any prior test run could have written to the file before this
  one was caught*: checked the full 45-commit history of
  `data/fibo_live/v1/events.jsonl` (`git log --follow`) -- every commit
  message matches either the automated `"Fibo {evening,morning} events
  -- synced <date>"` pattern from `sync_events_log_to_git`, or one of two
  known manual interventions (`2026-10-16`'s gap backfill,
  `2026-10-11`'s initial tracking commit). None is anomalous. Checked the
  file's current content for any `trade_date`/`target_trade_date`/
  `as_of_date` in 2027 or later (this project's "has this leaked
  somewhere" canary, since no real job has run against a 2027+ date as
  of 2026-11-15) -- zero matches. The one real mix found while building
  the integrity check below (1,233 lines with a naive `ts`, 2026-10-08
  through 2026-10-13; 2,567 with an explicit `+05:30` offset,
  2026-10-13 onward, one day of overlap) is fully explained by
  `append_event` gaining IST-aware timestamping that day, not by any
  unaccounted-for write. No prior test-caused write is visible anywhere
  in the file's committed history.

**Status: fixed, 2026-11-15**, with two independent, deliberately
overlapping structural layers (neither alone is a complete fix):
1. All 7 functions above now take `log_path: Path | None = None` and
   resolve `fibo_live.config.EVENTS_LOG` FRESH, at call time, via a
   module-qualified `config.EVENTS_LOG` lookup rather than a bound
   default -- the same fix already proven for `make_logger`'s
   `SCHEDULER_LOG`. This alone would already have prevented the near
   miss above, since `assert_watchlist_current` would then have picked
   up a session-wide redirect automatically.
2. `tests/conftest.py` (new file -- none existed in this repo before):
   an autouse `_redirect_events_log` fixture patches
   `fibo_live.config.EVENTS_LOG` to a fresh `tmp_path` for every single
   test, with zero per-test monkeypatching required; a session-scoped
   `_protect_production_files` fixture makes `events.jsonl`,
   `scheduler.log`, `warehouse.duckdb`, and `fibo_intraday.duckdb`
   read-only at the OS level for the whole pytest session (confirmed
   empirically on this Windows dev machine: a chmod-read-only file
   blocks both a plain `open(path, "a")` and a write-mode
   `duckdb.connect(path)`, while a `read_only=True` DuckDB connection is
   unaffected); and `pytest_sessionstart`/`pytest_sessionfinish` hooks
   hash the real `events.jsonl` before and after the ENTIRE test run,
   forcing `session.exitstatus = 1` (confirmed empirically that this
   actually flips the process exit code even when every individual test
   passed) if the hash ever differs, regardless of which test file ran
   when.

**Residual, known, not fixed**: `fibo_live.config.RAW_PRICES_DIR` /
`RAW_INDEX_DIR` are directories, not files -- chmod's read-only attribute
is not reliably enforced on a Windows/NTFS directory the way it is on a
file (confirmed empirically the same day: it did not block file creation
inside a chmod'd directory), so layer 2 above does not cover them.
Currently protected only by the two tests that reach that code path
(`test_holiday_week_oct2026.py`, `test_fibo_evening_staleness_ordering.py`)
explicitly monkeypatching `fibo_evening.RAW_PRICES_DIR` to a `tmp_path` --
vigilance-based, the exact shape this bug exists to move away from.
Making that directory level genuinely tamper-proof would need an ACL
change (`icacls`), not attempted here. `sync_events_log_to_git`'s real
`git add`/`commit`/`push` subprocess calls (git_sync.py) are a related,
currently-unreachable risk: both call sites are gated by
`if __name__ == "__main__":`, which a test importing the module and
calling `main()` directly never triggers -- flagged here as an adjacent
risk worth knowing about, not a gap that needed building against, since
nothing in the current suite can reach it.

**New test coverage**: `tests/test_events_log_integrity.py` -- 4 tests
checking the real file directly (never through the redirect fixture):
every line is valid JSON with required fields, all `event_id`s are
unique, timestamps are monotonic within each single-writer `kind`
(`notification`/`session_status` excluded, since both jobs legitimately
write those), and the file has no uncommitted diff against `HEAD`.
Verified live: full suite run before and after this fix, 692 passed / 1
failed (the known, untouched `test_monitor_persistence.py`), hash of
`data/fibo_live/v1/events.jsonl` identical before and after, `git
status` clean.

## Bug #25: a module-level SyntaxError on Python 3.11, invisible on this laptop's 3.13

**Found live, by the new CI workflow's first real run (2026-11-15,
`.github/workflows/test_suite.yml`, BUGS.md Bug #24's own hermetic-test
work)**: `src/lead_lag/inference.py` line 384 failed to even import on
the GitHub Actions runner (Python 3.11.18), `SyntaxError: unterminated
string literal`, which `pytest` surfaced as a collection ERROR for both
`tests/test_lead_lag_inference.py` and
`tests/test_lead_lag_null_imposed_inference.py` -- the whole run never
reached a single test. This laptop's own Python (3.13) imports the same
file without complaint, so nothing local had ever caught it.

**Mechanism**: the `warnings.warn(...)` call built its message from
several ADJACENT f-string literals (ordinary implicit concatenation),
and one `{...}` expression's content --
`{zero_variance_regressors or '(none -- '` -- was left open across the
boundary into the NEXT literal, which closed it:
`f'deficiency ... column)'}`. Each f-string literal is tokenized as a
self-contained unit; pre-3.12 Python requires every `{}` expression to
be complete within the single literal it appears in, so this is not
valid syntax before PEP 701 (Python 3.12's relaxed f-string grammar).
Python 3.13 (this laptop) accepts it; Python 3.11 (this project's own
pinned CI/Actions Python, `fibo_morning.yml`'s own `python-version:
"3.11"`) does not.

**Blast radius**: confirmed, not assumed, that this is isolated to this
one call site -- re-byte-compiled all 400 `.py` files under `src/`,
`scripts/`, and `tests/` with a real local Python 3.11.9 install
(`python -m py_compile`) after the fix; zero other files fail. Before
this CI workflow existed, nothing in this project's own test suite or
development workflow ever ran on anything but this laptop's 3.13, so a
3.11-incompatible construct like this could have shipped into
`fibo_morning.yml`'s own runner (also 3.11) the moment anything there
imported `lead_lag.inference` -- it happens not to, today, but nothing
structural prevented it.

**Status: fixed, 2026-11-15.** Extracted the zero-variance description
to a plain local variable (`zero_variance_desc`) before the
`warnings.warn(...)` call, removing the cross-literal brace entirely --
portable on both 3.11 and 3.13. Verified: `python -m py_compile` clean
on 3.11.9 for all 400 files; `pytest tests/test_lead_lag_inference.py
tests/test_lead_lag_null_imposed_inference.py` still 45 passed on 3.13,
with the warning text byte-for-byte unchanged; full suite re-run
afterward, 692 passed / 1 pre-existing failure (untouched), events.jsonl
hash unchanged.

## Bug #24 follow-up: the known test_monitor_persistence.py failure was data drift, not a code bug

**Investigated 2026-11-16**, prompted by this same session's work: the
long-standing `test_reproduces_the_three_published_pre_holdout_regimes`
failure (first seen in this session's own full-suite runs, present
since the module was built 2026-09-27 -- 49 days before this
investigation) was never root-caused before this; it was only ever
carried as "known, pre-existing, untouched."

**Which side was wrong -- settled by direct comparison, not assumption**:
ran `scripts/run_momentum_persistence_regime_count.py` live against the
current real warehouse. It reported 82 excluded same-ISIN-jump entities
and 5 mechanical regimes (2017-2019 +, 2020 -, 2021 +, 2022 -,
2023-2024 +) -- IDENTICAL to the test's own actual (failing) output,
confirmed via both using the exact same `monitor.persistence` functions
(`same_isin_jump_excluded_entities`, `compute_daily_persistence`,
`annual_mean_sign`, `mechanical_regimes`). No divergence between the
script and the module exists. Checked `git log` on
`src/data_layer/lineage_jump_guard.py` and `src/monitor/persistence.py`:
neither has changed since before the module was built (2026-09-23 and
2026-09-27 respectively) -- so this is not a regression from a code
edit either.

**The actual cause**: `same_isin_jump_excluded_entities()` and
`compute_daily_persistence()` both read the FULL warehouse at call
time, by design ("full warehouse, no `before` cutoff," that function's
own docstring) -- not a point-in-time snapshot. On 2026-09-27, that
query returned 78 excluded entities and a 3-regime result; 49 days of
ordinary ongoing backfill later, it returns 82 and 5 regimes. The
CODE never changed and is not wrong; three STATIC TEXTS treated a
live, data-dependent query's result as a permanent fact: this test's
hardcoded assertion, `monitor/persistence.py`'s own module docstring,
and `scripts/run_momentum_persistence_regime_count.py`'s own docstring
(all three said "still exactly 3... unchanged"). Fixed all three to
state the current number with an explicit "this moves" caveat, not a
fourth permanent snapshot.

**Blast radius -- checked, not assumed, whether any LIVE output was ever
actually wrong**: `src/monitor/web.py`'s `build_monitor_payload()` (the
screener web app's `/api/monitor` panel) also calls `mechanical_regimes`
and is regenerated FRESH "at server startup" every time (its own
docstring) -- it was never a cached, stale value; anyone who looked at
that panel on any day since the exclusion set grew would have seen the
CORRECT count for that day, not a frozen "3." Nothing in this project's
trading logic reads `mechanical_regimes`/`annual_mean_sign` at all
(grepped: only `web.py`, this test, and the two scripts above import
them) -- no paper-trading or backtest decision was ever downstream of
this number. **The one real, open question this does raise**:
`NEW_RESEARCH_DIRECTION.md`'s Hypothesis A-actionable rejection states
its basis as "3 [regimes], under the ~5 needed for a credible read,
fixed as the threshold before this was computed." The true current
count is 5 -- AT that threshold, not under it. This does not
automatically reverse the rejection (the threshold was not crossed, and
the broader regime-instability argument in that document does not rest
on this number alone), but the document's own "unchanged by this
correction" framing is no longer accurate and the rejection's wording
has not been revisited. Flagged for the user to decide; not edited
unilaterally here, since changing a hypothesis-rejection's stated
rationale is a bigger decision than a code fix.

**Status: fixed, 2026-11-16.** Test assertion updated to the current,
re-verified 5-regime result, with a docstring making explicit that this
number is expected to move again as the warehouse grows and should be
re-checked against the script rather than assumed. Full suite: **693
passed, 0 failed** -- the first fully green run this session.

**UPDATE, same day: the literal-5 fix above was itself the exact
mistake it warned against, caught before being asked to investigate
further.** Asserting a hardcoded `5` is just as fragile as the `3` it
replaced -- guaranteed to go red again the next time any single entity
anywhere in the warehouse gets newly flagged by the same-ISIN jump
guard, indistinguishable from a real regression. Rewritten to
`test_real_pre_holdout_regimes_are_a_well_formed_partition`: asserts
the mechanical rule's STRUCTURAL invariants (regimes are contiguous,
non-overlapping, every year is covered by exactly one regime, every
year's sign matches its regime's sign, adjacent regimes differ in
sign) rather than a specific count or boundary list -- true regardless
of how many regimes the current warehouse produces, so it cannot go
stale the way the last two versions did.

**Full mechanism, proved directly rather than inferred**: built a
checkpoint trace, re-running the exclusion-and-regime computation at
each date a new same-ISIN jump entered the exclusion set
(2026-09-27/28, 10-09/10, 11-04, 11-16). The count did NOT climb
steadily -- it held at 3 regimes (2022's mean_persistence a stable
+0.0032 to +0.0034) through 2026-10-10, then jumped discretely to 5 the
moment ONE entity, CONCORDBIO (INE338H01029), had its own same-ISIN
jump flagged with `jump_date=2026-11-04` (12 days before this
investigation, confirmed real and gap_days=2 -- a legitimate detection,
not a bug in the jump guard). Excluding that one entity removes its
entire multi-year history from the panel and flips 2022's
mean_persistence to -0.0022 -- crossing zero by under 0.006, entirely
attributable to this single entity. Nothing about 2022's own trading
activity changed; a jump discovered in an unrelated entity 12 days ago
retroactively reclassified a year that ended three years ago. This is
unambiguously the "window artifact" shape, not "new regimes occurred in
Sept-Nov 2026": the new regime boundary sits in 2022, not in the recent
window where the triggering jump was actually detected.

**Where "~5 regimes needed for a credible read" came from -- traced,
not assumed**: `NEW_RESEARCH_DIRECTION.md` line 385-387 states it as
"the threshold stated in advance," with no formula, simulation, or
citation anywhere in that document. It draws an explicit analogy to
`FINDINGS.md` Section 12's power problem, but Section 12's own numbers
(a rigorous variance-only power calculation: ~8-72 years needed to
detect a 0.01-0.03 true IC difference) are about a completely different
metric (paired rank-IC difference between two factors) and do not
produce or imply "5" for counting discrete regime transitions anywhere
in their derivation. The "~5" figure is asserted, not derived, by this
document's own account of itself.

**Whether the Hypothesis A-actionable rejection stands -- reported, not
revised**: its SPECIFIC quantitative framing ("3, under the stated ~5
threshold") was never on solid ground in either direction -- not
because 3 vs. 5 is bad arithmetic, but because the "~5" comparison
point has no derivation to be calibrated against, and the regime count
being compared to it has now been shown to flip on a single entity's
data-quality flag discovered weeks after the fact, which is not a
stable basis for a threshold comparison at any threshold value. The
rejection's broader QUALITATIVE argument -- too few independent
regime-transition events (2-4, however exactly counted) to learn a
reliable regime-length or power estimate, the same fundamental problem
Section 12 demonstrated for a different metric -- does not depend on
the exact count or the specific "~5" and is on more defensible ground
on its own terms. Not acted on here; left for a decision, not resolved
by this entry.

**UPDATE, 2026-11-16: reproducibility impact on the one positive result
in this repository -- the record stands, a separate sensitivity
diagnostic is thinner than it first read.** The same unpinned-exclusion
problem that moved the regime count also touches `FINDINGS.md` Section
2's Bug #11 materiality check. **The record is unchanged: margin 3.87
-> 3.64 at the exclusion set's state on 2026-09-27 (78 entities, the
holdout read date)** -- that is what a re-run on that date would
reproduce, and it is not being revised here. Separately, re-running the
same mechanism today would silently apply 82, not 78, with no record of
which version produced which number -- a reproducibility gap, not a
license to treat "today's number" as an update. Diagnostic only (window
held fixed, only the exclusion-set snapshot varied): margin ranges
3.57-5.22 across every version that has existed since 2026-09-27. A
single entity (MOLDTKPAC) has been observed moving it 1.65 points while
the buffer above 3.0 across these snapshots is only 0.57-1.00 points --
one further adverse addition of a size already seen would exceed that
buffer. Full table and entity breakdown in `FINDINGS.md` Section 2's own
update. **Proposed fix (not implemented, per instruction
-- report and list blast radius only)**: `same_isin_jump_excluded_
entities()`'s underlying detector (`unexplained_same_isin_jump_entities`,
`data_layer/same_isin_jump_guard.py`) already accepts a `before: dt.date`
cutoff, the same point-in-time convention `lineage_jump_guard` and
`isin_lineage`'s own `as_of` already use elsewhere in this codebase --
`same_isin_jump_excluded_entities()` itself just never threads it
through, always calling with no cutoff at all. Fix would be: add
`as_of: dt.date | None = None` to that one function, and require every
caller to pass and record the value it used. Blast radius -- every
consumer, by which function it actually calls:
- Via the canonical `monitor.persistence.same_isin_jump_excluded_
  entities()` (would need an explicit `as_of` added): `src/monitor/
  web.py` (live `/api/monitor` payload), `scripts/
  run_momentum_basket_snapshot.py` (**the live forward-paper-trading
  basket freeze -- highest stakes here**: two basket snapshots months
  apart could already differ in universe for a reason nobody can
  reconstruct), `run_momentum_persistence_monitor.py`,
  `run_momentum_persistence_regime_count.py`,
  `run_holdout_study1_bug11_check.py` (+ the new `_versioned.py`),
  `run_momentum_backtest_bug11_check.py`, `run_study2_largecap_bug11_
  check.py`, `run_portfolio_power_calc.py`.
- Via the lower-level detector directly, own filtering, separate family
  (swing project, not momentum): `src/fibo/jump_guard.py` (already
  passes its own `before=`), `scripts/run_swing_phase3_clean_rerun.py`,
  `run_swing_phase3_decomposition.py`, `run_swing_v1_checks.py`,
  `run_swing_v1_holdout.py`, `run_swing_v1_regime_check.py`,
  `run_swing_v1_regime_check2.py`.

## Bug #26: the earnings-drift Phase 0 scripts computed 60-day forward returns without either jump guard -- 1,519 of 115,817 windows contaminated

**Found 2026-11-16**, investigating the +18,939% 60-day-return outlier
driving `EARNINGS_DRIFT_PHASE0.md`'s raw-MDE instability, at the user's
explicit request before relying on winsorization to cover it.

**The one row, traced**: entity `INE234I01010` (KAUSHALYA Infrastructure
Development Corp.), 4 filings broadcast 2023-05-30 (Q4 Consolidated, Q4
Non-Consolidated, Annual Consolidated, Annual Non-Consolidated --
**genuinely distinct filings, not a pipeline duplicate**; Indian
companies routinely co-file all four variants at FY-end, and this
project's event construction does not currently deduplicate by
announcement day, so one contaminated day gets 4 votes instead of 1 --
noted, not fixed here, out of scope for this investigation). `t0` =
2023-05-30 (close ₹4.00), `tf` = 2024-04-30 (close ₹761.55) -- the
189.4x move. `prices_eod` has **zero rows for this ISIN between
2024-01-12 and 2024-05-10** (the real feed went dark); `entity_prices_
daily` is nonetheless densely populated across exactly that gap,
because `isin_lineage` maps a SECOND isin (`INE234I01028`, transition
`known_date` 2024-03-04) to the same `entity_id`, and the materialize
join (`entity_panel.py`) silently stitches both ISINs' price series
together as one continuous entity. `corporate_actions` has zero rows
for either ISIN across the transition; `adjustment_factors.factor`
is `1.0` throughout (no correction ever applied). **This is already a
named, detected case**: `lineage_jump_guard.find_unexplained_jumps()`
(Bug #1's own detector) flags this exact transition --
`boundary_ratio=89.83`, `has_nearby_ca_record=False` -- i.e. an ~90x
unexplained jump, almost certainly a corporate restructuring or
ISIN-reissue with a share-count change that was never captured as a
`corporate_actions` row, the same underlying mechanism as Bug #1
(MAJESCO) and Bug #11, just at a lineage-transition boundary rather
than a same-ISIN one.

**Class size, not one row**: 51 of 115,817 survivor events exceed a
500% 60-day return (25 distinct entity/announcement-day pairs, each
multiplied by its co-filed variants). **50 of 51 are flagged by one of
this project's two existing jump guards** (`lineage_jump_guard` or
`same_isin_jump_guard`, either one, any `gap_days`) -- a real class
with a known, already-instrumented cause, not noise. The one
unflagged row (`INE294G01026`/ROML, +996% over 2020-11 to 2021-05) has
no single-day ratio above 1.05 anywhere in its window -- a genuine,
gradual COVID-era microcap rally, not an artifact.

**The actual bug**: `scripts/earnings_drift_phase0.py` and
`scripts/earnings_drift_phase0_mde_correction.py` compute every 60-day
forward return directly from `entity_prices_daily` and apply **neither**
jump guard -- not `lineage_jump_guard` (Bug #1), and not even
`same_isin_jump_guard` (Bug #11), despite `PREREGISTRATION_EARNINGS_
DRIFT.md` Section 1 naming the latter (the 78-entity, `gap_days<=5`
"canonical" pin) as part of the universe. `src/factors/momentum.py`
already guards exactly this shape for its own comparable (63-trading-
day) forward-return horizon (`_is_unexplained_jump_row`, "a hard
boundary regardless of calendar gap size"); the earnings-drift scripts
never adopted the equivalent check. Separately: the 78-entity canonical
pin itself is a **narrow** subset of `same_isin_jump_guard`'s own full
output -- it only keeps jumps with `gap_days<=5` (`JUMP_GAP_DAYS_CUTOFF`,
`src/monitor/persistence.py`), by design, for a different reason
(filtering same-ISIN detections down to the no-real-gap MAJESCO shape).
The full, untightened same-isin-guard population is **714 distinct
ISINs** with an unexplained jump somewhere in their history -- KAUSHALYA
itself is not even IN the 78/82-entity canonical set (its own flagged
same-isin-adjacent jumps have `gap_days` 61-146, all above the cutoff).
A 60-day forward-return window can straddle a jump of ANY `gap_days`,
tight or wide, same-isin or lineage-transition -- the canonical pin was
never designed to protect this horizon and does not.

**Blast radius, both directions, measured not assumed**:
- **Under-exclusion (the direction that matters)**: of the 115,817
  survivor events, **1,519 (1.3%) have a 60-day window containing an
  unexplained jump** under either guard -- 18 events / 8 entities via
  `lineage_jump_guard`, 1,501 events / 476 entities via the FULL
  `same_isin_jump_guard` output (not the 78/82-entity tight-gap subset,
  which catches essentially none of these). None of these 1,519 are
  excluded by anything in the currently-committed preregistration or
  Phase 0 scripts.
- **Does this threaten the already-committed Phase 0 MDE?** Checked
  directly: of the 1,519 contaminated events, 603 (40%) are already
  removed as a side effect of the frozen within-quarter 1st/99th
  percentile winsorization rule (Section 6) -- they are extreme enough
  to be clipped regardless of cause. **916 (60%) are NOT clipped** --
  their net 60-day return is modest enough to pass through winsorization
  untouched while still containing an unrelated, unexplained price
  discontinuity somewhere inside the window. Winsorization is not a
  substitute for excluding these; it coincidentally removes under half
  of them.
- **Scope beyond this one study**: `scripts/earnings_drift_phase0.py`
  and `_mde_correction.py` are the only callers of a raw forward-return
  construction added this session; no other script in this project
  computes a `entity_prices_daily`-based forward return over a
  comparable horizon without going through `factors/momentum.py` (which
  already guards this) or one of the swing-project scripts (which
  already pass `before=` to the lower-level detector directly). This
  bug is new-study-specific, not a defect in `lineage_jump_guard` or
  `same_isin_jump_guard` themselves -- both detectors worked correctly
  the moment they were actually queried.

**Fix, applied as `PREREGISTRATION_EARNINGS_DRIFT.md` Amendment 2
(not here)**: exclude any event whose `[t0, tf]` window contains an
unexplained jump under either guard, any `gap_days`, in addition to
(not instead of) the existing 78-entity canonical same-ISIN pin and the
unchanged winsorization rule. Status: **fixed in the preregistration
before DEV ran**, per that document's own Amendment 2.

## Bug #26 follow-up: proposal to make `read_entity_panel()` guard by default -- blast radius only, NOT IMPLEMENTED

**Requested 2026-11-16**: Bug #26 is the eighth time a fix existed and new
code simply didn't call it (`PROJECT_CONTEXT.md` finding #4, "fixed where
noticed, not everywhere the pattern recurs"), and Bug #11's own record
shows a sweep already missed seven scripts once. A guard that must be
remembered will be forgotten again. This section reports what making the
panel guarded-by-default would break, so the change itself is not made
blind. **Nothing below is implemented.**

### Current state, swept fresh against today's code

Every caller of `read_entity_panel()` / direct reader of
`entity_prices_daily`, classified by what it actually applies:

| Guard applied | Scripts/modules |
|---|---|
| **Both** (lineage + same-ISIN) | `run_momentum_persistence_regime_count.py`, `run_portfolio_power_calc.py`, `tests/test_monitor_persistence.py`, `src/monitor/web.py`, and the swing-project scripts already recorded above (`run_swing_v1_holdout.py`, `run_swing_v1_checks.py`, `run_swing_phase3_clean_rerun.py`, `run_swing_phase3_decomposition.py`, `run_swing_v1_regime_check.py`, `run_swing_v1_regime_check2.py`) |
| **Same-ISIN only** (dedicated materiality re-checks, not the original script) | `run_momentum_backtest_bug11_check.py`, `run_study2_largecap_bug11_check.py` |
| **Lineage only** | `run_lineage_jump_fix_impact.py` (diagnostic), `run_swing_phase1_cost_dispersion.py`, `run_swing_phase2_candidate_counts.py` |
| **Neither**, but routes through `factors/momentum.py`/`factors/target.py` (gets `STALE_GAP_DAYS`'s incidental protection for jumps with a >5-calendar-day gap; still fully exposed to zero-gap same-ISIN jumps) | `run_combination_ic_power_analysis.py`, `run_combination_power_analysis.py`, `run_ey_momentum_diagnostic.py`, `run_factor_ic_report.py`, `run_lowliq_cost_sensitivity.py`, `run_momentum_backtest.py`, `run_phase2_diagnostics.py`, `run_phase_e_factors.py`, `run_study2_largecap.py`, `run_survivorship_quantification.py`, **and `run_holdout_study1.py` itself** |
| **Neither, and bypasses the factor layer entirely** (zero incidental protection) | the now-fixed `scripts/earnings_drift_phase0*.py` (Bug #26, above) |
| **Not exposed** (no return computed across a time span) | `run_lowliq_cost_calibration_diagnostic.py` (turnover/spread only) |

**The one finding that matters most**: `scripts/run_holdout_study1.py` --
the script behind this project's one sealed-holdout-validated positive
result -- calls `compute_momentum_12_1(panel)` and
`compute_forward_return(panel)` with no `unexplained_jump_dates`
argument. Checked what this actually means, not just flagged: **for
lineage-transition jumps, it is already protected as a side effect**.
`run_lineage_jump_fix_impact.py`'s own prior measurement found all 14
known lineage-jump transitions (as of that check) have a 29-2622-day
calendar gap, comfortably past `STALE_GAP_DAYS=5` -- `factors/momentum.py`'s
pre-existing, unconditional gap-based NaN'ing (Bug #2, already in
production, no dict required) catches these regardless of whether the
guard parameter is passed. The new KAUSHALYA transition (Bug #26) has a
~26-day gap -- same mechanism would catch it too, if `run_holdout_study1.py`
used it. **What Study 1 is NOT protected against by anything in its own
code: zero-gap same-ISIN jumps (Bug #11's own shape)** -- but that
specific exposure was already measured separately
(`run_holdout_study1_bug11_check.py`, `FINDINGS.md` Section 2: margin
3.87 -> 3.64 at the 2026-09-27/78-entity snapshot), just via a side
script, never folded into the original. Reported plainly; not re-litigated
or reopened here -- that is a bigger decision than this section.

### The proposed fix, and why it is not a one-line change

Requested shape: `read_entity_panel(con, guard=True)` by default, opt-out
requires a stated reason. **Two implementations are possible, and only
one is safe:**

1. **Delete the contaminated rows from the panel.** Unsafe. Momentum,
   forward-return, and most other factor code in this project use
   row-INDEX-based `.shift()`/`.rolling()` (position in the entity's own
   sorted sequence, not calendar alignment). Deleting one row does not
   null one computation -- it silently reindexes every later row in that
   entity's series by one position, misaligning every subsequent
   window. This would be a NEW bug class, probably worse than the
   status quo, and is exactly why the existing lineage guard works by
   NaN'ing the derived VALUE post-hoc (`_is_unexplained_jump_row`) rather
   than deleting the input row.
2. **Drop the affected ENTITY entirely** (same mechanism the 78/82-entity
   same-ISIN pin already uses). Safe -- no partial-series misalignment,
   since nothing survives to be misaligned. Costly: scoped to the FULL
   same-ISIN population (not the tight `gap_days<=5` canonical pin) plus
   the lineage population, this removes **up to ~700-750 entities**
   (same-ISIN full scope ~714 ISINs + lineage ~45, minus overlap, against
   a tracked universe of ~2,400-2,500 entities -- **roughly 30%**).
   Scoped to the TIGHT canonical pin instead (78/82 + the 45 lineage
   entities, ~120-125 total) the blast radius is small and safe, but
   **would NOT have caught Bug #26** -- KAUSHALYA's own same-isin-adjacent
   jumps have `gap_days` 61-146, all above the tight cutoff of 5.

**Conclusion, not a recommendation to implement yet**: a safe,
entity-level default guard using the TIGHT scope is cheap and would have
prevented the seven-script Bug #11 propagation gap, but would not have
prevented Bug #26 on its own. Preventing Bug #26-shaped issues (a forward
return spanning an arbitrary, caller-chosen horizon) requires either
widening the default to the full same-ISIN population (large, ~30%,
blast radius -- discards good history for hundreds of entities whose
only flaw is one old jump) or keeping the per-window check
(Amendment 2's own approach) as something every forward-return-building
script must still do explicitly, which is the exact "must be remembered"
problem this proposal was meant to solve. Flagged, not resolved; no code
changed.

## Bug #26 follow-up 2: a third option (mask, don't delete) -- and a correction to the follow-up above

**Requested 2026-11-16.** Masking (set the contaminated row's price to
NaN, keep the row) was not in the original two options. Checked
directly, not assumed: **masking is strictly safer than deletion for
row-index alignment, but it does not give the "NaN propagates
naturally" protection the proposal expected for this project's actual
factor code, and it would not have caught Bug #26 on its own.**

**Why not.** `compute_momentum`/`compute_forward_return` are TWO-POINT
`.shift()`-based ratios (`value = close[t-skip] / close[t-skip-window]
- 1`), never a day-by-day compounded product. NaN at a masked row `j`
only propagates into a downstream value when `j` is itself one of the
two shifted reference rows for that output -- a small minority of the
rows a window of width W actually touches. For every output row whose
window spans OVER `j` without landing on it as an endpoint, BOTH
reference prices read are perfectly valid, non-NaN numbers, and their
ratio still reflects the uncorrected price-level jump sitting between
them. **This is exactly Bug #26's own shape**: KAUSHALYA's transition
sits at 2024-02/03, strictly between `t0`=2023-05-30 and
`tf`=2024-04-30 -- neither endpoint. Masking the transition's own row
would have left both of Bug #26's endpoint lookups untouched and NaN-free,
and the 189x contamination would have passed through exactly as it did.
The project's EXISTING protection (`_max_gap_in_window`, a rolling-MAX
over a boolean flag across the full lookback window) already solves the
"window-spanning, not endpoint" problem correctly -- but it is a
separate, explicit, window-size-aware check, not something masking
makes unnecessary. A masked panel and an unmasked panel look identical
to `_max_gap_in_window` unless `unexplained_jump_dates` is still passed
to it explicitly -- masking the PRICE does not feed that check at all.

**What masking breaks that deletion does not.** Deletion is all-or-
nothing per entity; no row survives partially, so no aggregate can
"quietly heal" over a gap. Masking leaves the row in place with a NaN
field, and many common pandas idioms do NOT propagate that NaN loudly:
a `.rolling(W, min_periods=k)` with `k<W` (this project's own
`_max_gap_in_window` uses `min_periods=1`) or any `skipna=True`
aggregate will silently compute a result from whatever non-NaN values
remain in the window, with no error and no warning -- a false sense
that "NaN handles it" when the computation actually healed over the
contamination unnoticed. Deletion cannot do this; there is no row to
work around. Row-count-based logic (this project's own join-attrition
checks, including `scripts/earnings_drift_dev_stage1_universe.py`'s own
`len(dates) - idx - 1 < HORIZON`) is exactly backwards: masking
preserves row counts correctly (the trading day happened; only the
price is bad), while deletion would have silently shifted every later
row's index distance for that entity -- this is the one place masking
is unambiguously the correct choice over deletion, consistent with
Section 0 above.

**Cost versus the ~30% figure.** Masking invalidates individual FLAGGED
ROWS, not whole entities -- on the order of 45-90 rows total (one per
lineage transition, a handful per same-ISIN jump), against a panel of
~3.46 million rows: **under 0.01% of the panel by row count**, vastly
cheaper than entity-level deletion's ~30%. But cheap-by-row-count and
effective-by-coverage are different claims: because of the two-point-
ratio mechanics above, this cheapness does not translate into
protection for the dominant computation pattern (momentum, forward
return, and Bug #26's own construction) without ALSO changing those
functions to check "is there a masked NaN anywhere in my window" --
which is a second, necessary layer, not a byproduct of masking alone.
Where masking DOES help for free: any computation that reads a specific
date directly (Bug #26's own `c0/c1/c2/c_entry/c_exit` lookups would
correctly see NaN if the EXACT flagged date were one of those lookups --
narrower coverage than the window-spanning case, but real).

**No code changed.**

## Bug #26 follow-up 3: Study 1's lineage exposure -- answered precisely, and a correction

**Asked 2026-11-16: is `run_holdout_study1.py` exposed to zero-gap
LINEAGE jumps outside the 78-entity same-ISIN set?**

**Yes. Count: 40 entities, never measured.**

Of the 45 currently-flagged unexplained lineage transitions
(`lineage_jump_guard.unexplained_jump_boundaries`), **41 have a
calendar gap of 5 days or less** (mostly exactly 1 day -- an ISIN
re-issue with continuous trading, no halt at all) and are therefore
**not** caught by `factors/momentum.py`'s incidental `STALE_GAP_DAYS`
protection. Of those 41, exactly **1** overlaps with the 78-entity tight
same-ISIN pin (`gap_days<=5`, pinned 2026-09-27). **40 are a genuinely
distinct, never-measured exposure.**

**Correction to the follow-up above (Bug #26 follow-up 1), not an
edit** -- that entry stated "all 14 known lineage-jump transitions have
a 29-2622-day calendar gap... comfortably past `STALE_GAP_DAYS=5`,"
citing `run_lineage_jump_fix_impact.py`'s own measurement, and used
this to conclude Study 1 is incidentally protected against lineage-type
jumps generally. **That was true of the 14-entity population that
script measured against, and is false of the current, full 45-entity
population**: only 4 of 45 have a wide gap (7, 26, 245, 559 days --
KAUSHALYA among them, correctly protected); the other 41 do not. The
14-entity figure was a snapshot from an earlier, smaller backfill state,
treated here as if it still described today's data without
re-checking it first -- the same failure shape `PROJECT_CONTEXT.md`'s
own Section 9 already names twice (the 3-regime/5-regime drift,
Bug #24 follow-up). Recorded as a third instance of that shape, from
this session, on this same bug.

**Cost of measuring it, not done here, per instruction**: build a
sibling script to the existing `run_holdout_study1_bug11_check.py`
(itself a known-cost, already-run pattern), excluding these 40 entities
instead of/alongside the 78. Computationally cheap -- the same full
continuous-simulation backtest this project already reruns routinely
for materiality checks. The real cost is conceptual, not computational:
it is another read of the retired historical holdout, which this
project already treats as a materiality check rather than a new spend
(`FINDINGS.md` Section 7, the existing Bug #11 check's own precedent) --
it would need its own `data/holdout_access_log.txt` entry on that same
basis. **Not run.**
