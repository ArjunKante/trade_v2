"""Live bid-ask spread measurement, infrastructure only.

No strategy logic, no signals, no orders. Records what Angel One's
market-depth quote returns, as a logged, auditable dataset -- nothing in
this package decides whether any spread is cheap, expensive, or
tradeable. See scripts/snapshot_spreads.py and scripts/spread_summary.py
for the two entry points.
"""
