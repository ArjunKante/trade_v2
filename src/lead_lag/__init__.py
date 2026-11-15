"""Cross-Liquidity-Tier Return Propagation (lead-lag) family.

Isolated namespace, new in Phase 4. No existing strategy family's module
is imported for write purposes; read-only reuse only (see
`PREREGISTRATION_LEAD_LAG_V1.md` Section 0 reuse boundaries):
`fibo.universe`, `fibo.intraday_db`, `data_layer.nse_holidays`,
`data_layer.isin_lineage`/`corporate_actions` (schema only, via direct
SQL against the warehouse), `data_layer.holdout` (retired for this
warehouse, not invoked).

Governing documents: `PREREGISTRATION_LEAD_LAG_V1.md`,
`LEAD_LAG_PORTFOLIO_LEVEL_METHODOLOGY_PROPOSAL.md`,
`lead_lag/MASTER_SPEC_LEAD_LAG.md`. Approved decisions implemented here:
6, 7, 8, 9, 10, 11, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24.

Deferred, NOT implemented in this phase (per explicit Phase 4
authorization scope): Decision 12's bootstrap numerical sub-parameters,
missingness emulation, follower-breadth/power diagnostics, and making
the primary-gate multiplicity correction operative. No null-generation
or multiple-testing machinery is implemented here; no primary gate is
run.
"""
