# Delivery Study 1: experiments log

Companion to `PREREGISTRATION_DELIVERY.md` (frozen rules, commit
`311e111`, Section 6 corrected in `daacb98` before any aggregate number
existed). Records what was actually run and found, per that document's
Process section.

**Bottom line, stated first per this project's "bad results first"
discipline: DEV's mean quarterly spread is indistinguishable from zero**
(-0.20%, SE 0.69%, 38 quarters) **-- not a negative edge, simply no
signal at this power. FAMILY CLOSED, 2026-11-19, per rule 7, without
running the SELECTION null** (`PROJECT_CONTEXT.md` §3: a decisive
failure of the first gate condition kills the run; the nulls cannot
rescue it).

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
project's base rate (before this study) was 20 strategies specified, 1
passed; the ~1% MDE (Section 6) requires an effect as large as
momentum's own per-period margin to clear; and the signal is only
weakly related to momentum (Spearman 0.15-0.21), so it gets no free
ride from the one mechanism that has actually worked here. Explicitly a
prediction about the VERDICT, not about WHY -- the user's own
mechanism-prediction record in this project stands at 0 for 6.

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

## DEV result -- FAMILY CLOSED

**Bad result first: the mean quarterly spread is indistinguishable from
zero.** -0.20% net of costs across 38 usable DEV rebalance dates
(2016-07-07 to 2025-12-15), with a realized quarterly SD of 4.26%, gives
a standard error near 0.69% -- the interval comfortably contains zero.
Calling this a "negative edge" would be over-reading it; it is simply
no signal, measured at this power.

| | value |
|---|---|
| usable quarters | 38 of 38 attempted (0 skipped for an empty pool) |
| mean quarterly spread, net of costs | -0.20% |
| SD of quarterly spread | 4.26% |
| SE of the mean | 0.69% |
| win rate (spread > 0) | 42.1% (16/38) |
| mean spread dropping the single best quarter (2021-05-17, +15.97%) | -0.64% -- WORSE, not better, so the near-zero headline is not an artifact of one good quarter propping it up |

Full per-rebalance detail: `results/run_delivery_study1_dev_portfolio.csv`
(`scripts/run_delivery_study1_dev_portfolio.py`).

**BUG, found and fixed in the same step, before this number was
reported**: `delivery.signal.rebalance_dates` originally strided over
the full PRICE panel's own date range, which extends past
`delivery_eod`'s 2016-2025 coverage into 2026. That produced two
degenerate candidate rebalance dates (2026-03-18, 2026-06-23) with
eligible pools of 12 and 1 entities -- a data-coverage artifact, not a
reading. Fixed by clipping candidates to `delivery_eod`'s own max date
before striding, matching what `PREREGISTRATION_DELIVERY.md` Section 1
already specified in words; 40 usable dates became 38 (see the
Hand-trace section above, which was re-run on the fix -- no trace's
conclusion changed).

**The SELECTION null was NOT run, and will not be.**
`PROJECT_CONTEXT.md` §3's own rule: "If the first condition fails
decisively, the run is killed -- the nulls cannot rescue it." Condition
(a) (spread exceeds the benchmark, net of costs) already fails, and no
null percentile can turn an indistinguishable-from-zero mean into a
pass against condition (b). Spending the null's 5,000 seeds -- the
expensive, previously-unreliable stage the user flagged ("this
environment has killed long runs before -- a job estimated at four
hours once took seventeen") -- would buy a number with no decision
value.

**Both predictions, on the record:**

- **The user's prediction (fails the gate): CONFIRMED on verdict.** No
  mechanism was claimed, consistent with the user's own 0-for-6
  mechanism record stated in the Pre-commitments section above.
- **Claude's prediction (`PREREGISTRATION_DELIVERY.md` Section 9: fails,
  most likely at condition (b), the SELECTION-null percentile): WRONG
  on mechanism.** The result failed earlier and more plainly, at
  condition (a) itself -- the null-percentile question was never
  reached. **That is seven consecutive wrong mechanism predictions**
  for Claude in this project (`PROJECT_CONTEXT.md` §9, extended from six
  to seven by this study).

**Verdict, per the pre-committed outcome table and rule 7: NULL. FAMILY
CLOSED, 2026-11-19.** Per amendment 4 / rule 7, there is no retry at a
90-day baseline, all-days delivery, up-minus-down-days delivery,
volume-weighted delivery, or any other configuration (Section 1's three
named alternatives, and the baseline-width variants Section 5 preempted
explicitly). Any of those is a new, separately pre-registered trial --
not a continuation of this one. `PROJECT_CONTEXT.md`'s equity strategy
scoreboard updated: 21 specified, 1 passed, 20 closed.

**One finding carried forward, not specific to delivery**: the real
portfolio's own spread SD (4.26%) is roughly double Section 6's Phase 0
random-decile-null SD (2.12%) -- a signal-selected decile concentrates
exposures (sector, size, volatility) in a way a random decile does not,
so its realized dispersion is wider. Section 6's ~1% MDE was therefore
optimistic; the true detectable effect here was closer to ~2%. Recorded
as `PROJECT_CONTEXT.md` §7 finding #24, applied retroactively to the
earnings-drift MDE as well.
