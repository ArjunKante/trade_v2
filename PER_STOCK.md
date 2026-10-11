# Per-Stock Weekly Rules Study

**STATUS: CLOSED. Zero survivors. Pre-committed reading applied (Section
4). No forward-logging job was built.** Reopen only by an explicit,
recorded amendment -- the same discipline this project's other
pre-registered studies use, not a silent re-run.

**ALL HISTORICAL DATA USED BELOW HAS ALREADY BEEN EXAMINED in earlier
projects sharing this warehouse. The historical (FIT/CHECK) results in
this document are DEVELOPMENT EVIDENCE, NOT VALIDATION. Only forward
paper trading, logged before outcomes are known, validates anything
here.** See `PREREGISTRATION_PER_STOCK.md` for the full frozen
methodology this report applies without deviation.

**New, separate module** (`src/per_stock/`). Fibo, momentum, and every
other existing result in this project were not touched to produce this
report -- two of their tools (`fibo.universe`, the fundamental screener)
were read, unmodified, the same way they are already read elsewhere.

Run date: 2026-10-11. Warehouse data through 2026-10-09 (Bug #15's
correction -- see BUGS.md).

---

## 1. Universe: top-50 by turnover, current point-in-time, screener-gated

Top-50-by-turnover membership is the LATEST reconstituted year from
`fibo.universe.reconstitute_annually` -- **2026's membership, ranked off
2025's full-year median daily turnover.** Each of those 50 was then run
through the existing fundamental screener (`evaluate_company`, unmodified).

**21 of 50 pass** (verdict PASS or FINANCIALS-PARTIAL):

| Rank | Symbol | Verdict | Rank | Symbol | Verdict |
|---|---|---|---|---|---|
| 1 | HDFCBANK | INSUFFICIENT DATA | 26 | PAYTM | FAIL |
| 2 | RELIANCE | **PASS** | 27 | CDSL | **FINANCIALS-PARTIAL** |
| 3 | MEESHO | INSUFFICIENT DATA | 28 | IDEA | FAIL |
| 4 | BSE | **FINANCIALS-PARTIAL** | 29 | TMCV | INSUFFICIENT DATA |
| 5 | ICICIBANK | INSUFFICIENT DATA | 30 | HCLTECH | **PASS** |
| 6 | INFY | **PASS** | 31 | SWIGGY | INSUFFICIENT DATA |
| 7 | BHARTIARTL | FAIL | 32 | JIOFIN | FAIL |
| 8 | ETERNAL | **PASS** | 33 | TATASTEEL | FAIL |
| 9 | GROWW | INSUFFICIENT DATA | 34 | VEDL | **PASS** |
| 10 | TCS | **PASS** | 35 | SHRIRAMFIN | FAIL |
| 11 | SBIN | INSUFFICIENT DATA | 36 | INDUSINDBK | FAIL |
| 12 | M&M | FAIL | 37 | SUNPHARMA | FAIL |
| 13 | TMPV | **PASS** | 38 | WAAREEENER | INSUFFICIENT DATA |
| 14 | BAJFINANCE | FAIL | 39 | HINDUNILVR | **PASS** |
| 15 | AXISBANK | FAIL | 40 | MCX | INSUFFICIENT DATA |
| 16 | KOTAKBANK | INSUFFICIENT DATA | 41 | ICICIAMC | INSUFFICIENT DATA |
| 17 | LT | FAIL | 42 | HINDALCO | **PASS** |
| 18 | HAL | **PASS** | 43 | SUZLON | FAIL |
| 19 | BEL | **PASS** | 44 | NTPC | **PASS** |
| 20 | ITC | FAIL | 45 | POWERGRID | **PASS** |
| 21 | MAZDOCK | **PASS** | 46 | KAYNES | FAIL |
| 22 | TRENT | **PASS** | 47 | COFORGE | FAIL |
| 23 | DIXON | **PASS** | 48 | BAJAJ-AUTO | **PASS** |
| 24 | MARUTI | **PASS** | 49 | VBL | **PASS** |
| 25 | INDIGO | FAIL | 50 | CAPILLARY | INSUFFICIENT DATA |

**Lookahead caveat, stated per the pre-registration**: this screener
verdict is CURRENT-STATE only (no point-in-time history -- BUGS.md Bug
#12). A mild lookahead: some of these 21 could have failed this exact
screen earlier in the 2016-2026 window tested below, or the reverse. This
affects only WHICH 21 names were chosen to test, not the prices the
backtest below reads for them.

**21 stocks x 2 rules = 42 trials actually run** (not 50 x 2 = 100 --
the universe step above already narrowed 50 to 21 before any rule was
tested; see Section 3 for why 42, not 100, is Bonferroni's denominator).

---

## 2. Full trial table -- every trial, including every rejected one

`FIT`/`FIT t`/`FIT p`: mean net return per trade, t-stat, two-sided
p-value over 2016-10-01 to 2022-12-31. `CHECK`: same, over 2023-01-01 to
2026-09-30. `Null pctl`: CHECK mean's percentile against its own
1000-seed random-entry null (`n/a` = fewer than 15 CHECK trades, null not
computed). Last six columns: pass (Y) / fail (N) on each of the five
pre-registered conditions, individually, plus the combined `QUALIFIES`.

| Symbol | Rule | FIT n | FIT mean | FIT t | FIT p | CHECK n | CHECK mean | CHECK t | Null pctl | FITmean>0 | FITt>=2 | CHECKmean>0 | CHECKn>=15 | Bonf | Null>=95 | QUALIFIES |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BAJAJ-AUTO | CONTINUATION | 42 | -0.84% | -1.85 | 0.0714 | 34 | 0.27% | 0.49 | 70.1 | N | N | Y | Y | N | N | N |
| BAJAJ-AUTO | REVERSAL | 48 | -0.35% | -0.66 | 0.5126 | 13 | 1.20% | 0.93 | n/a | N | N | Y | N | N | N | N |
| BEL | CONTINUATION | 46 | -1.04% | -1.97 | 0.0553 | 35 | -0.42% | -0.64 | 35.2 | N | N | N | Y | N | N | N |
| BEL | REVERSAL | 39 | -0.86% | -1.09 | 0.2824 | 24 | 1.53% | 1.98 | 98.9 | N | N | Y | Y | N | Y | N |
| BSE | CONTINUATION | 36 | -0.20% | -0.16 | 0.8714 | 39 | 1.28% | 1.15 | 65.7 | N | N | Y | Y | N | N | N |
| BSE | REVERSAL | 41 | -0.21% | -0.25 | 0.8039 | 11 | 2.93% | 1.24 | n/a | N | N | Y | N | N | N | N |
| CDSL | CONTINUATION | 33 | -0.60% | -0.74 | 0.4618 | 33 | -0.50% | -0.54 | 35.3 | N | N | N | Y | N | N | N |
| CDSL | REVERSAL | 19 | -1.77% | -1.88 | 0.0767 | 26 | 0.65% | 0.70 | 80.8 | N | N | Y | Y | N | N | N |
| DIXON | CONTINUATION | 37 | -0.58% | -0.63 | 0.5302 | 31 | 0.57% | 0.55 | 73.0 | N | N | Y | Y | N | N | N |
| DIXON | REVERSAL | 21 | -0.73% | -0.47 | 0.6427 | 20 | -0.43% | -0.48 | 33.7 | N | N | N | Y | N | N | N |
| ETERNAL | CONTINUATION | 4 | -2.72% | -0.51 | 0.6450 | 34 | -0.06% | -0.07 | 36.0 | N | N | N | Y | N | N | N |
| ETERNAL | REVERSAL | 4 | 5.08% | 1.09 | 0.3549 | 18 | 0.67% | 0.51 | 66.2 | Y | N | Y | Y | N | N | N |
| HAL | CONTINUATION | 28 | 2.46% | 1.64 | 0.1121 | 33 | -0.33% | -0.37 | 43.2 | Y | N | N | Y | N | N | N |
| HAL | REVERSAL | 20 | -2.40% | -1.86 | 0.0778 | 21 | 1.06% | 1.07 | 89.2 | N | N | Y | Y | N | N | N |
| HCLTECH | CONTINUATION | 43 | 0.23% | 0.51 | 0.6125 | 31 | 0.03% | 0.08 | 78.1 | Y | N | Y | Y | N | N | N |
| HCLTECH | REVERSAL | 37 | 0.03% | 0.05 | 0.9568 | 24 | -0.63% | -1.05 | 34.8 | Y | N | N | Y | N | N | N |
| HINDALCO | CONTINUATION | 49 | -0.77% | -1.02 | 0.3122 | 32 | -0.66% | -1.26 | 24.6 | N | N | N | Y | N | N | N |
| HINDALCO | REVERSAL | 42 | 0.64% | 0.72 | 0.4762 | 20 | 0.07% | 0.11 | 66.9 | Y | N | Y | Y | N | N | N |
| HINDUNILVR | CONTINUATION | 60 | 0.03% | 0.11 | 0.9142 | 26 | -0.79% | -1.48 | 39.9 | Y | N | N | Y | N | N | N |
| HINDUNILVR | REVERSAL | 32 | -0.02% | -0.04 | 0.9654 | 31 | -0.97% | -2.28 | 22.4 | N | N | N | Y | N | N | N |
| INFY | CONTINUATION | 49 | -0.01% | -0.02 | 0.9857 | 34 | -0.97% | -2.20 | 19.7 | N | N | N | Y | N | N | N |
| INFY | REVERSAL | 39 | 0.96% | 1.29 | 0.2053 | 27 | 0.24% | 0.38 | 93.7 | Y | N | Y | Y | N | N | N |
| MARUTI | CONTINUATION | 38 | -1.40% | -2.82 | 0.0077 | 25 | -0.95% | -2.12 | 10.7 | N | N | N | Y | N | N | N |
| MARUTI | REVERSAL | 38 | 0.64% | 0.69 | 0.4942 | 24 | -0.63% | -1.13 | 29.3 | Y | N | N | Y | N | N | N |
| MAZDOCK | CONTINUATION | 12 | 3.60% | 1.19 | 0.2594 | 29 | 2.88% | 1.81 | 98.7 | Y | N | Y | Y | N | Y | N |
| MAZDOCK | REVERSAL | 9 | 0.04% | 0.01 | 0.9899 | 12 | 4.12% | 1.35 | n/a | Y | N | Y | N | N | N | N |
| NTPC | CONTINUATION | 41 | -1.09% | -2.05 | 0.0468 | 35 | 0.31% | 0.59 | 88.6 | N | N | Y | Y | N | N | N |
| NTPC | REVERSAL | 48 | -0.91% | -1.63 | 0.1091 | 25 | 0.64% | 0.66 | 92.8 | N | N | Y | Y | N | N | N |
| POWERGRID | CONTINUATION | 47 | -1.44% | -3.09 | 0.0034 | 23 | -0.81% | -1.33 | 20.2 | N | N | N | Y | N | N | N |
| POWERGRID | REVERSAL | 47 | 0.24% | 0.39 | 0.6951 | 19 | -0.76% | -0.87 | 23.0 | Y | N | N | Y | N | N | N |
| RELIANCE | CONTINUATION | 51 | -0.02% | -0.05 | 0.9629 | 22 | -1.33% | -2.95 | 6.8 | N | N | N | Y | N | N | N |
| RELIANCE | REVERSAL | 36 | 0.18% | 0.23 | 0.8170 | 29 | -0.06% | -0.14 | 82.6 | Y | N | N | Y | N | N | N |
| TCS | CONTINUATION | 51 | -0.53% | -1.08 | 0.2870 | 31 | -1.11% | -2.21 | 18.9 | N | N | N | Y | N | N | N |
| TCS | REVERSAL | 42 | 0.17% | 0.31 | 0.7547 | 29 | -0.87% | -1.92 | 32.6 | Y | N | N | Y | N | N | N |
| TMPV | CONTINUATION | 35 | 0.25% | 0.23 | 0.8225 | 28 | -0.84% | -1.45 | 45.1 | Y | N | N | Y | N | N | N |
| TMPV | REVERSAL | 45 | -1.87% | -2.23 | 0.0311 | 25 | -2.70% | -1.49 | 3.7 | N | N | N | Y | N | N | N |
| TRENT | CONTINUATION | 47 | -0.17% | -0.22 | 0.8264 | 30 | 1.01% | 1.57 | 95.6 | N | N | Y | Y | N | Y | N |
| TRENT | REVERSAL | 37 | -0.44% | -0.49 | 0.6272 | 22 | -0.86% | -0.91 | 28.4 | N | N | N | Y | N | N | N |
| VBL | CONTINUATION | 43 | -1.59% | -2.13 | 0.0389 | 25 | -1.06% | -1.19 | 19.0 | N | N | N | Y | N | N | N |
| VBL | REVERSAL | 30 | 3.06% | 3.60 | 0.0012 | 26 | -0.27% | -0.26 | 54.2 | Y | Y | N | Y | Y | N | N |
| VEDL | CONTINUATION | 38 | -1.85% | -2.38 | 0.0228 | 24 | 0.39% | 0.40 | 83.6 | N | N | Y | Y | N | N | N |
| VEDL | REVERSAL | 50 | -0.39% | -0.49 | 0.6291 | 19 | -2.33% | -0.66 | 10.9 | N | N | N | Y | N | N | N |

**Zero trials have QUALIFIES = Y.** No stock ever reached the "both rules
qualify -> drop both" conflict case, because no stock had even one rule
qualify.

### Illustrative case: VBL R_REVERSAL

Of all 42 trials, **VBL R_REVERSAL is the one case that shows why this
study needed every one of its gates, not just the easiest one to clear**:

| Gate | VBL R_REVERSAL | Margin |
|---|---|---|
| FIT mean > 0 | **PASS** (+3.06%/trade) | -- |
| FIT t >= 2 | **PASS** (t = 3.60) | comfortably clears 2.0 |
| Bonferroni (p <= alpha/42) | **PASS** (p = 0.00118 vs. threshold 0.00119) | inside by **under 0.1% of the threshold itself** -- the single tightest pass or fail margin anywhere in this run |
| CHECK mean > 0 | **FAIL** (-0.27%/trade) | sign flips from FIT to CHECK |
| CHECK n >= 15 | PASS (26 trades) | -- |
| Beats random-entry null | FAIL (54.2th percentile -- below the 95th-percentile bar) | not even close, once CHECK's own mean is already negative |

Judged on FIT and Bonferroni ALONE -- the two conditions a simpler study
might stop at -- this trial would have been the single strongest result
in the entire universe: a comfortable t-stat, and a p-value that survives
even a 42-way multiple-testing correction with almost no room to spare.
**It still fails**, because the apparent edge did not replicate in the
CHECK window at all (the sign of the mean return flips), and -- entirely
independently -- it does not beat what randomly entering 26 arbitrary
weeks in that same stock, same window, would have achieved anyway. This
is the concrete, numerical version of this document's own opening claim:
FIT-window backtest evidence is development evidence, not validation --
even when it clears a strict significance bar by a wide margin, it can
still be nothing once checked against an out-of-sample window and a null.

---

## 3. Survivors: zero

**No stock+rule survives all five conditions.**

**Expected number of survivors by chance alone**, two ways (n_trials_run
= 42):
- **Naive, uncorrected** (each trial tested independently at alpha=0.05,
  no multiple-testing adjustment): 42 x 0.05 = **2.1 expected false
  positives**.
- **Bonferroni-corrected** (this study's ACTUAL gate -- each trial tested
  at alpha/42 = 0.00119): 42 x (0.05/42) = **0.05 expected false
  positives** -- pinned near 0.05 regardless of how many trials were run;
  that is the entire point of the correction.

**Observed: 0.** Below even the uncorrected naive expectation (2.1), and
consistent with (not distinguishable from) the Bonferroni-corrected
expectation of 0.05.

**Forward trades needed / time to confirm**: not applicable -- there are
no survivors to compute this for.

---

## 4. Pre-committed reading, applied

Per `PREREGISTRATION_PER_STOCK.md` Section 5, recorded before this
report was written:

> **Zero survivors -> per-stock weekly patterns of this kind do not exist
> in this data at a detectable level. Record and stop.**

**This is the result.** Zero of 42 actually-run trials survive FIT
significance + Bonferroni correction + CHECK-window replication +
beating their own stock's random-entry null. The illustrative case
(Section 2, VBL R_REVERSAL) is the sharpest version of why: it passed FIT
and Bonferroni by the tightest margin anywhere in this run, then failed
CHECK replication and the null anyway -- exactly the failure mode Section
0's "development evidence, not validation" framing exists to catch, and
exactly why the CHECK window and the null are both required, not
optional extras layered on top of a FIT-only result.

**>>> STOPPING HERE, per instruction.** Forward logging (Section 6 of
`PREREGISTRATION_PER_STOCK.md`) is not built. No `src/per_stock/` runner
script, no `data/per_stock/v1/events.jsonl`, no email job exist yet. The
user decides whether forward paper trading starts on this result -- the
pre-committed reading above is a recommendation recorded in advance, not
an autonomous decision made here.

---

## Appendix: run provenance

- Universe + screener gate: `src/per_stock/universe.py`.
- Weekly/sigma panel: `src/per_stock/weekly.py` (52-week trailing sample
  std, point-in-time).
- Rule mechanics + costs: `src/per_stock/rules.py`, `src/per_stock/costs.py`
  (DELIVERY round-trip cost via `swing.costs`, unmodified; fixed-risk
  position sizing at Rs 2,000/trade, stated in the pre-registration, not
  tuned).
- FIT/CHECK/Bonferroni/null evaluation: `src/per_stock/stats.py`,
  `src/per_stock/study.py`.
- Full 42-row trial table: this document, Section 2 (also cached at
  `data/per_stock/trials_20261011.csv` for anyone re-deriving the
  numbers above without re-running the study).
- Logged in `experiments_per_stock.csv` (run_ts 2026-10-11).
