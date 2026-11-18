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
Rebalance dates: **40 usable**, 2016-07-07 to 2026-06-23 (nominal
stride-63 count before the warmup/tail trim was 43 -- close to, and
consistent with, the ~35-40 the Section 6 power calculation needs).

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
   40 usable rebalance dates for a real tie (a priori unlikely on a
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

## DEV result

Not yet run.
