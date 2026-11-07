# Governing research directive: Cross-Stock Lead-Lag Propagation

## Provenance

This document did not previously exist as a committed artifact. It is the
exact text the human user gave Claude, verbatim, as the task-originating
instructions for the "cross-stock lead-lag propagation" research family,
on 2026-11-07, in the session that produced `lead_lag/LEAD_LAG_RECONNAISSANCE.md`,
`lead_lag/DATA_AUDIT_LEAD_LAG.md`, `lead_lag/LEAD_LAG_FEASIBILITY.md`, and
`PREREGISTRATION_LEAD_LAG_V1.md`.

**Why this file exists now, and not from the start**: those four documents
cite this text roughly two dozen times as "Part 0" through "Part 15,"
"Part 4.1," "Part 7.4," "Part 12 Phase 2," etc., as if it were an
authoritative, checkable specification. An independent methodology review
(2026-11-08) searched the entire repository for this text and found zero
hits outside the lead-lag family's own citing documents -- i.e. every
"per Part X.Y" claim in those four documents was, until this commit,
**unverifiable from the repository itself**, in violation of this
project's own standing rule that "a figure is not a project fact until it
is committed" (`OPERATIONS.md` line ~1533, quoted in
`LEAD_LAG_RECONNAISSANCE.md` Section 6). This file closes that gap by
committing the actual text being cited, reproduced exactly as given, with
no paraphrasing, summarizing, or reinterpretation. It is authoritative for
this family specifically because it is the literal instruction set that
created the family -- not because it is claimed to be an external,
pre-existing standard. Nothing below has been edited to retroactively
justify any design choice already made in Phases 0-3; it is reproduced
as-received.

Section numbering below ("PART 0" through "PART 15") matches the citation
convention already in use in the other lead-lag documents, so existing
"Part X.Y" references now resolve to this file without needing to be
rewritten, except where the Amendment to `PREREGISTRATION_LEAD_LAG_V1.md`
(2026-11-08) explicitly updates a citation for clarity.

---

# MASTER PROMPT — CROSS-STOCK LEAD-LAG PROPAGATION
## NSE Equities | 1-Minute Historical Data | Independent Quantitative Research Family

You are acting as a senior quantitative researcher, financial econometrician, market microstructure researcher, and research-engineering auditor.

Your task is to investigate whether **cross-stock lead-lag propagation creates a statistically detectable and economically tradeable predictive relationship in Indian NSE equities**.

This is a completely new research family.

You must follow the existing project's research methodology, documentation conventions, statistical standards, and operational constraints.

You are not being asked to manufacture a profitable strategy. You are being asked to determine, honestly and reproducibly, whether a particular market phenomenon exists in the available data, whether it is robust, and whether it can potentially be monetised after realistic execution costs.

A negative result is a valid and useful outcome.

A statistically significant result that cannot survive transaction costs is a failure as a trading strategy.

Do not optimise your way into a positive result.

---

# PART 0 — PROJECT CONTEXT AND AUTHORITY

Before doing anything, read the project's existing context and research documentation.

The primary project context document is:

`PROJECT_CONTEXT.md`

Read the relevant existing files, including, wherever available:

- `OPERATIONS.md`
- `FINDINGS.md`
- Existing preregistrations.
- Existing findings and abandonment documents.
- Existing cost-model documentation.
- Existing data-quality and point-in-time validation documentation.
- Existing execution and trade-simulation implementations.
- Existing universe construction and entity-resolution documentation.

The project is a systematic research programme on NSE equities.

The purpose is to identify genuine, statistically defensible, economically viable trading edges.

The project has already established:

1. 63-day cross-sectional momentum is the only clean sealed historical pass.
2. Fibo/ORB has passed after multiple corrections, but has significant caveats and is undergoing prospective forward testing.
3. Multiple intraday strategies, including liquidity sweeps, Darvas, FVG, POC, and other chart-pattern families, failed.
4. The Liquidity family was closed on 2026-11-07. It must not be revived.
5. The historical equity holdout is retired. No new equity research can claim independent historical holdout validation.
6. All new equity studies are development-only and can justify prospective forward testing, nothing more.
7. The project has a strict preregistration, null-testing, multiple-testing, cost-accounting, and documentation methodology.

The project's transferable findings are particularly important:

- Matched random entry from the same pool is a critical benchmark.
- Beating random is necessary but not sufficient.
- A gross-return null cannot identify position-sizing or execution-cost problems.
- Candle-counted windows must be converted into fixed minutes when comparing timeframes.
- A counterfactual must reuse the original setup rather than independently rerun a detector.
- Bugs must be measured in both directions.
- Statistical power and MDE must be calculated before a comparison study is finalized.
- A failed DEV study is closed automatically.
- Results must be recorded honestly, including negative and inconclusive findings.

Treat these as binding research rules.

## Absolute isolation requirement

This research family must not interfere with any existing strategy, study, or live system.

DO NOT:

- Modify existing strategy source files.
- Modify existing strategy parameters.
- Modify existing preregistrations.
- Modify existing findings.
- Reopen closed studies.
- Change the Fibo forward test.
- Change the momentum basket.
- Change existing data-ingestion behaviour.
- Change the project's shared cost assumptions.
- Change shared trading infrastructure.
- Modify historical datasets.
- Reuse a failed strategy's entry detector under a different name.
- Combine this strategy with any existing strategy.

Existing infrastructure may be read and reused where appropriate, but all new research outputs, configurations, experiment identifiers, results, and trade ledgers must be independent.

If a shared component needs modification, do not make the modification. Document the requirement and stop for approval.

This family must have its own trial accounting and multiple-testing correction.

---

# PART 1 — RESEARCH QUESTION

Investigate the following hypothesis:

**When a group of leading NSE stocks experiences an abnormal price movement, do other stocks within the same sector respond with a measurable delay, creating a predictable subsequent return relationship?**

Example:

- A leading banking stock experiences an abnormal positive return.
- Other banking stocks have not yet exhibited the same magnitude of movement.
- Over the subsequent 5–60 minutes, do those stocks exhibit positive abnormal returns?

The underlying proposed mechanism is information propagation, common-factor transmission, or asynchronous repricing across related securities.

Do not assume that the mechanism is true.

The objective is to measure whether a predictive relationship exists.

Distinguish carefully between:

1. Correlation.
2. Predictive lead-lag relationships.
3. Sector-wide common-factor movements.
4. Genuine incremental predictive information.
5. Economically executable trading opportunities.

A stock moving before another stock does not automatically establish a tradeable lead-lag relationship.

The leading stock might simply be reacting to information that is already reflected in the broader market.

You must control for that possibility.

---

# PART 2 — DATA AUDIT BEFORE RESEARCH

The project has approximately ten years of historical data.

Known context:

- NSE equities.
- Point-in-time daily price data beginning January 2016.
- One-minute intraday OHLCV bars beginning 2016-10-04.
- Intraday universe described as the top 200 stocks.
- Corporate-action handling and ISIN/entity resolution infrastructure.
- Existing market data and execution tooling.
- Historical NIFTY and sector-related information may be available.

These are known project-level descriptions, NOT permission to assume every required field is complete.

Your first task is to inspect the actual database, repository, and data schemas.

Establish:

### 2.1 Data coverage

Report:

- Actual earliest one-minute date.
- Actual latest one-minute date.
- Number of unique instruments.
- Number of unique ISINs.
- Number of trading dates.
- Number of observations.
- Number of missing trading dates.
- Number of missing bars within trading sessions.
- Number of duplicate bars.
- Number of zero-volume bars.
- Number of abnormal OHLC records.
- Coverage by stock and year.
- Coverage by sector, if available.

Identify whether the top-200 universe is:

- A historically point-in-time universe.
- A present-day top-200 universe backfilled historically.
- A mixed universe.
- Something else.

Do not assume it is survivorship-bias-free.

### 2.2 Timestamp integrity

Verify:

- Whether bar timestamps represent bar start or bar end.
- Whether the timestamp denotes exchange time or ingestion time.
- Whether timestamps are consistently in IST.
- Whether missing timestamps represent genuine no-trade intervals or missing data.
- Whether the final bar of the session is handled consistently.
- Whether the opening auction and pre-open period are included.
- Whether all instruments follow the same session conventions.

Do not infer tradability from a missing bar.

### 2.3 Price integrity

Inspect:

- Split adjustment.
- Bonus adjustment.
- Corporate-action handling.
- ISIN changes.
- Entity resolution.
- Stale prices.
- Price-scale inconsistencies.
- Historical instrument mappings.

Pay particular attention to the project's documented Bug #18, involving inconsistent price scales and incorrect stock selection.

Use the validated price-adjustment infrastructure.

Do not create a second independent corporate-action adjustment mechanism.

Verify the relevant correction has been propagated to every new data path.

### 2.4 Data availability decision

Create:

`DATA_AUDIT_LEAD_LAG.md`

Classify each requirement as:

- PASS.
- FAIL.
- PARTIAL.
- UNVERIFIED.

If historical sector classifications, constituent membership, or historical liquidity data are missing, do not silently substitute current information.

Document what is unavailable and how it affects the research design.

Do not run outcome analysis until the audit is complete.

---

# PART 3 — STOCK UNIVERSE AND GROUPING

This is one of the most important parts of the research.

The objective is to identify relationships between stocks that genuinely belong to related economic or market groups.

Do not simply group stocks based on their recent price correlations. That would create data-dependent groups and introduce another source of selection bias.

## 3.1 Primary universe: sector-based grouping

Use historical NSE sector classification or another historically valid, documented classification source.

Preferred hierarchy:

1. NSE sector classifications.
2. Historical NSE sector-index constituents.
3. Historical industry classifications already maintained in the project.
4. Another reliable historical classification source, only if documented and justified.

Do not use today's sector membership for historical dates without explicitly quantifying the survivorship and classification bias.

Create sector groups such as:

- Banking.
- Financial Services.
- Information Technology.
- Automobiles.
- FMCG.
- Pharmaceuticals.
- Metals.
- Energy.
- Realty.
- Infrastructure.
- Telecommunications.
- Consumer Durables.
- Chemicals.
- Other valid sectors supported by the data.

This list is illustrative. Use the actual historical classification and do not force stocks into categories that are not supported by the source.

## 3.2 Primary eligibility rules

A stock must satisfy:

- Valid historical entity mapping.
- Valid trading status on the relevant date.
- Sufficient historical data.
- Sufficient liquidity.
- Valid OHLCV records.
- No unresolved corporate-action or price-scale issue.
- A reliable historical sector classification.

Use trailing information only when determining eligibility.

For example, liquidity eligibility must use data available before the signal date.

Do not use future market capitalisation, future turnover, or current index membership to select historical leaders.

## 3.3 Leader and laggard classification

Define two roles:

**Leaders:** stocks with relatively high historical liquidity within their sector.

**Laggards:** other eligible stocks in the same sector.

Use trailing median traded value as the initial liquidity measure.

Candidate lookback:

- 60 trading sessions.
- Calculate median daily traded value.
- Rank stocks within each sector.
- Identify the most liquid 20% as the initial leader pool.

This is a proposed starting specification, not a result.

Before adopting it:

- Verify that it provides sufficient stocks per sector.
- Calculate the number of eligible leader-laggard pairs.
- Check how frequently group membership changes.
- Determine whether the resulting sample is statistically adequate.
- Calculate MDE.

If 20% produces too few leaders or insufficient coverage, do not casually change it.

Document the issue and propose an alternative before examining predictive outcomes.

The primary classification must be frozen before outcome analysis.

## 3.4 Minimum group requirements

A sector must have enough eligible securities to support a meaningful comparison.

Investigate:

- Minimum eligible stocks per sector.
- Minimum number of leaders.
- Minimum number of laggards.
- Number of valid leader-laggard pairs.
- Coverage over time.

Do not let one sector with hundreds of observations dominate the result simply because it has more constituents.

Report results by sector as well as aggregate results.

Sectors with inadequate coverage should be excluded from the primary universe with the exclusion documented.

---

# PART 4 — SIGNAL CONSTRUCTION

The core signal is an abnormal movement in a leader relative to its relevant market and sector factors.

The signal must be calculated using information available at the time.

No future information is permitted.

## 4.1 Market adjustment

For each stock, construct minute-level returns.

Use consistent price conventions and validated corporate-action handling.

Calculate market-adjusted returns using an appropriate market benchmark, preferably NIFTY 50 or a suitable broader market benchmark if available.

Also calculate sector-adjusted returns.

Use leave-one-out sector returns:

When evaluating stock A, the sector benchmark must not include stock A.

Likewise, a leader's own movement must not mechanically contaminate the laggard's benchmark.

The benchmark construction must be documented.

## 4.2 Leader signal

Primary proposed signal:

A leader's cumulative abnormal return over the preceding 5-minute interval.

Formally:

\[
S_{i,t}^{(5)}
=
\sum_{k=t-4}^{t} AR_{i,k}
\]

Where:

- \(i\) is the leader.
- \(t\) is the completed signal minute.
- \(AR\) is the appropriately market- and sector-adjusted return.

Verify the exact timestamp convention before implementing this formula.

A signal is only available after the final required bar has completed.

Do not use the current incomplete candle.

## 4.3 Sector leader portfolio

Where multiple leaders exist in a sector, construct a leader portfolio.

Use equal weighting as the primary specification.

Do not choose weights after observing results.

The portfolio return must be calculated from information available at that point.

Avoid double-counting the same stock when constructing multiple leader signals.

## 4.4 Laggard response

For each eligible laggard, measure:

- Its abnormal return over the leader's signal interval.
- Its relative movement compared with the leader portfolio.
- Its subsequent abnormal return.

The initial question is:

Does the leader portfolio's abnormal movement predict the laggard portfolio's subsequent abnormal movement?

Also investigate whether the relationship exists at individual stock level.

The primary analysis should preserve the distinction between:

- A laggard that has not yet moved.
- A stock that has already moved in the opposite direction.
- A stock that has already moved in the same direction.

Do not automatically classify every lower-return stock as a laggard without investigating its prior movement.

## 4.5 Continuous signal first

The primary research should use continuous signals.

Do not start by searching through dozens of threshold combinations.

Investigate whether the magnitude of leader abnormal returns has incremental predictive power for future laggard abnormal returns.

A regression-based approach is appropriate.

At minimum, consider:

\[
AR_{j,t+h}
=
\alpha
+
\beta S_{sector,t}
+
\gamma X_{j,t}
+
\epsilon_{j,t+h}
\]

Where:

- \(j\) is the laggard.
- \(S_{sector,t}\) is the leader portfolio signal.
- \(X_{j,t}\) contains predetermined control variables.
- \(h\) is the prediction horizon.

The actual model must account for relevant market, sector, volatility, liquidity, time-of-day and own-stock momentum effects.

Do not treat this simple equation as a complete specification.

The objective is to determine whether the leader signal adds information beyond those controls.

---

# PART 5 — TIME HORIZONS

The research must explicitly investigate different prediction horizons.

Primary proposed horizons:

| Horizon | Purpose |
|---|---|
| 5 minutes | Very short propagation |
| 15 minutes | Short-term propagation |
| 30 minutes | Medium intraday propagation |
| 60 minutes | Longer intraday propagation |

All windows must be expressed in actual trading minutes.

Do not use candle counts as substitutes for elapsed time.

Do not accidentally cross the market close.

Do not treat overnight gaps as ordinary intraday observations.

Account for:

- Market holidays.
- Trading halts.
- Missing bars.
- Session boundaries.
- Instrument-specific trading availability.

The primary horizon must be selected before outcome analysis using economic reasoning, feasibility, and statistical power.

Other horizons must be included in the multiple-testing correction.

Do not report only the best-performing horizon.

---

# PART 6 — MARKET REGIMES AND CONTROL VARIABLES

Investigate whether the relationship changes under different market conditions.

Potential control variables:

1. NIFTY market return.
2. Sector return.
3. Laggard's own recent momentum.
4. Leader's recent volatility.
5. Laggard's historical volatility.
6. Relative traded value.
7. Time of day.
8. Market-wide volatility.
9. Market direction.
10. Liquidity conditions.

Use historically available information only.

Potential regime breakdowns:

- High versus low market volatility.
- Bull versus bear market periods.
- High versus low market activity.
- Opening session versus midday versus closing session.
- Large-cap versus smaller eligible stocks.

These are initially descriptive or pre-specified interaction analyses.

Do not create many arbitrary regime thresholds and select the best one.

Any regime-specific result must account for multiple testing.

---

# PART 7 — PRIMARY STATISTICAL STUDY

Before running any predictive outcome analysis, create a complete preregistration.

Filename:

`PREREGISTRATION_LEAD_LAG_V1.md`

It must contain:

1. Research hypothesis.
2. Primary estimand.
3. Data sources.
4. Universe definition.
5. Historical sector grouping.
6. Leader definition.
7. Laggard definition.
8. Signal construction.
9. Benchmark construction.
10. Prediction horizons.
11. Controls.
12. Exclusions.
13. Missing-data handling.
14. Statistical methodology.
15. Multiple-testing correction.
16. Null hypotheses.
17. Power and MDE.
18. Economic significance threshold.
19. Execution-cost assumptions for any secondary trading simulation.
20. Verdict rules.
21. Failure conditions.
22. Reproducibility requirements.

The preregistration must be committed alone before the first outcome result exists.

Do not modify it after the results are known.

If any specification needs to change, record the change in a new version with its own trial accounting.

## 7.1 Primary estimand

Measure the incremental predictive relationship between leader abnormal returns and subsequent laggard abnormal returns.

Report:

- Regression coefficient.
- Standard error.
- Confidence interval.
- Statistical significance.
- Economic magnitude.
- Incremental explanatory power.
- Stability across time.
- Stability across sectors.
- Stability across liquidity bands.

Do not rely exclusively on a p-value.

## 7.2 Statistical inference

Intraday observations are highly dependent.

Do not use ordinary IID standard errors.

Use appropriate dependence-aware inference, including:

- Trading-day clustered standard errors.
- Multi-day or block bootstrap as appropriate.
- Resampling methods that preserve cross-sectional dependence.
- Robustness checks against alternative inference procedures.

Do not resample individual minute observations independently.

Account for overlapping forward-return horizons.

Where possible, use a non-overlapping sample as a robustness check.

Explain the limitations of the chosen inference method.

## 7.3 Multiple testing

Account for all configurations that reach a gate.

Include:

- Prediction horizons.
- Sector-level tests.
- Market-regime tests.
- Signal variants.
- Any other tested configurations.

Use an appropriate family-wise correction, such as Bonferroni, where applicable.

A secondary false-discovery-rate analysis may be reported, but must not replace the primary correction.

Do not silently change the denominator.

Maintain an append-only trial ledger.

## 7.4 Economic significance

A statistically detectable relationship may be too small to trade.

Define a minimum economically meaningful effect before outcome analysis.

Calculate the MDE at the required power and significance level.

If the study is underpowered to detect a plausible economically meaningful relationship, stop before running the expensive study.

Do not run an experiment simply because the dataset is large.

---

# PART 8 — NULL HYPOTHESES

Both project-standard nulls are mandatory for a trading simulation.

For the predictive measurement, additionally use the following controls.

## 8.1 Timing null

Does the leader signal provide better prediction than randomly selected signal times for the same securities and dates?

Random timing must preserve:

- Stock identity.
- Trading date.
- Time-of-day characteristics.
- Relevant market conditions.
- Eligibility conditions.

Do not randomly select arbitrary dates from the entire dataset.

## 8.2 Selection null

Does the strategy outperform randomly selected eligible laggard stocks from the same sector, date, and time?

Preserve the relevant liquidity and eligibility constraints.

The null must not be made artificially weak.

## 8.3 Market-factor null

Can the same prediction be explained by market and sector returns alone?

Test whether the leader signal provides incremental information after controlling for:

- NIFTY returns.
- Sector returns.
- Laggard's own returns.
- Relevant volatility and liquidity conditions.

## 8.4 Reverse-direction diagnostic

Investigate whether the apparent relationship is directional.

Test whether:

- Leaders predict laggards.
- Laggards predict leaders.
- Both simply react to the same common factor.

This is a diagnostic, not permission to select whichever direction performs best.

## 8.5 Placebo diagnostic

Use an appropriately shifted or mismatched leader signal as a placebo.

Ensure the placebo does not inadvertently contain overlapping information from the original signal window.

Document the construction.

---

# PART 9 — TRADING SIMULATION: ONLY IF THE MEASUREMENT SUPPORTS IT

Do not automatically create a trading strategy just because the predictive regression is statistically significant.

First establish that the relationship is sufficiently large, stable, and economically plausible.

If it passes the pre-specified measurement gates, a separate strategy-development specification may be prepared.

Do not change the measurement study after observing results.

## 9.1 Direction

Initial trading direction:

- Positive leader abnormal return → evaluate long laggards.
- Negative leader abnormal return → evaluate short laggards, if the instrument and permitted execution mechanism support it.

Do not assume both directions are equally effective.

Long and short results must be reported separately.

## 9.2 Entry

A signal must be generated after the leader's signal window is complete.

Entry must occur at the next realistically executable opportunity.

Do not enter retrospectively at the close of a candle that was necessary to generate the signal.

Use realistic prices based on the available execution data.

If only OHLCV bars are available, do not pretend the bar open or close is a guaranteed fill.

Document the execution approximation and its limitations.

## 9.3 Position construction

Use fixed capital or fixed notional sizing initially.

Do not size positions by an arbitrarily small stop distance.

Use the project's established minimum-stop-distance and position-cap safeguards wherever applicable.

Report:

- Number of positions.
- Gross exposure.
- Net exposure.
- Turnover.
- Sector concentration.
- Maximum simultaneous positions.
- Capital utilisation.

Do not introduce leverage to make results look better.

## 9.4 Stop-loss and take-profit policy

IMPORTANT:

Do not force a traditional stop-loss or take-profit into the primary lead-lag measurement.

The primary measurement is a prediction study, not a chart-pattern strategy.

For the initial trading simulation, use fixed-time exits corresponding to the pre-registered prediction horizon.

For example:

- Entry at the next executable opportunity.
- Exit after 5 trading minutes.
- Alternatively, exit after the pre-registered 15, 30 or 60-minute horizon.

No discretionary trailing stops.

No moving averages or chart-pattern exits.

No arbitrary 1R/2R targets.

This prevents a stop/target optimisation exercise from contaminating the primary hypothesis.

If the fixed-time simulation demonstrates a credible net edge, a separate, preregistered risk-management study may investigate:

- Volatility-scaled stop distances.
- Fixed maximum loss limits.
- Volatility-scaled profit targets.
- No-stop versus fixed-stop behaviour.

Any such study must have its own hypothesis, power analysis, trial accounting and correction.

Do not select SL/TP values from the best historical backtest result.

## 9.5 Costs

Use the existing project's validated execution-cost methodology.

Include all applicable costs:

- Brokerage.
- STT.
- Exchange transaction charges.
- GST.
- SEBI charges.
- Stamp duty.
- Bid-ask spread.
- Slippage.
- Market impact where estimable.

Use the correct applicable rates for the relevant historical period.

Do not invent historical costs.

Do not assume today's cost model applies unchanged to 2016.

If historical spread data is unavailable, use a documented conservative cost model and provide sensitivity analysis.

The project's spread estimator validation is still pending. Do not claim that an unvalidated spread estimate is validated.

Report gross and net results separately.

---

# PART 10 — STRATEGY-LEVEL EVALUATION METRICS

If and only if a strategy simulation is authorised, report:

### Returns

- Gross return.
- Net return.
- Mean return per trade.
- Median return per trade.
- Annualised return where meaningful.
- Cumulative equity curve.

### Risk

- Maximum drawdown.
- Drawdown duration.
- Volatility.
- Downside deviation.
- Worst trade.
- Worst trading day.
- Tail losses.

### Trade characteristics

- Number of trades.
- Win rate.
- Average winner.
- Average loser.
- Profit factor.
- Average holding period.
- Turnover.
- Average cost per trade.
- Cost as a percentage of gross edge.

### Robustness

- Day-clustered bootstrap confidence intervals.
- Performance by year.
- Performance by sector.
- Performance by liquidity band.
- Performance by market regime.
- Performance excluding the best calendar year.
- Sensitivity to conservative execution costs.

A positive Sharpe ratio alone is not a pass.

A high win rate alone is not a pass.

A result that beats a weak random benchmark but loses after costs is a failure.

---

# PART 11 — EXECUTION AND DATA-INTEGRITY REQUIREMENTS

This project has experienced plausible but incorrect results from implementation defects.

You must apply the following safeguards.

### 11.1 No look-ahead bias

At signal time, only completed bars and previously available information may be used.

### 11.2 No survivorship bias

Historical eligibility must use historical information.

Do not reconstruct the 2016 universe from today's surviving stocks.

### 11.3 No entity leakage

Use the project's validated entity and ISIN resolution.

Do not use `entity_id` as a predictive feature.

### 11.4 No cross-stock contamination

A stock's return must not leak into its own sector benchmark.

Use leave-one-out benchmarks where necessary.

### 11.5 No future liquidity information

Leader eligibility and laggard eligibility must use trailing information only.

### 11.6 No duplicate observations

A single underlying market observation must not be counted multiple times merely because it participates in multiple leader-laggard pairs.

Use appropriate dependence-aware inference.

### 11.7 No false execution

A signal must be actionable after it becomes observable.

Do not fill at prices that were only available before the signal existed.

### 11.8 Manual trade tracing

Before aggregate results are accepted, manually trace at least five representative observations, covering:

- A successful positive leader signal.
- A successful negative leader signal.
- A failed prediction.
- A missing or stale-bar case.
- A market or session boundary case.

Trace every stage from raw minute bars to final calculated outcome.

### 11.9 Checkpointing

Long-running jobs must checkpoint between stages.

Do not assume unattended runs will complete.

Persist intermediate results.

Ensure jobs can resume without duplicating observations.

Do not hold the entire decade of minute-level data in memory unnecessarily.

---

# PART 12 — REQUIRED RESEARCH STAGES

Execute in the following order.

## Phase 0 — Repository reconnaissance

Inspect the repository.

Identify:

- Current project tree.
- Existing data models.
- Database tables.
- Data access patterns.
- Existing backtesting infrastructure.
- Cost models.
- Entity-resolution utilities.
- Corporate-action utilities.
- Testing conventions.
- Documentation conventions.
- Existing experiment identifiers.

Do not guess file locations.

Reuse only safe, read-only shared infrastructure.

Produce:

`LEAD_LAG_RECONNAISSANCE.md`

## Phase 1 — Data audit

Perform the audit described in Part 2.

Produce:

`DATA_AUDIT_LEAD_LAG.md`

Do not proceed if critical data-integrity requirements fail.

## Phase 2 — Feasibility and power

Before looking at predictive outcomes:

- Estimate eligible sectors.
- Estimate leader-laggard pairs.
- Estimate available observations.
- Estimate computational requirements.
- Estimate sample dependence.
- Calculate MDE.
- Assess whether the study can detect an economically meaningful relationship.

Produce:

`LEAD_LAG_FEASIBILITY.md`

If the study is unidentifiable or severely underpowered, abandon it at this stage.

Do not manufacture alternative parameters to force feasibility.

## Phase 3 — Research design and preregistration

Produce:

`PREREGISTRATION_LEAD_LAG_V1.md`

Include the complete methodology and verdict rules.

Commit the preregistration alone.

Do not run outcome analysis before the preregistration commit exists.

Then STOP and present the completed audit, feasibility assessment, proposed methodology, and exact commit hash for human review.

**Do not proceed to outcome analysis without explicit human approval.**

## Phase 4 — Implementation

After approval:

Create isolated source code for the new family.

Use a clean namespace and unique experiment identifier.

Do not modify existing strategies.

Implement:

- Historical universe construction.
- Sector grouping.
- Leader selection.
- Laggard selection.
- Market-adjusted returns.
- Leave-one-out sector returns.
- Signal construction.
- Forward-return measurement.
- Statistical controls.
- Null generation.
- Multiple-testing correction.
- Checkpointing.
- Reproducible outputs.

Create unit tests and integration tests.

Run the tests before any full research run.

## Phase 5 — Hand tracing and validation

Trace five representative observations against raw data.

Validate:

- Signal timestamp.
- Availability of all input information.
- Correct benchmark construction.
- Correct leader-laggard mapping.
- Correct future-return window.
- Correct handling of missing data.
- Correct trading-session boundaries.

Fix defects before calculating aggregate results.

If a bug is found, measure its blast radius in both directions before correction.

Search for every other occurrence of the same defect shape.

## Phase 6 — DEV measurement

Run the preregistered study.

Produce:

`FINDINGS_LEAD_LAG_V1.md`

Report the primary result first.

Do not hide negative results.

Do not select a different sector, horizon, threshold, or universe after seeing a failure.

If the primary gate fails decisively, close the study.

## Phase 7 — Conditional trading simulation

Only if the measurement gates pass, and after separate human approval:

Prepare a separate strategy preregistration.

Specify the trading direction, execution model, holding period, costs, sizing, and nulls.

Run the simulation independently.

Do not reinterpret the measurement result as a trading-strategy pass.

## Phase 8 — Final disposition

Classify the research family as one of:

- PASS — measurement only.
- PASS — economic simulation, subject to project gates.
- FAIL — statistically inadequate.
- FAIL — economically untradeable.
- INCONCLUSIVE — insufficient power or data.
- ABANDONED — structural identification or data-integrity problem.

Do not use PASS to imply prospective validation.

A historical development result is not proof of a live edge.

---

# PART 13 — REQUIRED DOCUMENTATION

At minimum, create:

```text
[discover appropriate existing research root]/
    lead_lag/
        LEAD_LAG_RECONNAISSANCE.md
        DATA_AUDIT_LEAD_LAG.md
        LEAD_LAG_FEASIBILITY.md
        PREREGISTRATION_LEAD_LAG_V1.md
        FINDINGS_LEAD_LAG_V1.md

        src/
            universe.py
            sector_mapping.py
            leader_selection.py
            signal.py
            benchmarks.py
            measurement.py
            nulls.py
            statistics.py
            validation.py

        tests/
            test_universe.py
            test_sector_mapping.py
            test_leader_selection.py
            test_signal.py
            test_benchmarks.py
            test_no_lookahead.py
            test_forward_returns.py
            test_nulls.py
            test_statistics.py

        configs/
        results/
        logs/
```

This is a suggested structure, not an instruction to force a new directory into an incompatible existing architecture.

Discover the correct project root and follow its conventions.

Do not create unnecessary duplicate utilities.

Keep generated results, temporary files, and caches outside existing strategy directories.

---

# PART 14 — WHAT I EXPECT FROM YOU AS THE RESEARCHER

You must challenge this hypothesis rather than advocate for it.

Specifically investigate the possibility that:

1. All stocks are simply responding to NIFTY movements.
2. Sector leaders are just proxies for sector momentum.
3. Laggards are already exhibiting their own momentum.
4. The apparent lag is a timestamp or data-availability artefact.
5. The relationship is explained by liquidity differences.
6. The effect exists only during a few unusual years.
7. The relationship is concentrated in one or two sectors.
8. The apparent prediction disappears after realistic execution costs.
9. The effect is a statistical consequence of overlapping observations.
10. The leader definition itself creates a selection bias.

Do not defend the hypothesis when evidence contradicts it.

Do not interpret a statistically significant coefficient as proof of a tradable strategy.

Do not make predictions about the result before measuring it.

---

# PART 15 — STRICT COMMUNICATION RULES

During this task:

- Report failures in the first sentence of findings reports.
- Separate measured facts from hypotheses.
- Clearly label assumptions.
- Do not invent missing data.
- Do not claim that an unvalidated cost estimate is validated.
- Do not silently substitute a different data source.
- Do not silently change the methodology.
- Do not change a closed experiment.
- Do not create a strategy merely to produce a backtest.
- Do not proceed past human approval gates.
- Do not claim a historical holdout pass.

When reporting a result, always distinguish:

1. What was measured.
2. What the result establishes.
3. What the result does not establish.
4. What remains unknown.
5. Whether further research is justified.

If something cannot be determined, say so explicitly.

---

# FINAL INSTRUCTION

Begin with Phase 0 only.

Inspect the existing repository and documentation thoroughly.

Do not immediately start coding the trading strategy.

Do not assume the proposed hypothesis is true.

Your first deliverable is a reconnaissance report identifying the correct project structure, available data, reusable infrastructure, and any risks to the proposed research.

Then proceed sequentially through the specified phases.

The goal is not to find a positive backtest.

**The goal is to determine whether cross-stock lead-lag propagation is a genuine, incremental, reproducible, and potentially tradeable phenomenon in NSE equities.**

A rigorous failure is more valuable than a fabricated success.

---

## Note on deviations already taken, recorded here for cross-reference

Two binding scope decisions were made by the human user during Phase 1,
diverging from this document's literal text, both recorded in
`PREREGISTRATION_LEAD_LAG_V1.md`'s own Provenance section and not
repeated in full here:

1. Part 3's sector-based grouping (3.1-3.4) was **not used** -- Phase 1's
   data audit found no point-in-time sector classification exists in this
   repository (`DATA_AUDIT_LEAD_LAG.md` Section 4). The user chose
   sector-agnostic liquidity-tier grouping instead, from three offered
   options.
2. Part 1's framing ("stocks within the same sector") was reframed by the
   2026-11-08 amendment to `PREREGISTRATION_LEAD_LAG_V1.md` as
   "cross-liquidity-tier return propagation" specifically because the
   sector-agnostic design tests a different, narrower mechanism than the
   literal sector-propagation language above -- see that document's
   amendment log for the full reasoning, prompted by an independent
   methodology review.

Both deviations are deliberate, evidence-based, and explicitly disclosed
-- not silent departures from this directive.
