# NSE Free Daily F&O Bhavcopy — Historical NIFTY Options Feasibility

**FEASIBILITY ONLY. No analysis, no implementation, no schema, no
backfill run.** Answers five specific questions, each checked live
against the real archive, not inferred from the equity bhavcopy's
already-documented behavior (`src/data_layer/prices_nse.py`) even where
the two turned out to match exactly.

**Relationship to `OPTIONS_FEASIBILITY.md`**: that audit is about a
DIFFERENT question and is untouched by this one. It asked whether
EXECUTABLE bid/ask depth can be recovered retroactively (verdict:
BLOCKED — Angel's live API only serves currently-listed contracts, and
NSE's own paid historical products that carry bid/ask are real-time-only
or cost lakhs/year) and whether a FORWARD depth collector could be built
(verdict: yes, built, `src/options_depth/`). It never checked NSE's own
**free** daily settlement-price archive, because that archive cannot
answer the bid/ask question at all — see "Confirm it has NO bid/ask"
below. This document checks it anyway, because the research question it
can serve is different (see "What this would and would not establish").

## 1. URL patterns — confirmed back to 2016, same legacy/UDiFF split as equities

Checked live (GET, same headers as `src/data_layer/prices_nse.py`'s
fetcher; a HEAD request gets a `503` from NSE's WAF on the legacy path —
GET is required, same as the equity fetcher already assumes).

**Legacy** (date-path, one file per day):
```
https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{YYYY}/{MMM}/fo{DD}{MMM}{YYYY}bhav.csv.zip
```
e.g. `.../2020/MAR/fo23MAR2020bhav.csv.zip`

**UDiFF** (flat path, date in the filename):
```
https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip
```
e.g. `BhavCopy_NSE_FO_0_0_0_20260101_F_0000.csv.zip`

**Cutover dates, confirmed live, and they land on the EXACT SAME dates
the equity bhavcopy already cut over on** (`LEGACY_LAST_DATE`/
`UDIFF_FIRST_DATE` in `prices_nse.py`):

| date | legacy | UDiFF |
|---|---|---|
| 2024-07-05 | 200 OK | — |
| 2024-07-08 | **404** | — |
| 2024-01-01 | — | 200 OK |
| 2023-12-29 | — | **404** |

Both formats overlap Jan–Jul 2024; following the equity fetcher's own
`format_for_date` convention (prefer UDiFF whenever both exist) gives a
clean split: **legacy 2016-01-01 to 2023-12-31, UDiFF 2024-01-01
onward.**

**2016 start confirmed with real content, not just a 200**:
`fo04JAN2016bhav.csv.zip` fetched live — 2,040 `OPTIDX,NIFTY,...` rows
present. NIFTY options data exists at the very first available date.

## 2. Fields — confirmed in both formats

**Legacy** (`fo{DD}{MMM}{YYYY}bhav.csv`), header read directly off a
real file:
```
INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,
SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP
```
`INSTRUMENT`="OPTIDX" + `SYMBOL`="NIFTY" identifies the underlying/
instrument class; `EXPIRY_DT`+`STRIKE_PR`+`OPTION_TYP` (CE/PE) complete a
contract's identity (no single contract-ID field in this format — the
four together ARE the key). `OPEN`/`HIGH`/`LOW`/`CLOSE`, `SETTLE_PR`
(settlement price), `CONTRACTS` (volume, in number of contracts),
`OPEN_INT` all present and populated.

**UDiFF** (`BhavCopy_NSE_FO_0_0_0_{date}_F_0000.csv`), header and one
real row read directly:
```
TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,
XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,
LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,
ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,
Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
```
`FinInstrmId` is an actual numeric contract identifier; `FinInstrmNm`
(e.g. `NIFTY2612026950CE`) is a human-readable one. `FinInstrmTp`="IDO"
is NIFTY/BANKNIFTY-class index options specifically (`IDF`=index
futures, `STO`/`STF`=stock options/futures — four codes total, confirmed
live). `XpryDt`, `StrkPric`, `OptnTp` present; OHLC
(`OpnPric`/`HghPric`/`LwPric`/`ClsPric`), `SttlmPric`, `TtlTradgVol`
(volume), `OpnIntrst` all present and populated. Bonus field not asked
for but relevant to the stated research question: `UndrlygPric` — NSE's
own recorded NIFTY spot/underlying reference for that contract, same
moment, same file, no separate join needed.

## 3. No bid/ask — confirmed plainly

**Neither format has a bid, ask, or any depth field, anywhere, in any
row, in either era.** Every column in both headers above is either an
identifier, an expiry/strike/type, a traded-price statistic (open/high/
low/close/settlement/last), or a volume/OI statistic. This is a
once-a-day POST-CLOSE settlement file, not a quote feed — it was never
going to carry depth, and it does not. Confirms `OPTIONS_FEASIBILITY.md`
Section "The structural finding" from the opposite direction: that audit
showed Angel's LIVE feed can't be used to reconstruct the PAST; this
shows NSE's own PAST archive never carried the thing being reconstructed
in the first place.

## 4. Licensing — same terms already cleared, same host

Both URL patterns above are served from **`nsearchives.nseindia.com`**
— the exact host `LICENSE_ASSESSMENT.md` Section A already assessed for
the equity bhavcopy (`.../content/cm/BhavCopy_NSE_CM_...`), under NSE's
site-wide Data Usage and Data Sharing Policy (personal/informational/
educational use permitted, no fee; commercial exploitation and AI-
training/third-party-commercial use barred). That policy is NSE-site-
wide, not product-specific to the equity archive — it governs this same
archive mechanism (date-keyed bulk CSV.zip files) for F&O exactly as it
already does for equities. Same conditions carry over unchanged: don't
redistribute the raw files, don't sell derived signals, don't publish
the raw data; re-check before any commercial use. No separate F&O-
specific terms page was found or would be expected, given it is the same
host, the same archive mechanism, under the same general policy already
read in full for Section A.

## 5. Sample days fetched — three, including March 2020

All three fetched live via GET, parsed, and the NIFTY rows counted
directly from the downloaded content (not assumed from a status code).

| date | format | file size (zipped) | NIFTY rows found |
|---|---|---|---|
| **2016-01-04** | legacy | 326 KB | 2,040 `OPTIDX,NIFTY` rows |
| **2020-03-23** | legacy | 502 KB | 4,576 `OPTIDX,NIFTY` rows |
| **2026-01-01** | UDiFF | 1.02 MB | 1,444 `NIFTY`+`IDO` rows |

**2020-03-23 is the Monday after NIFTY's COVID-crash low week** (index
closed that day in the low-7600s having touched ~7511 days earlier) —
exactly the kind of extreme-volatility day the proposed research
question cares most about, and it has full coverage: every strike across
every listed NIFTY expiry that day, OHLC, settlement price, OI.

**One real data-quality nuance worth recording, found while reading
these rows, not assumed**: some far strikes show `OPEN=HIGH=LOW=0` but a
NON-ZERO `SETTLE_PR` — e.g. `OPTIDX,NIFTY,26-Mar-2020,6850,CE,0,0,0,
1425.95,778.35,0,0,0,0`. Zero OHLC with zero `CONTRACTS`/`OPEN_INT` means
that strike did not trade that day; NSE still publishes a model-computed
settlement price for it regardless. A "liquid near-the-money" filter
(as the stated research question already plans to use) would exclude
exactly these untraded-but-settled rows — the right filter for this
reason, confirmed by seeing a real example of what it excludes and why.

## 6. Size and time estimate — NIFTY's share of a whole-market archive

**There is no way to download NIFTY only.** Each day's file is the
WHOLE F&O market (every stock future/option plus every index
future/option) — NIFTY rows must be downloaded as part of the full file
and filtered out afterward locally. Two different numbers therefore
matter: what must be TRANSFERRED (the full files) and what would
actually be KEPT (NIFTY options only).

**Trading days, 2016-01-01 through 2026-10-12** (~248 trading days/year,
NSE's typical count): legacy era (2016–2023, 8 full years) ≈ 1,984 days;
UDiFF era (2024 through 2026-10-12) ≈ 692 days. **Total ≈ 2,676 files.**

**Average file size, measured directly from 12 real samples spread
across 2016–2026** (not interpolated from the 3 required samples alone):
legacy era mean ≈ 501 KB/day (range 326–757 KB — file size grows over
the period as weekly expiries and more stock-option strikes were added);
UDiFF era mean ≈ 999 KB/day (range 931 KB–1.09 MB).

**Total download required**: 1,984 × ~501 KB + 692 × ~999 KB ≈
**1.6 GB**, at the same polite 0.8s-sleep-between-requests convention
`prices_nse.py` already uses for equities. Real fetch time observed
across the 12 samples averaged 0.84s/file; at (0.84 + 0.8)s/file ×
2,676 files ≈ **73 minutes (~1.2 hours)**.

**NIFTY-options-only share, measured directly** (not assumed): in the
2020-03-23 legacy sample, NIFTY-option rows are 10.3% of that day's
uncompressed bytes; in the 2026-01-01 UDiFF sample, 4.3% (UDiFF's
per-day universe is larger — more stock-option strikes — so NIFTY is a
smaller slice of a bigger file, despite similar absolute NIFTY row
counts). Applying each era's own measured fraction to that era's total:
**NIFTY-options-only extracted size ≈ 100 MB (legacy era) + 29 MB
(UDiFF era) ≈ 129 MB for the full 2016–2026 history.** An
order-of-magnitude estimate (the fraction visibly varies day to day with
volatility and strike-chain width), not a precise prediction.

## What this would, and would not, establish

**Would serve**: the stated research question — whether NIFTY option
prices systematically imply larger moves than subsequently occur — needs
FAIR prices to compare against realized moves, not EXECUTABLE ones.
Liquid near-the-money closing/settlement prices (filterable using OI and
volume, both present in every row, in both eras) are a reasonable proxy
for a fair price at each day's close, for exactly this purpose.

**Would NOT establish**: tradeability after costs. This archive has no
bid/ask at any point in its history (Section 3) — there is no way to
compute a realistic spread, slippage, or fill-quality estimate from it,
for any date, ever. Any version of this research that tried to say "and
this edge survives execution costs" would be asserting something this
data source cannot support, in either direction. That is exactly the
same boundary `OPTIONS_FEASIBILITY.md` already drew for the live-depth
collector, applied here to a different, non-executable data source for
a different, non-executable research question.

## Status: feasible for the fair-price research question. Not built.

No fetcher, schema, or backfill script exists as a result of this
document. No slot spent, no pre-registration, no decision made here
beyond the feasibility check itself.
