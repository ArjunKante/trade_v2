# Liquidity confluence, Study F (hourly structure, 5-minute confirmation): abandoned at Phase 1

No preregistration document exists for this study and none was written.
`src/liquidity/f.py` was never created. This file is the complete record
of what was proposed, what Phase 1 found, and why it was closed.

## Status, stated first

**CLOSED AT PHASE 1, BEFORE PREREGISTRATION, ON DESIGN GROUNDS.** Study F
is not a DEV failure (no DEV backtest ever ran) and not an underpowered
design (power was never the issue). It is **UNIDENTIFIABLE**: as
specified, no outcome of the comparison could have been attributed to
the variable the study intended to isolate.

## Provenance

**Study A (long, 5-min)**: -0.2841%, 8,131 trades, both nulls 100th
percentile. **Study B (short, 5-min)**: -0.1212%, 9,222 trades, both
nulls 100th percentile. **Study C (retest)**: -0.2694% / -0.1096%,
failed, reach rate fell. **Study D (ascending)**: -0.2926% / -0.1383%,
failed, reach rate fell. **Study E (timeframe)**: abandoned at Phase 1,
design confounded. Four DEV failures, one abandonment before Study F.
Severe selection pressure, recorded as it was for every prior trial in
this family: swing V1 hit the 100th percentile on 65,219 development
trades at p=0.001, cleared Bonferroni and BH, and scored 61.4th on its
own holdout.

**The hypothesis**: establish that a sweep occurred using the HOURLY
candle (structure), then confirm the reclaim on 5-minute candles over a
FIXED 15-minute window — the reclaim window held constant in real time,
specifically to avoid Study E's own failure (where "3 candles" silently
meant 15 minutes on one arm and 3 hours on the other). Only the sweep's
own timeframe was meant to differ from Studies A and B.

## The reason, stated plainly: two variables differ, not one

The reclaim window's WIDTH was correctly fixed at 15 minutes regardless
of the sweep timeframe — that part of Study E's own lesson was applied
correctly. But a second variable was not controlled, and it dominated
the result:

**The latency from the sweep's own extreme to the START of the reclaim
check.** In A and B, the sweep is detected on a 5-minute candle and the
reclaim check begins essentially immediately after — a lag of roughly
5 minutes between the sweep's own low/high occurring and the
confirmation clock starting. In Study F, the sweep is detected on an
HOURLY candle but is only KNOWABLE at that candle's CLOSE — so the
reclaim clock does not start until up to 55 minutes after the sweep's
own extreme occurred, averaging roughly 30 minutes depending on where
within the hour the extreme fell. **That latency was not held constant
between F and A/B. It varied by roughly 6x on average and up to 11x at
the extreme, uncontrolled, while the comparison's own framing addressed
only the reclaim window's width.**

This is not a minor confound. Because the reclaim clock starts so much
later, a large share of setups have already silently resolved — usually
by recovering back toward or past the zone — within the hour, before
the official 15-minute window even opens. The first 5-minute candle
checked after the hourly close is then often already sitting at or
above the zone, making RECLAIMED close to automatic in a way it never
is for A/B's own near-immediate check. **The latency, not the sweep
timeframe itself, was the dominant driver of the result.**

## Phase 1 numbers, verbatim

Same 12-entity, 84-entity-year sample used for Study E's own Phase 1
(6% of the universe, scale factor 16.67x, 15,176 eligible entity-days),
run through Study F's own mechanics: sweep on hourly candles from the
first hourly bucket onward, reclaim on a genuinely fixed 3-candle
(15-minute) window starting at the hourly candle's own `bucket_end`,
any new extreme during that window killing the setup as
`SWEEP_EXTENDED` rather than merely updating the stop.

| | scaled sweep_found | scaled sweep_extended | scaled not_reclaimed | scaled reclaimed | scaled fill-in-window | scaled lost to cutoff |
|---|---|---|---|---|---|---|
| Long | 44,617 | 9,883 | 17,750 | 16,983 | **15,567** | 1,350 |
| Short | 52,200 | 10,317 | 19,267 | 22,617 | **21,583** | 1,000 |

**Against A (8,131) and B (9,222): long came out ~1.9x A's count, short
~2.3x B's — an increase, in the opposite direction from what the
coarser grid alone predicts.** A coarser grid (fewer, wider hourly
candles) should, on its own, produce fewer qualifying sweep events, not
more trades overall — and indeed `sweep_found` was not dramatically
higher than the 5-minute arm's own. The inflation happened entirely
downstream, in the sweep-to-reclaim conversion rate, which the delayed
check structurally favors.

## Why this is not a fixable implementation defect

The latency is not a bug to patch. **Actionability gates on the hourly
candle's own close — the sweep is not knowable before then, by the
hypothesis's own definition of "establish structure on the hourly
candle."** Any study that establishes structure on a slower timeframe
necessarily delays the start of whatever confirmation window follows
it by up to one full slow candle, because the structure itself cannot
be confirmed any earlier. There is no alternative implementation of
"hourly sweep, 5-minute reclaim" that removes this delay without
abandoning the hourly sweep itself.

**Study F could only be run as a standalone strategy making no
timeframe claim against A and B** — "does an hourly-sweep-then-
15-minute-reclaim entry have an edge" is an answerable, well-posed
question on its own. But that is not what Study F was proposed as. It
was proposed as a timeframe comparison against A and B, specifically
designed (per its own stated purpose) to isolate whether hourly
structure selects better trades than 5-minute structure, with the
reclaim window held constant as the control. The control did not hold
the one thing that mattered. No outcome from running Study F to
completion could have been read as "hourly structure is better/worse,"
only as "hourly structure plus an average 30-minute uncontrolled delay
is better/worse" — a different, uninterrogated question.

## Runtime estimate

Using the same Study-D-derived per-trade null-stage heuristic (~3.5
seconds/trade) applied to Study E's own Phase 1: long (~15,567 trades)
≈ 15.1 hours of null stages + ~35 minutes of backtest ≈ **~15.7 hours**;
short (~21,583 trades) ≈ 21.0 hours + ~38 minutes ≈ **~21.6 hours**.
**Total sequential across the 2 configurations: ≈ 37 hours, averaging
~18.6 hours/configuration — higher per-configuration than Study E's own
average (~11.25 hours/configuration across 4 configs), despite Study F
having fewer configurations overall**, because each one individually
produces more trades.

**The 3.5-second/trade heuristic itself is a single, uncertain data
point** (one historical observation, Study D's own 2LOW-long
null-stage time divided by its trade count), not a calibrated model.
Worth stating plainly rather than treating it as more precise than it
is: **Study D's own original estimate ("in hours") was overrun by
roughly 5x** (it needed roughly 20 hours, not the few hours first
assumed) — so even this heuristic's own source already understated
reality once, and the true cost of running Study F to completion could
plausibly be higher than 37 hours, not lower.

## One design decision carried forward, reasoned correctly

The first hourly bucket (09:15-10:15) was made eligible for sweep
detection, unlike the (unexamined) exclusion Study E's own Phase 1
inherited from reusing `poc.v4.find_sweep` unchanged. The reasoning:
actionability gates on the candle's CLOSE, and the first hourly close
(10:15) already clears the 09:45 window open — so excluding it would
be arbitrary, based on an intuition about "incomplete early sessions"
that doesn't actually apply once the gating logic is examined, rather
than a deliberate conclusion from the actionability rule itself. **This
reasoning is correct and should be carried forward as the stated
default in any future intraday preregistration in this repository**:
eligibility gates on when a candle's information becomes knowable
(its close), never on when the candle itself opens.

## Liquidity family status

**Four DEV failures (A, B, C, D) — all closed at DEV with NO EDGE, TEST
never read. Two abandonments (E, F) — both caught at Phase 1, before
any preregistration was written and before any DEV backtest compute was
spent.** Study F is recorded in the same category as Study E:
specified, evaluated at the feasibility stage, found undecidable (E) or
unidentifiable (F) by design, and deliberately closed — not a DEV
failure, and not an untested idea.

This is the second time in this project that the Phase 1 feasibility
gate has caught a fatal design problem before any backtest compute was
spent on it — recorded in `OPERATIONS.md` as the second case where that
gate paid for itself.

**No committed Bonferroni gate threshold exists for this study.** A "two
configurations, p < 0.025" framing was discussed before this study was
closed, but that framing was never written into this document or into
any other committed file — it exists only in chat. Any figure for this
study's own Bonferroni correction circulating outside this repository
was never committed and should not be treated as a project fact
(`OPERATIONS.md`'s own standing rule on this).
