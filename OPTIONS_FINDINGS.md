# NIFTY ATM Straddle vs. Realised Payoff — Findings

**STATUS: CLOSED.** Pre-registered (`PREREGISTRATION_OPTIONS.md`, amended
and committed on its own, `3974d09`, before any number existed), run
once, DEV and TEST in the same pass, sealed-test access authorized and
logged (`data/options_history/test_window_access_log.txt`). This document
records the result and closes the study — reopening it is an explicit,
recorded amendment, not a silent re-run.

## Verdict

**NO DETECTABLE MISPRICING AT THIS SAMPLE SIZE.**

Per the Section 5f decision rule, applied exactly as written: DEV's mean
R was not negative at all (+0.1089, 95% CI [-0.0758, 0.3232], includes
0) — the strongest possible pre-condition for "systematically
overpriced" already fails in the development window, so the TEST
window's own result (mean R -0.1327, CI [-0.3278, 0.0849], same sign as
"overpriced" but not significant) is moot for the combined verdict.

**This is an absence-of-evidence statement, not proof that NIFTY options
are fairly priced.** 82 (DEV) and 41 (TEST) non-overlapping monthly
observations is not a large sample for a quantity this volatile; a real
effect smaller than the study's own pre-registered detectable-effect
size (Section 5b: roughly 0.21-0.29 standardized) would not have been
caught here even if it exists.

## The key observation — the amendment's own vindication, numerically confirmed

**Median R was negative in every single window**: -0.0758 (DEV), -0.1193
(DEV excluding 2020), -0.3359 (TEST). **Mean R was NOT negative in DEV or
DEV-excluding-2020** (+0.1089 and +0.0175 respectively) — only TEST's
mean matched its median's sign (-0.1327), and even there the CI does not
exclude zero.

This is not a side note — it is the concrete reason
`PREREGISTRATION_OPTIONS.md`'s amendment 1 replaced the original
log-ratio test before any of this was computed. Checked directly, after
the fact, as a verification of that amendment's own reasoning rather
than a second official test: recomputing **mean(log(payoff/straddle))**
— the ORIGINAL, now-replaced test statistic — on the exact same observations
gives **-0.2774 (DEV), -0.3504 (DEV excl. 2020), -0.4914 (TEST)**. Negative
in all three. The original test would have reported **"options are
systematically overpriced" in every window, including DEV**, where the
real quantity that actually matters for "overpriced" — the plain mean
return from buying the straddle, R — is positive. A log-based test
flags a market as overpriced for buying the straddle in a window where
doing so, on average, made money. This is exactly Jensen's-inequality
artifact the amendment described before seeing any number: `E[log(X)] <
log(E[X])` for skewed X regardless of whether `E[X]` itself is above or
below 1. The amendment was not a style preference; a wrong test would
have produced a confidently wrong headline here.

## Descriptive only — not a tested claim

DEV's positive mean R is carried almost entirely by one year: **+0.1089
with 2020 included, +0.0175 with it excluded** — a roughly 6x reduction,
not a rounding difference. This is consistent with the classic shape of
selling optionality: small, steady gains in most months (the negative
median — in a typical month, the straddle cost more than it paid out)
offset by rare, large losses to the seller (equivalently, large gains to
the buyer) exactly when realised volatility spikes far beyond what was
priced in, as it did in 2020-03. **This is a description of the result's
composition, not a hypothesis this study tested or pre-registered** — no
claim is made here about whether this pattern would recur, generalize,
or be tradeable; it is offered only because the decision rule's own DEV-
excluding-2020 figure (Section 5c) was specifically designed to make this
visible rather than buried inside one pooled number, and it is visible.

## Full figures

| | DEV | DEV excl. 2020 | TEST (sealed) |
|---|---|---|---|
| Calendar months | 84 | 72 | 45 |
| Achieved n | 82 | 70 | 41 |
| Mean R | +0.1089 | +0.0175 | -0.1327 |
| 95% bootstrap CI (10,000 resamples) | [-0.0758, 0.3232] | [-0.1490, 0.1824] | [-0.3278, 0.0849] |
| Median R (descriptive) | -0.0758 | -0.1193 | -0.3359 |
| mean(log(payoff/straddle)) — the REPLACED test, for comparison only | -0.2774 | -0.3504 | -0.4914 |
| Lag-1 autocorrelation of R | -0.0228 | -0.0078 | +0.1253 |
| Materiality threshold (2/√n) | 0.2209 | 0.2390 | 0.3123 |
| Block bootstrap triggered | No | No | No |
| Realised move, mean/median (NIFTY points, secondary/descriptive) | 487.82 / 453.32 | 425.77 / 376.33 | 571.26 / 507.55 |

5 of 129 calendar months were dropped, each with a stated, non-improvised
reason (full detail in the run's own output): 1 (DEV, 2016-01) had fewer
than 20 trading days of NIFTY history before it; 4 (1 DEV, 3 TEST) had a
contractual expiry date that is a confirmed NSE holiday, which NSE's
bhavcopy records anyway even though no trading — and so no NIFTY close —
actually occurred that day; 1 (TEST, 2026-09-29) fell past
`index_eod`'s own data coverage. None were liquidity-filter drops in this
run — every month that had a computable measurement reached a nonzero-
volume ATM strike on both legs.

## Limitation

**Closing prices only. No bid/ask exists anywhere in this dataset, at
any date** (`OPTIONS_HISTORICAL_FEASIBILITY.md`). This result says
something about whether NIFTY options were fairly priced relative to
what subsequently happened — it says nothing, and cannot be extended by
further analysis of this same data to say anything, about whether a
strategy acting on it would be profitable after real transaction costs.

## Scope note

This closes the **options-history** study (`src/options_history/`,
`data/options_history/options_history.duckdb`). The **forward live
options-depth collector** (`src/options_depth/`,
`scripts/snapshot_options_depth.py`, the `FiboEvening`-style scheduled
collection of live NIFTY-option bid/ask depth) is a separate module,
answers a separate question, and is unaffected — it continues collecting
on its own schedule.
