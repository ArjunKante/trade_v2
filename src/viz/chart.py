"""Study-agnostic trade/setup chart renderer -- 1-minute candles with
volume beneath, plus an optional `Overlay` (src/viz/overlay.py) a
strategy's own adapter supplies. This module knows nothing about any one
strategy; everything strategy-specific lives in the overlay it is handed.

CORE (no overlay) must work standalone -- the overlay argument is
optional and every overlay-rendering block below is skipped entirely
when it is None.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless -- this tool only ever writes PNGs, never shows a window
import matplotlib.pyplot as plt

from viz.overlay import Overlay

UP_COLOR = "#2a9d4a"
DOWN_COLOR = "#d6392b"
CANDLE_WIDTH = 0.6
TICK_EVERY_MINUTES = 30


def _nearest_index(ts_arr: np.ndarray, target_ts: pd.Timestamp) -> int | None:
    """Index of the bar closest to `target_ts` -- used to place a
    vertical marker or a price marker even if `target_ts` does not land
    exactly on a bar boundary (e.g. an exit between two 1-minute bars).
    None if `target_ts` is more than two bar-widths outside the plotted
    range -- e.g. a marker whose own time falls outside an active zoom
    `window` -- so a caller can drop it instead of drawing it at the
    nearest visible edge, which would misrepresent where it happened."""
    target64 = np.datetime64(pd.Timestamp(target_ts))
    diffs = np.abs(ts_arr - target64)
    idx = int(np.argmin(diffs))
    bar_width = np.median(np.diff(ts_arr)) if len(ts_arr) > 1 else np.timedelta64(1, "m")
    if diffs[idx] > 2 * bar_width:
        return None
    return idx


def plot_trade_chart(
    bars: pd.DataFrame, entity_id: str, trade_date: dt.date, scale_label: str,
    overlay: Overlay | None = None, out_path: Path | None = None, dpi: int = 130,
    window: tuple[dt.time, dt.time] | None = None,
) -> Path:
    """`bars`: [ts, open, high, low, close, volume], one trading day,
    already in whatever scale `scale_label` describes (this module does
    not resolve scale itself -- see `viz.data.fetch_raw_day_bars`).
    `window`: optional (start_time, end_time) to zoom the plotted range
    to a sub-window of the session (e.g. 09:30-10:30 to inspect a touch
    closely) -- an overlay marker whose own timestamp falls OUTSIDE the
    window is dropped, never silently relocated to the nearest visible
    bar, which would misrepresent where it actually happened.
    Saves a PNG to `out_path` (created if missing) and returns it."""
    if bars.empty:
        raise ValueError(f"no bars to plot for {entity_id} on {trade_date}")

    bars = bars.sort_values("ts").reset_index(drop=True)
    if window is not None:
        start_t, end_t = window
        times_of_day = pd.to_datetime(bars["ts"]).dt.time
        bars = bars[(times_of_day >= start_t) & (times_of_day <= end_t)].reset_index(drop=True)
        if bars.empty:
            raise ValueError(f"window {window} excludes every bar for {entity_id} on {trade_date}")
    n = len(bars)
    x = np.arange(n)
    ts_arr = bars["ts"].to_numpy()
    opens = bars["open"].to_numpy(dtype="float64")
    highs = bars["high"].to_numpy(dtype="float64")
    lows = bars["low"].to_numpy(dtype="float64")
    closes = bars["close"].to_numpy(dtype="float64")
    volumes = bars["volume"].to_numpy(dtype="float64")

    is_up = closes >= opens
    colors = np.where(is_up, UP_COLOR, DOWN_COLOR)

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(15, 8.5), sharex=True, gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06},
    )

    # --- CORE: candles ---
    ax_price.vlines(x, lows, highs, color=colors, linewidth=0.8, zorder=2)
    price_range = float(highs.max() - lows.min()) or 1.0
    min_body = 0.0008 * price_range  # keeps a doji visible as a thin line, not invisible
    body_bottom = np.minimum(opens, closes)
    body_height = np.maximum(np.abs(closes - opens), min_body)
    ax_price.bar(x, body_height, bottom=body_bottom, width=CANDLE_WIDTH, color=colors,
                 edgecolor=colors, linewidth=0.5, zorder=3)

    # --- CORE: volume ---
    ax_vol.bar(x, volumes, width=CANDLE_WIDTH, color=colors)
    ax_vol.set_ylabel("Volume")
    ax_vol.ticklabel_format(style="plain", axis="y")

    # --- CORE: x-axis ticks as HH:MM ---
    times = pd.to_datetime(bars["ts"])
    start_ts = times.iloc[0]
    minutes_since_start = (times - start_ts).dt.total_seconds() / 60.0
    tick_mask = (minutes_since_start % TICK_EVERY_MINUTES) < 1.0
    tick_idx = x[tick_mask.to_numpy()]
    if len(tick_idx) == 0 or tick_idx[0] != 0:
        tick_idx = np.concatenate(([0], tick_idx))
    ax_vol.set_xticks(tick_idx)
    ax_vol.set_xticklabels([times.iloc[i].strftime("%H:%M") for i in tick_idx], rotation=45, ha="right")
    right_margin = max(8, int(n * 0.08)) if (overlay is not None and (overlay.levels or overlay.bands)) else 1
    ax_price.set_xlim(-1, n + right_margin)
    ax_price.set_ylabel("Price")

    # --- OVERLAY (optional, study-agnostic) ---
    if overlay is not None:
        for band in overlay.bands:
            ax_price.axhspan(band.low, band.high, color=band.color, alpha=band.alpha, zorder=1)
            ax_price.text(n * 1.005, (band.low + band.high) / 2, band.label, color=band.color,
                          fontsize=8, va="center", fontweight="bold")

        for level in overlay.levels:
            ax_price.axhline(level.price, color=level.color, linestyle=level.linestyle,
                             linewidth=1.1, zorder=1.5)
            ax_price.text(n * 1.005, level.price, f"{level.label} {level.price:.2f}",
                          color=level.color, fontsize=8, va="center")

        for vm in overlay.vmarkers:
            idx = _nearest_index(ts_arr, vm.ts)
            if idx is None:
                continue  # vm.ts falls outside the active zoom window -- dropped, not relocated
            for ax in (ax_price, ax_vol):
                ax.axvline(idx, color=vm.color, linestyle=vm.linestyle, linewidth=1.0, zorder=1.2)
            ax_price.text(idx, highs.max() + price_range * 0.02, vm.label, color=vm.color,
                          fontsize=7.5, rotation=60, ha="left", va="bottom")

        for pm in overlay.price_markers:
            idx = _nearest_index(ts_arr, pm.ts)
            if idx is None:
                continue  # pm.ts falls outside the active zoom window -- dropped, not relocated
            marker = "^" if pm.kind == "entry" else "v"
            mcolor = "blue" if pm.kind == "entry" else "black"
            ax_price.scatter([idx], [pm.price], marker=marker, s=140, color=mcolor,
                             edgecolor="white", linewidth=0.8, zorder=5)
            label = pm.label or f"{pm.kind.upper()} {pm.price:.2f}"
            offset = -1 if pm.kind == "entry" else 1
            ax_price.annotate(label, (idx, pm.price), xytext=(6, 14 * offset),
                              textcoords="offset points", fontsize=8, color=mcolor, fontweight="bold")

        if overlay.text_panel:
            # top-RIGHT, not top-left: touch/confirm/entry vmarker labels
            # (above) cluster early in the session far more often than
            # late (a POC touch is usually sought soon after 09:45), so a
            # top-left info box routinely overlapped and visually clipped
            # them -- found rendering the very first real overlay chart.
            box_text = "\n".join(overlay.text_panel)
            ax_price.text(0.99, 0.98, box_text, transform=ax_price.transAxes, va="top", ha="right",
                          fontsize=8.5, family="monospace", zorder=10,
                          bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.9))

    title = f"{entity_id} -- {trade_date}"
    if overlay is not None and overlay.title_suffix:
        title += f" -- {overlay.title_suffix}"
    ax_price.set_title(title, fontsize=12, fontweight="bold")

    scale_color = "firebrick" if "UNRESOLVED" in scale_label or "NO DATA" in scale_label else "dimgray"
    fig.text(0.5, 0.005, scale_label, ha="center", fontsize=8.5, color=scale_color,
              fontweight="bold" if scale_color == "firebrick" else "normal")

    fig.tight_layout(rect=(0, 0.02, 1, 1))

    if out_path is None:
        out_path = Path("data/viz") / f"{entity_id}_{trade_date}.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path
