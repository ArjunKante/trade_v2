# Post-earnings-drift: DEV result -- FAILED. Study closed. Sealed window stays shut.

**DEV fails Gate conditions 1 and 2 of `PREREGISTRATION_EARNINGS_DRIFT.md`
Section 5. Per this project's own standing rule ("A DEV failure closes a
study automatically. No approval needed, and no [sealed] read happens" --
`PROJECT_CONTEXT.md` Section 3), this closes the post-earnings-drift
family at trial 1. `known_date >= 2025-07-01` remains unread.**

Run per the preregistration's Section 10 procedure, as amended (close-
based entry, event-universe equal-weight benchmark, jump-contaminated-
window exclusion). Scripts: `scripts/earnings_drift_dev_stage1_universe.py`
through `..._stage5_remaining_gate.py`. No code in these scripts touches
`known_date >= 2025-07-01` at any point.

---

## Universe, after all exclusions (Section 1, as amended)

| Step | Count |
|---|---:|
| Events, `known_date < 2025-07-01` | 137,110 |
| No `isin_lineage` match | -1,097 |
| 78-entity canonical same-ISIN pin (79 entities, `gap_days<=5`, pinned 2026-09-27) | -- |
| Day-0/entry resolvable against the real NSE calendar | 130,353 |
| Complete event-window + entry + exit prices | 109,730 |
| Amendment 2: jump-contaminated `[d0, exit]` window | -1,257 |
| **Final DEV universe** | **108,473 events, 2,238 entities, 36 quarters** |

(The "79" vs the canonical "78" is a 1-entity difference from the exact
`before=` boundary used; not chased further, both anchor to the same
2026-09-27 pin.)

## Gate evaluation (Section 5, all five required)

**1. Mean spread > 0 with a quarter-clustered bootstrap CI excluding
zero. -- FAIL (both raw and winsorized).**

| | mean spread | 95% bootstrap CI (5,000 resamples, 36 quarter-clusters) |
|---|---:|---|
| Raw | +1.025% | [-0.098%, +2.062%] -- includes zero |
| Winsorized (primary) | +0.555% | [-0.439%, +1.536%] -- includes zero |

**2a. SELECTION null (random decile assignment within quarter, same
construction as Phase 0's corrected MDE), >=95th percentile. -- PASS.**
Raw: 100.0th percentile. Winsorized: 99.0th percentile (500 draws).

**2b. TIMING null (same events, random 60-day entry elsewhere in the
same calendar year), >=95th percentile. -- FAIL, decisively.** Real
mean spread (raw +1.025%, winsorized +0.555%) sits at the **0.0th
percentile** of 50 random-timing draws, whose own mean spread is
**+5.35% (raw) / +4.72% (winsorized)**, sd only 0.26-0.30pp across
draws -- i.e. not noisy, a stable, large gap. **Random timing on these
same stocks produces a far larger decile-minus-rest spread than
entering right after the real announcement does.** This is the
decisive, informative failure: it says the apparent edge is almost
entirely about which stocks get selected into the top decile (volatile,
likely small/micro-cap names whose 3-day event return happens to be
large), not about anything specific to the announcement or its timing.
Entering right after the announcement, as this design does by
construction (Amendment 1), captures *less* of these stocks' own
typical drift than a random entry would -- plausibly because some of
the move is already reflected in the price by the time entry happens,
3 sessions after day 0.

**3. Still positive after dropping the single best calendar year. --
PASS.** Best year: 2020 (raw +3.17%, winsorized +2.78% mean spread).
After dropping it: raw +0.757%, winsorized +0.278% -- still positive,
though winsorized is now very close to zero.

**4. Positive within the liquid bands alone (high_liq + mid_liq
turnover terciles, low_liq excluded). -- PASS**, and more strongly than
the full universe: raw +1.170%, winsorized +1.058%, on 76,043 of
108,473 events (70.1%).

**5. Net of 0.20%-0.30% round-trip costs (top-decile leg only). --
PASS at both ends, on both raw and winsorized**: at 0.30% (the worse
end), raw net spread +0.719%, winsorized net spread +0.208%.

## Verdict

**Gate fails.** Conditions 3, 4, and 5 pass; conditions 1 and 2 do not,
and all five are required. Condition 2's failure (TIMING null) is not
a near-miss -- the real spread sits below the entire 50-draw null
distribution. Per Section 5's own stated rule, condition 1's failure
alone ("If condition 1 fails decisively, the run is killed outright --
the nulls do not get a chance to rescue it") would have been enough to
stop here; the nulls were run anyway, cheaply, and corroborate the
failure rather than rescuing it.

**The sealed window (`known_date >= 2025-07-01`) was never touched.**
No script in this DEV run reads, queries, or filters on that range.

## Calibration check against Section 9's pre-committed prediction

**Wrong, specifically.** The prediction named condition 4 (liquid
bands) as the most likely failure mode, on the grounds that PEAD
effects concentrate in illiquid names. Measured result: condition 4
**passes**, and passes more strongly in the liquid subset than in the
full universe -- the opposite of the predicted direction. The actual
failure mode (TIMING null, condition 2) was not named as a candidate at
all. Consistent with this project's own calibration record
(`PROJECT_CONTEXT.md` Section 9: verdict right, mechanism wrong, 5-for-5
in the Liquidity family) -- here the *verdict* itself (fail) was
directionally expected ("I predict the study fails at least one Gate
condition"), but both the mechanism and the specific condition named
were wrong.

## Family status

**Post-earnings-drift family: CLOSED at trial 1.** No Study 2. The
family's own trial count is 1 (Phase 0 + DEV together, per the explicit
instruction recorded when the Phase 0 MDE was corrected).

---

## Pre-committed: descriptive measurement, momentum_12_1 overlap

**This is NOT a new trial. Nothing about the closed study above is
varied, re-run, or reopened by this measurement. No combined strategy is
being proposed or licensed by any result below -- the momentum+
fundamentals combination study already found combinations in this repo
need 8-72 years to size (`FINDINGS.md` Section 12). The only purpose is
to know whether the earnings-drift selection signal is distinct from
momentum_12_1, the one strategy in this repo that has passed a sealed
holdout, because that bears on how any FUTURE selection-type result here
should be read -- not on reopening this one.**

**Pre-committed, before the number exists**: a high overlap does not
reopen earnings drift and does not license a combined strategy, for the
reason stated above. A low overlap would say the two selection
mechanisms are picking different things, which is informative on its own
terms but, equally, licenses nothing by itself.

**Exact specification, frozen now:**

1. **Population**: the closed study's own final DEV universe (108,473
   events), deduplicated to one row per `(entity_id, d0)` first --
   same-day co-filed variants (Bug #26's own finding: FY-end filings
   produce up to 4 identical-return duplicates) would otherwise inflate
   the correlation sample and double/quadruple-count overlap hits for no
   new information. `is_top_decile` and `event_return` are unchanged
   from the closed study's own ranking (Stage 2).
2. **Momentum factor**: `factors.momentum.compute_momentum_12_1`, over
   `read_entity_panel()` (the same `entity_prices_daily` panel, no
   holdout authorization needed -- nothing past `SEALED_HOLDOUT_START`
   is read, since that table is already truncated there). No jump-date
   guard passed, matching exactly how `scripts/run_holdout_study1.py`
   itself calls it -- this measurement is against momentum AS ACTUALLY
   RUN, not an improved version of it.
3. **Momentum top-decile membership, "at the same date"**: momentum's
   own rebalance schedule (`all_dates[::63]`, identical construction to
   `run_holdout_study1.py`), cross-sectional top decile (`DECILE_FRAC=
   0.10`) among entities with a valid momentum value, valid 20-day
   liquidity tercile, and valid forward return (the `clean` population,
   same as the momentum study's own selection) at each rebalance date.
   For each earnings event, use the LATEST momentum rebalance date on or
   before `d0` (point-in-time, no lookahead) -- i.e., whichever momentum
   portfolio would actually have been held on that date.
4. **Rank correlation**: momentum_12_1's own dense daily value (not
   rebalance-restricted) AT `d0`, Spearman-correlated against
   `event_return`, computed separately within each of the 36 quarters.
5. **Report**: the distribution (mean, median, min, max) of (a) the
   per-quarter overlap fraction -- of each quarter's earnings-top-decile
   events, what fraction were also in momentum's own top decile at `d0`
   -- and (b) the per-quarter Spearman correlation. No aggregate
   single-number headline computed in place of the distribution.

Script, to be written and run after this commit:
`scripts/earnings_drift_momentum_overlap.py`.

### Result

52,421 deduplicated earnings events (one row per `entity_id`/`d0`),
against 37 momentum rebalance dates over the same panel.

**Overlap**: mean **7.7%**, median 7.9%, range 0.9%-12.7% across 31
quarters with both a defined earnings top decile and a defined momentum
rebalance in effect. A momentum top decile is, by construction, ~10% of
its own eligible population at every rebalance -- an overlap of 7.7% is
at or slightly *below* what pure chance would produce, not above it.

**Rank correlation** (event_return vs momentum_12_1 at `d0`): mean
**0.030**, median 0.042, range -0.078 to +0.240 across 32 quarters.
Centered near zero, no quarter far from it.

**Reading, per the pre-commitment above**: the earnings-drift selection
signal is **not meaningfully related to momentum_12_1** -- overlap is at
chance levels and the rank correlation is weak and centered on zero.
Whatever the earnings top decile was actually selecting (Gate condition
2b's own TIMING-null result already says it wasn't really the
announcement either), it was not a disguised version of momentum. This
does not reopen the closed study and licenses no combined strategy; it
says that a future selection-type result in this repo should not be
assumed to be "secretly momentum" without checking, the same way this
one checked out not to be.
