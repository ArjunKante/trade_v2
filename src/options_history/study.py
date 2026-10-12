"""The actual computation specified in PREREGISTRATION_OPTIONS.md --
built only after that document was committed and pushed on its own
(evidence the design preceded the result). Every function here
implements one literal step of that document; nothing here introduces a
definition not already stated there. Where a real data gap makes one
month's observation impossible, it is dropped WITH A STATED REASON
(`Observation.dropped`/`reason`), never silently excluded and never
patched over with a substitute value -- per instruction, an
unexpected gap is reported, not improvised around.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import duckdb
import numpy as np
import pandas as pd

MEASUREMENT_LOOKBACK_TRADING_DAYS = 20
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261013  # fixed, dated, so a re-run reproduces the exact same resample draws
AUTOCORR_MATERIALITY = lambda n: 2 / (n ** 0.5)  # PREREGISTRATION_OPTIONS.md Section 5e
BLOCK_SIZE_IF_TRIGGERED = 3  # not specified in the pre-registration; filled here ONLY if 5e actually triggers


@dataclass
class Observation:
    expiry: dt.date
    dropped: bool
    reason: str = ""
    measurement_date: dt.date | None = None
    strike: float | None = None
    nifty_measurement: float | None = None
    nifty_expiry: float | None = None
    straddle_price: float | None = None
    payoff: float | None = None
    realised_move: float | None = None
    R: float | None = None
    ce_volume: int | None = None
    pe_volume: int | None = None


def monthly_expiry_dates(con_opts: duckdb.DuckDBPyConnection, start: dt.date, end: dt.date) -> list[dt.date]:
    """PREREGISTRATION_OPTIONS.md Section 2.2: for each calendar month in
    [start, end], the LATEST distinct NIFTY option expiry_date within
    that month -- derived from the data, not an assumed weekday."""
    rows = con_opts.execute(
        "SELECT DISTINCT expiry_date FROM nifty_options_eod WHERE expiry_date BETWEEN ? AND ? ORDER BY expiry_date",
        [start, end],
    ).fetchdf()["expiry_date"].tolist()
    by_month: dict[tuple[int, int], dt.date] = {}
    for d in rows:
        key = (d.year, d.month)
        if key not in by_month or d > by_month[key]:
            by_month[key] = d
    return sorted(by_month.values())


def trading_days_series(con_idx: duckdb.DuckDBPyConnection) -> pd.Series:
    df = con_idx.execute(
        "SELECT trade_date FROM index_eod WHERE index_name = 'NIFTY50' ORDER BY trade_date"
    ).fetchdf()
    return df["trade_date"].reset_index(drop=True)


def _measurement_date(trading_days: pd.Series, expiry: dt.date,
                       lookback: int = MEASUREMENT_LOOKBACK_TRADING_DAYS) -> dt.date | None:
    """`lookback` trading days before `expiry`, along NIFTY's own
    index_eod calendar. None if `expiry` is not itself a date in that
    calendar, or fewer than `lookback` trading days of history precede
    it (not expected to occur inside this study's windows, but not
    assumed impossible either)."""
    matches = trading_days.index[trading_days == expiry]
    if len(matches) == 0:
        return None
    pos = matches[0]
    if pos - lookback < 0:
        return None
    return trading_days.iloc[pos - lookback]


def _expiry_unreachable_reason(expiry: dt.date, trading_days: pd.Series) -> str:
    """Found live, running this study for real (not anticipated in
    PREREGISTRATION_OPTIONS.md): NSE's F&O bhavcopy records a contract's
    NOMINAL/contractual expiry_date even on the rare occasion that date
    turns out to be a trading holiday (NSE settles such contracts using
    the prior trading day in practice; this project's raw data does not
    reflect that adjustment). Distinguishing WHY an expiry date is
    missing from NIFTY's own trading-day calendar -- a confirmed holiday
    versus a genuine data-coverage gap -- is reported explicitly rather
    than collapsed into one generic message, per instruction to report
    gaps rather than paper over them."""
    from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday
    # The holiday master stores plain datetime.date objects; a pandas
    # Timestamp (what DuckDB's fetchdf() hands back) compares UNEQUAL to
    # an equal-valued date both by == and by set membership (confirmed
    # live: hash(Timestamp) != hash(date) for the same calendar day) --
    # normalize before the lookup, or is_nse_holiday silently returns
    # False for every real holiday.
    expiry_as_date = expiry.date() if hasattr(expiry, "date") and callable(expiry.date) else expiry
    try:
        if is_nse_holiday(expiry_as_date):
            return (f"contractual expiry date {expiry} is a CONFIRMED NSE HOLIDAY -- NSE's bhavcopy "
                    f"records this as the contract's nominal expiry anyway, but NIFTY's own index_eod "
                    f"correctly has no trading row for it; this study does not substitute the prior "
                    f"trading day's close (that would be a definition change made after seeing this, "
                    f"not specified in the pre-registration)")
    except HolidayCalendarMissing:
        pass
    if len(trading_days) and expiry > trading_days.iloc[-1]:
        return (f"contractual expiry date {expiry} is after index_eod's own latest date "
                f"({trading_days.iloc[-1]}) -- a data-coverage gap, not a holiday")
    return (f"contractual expiry date {expiry} does not appear in NIFTY's own trading-day calendar "
            f"for an unidentified reason (not a confirmed holiday, not past index_eod's coverage)")


def _nifty_close(con_idx: duckdb.DuckDBPyConnection, date: dt.date) -> float | None:
    row = con_idx.execute(
        "SELECT close FROM index_eod WHERE index_name = 'NIFTY50' AND trade_date = ?", [date]
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _atm_strike(con_opts: duckdb.DuckDBPyConnection, expiry: dt.date, measurement_date: dt.date,
                 spot: float) -> float | None:
    """PREREGISTRATION_OPTIONS.md Section 2.3: the listed strike closest
    to NIFTY's own close on the measurement date. Tie-break (not
    specified in the pre-registration -- filled here, stated plainly):
    the SMALLER strike wins an exact tie, a deterministic, arbitrary-but-
    fixed rule never expected to actually bind (spot is continuous,
    strikes are not)."""
    strikes = con_opts.execute(
        "SELECT DISTINCT strike FROM nifty_options_eod WHERE expiry_date = ? AND trade_date = ?",
        [expiry, measurement_date],
    ).fetchdf()["strike"].tolist()
    if not strikes:
        return None
    return min(strikes, key=lambda k: (abs(k - spot), k))


def _leg(con_opts: duckdb.DuckDBPyConnection, expiry: dt.date, strike: float, option_type: str,
         trade_date: dt.date) -> tuple[float, int] | None:
    row = con_opts.execute(
        "SELECT close, volume FROM nifty_options_eod WHERE expiry_date = ? AND strike = ? "
        "AND option_type = ? AND trade_date = ?",
        [expiry, strike, option_type, trade_date],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0]), int(row[1] or 0)


def build_observation(con_opts: duckdb.DuckDBPyConnection, con_idx: duckdb.DuckDBPyConnection,
                       trading_days: pd.Series, expiry: dt.date) -> Observation:
    """One monthly expiry's full observation, or a dropped Observation
    with a stated reason -- every step below is one literal line of
    PREREGISTRATION_OPTIONS.md Section 2, in order."""
    meas_date = _measurement_date(trading_days, expiry)
    if meas_date is None:
        is_in_calendar = (trading_days == expiry).any()
        if is_in_calendar:
            reason = (f"expiry date {expiry} is in NIFTY's trading-day calendar, but fewer than "
                      f"{MEASUREMENT_LOOKBACK_TRADING_DAYS} trading days of index history precede it")
        else:
            reason = _expiry_unreachable_reason(expiry, trading_days)
        return Observation(expiry=expiry, dropped=True, reason=reason)

    spot_meas = _nifty_close(con_idx, meas_date)
    if spot_meas is None:
        return Observation(expiry=expiry, dropped=True, measurement_date=meas_date,
                            reason=f"no NIFTY index close available at the measurement date {meas_date}")

    spot_expiry = _nifty_close(con_idx, expiry)
    if spot_expiry is None:
        return Observation(expiry=expiry, dropped=True, measurement_date=meas_date,
                            reason=f"no NIFTY index close available at the expiry date {expiry} "
                                   f"(index_eod does not extend this far)")

    strike = _atm_strike(con_opts, expiry, meas_date, spot_meas)
    if strike is None:
        return Observation(expiry=expiry, dropped=True, measurement_date=meas_date,
                            reason="no NIFTY option strikes listed for this expiry on the measurement date")

    ce = _leg(con_opts, expiry, strike, "CE", meas_date)
    pe = _leg(con_opts, expiry, strike, "PE", meas_date)
    if ce is None or pe is None:
        missing = "CE" if ce is None else "PE"
        return Observation(expiry=expiry, dropped=True, measurement_date=meas_date, strike=strike,
                            reason=f"no {missing} row at strike {strike} on the measurement date")

    ce_close, ce_vol = ce
    pe_close, pe_vol = pe
    if ce_vol == 0 or pe_vol == 0:
        return Observation(expiry=expiry, dropped=True, measurement_date=meas_date, strike=strike,
                            ce_volume=ce_vol, pe_volume=pe_vol,
                            reason=f"zero-volume leg (liquidity filter, Section 4): CE volume={ce_vol}, PE volume={pe_vol}")

    straddle = ce_close + pe_close
    payoff = abs(spot_expiry - strike)
    realised_move = abs(spot_expiry - spot_meas)
    R = payoff / straddle - 1.0

    return Observation(
        expiry=expiry, dropped=False, measurement_date=meas_date, strike=strike,
        nifty_measurement=spot_meas, nifty_expiry=spot_expiry, straddle_price=straddle,
        payoff=payoff, realised_move=realised_move, R=R, ce_volume=ce_vol, pe_volume=pe_vol,
    )


def build_window(con_opts: duckdb.DuckDBPyConnection, con_idx: duckdb.DuckDBPyConnection,
                  trading_days: pd.Series, start: dt.date, end: dt.date) -> list[Observation]:
    expiries = monthly_expiry_dates(con_opts, start, end)
    return [build_observation(con_opts, con_idx, trading_days, e) for e in expiries]


def bootstrap_mean_ci(values: list[float], n_resamples: int = BOOTSTRAP_RESAMPLES,
                       seed: int = BOOTSTRAP_SEED, ci: float = 0.95) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(arr)
    means = np.empty(n_resamples)
    for i in range(n_resamples):
        means[i] = rng.choice(arr, size=n, replace=True).mean()
    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    return float(np.percentile(means, lo)), float(np.percentile(means, hi))


def block_bootstrap_mean_ci(values: list[float], block_size: int = BLOCK_SIZE_IF_TRIGGERED,
                             n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
                             ci: float = 0.95) -> tuple[float, float]:
    """Moving-block bootstrap: resamples overlapping contiguous blocks of
    `block_size` consecutive (chronologically-ordered) observations,
    concatenates enough of them to match the original length, and takes
    the mean -- used in place of bootstrap_mean_ci only when Section 5e's
    lag-1 autocorrelation check actually finds the plain i.i.d. bootstrap
    unjustified."""
    arr = np.asarray(values, dtype=float)
    n = len(arr)
    if n <= block_size:
        return bootstrap_mean_ci(values, n_resamples=n_resamples, seed=seed, ci=ci)
    blocks = [arr[i:i + block_size] for i in range(n - block_size + 1)]
    n_blocks_needed = int(np.ceil(n / block_size))
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples)
    for i in range(n_resamples):
        chosen = [blocks[rng.integers(0, len(blocks))] for _ in range(n_blocks_needed)]
        sample = np.concatenate(chosen)[:n]
        means[i] = sample.mean()
    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    return float(np.percentile(means, lo)), float(np.percentile(means, hi))


def lag1_autocorrelation(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if len(arr) < 3:
        return float("nan")
    return float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
