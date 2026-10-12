"""Historical NIFTY index-option EOD data: NSE's free daily F&O
bhavcopy archive, NIFTY-options rows only, 2016-2026.

FEASIBILITY ALREADY ESTABLISHED (OPTIONS_HISTORICAL_FEASIBILITY.md) --
this package is the actual ingestion, not a repeat of that check. NO
BID/ASK EXISTS IN THIS DATA, IN EITHER FORMAT, AT ANY DATE -- this
package can support a fair-price-vs-realized-move research question
(PREREGISTRATION_OPTIONS.md), never an execution-cost or tradeability
question. Separate from Fibo, momentum, swing, per_stock, and
options_depth (the live forward depth collector, a different package
entirely) -- nothing in those packages is imported or modified here.

Own DuckDB file: data/options_history/options_history.duckdb. NOT
data/warehouse.duckdb.

SEALED TEST WINDOW: src/options_history/test_seal.py guards the
2023-01 to 2026-09 window the same way src/data_layer/holdout.py guards
Fibo/momentum's own sealed holdout -- raises unless explicitly
authorized. No analysis in this package may read across that boundary
by accident.
"""
