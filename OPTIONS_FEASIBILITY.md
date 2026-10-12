# NSE Options — Data Feasibility Audit

**VERDICT: BLOCKED — INSUFFICIENT DATA** for multi-year executable options
backtesting. Audit only. No schema, no implementation, no strategy. No
existing equity experiment, result, or frozen specification was touched by
this work.

## The structural finding, stated first

**Angel One SmartAPI's instrument (scrip) master contains zero expired
option contracts, verified live, not inferred.** On 2026-10-10, the full
scrip master was pulled (149,479 instruments; 36,465 NFO option
instruments) and every NFO option expiry date present was read off: the
**earliest expiry in the master was 2026-10-13 — two days out from that
date.** Not one already-expired contract was present.

This is the actual blocker, ahead of any question about which fields the
historical API returns: `symboltoken` resolution for an option contract
depends entirely on that contract still being listed. Once an option
expires, Angel's master drops it, and there is no documented way to recover
a token for it after the fact. A live authenticated call confirms the
consequence directly — `getCandleData` for a currently-listed NIFTY
03-Nov-2026 25000 CE option, requesting 60 days of history, returned data
starting only from 2026-09-28 (the contract's own listing date, 9 candles,
not 60) and exactly `[timestamp, open, high, low, close, volume]` — six
fields, no bid, no ask, no depth, for a contract that **hasn't even expired
yet**. Angel's own community documentation states the general rule this
single call illustrates: "The historical data API can provide only data of
live F&O contracts, not the expired ones." There is no field-content
question to resolve here — the data is structurally unreachable regardless
of what fields it would carry.

## Supporting evidence

**This repo today**: zero options data in any form. Checked
`data/warehouse.duckdb` (10 tables, all equity/index) and
`data/fibo_intraday.duckdb` (equity 1-minute bars only) directly, plus
every markdown doc in the repo — the only F&O references anywhere are
"F&O eligibility" used as a stock-universe liquidity filter, never actual
option contract data.

**NSE's own paid products** (official pricing sheet, effective 2026-04-01,
`NSE_Pricing_file_-_Domestic_clients_20260309171343.pdf`, fetched and read
directly): the only product in NSE's own catalog capable of reconstructing
historical bid/ask depth for options is **Historical Order & Trade Data**
(raw order-book events — new/modify/cancel messages, not a quote series) —
**Rs 6.25 lakh/year** (students/researchers, F&O) to **Rs 31.3 lakh/year**
(global commercial usage). Every other NSE product that actually carries
bid/ask (Realtime L1/L2) is real-time only, not historical. "Historical
Trade Data" (Rs 1.1 lakh/year) is trade prints only — no bid/ask. The one
viable product requires a formal license agreement with NSE Data &
Analytics and delivers raw order messages that would themselves need a
book-reconstruction engine built against them — a second project, not a
data purchase, and out of scope by instruction (no implementation).

**Retail/free vendors** (TrueData, Global Datafeeds/GDFL — checked their
own published specs, not assumed usable): neither sells a multi-year
options tick archive. TrueData's own pricing page sells tick-data retention
in **days** (10-day tier, Rs 699/month). GDFL's own data-availability table
states options (contractwise) retention is **1 calendar month**, with tick
granularity marked "NA" for options — not available at any retention. Both
are built for capturing forward from subscription date, not retrieving the
past; starting either today would mean waiting months to years to
accumulate a testable history, which is not what this question asked.

## What was not proposed

No last-traded-price substitute was proposed or considered as a
workaround. LTP-only data would make illiquid option series look
tradeable when the executable bid/ask that would actually determine fill
quality is exactly the thing this audit could not obtain. Reporting the
block as a complete answer, per instruction, rather than building around
it with weaker data.

## What this does not conclude

Implied-vs-realized volatility (and any other options-based hypothesis)
remains a defensible research question. This audit found no data path to
TEST it affordably — that is a data-access conclusion, not a judgment on
the hypothesis itself. Nothing here says the idea is weak; it says this
project cannot currently fund the data required to evaluate it.

## Status

**Supplementary live check, run 2026-10-12 09:40 IST during market hours
(`scripts/test_options_depth.py`): RESULT YES.** Angel One's
`getMarketData(mode="FULL")` — the same call `src/spread_monitor/` already
uses for equities — returns full 5-level bid/ask depth for a **live**
NFO option contract. Tested against `NIFTY03NOV2625000CE` (expiry
03-Nov-2026, not yet expired): the response carried `depth.buy`/
`depth.sell`, 5 levels each, with `price`/`quantity`/`orders` per level,
alongside LTP, open interest, and traded volume. Full raw payload logged
in the script's own output and `scripts/test_options_depth_result.txt`.

**This changes nothing above.** The verdict (BLOCKED — INSUFFICIENT DATA
for multi-year EXECUTABLE backtesting) rests on the scrip master carrying
zero expired option contracts — a fact about the PAST, which live depth
on a currently-listed contract cannot touch. What this result DOES confirm
is that a FORWARD depth collector could be built starting now, since the
one previously-open question (does Angel's live quote endpoint even carry
option depth at all) is answered. See below for that collector
(`src/options_depth/`, research/collection only).

**Observed spread on the test contract, a concrete illustration of why
"forward collector" and "tradeable" are different questions**: best bid
4.05 (qty 1300) / best ask 4.55 (qty 65), mid 4.30, spread 0.50 —
**11.6% of mid (1163 bps)**. Against this project's own LIVE-MEASURED
equity spreads on NSE cash names (`PREREGISTRATION_FIBO.md`'s band-1-50
median 0.85 bps; `FIBO_FINDINGS.md`'s band-101-200 live reading, six
names, mean 4.3 bps, range 3.1-5.7 bps) — this one option contract's
spread is **roughly 200-1400x wider** than any equity band actually
measured in this project, depending which band it's compared against.
One contract, one moment, deep out-of-the-money-adjacent but not
obviously illiquid by OI/volume shown above — not asserted as
representative of every NIFTY strike/expiry, but a real, measured number
in the same units as this project's own equity cost model, not an
assumption.

### Forward collector built (`src/options_depth/`) — research/collection only, not scheduled

A minimal collector exists: `scripts/snapshot_options_depth.py`, one
snapshot per invocation — live NIFTY spot, then every NIFTY index-option
contract across the nearest 2 expiries with strike within ±5% of that
spot, full 5-level bid/ask depth, LTP, volume, OI, appended to
`data/options_depth/v1/nifty_depth_log.csv`. No strategy, no analysis, no
signal anywhere in this package — it only collects. Separate from Fibo,
momentum, swing, and per_stock; nothing in those packages was touched.

**Run live, 2026-10-12 09:50 IST, market open**: spot 22520.5, nearest 2
expiries (13OCT2026, 19OCT2026) resolved to **180 contracts** (45 strikes
× 2 types × 2 expiries), fetched in 4 chunks of ≤50 tokens each (Angel's
`getMarketData` has a **hard 50-token-per-call limit**, confirmed live the
same session: 51 tokens → error `AB4029` "Tokens max limit exceeded", 50 →
success — not documented anywhere found in this project before now, and
the main reason this collector chunks and paces its calls at all). All 180
recorded, 0 failed.

**Storage size, measured from that real run, not estimated**:
- 1 contract's row: **~219 bytes** (CSV, 31 columns incl. full 10-price/
  qty depth fields).
- 1 snapshot (180 contracts): **~38.6 KB**.
- **1 day (3 snapshots): ~116 KB.**
- 1 trading week (5 days): ~578 KB.
- 1 trading month (~21 days): ~2.4 MB.
- 1 trading year (~250 days): ~28 MB.

Contract count (180) will drift day to day with spot level and strike
spacing — this is a real measured count from one live morning, not a
fixed constant, but representative enough that the day/week/month/year
figures above should not be read as precise to more than this order of
magnitude.

**Not scheduled at the time this was written.** See `OPERATIONS.md` for
the Task Scheduler setup (weekdays 10:30/12:30/14:30, battery-tolerant,
never wakes the machine, never crashes the schedule) and
`src/options_depth/__init__.py` for why this log cannot be reconstructed
if lost and must be copied off this laptop manually -- it is not
git-tracked (exchange quote data, same as the rest of `data/`) and has
no automated backup.
