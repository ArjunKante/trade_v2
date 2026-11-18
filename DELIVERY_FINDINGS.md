# Delivery Study 1: experiments log

Companion to `PREREGISTRATION_DELIVERY.md` (frozen rules, commit
`311e111`, Section 6 corrected in `daacb98` before any aggregate number
existed). Records what was actually run and found, per that document's
Process section.

## Hand-trace verification (done before any aggregate number -- Section 10 step 3)

Per instruction, these five traces were chosen deliberately to be the
AWKWARD cases, not three ordinary dates. All five found a real instance
in the DEV data (`scripts/run_delivery_study1_handtrace.py`); **none
behaved unexpectedly -- no stop-and-report was triggered by any of
them.** No aggregate number (mean spread, null, gate) was computed
anywhere in this step.

Context figures from the same run: panel = 4,293,969 entity-days /
2,967 entities; delivery data resolved to entity_id = 3,826,195 rows /
2,616 entities; combined jump-exclusion set = 732 entities, 1,417
flagged (entity, date) rows (persisted to `results/exclusions/
run_delivery_study1_dev.json`, the first and only computation of it --
every later script in this family loads this file, never recomputes).
Rebalance dates: **38 usable**, 2016-07-07 to 2025-12-15 (nominal
stride-63 count before the warmup/tail trim was 43 -- close to, and
consistent with, the ~35-40 the Section 6 power calculation needs).

**BUG FOUND AND FIXED during Section 10 step 4 (the real DEV run), before
any aggregate number was reported**: `delivery.signal.rebalance_dates`
originally strided over the full PRICE panel's own date range, which
extends past `delivery_eod`'s 2016-2025 coverage into 2026 (price data
continues; delivery data does not). That produced two degenerate
candidate rebalance dates, 2026-03-18 and 2026-06-23, whose entire
21-day measurement window falls past delivery coverage -- eligible
pools of 12 and 1 entities respectively, a data-coverage artifact, not
a real reading. Caught before being included in any mean; fixed by
clipping candidate dates to `delivery_eod`'s own max date
(2025-12-31) before striding, matching what `PREREGISTRATION_DELIVERY.
md` Section 1 already specified in words. This number above (38, not
40) and the hand-trace re-run below both reflect the fix; none of the
five traces themselves used the two dropped dates, so none of their
conclusions change.

1. **Zero up-days in a FULL-length 21-day measurement window.** Entity
   `INE416A01036`, rebalance 2017-10-16: 21/21 measurement rows present,
   **0 of them up-days** -- `is_up_day` is `0.0` (not up) for all 21,
   never `NaN`. Checked against the raw adjusted close directly: a real,
   continuous collapse, Rs 134.00 (2017-09-14) down to Rs 51.10
   (2017-10-13), falling on literally every single trading day for a
   month -- not a frozen/stale-price artifact. **Result: `abnormal_
   delivery = NaN`, `eligible = False`** -- correctly excluded, never
   silently zero.

2. **A missing/excluded day inside a FULL-length 60-day baseline
   window.** Entity `IN9623B01058`, rebalance 2016-07-07: the baseline
   window (2016-02-19 to 2016-06-06, 60 rows) contains one row
   (2016-05-26) where the prior-day comparison is unusable (a >5-
   calendar-day gap or a jump-guard flag) -- `is_up_day = NaN` for that
   one row only. **Result: that day counts toward neither up nor down**;
   `n_up_baseline = 32` of the 59 usable rows, not 60 -- the gap
   correctly shrinks the denominator rather than being silently treated
   as a down-day or dropped from the row count entirely.

3. **An entity entering the universe strictly between the baseline and
   measurement windows (a real listing event).** Searched specifically
   for a case where the entity's first-ever trade date falls after the
   baseline window opens and before the measurement window opens, at a
   rebalance date past the dataset's own early-history warmup (to avoid
   confounding "newly listed" with "every entity's lookback is short
   near 2016"). Found: entity `INE010J01012` first traded 2017-06-27,
   strictly inside the 2017-10-16 rebalance's own baseline window
   (2017-06-19 to 2017-09-14). **Result: `n_baseline_rows = 55` of
   nominal 60 (short, as expected), but `n_up_baseline = 29` and
   `n_up_measurement = 5` -- exactly at the `MIN_UP_DAYS` floor --
   giving `eligible = True`, `abnormal_delivery = +2.86`.** A short
   baseline does not automatically disqualify an entity; it is the
   up-day-with-delivery COUNT, not the row count, that gates eligibility
   -- this is the mechanism working as specified, including a real
   example that lands exactly on the minimum-count boundary.

4. **The decile boundary and its tie-break.** At the sampled midpoint
   rebalance (2021-08-13): eligible pool = 1,837, 90th-percentile cutoff
   = 10.026407, selected (`>= cutoff`) = 184 -- exactly the nominal 10%,
   zero entities tied at the exact cutoff that day. Checked across ALL
   38 usable rebalance dates for a real tie (a priori unlikely on a
   continuous float): **found one, at 2022-08-19 -- 2 entities share the
   exact cutoff value, and both are included** (the inclusive `value >=
   quantile(0.90)` rule, reused verbatim from momentum's own
   `scripts/run_holdout_study1_lineage_check.py`, never breaks a tie
   arbitrarily; it admits every tied entity, which can make the realized
   decile larger than exactly 10% -- at this particular date it did not,
   184 vs. a 184 nominal both ways, but the mechanism was exercised on
   real data, not just present unused in the code).

5. **An entity in the jump-exclusion set.** Entity `INE012Q01021`,
   flagged date 2026-05-19: present in the raw panel, **absent from the
   up-day panel after the guard** -- confirmed by direct membership
   check, not inferred. Its next real trading day (2026-05-20) correctly
   shows `is_up_day = NaN`, because the row it would have compared
   against (2026-05-19) no longer exists -- the exclusion does not
   silently leave a stale comparison in place; it removes the row and
   correctly blanks the following day's own up/down read, matching
   every other study's "cannot silently reappear as an unflagged
   neighbor" convention for this guard.

**Clean.** All five awkward cases produced the behavior
`PREREGISTRATION_DELIVERY.md` Section 1 specifies -- NaN/ineligible
where data is insufficient (never a silent zero or a silent impute), a
short window that still correctly evaluates eligibility by count rather
than by calendar span, a tie-break rule that is both specified and, on
at least one real date, actually exercised, and an exclusion that
verifiably changes the computed result rather than being passed through
inertly. No stop-and-report was warranted. Proceeding to Section 10
step 4 (the real DEV run, the SELECTION null, and the gate) is next.

## Pre-commitments, recorded before the DEV run (before any number exists)

**The user's prediction, for the calibration record -- verdict only, no
mechanism claim**: **this fails the gate.** Stated reasons: this
project's base rate is 20 strategies tested and 1 passed; the ~1% MDE
(Section 6) requires an effect as large as momentum's own per-period
margin to clear; and the signal is only weakly related to momentum
(Spearman 0.15-0.21), so it gets no free ride from the one mechanism
that has actually worked here. Explicitly a prediction about the
VERDICT, not about WHY -- the user's own mechanism-prediction record in
this project stands at 0 for 6.

This is recorded alongside, not in place of, Claude's own prediction
already fixed in `PREREGISTRATION_DELIVERY.md` Section 9 (DEV fails,
most likely at condition (b), with the same base-rate reasoning but
flagging more uncertainty since this is a new signal family) -- both
predictions existed before any DEV number, so both are checkable for
calibration afterward, independently.

**What each outcome means, fixed now so it cannot be reinterpreted
after the number exists:**

| Result | Meaning |
|---|---|
| Spread above the SELECTION null's 95th percentile AND the other gate conditions (Section 5) clear | **PASS.** Justifies a forward paper test and nothing more, per rule 6. Not a validated edge. |
| Spread positive but below the 95th percentile | **NOT a near-miss, NOT grounds for a variant.** A null result at this power. Rule 7 closes the family. |
| Spread negative or zero | **Null.** Family closes. |

There is no fourth reading. A below-threshold or negative result is not
an invitation to retry at a 90-day baseline, all-days delivery, or any
other configuration (amendment 4) -- that temptation is exactly what
produced the Swing family's six variants and its own holdout failure,
named explicitly as the failure mode this pre-commitment exists to
block.

## DEV result -- Phase A (real portfolio vs. benchmark), checkpoint before the null

**Bad result first: the mean quarterly spread is negative, -0.20% net of
costs, across all 38 usable DEV rebalance dates (2016-07-07 to
2025-12-15).** Per the pre-committed outcome table above, a negative
spread is a NULL result and closes the family -- this does not depend
on the SELECTION null, which has not been run.

| | value |
|---|---|
| usable quarters | 38 of 38 attempted (0 skipped for an empty pool) |
| mean quarterly spread, net of costs | -0.20% |
| SD of quarterly spread | 4.26% (Phase 0's own random-decile-null proxy, Section 6, was 2.12% -- this run's REAL dispersion is roughly double that, see note below) |
| SE of the mean | 0.69% |
| win rate (spread > 0) | 42.1% (16/38) |
| mean spread dropping the single best quarter (2021-05-17, +15.97%) | -0.64% -- WORSE, not better, so the headline number is not an artifact of one bad quarter either |

Full per-rebalance detail: `results/run_delivery_study1_dev_portfolio.csv`
(`scripts/run_delivery_study1_dev_portfolio.py`).

**The real spread's own SD (4.26%) is about double Phase 0's 2.12%
random-decile figure.** That 2.12% was explicitly a null-world number
(spread under RANDOM decile assignment, where the real signal plays no
role) -- it was never claimed to equal the REAL strategy's own
dispersion, and Section 6 did not promise it would. It is still worth
flagging plainly: if the SELECTION null run in Phase B reproduces
something close to 4.26% (not 2.12%) under random assignment too, the
~35-quarter power claim in Section 6 would need revisiting -- the
0.69% SE above alone already implies this specific -0.20% mean is not
distinguishable from zero on this sample (well under 1 SE from either
side).

**Verdict, per the pre-committed table (`DELIVERY_FINDINGS.md`
"Pre-commitments" section) and rule 7: NULL. The family closes.** The
user's own prediction (fails the gate) is confirmed; Claude's own
Section 9 prediction (fails, most likely at condition (b)) is NOT
confirmed in its specific mechanism -- the result fails earlier, at
condition (a) itself (spread must simply exceed the benchmark net of
costs), never reaching the null-percentile question at all.

**The SELECTION null (Phase B, 5,000 seeds) has deliberately NOT been
run.** The pre-committed outcome table decides this case (negative
spread) without it, and running an expensive, previously-unreliable
stage (user's own caution: "this environment has killed long runs
before -- a job estimated at four hours once took seventeen") to
compute a number that cannot change an already-decided verdict is not
justified by the gate alone. Stated here as a checkpoint for the user
to confirm: run it anyway for the completeness of this write-up
(reports the actual null SD, useful given the 2.12%-vs-4.26% question
above), or close the family now without it.
