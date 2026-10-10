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

One supplementary live check remains scheduled, separate from the verdict
above: whether Angel One's `getMarketData` FULL mode (the same call
`src/spread_monitor/` already uses for equities) returns bid/ask depth for
a **live** (not expired) NFO option contract, during NSE market hours. This
cannot change the verdict above — it bears only on whether a *forward*
collector could be built starting now, never on retroactive historical
coverage, which is blocked regardless of this result. If the live depth
check comes back negative, it will be appended here and the options
workstream closes entirely; if positive, it is reported separately for a
build decision, not acted on in this document.
