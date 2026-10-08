"""Fibo live paper-trading system (PREREGISTRATION_FIBO.md Section 3 rules,
Section 8c frozen cost model). PAPER ONLY.

DATA-ONLY GUARANTEE, same as src/fibo/ (see PREREGISTRATION_FIBO.md Section
0): nothing in this package places, modifies, or cancels an order, and
nothing here imports or calls an Angel One order endpoint. The only Angel
One calls anywhere in src/fibo_live/ or scripts/fibo_morning.py are
getCandleData (historical/intraday candles) and the login session from
src/fibo/auth.py -- both read-only market data. This runs the frozen rules
forward on data that does not exist yet; it is a forward paper test, not an
execution system.

This is why: the historical sealed window is spent (PREREGISTRATION_FIBO.md
Section 6b, read once) and the amended re-test (Section 9) is a re-costing
of that same already-read window carrying three citation caveats (Section
9i). A live forward paper test on data that did not exist when the rules
were frozen is the only evaluation left that is not subject to those
caveats -- provided it is run honestly: watchlist fixed before the price is
known, no rule changes before 100 trades, no outcome ever edited after the
fact. See FIBO_FINDINGS.md Section 9 / 9i for why that discipline matters
here specifically.
"""
