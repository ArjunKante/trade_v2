"""Weight-based turnover and cost (PREREGISTRATION_PORTFOLIO.md Section
5), generalizing `scripts/run_holdout_study1.py`'s own name-count-
fraction formula (`turnover_frac = len(entered)/len(mom_set)`, cost
charged only on the entering set's own tercile) to a WEIGHTED portfolio,
where a name that stays in the portfolio can still change weight between
rebalances. Reduces identically to the original formula whenever every
held name has equal weight -- every name's own weight delta on entry or
exit is then exactly `1/N`, matching the original fraction exactly.

Cost is charged ONLY on INCREASING weight (a brand-new entry, or an
existing name's weight going up), each entity's own delta priced at its
own liquidity tercile's round-trip rate -- the exact convention stated
in `PREREGISTRATION.md`'s own Costs section ("applied only to entities
entering the portfolio"), extended here to mean "entering flow" in the
weighted sense rather than only a brand-new name. Decreasing weight is
never separately charged -- the round-trip rate already prices the
matched capital leaving elsewhere, the same convention the original
formula uses (it never looks at the exiting name's own tercile either).
"""
from __future__ import annotations

COST_BY_TERCILE = {"high_liq": 23.0, "mid_liq": 32.5, "low_liq": 118.0}
UNRESOLVED_TERCILE_BPS = COST_BY_TERCILE["low_liq"]  # conservative fallback, should not occur in practice


def turnover_and_cost(prev_weights: dict, new_weights: dict, tercile_lookup: dict) -> tuple[float, float]:
    """`prev_weights`/`new_weights`: {entity_id: weight}, missing keys
    treated as weight 0 (not previously held / no longer held).
    `tercile_lookup`: {entity_id: "high_liq"|"mid_liq"|"low_liq"} for
    every entity_id appearing in either dict.

    Returns (turnover, cost_as_fraction_of_nav). `turnover` is the
    standard one-way definition (`0.5 * sum(|delta|)` over the union of
    names) -- a full one-name-for-one-name swap at equal weight gives
    turnover = 1/N, matching `run_holdout_study1.py`'s own
    `turnover_frac` for a single swap exactly."""
    all_ids = set(prev_weights) | set(new_weights)
    turnover = 0.0
    cost = 0.0
    for eid in all_ids:
        w_old = prev_weights.get(eid, 0.0)
        w_new = new_weights.get(eid, 0.0)
        delta = w_new - w_old
        turnover += abs(delta)
        if delta > 0:
            bps = COST_BY_TERCILE.get(tercile_lookup.get(eid), UNRESOLVED_TERCILE_BPS)
            cost += delta * bps / 10000.0
    return turnover * 0.5, cost
