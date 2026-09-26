"""Swing-trading research, Phase 1: cost and dispersion, before any signal.
See SWING.md for the full project scope and phase gates.

Answers exactly one question: at horizons of 1, 2, 3, and 5 trading days,
is the cross-sectional dispersion of forward returns large enough, relative
to realistic NSE/Groww transaction costs, that a signal with a plausible
rank-IC could clear its own costs? No signal is built or tested here --
this is a viability gate that must pass before any rule-based or ML work
on this project is worth doing at all.

DATA SCOPE, stated explicitly: uses ONLY the pre-holdout entity panel
(data_layer.entity_panel.read_entity_panel, physically truncated before
SEALED_HOLDOUT_START) and the raw pre-holdout prices_eod table for the
same-day open/close case. This matches this project's own established
precedent (see experiments.csv's low_liq_tercile_cost_calibration entry:
"a truly current name list would require authorize_holdout=True... user
was asked and chose the pre-holdout-compliant list") of defaulting to the
pre-holdout-compliant path rather than requesting a holdout exception when
the pre-holdout window already has enough data to answer the question --
nine years of daily data is enough to measure dispersion; this diagnostic
does not need today's price. No signal is evaluated against dates inside
the sealed window, and no holdout exception is requested or used.

UNIVERSE, stated explicitly: the full whole-market EQ universe, no
liquidity filter -- matching Study 1's own "all INE/IN9 EQ entities, no
liquidity filter" convention (FINDINGS.md). This is deliberately broader
than the swing project's eventual Phase 2 universe (top two turnover
terciles of the momentum top decile, BE/BZ and surveillance-name
excluded), which has not been built yet. Both dispersion and true
achievable cost will change once that filter is applied -- probably in
offsetting directions (a narrower, more liquid universe likely has both
lower dispersion AND lower true spread cost than this first-pass,
whole-market number) -- so this script's verdict is a first-pass gate on
the broadest reasonable population, not a final answer for the eventual
filtered universe.

Usage:
    python scripts/run_swing_phase1_cost_dispersion.py
"""
from __future__ import annotations

import datetime as dt
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from data_layer.db import get_read_connection
from data_layer.entity_panel import read_entity_panel
from data_layer.holdout import SEALED_HOLDOUT_START, guard_date_range
from data_layer.lineage_jump_guard import unexplained_jump_boundaries
from factors.target import compute_forward_return
from swing.costs import round_trip_cost_bps

ROOT = Path(__file__).resolve().parents[1]
HORIZONS_DAYS = (1, 2, 3, 5)
TRADING_DAYS_PER_YEAR = 252
IC_VALUES = (0.02, 0.03, 0.05)
POSITION_SIZES_RS = (10_000, 50_000, 100_000, 500_000)
BREAK_EVEN_HURDLE = 1.0
STANDING_3X_HURDLE = 3.0  # imported convention from the sibling trade-info project's capacity study
                          # (ops/report_capacity_slippage_groundtruth.py) -- not this project's own
                          # established rule yet, reported alongside break-even per that project's own
                          # instruction: "these are different questions, break-even must not silently
                          # become the hurdle."


def cross_sectional_dispersion_by_horizon(con) -> dict[int, dict]:
    """Delivery-style (close-to-close) forward-return dispersion at each
    horizon, gap-guarded exactly as factors/target.py already requires for
    every other forward-return use in this project (STALE_GAP_DAYS +
    unexplained-jump guard) -- reused, not reimplemented."""
    panel = read_entity_panel(con)  # entity_id, trade_date, adjusted_close, ... -- pre-holdout only, by construction
    jump_dates = unexplained_jump_boundaries(con, before=SEALED_HOLDOUT_START)

    out = {}
    for h in HORIZONS_DAYS:
        fwd = compute_forward_return(panel, horizon=h, unexplained_jump_dates=jump_dates)
        per_date_std = fwd.groupby("trade_date")["fwd_return"].std()
        out[h] = {
            "xsec_std_mean": float(per_date_std.mean()),
            "xsec_std_median": float(per_date_std.median()),
            "n_dates": int(per_date_std.count()),
            "n_obs": int(len(fwd)),
        }
    return out


def same_day_open_close_dispersion(con) -> dict:
    """INTRADAY (open-to-close, same day) dispersion. No entity-adjustment
    needed -- open and close on the SAME trading day are unaffected by any
    between-day corporate action, so raw prices_eod.open/close is correct
    without going through adjustment_factors. Restricted to series='EQ'
    (main board), matching entity_panel's own convention, and to strictly
    before SEALED_HOLDOUT_START (guarded explicitly, not by convention)."""
    guard_date_range(dt.date(2016, 1, 1), SEALED_HOLDOUT_START - dt.timedelta(days=1))
    sql = """
        SELECT trade_date, isin, open, close
        FROM prices_eod
        WHERE series = 'EQ' AND trade_date < ? AND open > 0 AND close > 0
    """
    df = con.execute(sql, [SEALED_HOLDOUT_START]).fetchdf()
    df["ret"] = df["close"] / df["open"] - 1
    per_date_std = df.groupby("trade_date")["ret"].std()
    return {
        "xsec_std_mean": float(per_date_std.mean()),
        "xsec_std_median": float(per_date_std.median()),
        "n_dates": int(per_date_std.count()),
        "n_obs": int(len(df)),
    }


def report_row(label: str, xsec_std: float, periods_per_year: float, order_type: str) -> list[str]:
    lines = [
        f"\n--- {label} ---",
        f"cross-sectional std of forward returns: {xsec_std*100:.2f}%  "
        f"(non-overlapping periods/year for one persistent bet: {periods_per_year:.1f} -- "
        f"time-series independence, not cross-sectional breadth)",
    ]
    for ic in IC_VALUES:
        edge_bps = ic * xsec_std * 10_000
        lines.append(f"\n  IC={ic:.2f}  implied edge = IC x cross-sectional std = {edge_bps:.1f}bps per trade")
        lines.append(f"  {'position size':>15} {'cost range(bps)':>18} {'edge/cost range':>20} "
                      f"{'break-even, worst-cost':>24} {'3x hurdle, worst-cost':>23}")
        for size in POSITION_SIZES_RS:
            cost_lo, cost_hi = round_trip_cost_bps(size, order_type)
            ec_lo, ec_hi = edge_bps / cost_hi, edge_bps / cost_lo
            # PASS/FAIL here uses ec_lo -- the ratio at the WORST-CASE (highest) end of the cost
            # range, i.e. "does this clear the bar even if costs come in at the pessimistic end."
            # This is a different, stricter question than the stop-gate check below, which
            # deliberately uses the OPTIMISTIC (lowest) cost bound -- both are reported, never
            # conflated into one number.
            be = "PASS" if ec_lo >= BREAK_EVEN_HURDLE else "FAIL"
            hurdle3x = "PASS" if ec_lo >= STANDING_3X_HURDLE else "FAIL"
            lines.append(f"  Rs{size:>12,.0f} {cost_lo:>8.1f}-{cost_hi:<8.1f} "
                         f"{ec_lo:>8.2f}x-{ec_hi:<8.2f}x {be:>24} {hurdle3x:>23}")
    return lines


def main() -> int:
    con = get_read_connection(ROOT / "data" / "warehouse.duckdb")

    print("Computing delivery (close-to-close) dispersion at 1/2/3/5-day horizons "
          "(pre-holdout entity panel only)...", file=sys.stderr, flush=True)
    delivery_stats = cross_sectional_dispersion_by_horizon(con)

    print("Computing intraday (same-day open-to-close) dispersion...", file=sys.stderr, flush=True)
    intraday_stats = same_day_open_close_dispersion(con)
    con.close()

    lines = []
    A = lines.append
    A("=" * 100)
    A("SWING TRADING PHASE 1: COST AND DISPERSION, BEFORE ANY SIGNAL")
    A("Research question, universe, and data-scope caveats: see this script's module docstring "
      "and SWING.md. No signal, no rule, no decision threshold evaluated here.")
    A(f"Pre-holdout panel only (SEALED_HOLDOUT_START={SEALED_HOLDOUT_START}); whole-market EQ, "
      "no liquidity filter -- Phase 2 will narrow this.")
    A("=" * 100)

    A("\n" + "#" * 100)
    A("# SAME-DAY (INTRADAY, open-to-close) -- the shortest testable construction on daily bhavcopy data")
    A("#" * 100)
    s = intraday_stats
    A(f"n_dates={s['n_dates']}  n_obs={s['n_obs']}")
    lines += report_row("same-day open-to-close", s["xsec_std_mean"], TRADING_DAYS_PER_YEAR, "INTRADAY")

    A("\n" + "#" * 100)
    A("# DELIVERY (close-to-close, overnight, held 1/2/3/5 trading days) -- STT/DP charge apply here, not above")
    A("#" * 100)
    for h in HORIZONS_DAYS:
        d = delivery_stats[h]
        A(f"\nhorizon={h}d   n_dates={d['n_dates']}  n_obs={d['n_obs']}  "
          f"(median daily cross-sectional std: {d['xsec_std_median']*100:.2f}%)")
        lines += report_row(f"delivery, {h}-day horizon", d["xsec_std_mean"],
                             TRADING_DAYS_PER_YEAR / h, "DELIVERY")

    # ---- the stop gate ----
    all_ratios = []
    for h in HORIZONS_DAYS:
        xsec = delivery_stats[h]["xsec_std_mean"]
        for ic in IC_VALUES:
            edge_bps = ic * xsec * 10_000
            for size in POSITION_SIZES_RS:
                _, cost_hi = round_trip_cost_bps(size, "DELIVERY")
                all_ratios.append(edge_bps / cost_hi)
    xsec_intraday = intraday_stats["xsec_std_mean"]
    for ic in IC_VALUES:
        edge_bps = ic * xsec_intraday * 10_000
        for size in POSITION_SIZES_RS:
            _, cost_hi = round_trip_cost_bps(size, "INTRADAY")
            all_ratios.append(edge_bps / cost_hi)

    max_ratio_at_ic05 = max(
        (ic * delivery_stats[h]["xsec_std_mean"] * 10_000) / round_trip_cost_bps(size, "DELIVERY")[0]
        for h in HORIZONS_DAYS for ic in (0.05,) for size in POSITION_SIZES_RS
    )
    max_ratio_at_ic05_intraday = max(
        (0.05 * xsec_intraday * 10_000) / round_trip_cost_bps(size, "INTRADAY")[0]
        for size in POSITION_SIZES_RS
    )
    gate_fails_everywhere = max(max_ratio_at_ic05, max_ratio_at_ic05_intraday) < BREAK_EVEN_HURDLE

    A("\n" + "=" * 100)
    A("STOP-GATE CHECK (per instruction): is edge/cost below 1x at EVERY horizon, even at IC=0.05, "
      "using the OPTIMISTIC (low) end of the cost range?")
    A("=" * 100)
    A(f"Best-case edge/cost ratio found anywhere in this sweep (IC=0.05, optimistic cost, best "
      f"horizon/position-size combination): delivery {max_ratio_at_ic05:.2f}x, "
      f"intraday {max_ratio_at_ic05_intraday:.2f}x")
    if gate_fails_everywhere:
        A("\nRESULT: FAILS BREAK-EVEN EVERYWHERE, even at the most generous assumption tested (IC=0.05, "
          "optimistic/low end of the cost range). Per instruction, this is reported plainly: this "
          "would end the project before any signal is built, as a legitimate outcome.")
    else:
        A("\nRESULT: DOES NOT fail everywhere -- at least one (horizon, IC, position size) combination "
          "clears break-even at the optimistic cost estimate. This does NOT mean a working strategy "
          "exists (no signal has been tested, only the cost/dispersion ceiling), only that Phase 2 "
          "is not ruled out on this test alone. See the full table above for which combinations pass "
          "and which fail, and note the STANDING 3x HURDLE column separately from break-even -- the "
          "sibling trade-info project treats 1x and 3x as answering different questions, and this "
          "report keeps them separate rather than collapsing to one verdict.")
    A("=" * 100)

    report = "\n".join(lines)
    print(report)

    out_dir = ROOT / "data" / "swing_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    log_path = out_dir / f"swing_phase1_cost_dispersion_{ts}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(f"\nFull log written to {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
