"""Short-horizon (1-5 day) swing-trading research module.

Separate research question from the momentum/fundamentals work in
src/factors/ and src/reports/: see SWING.md for the question, scope, and
phase gates. Reuses src/data_layer/ read-only (prices_eod, entity
resolution, adjustment factors, isin_lineage, corporate actions via
isin_lineage/lineage_jump_guard) -- never writes to it, never modifies it.
"""
