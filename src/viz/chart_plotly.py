"""Interactive (Plotly) renderer for src/viz/ -- used ONLY by
`scripts/research_app.py`, for real pan/zoom and the multi-day lookback
view. `src/viz/chart.py` (matplotlib, static PNG) remains untouched and
is still what `scripts/plot_trade.py` (the CLI) uses -- a genuinely
different, still-useful tool for quick file-based inspection without a
browser, deliberately left alone.

Consumes the EXACT SAME `Overlay` (src/viz/overlay.py) the matplotlib
renderer does -- Level/Band/VMarker/PriceMarker are plain dataclasses
with no matplotlib dependency, so no strategy adapter needed any change
for this renderer to exist. Unlike the matplotlib renderer, this one
never draws a text panel -- the research app's own "Status" column
already shows `overlay.text_panel`'s content, and an in-chart box was
found to overlap price action and duplicate that panel.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from viz.overlay import Overlay

UP_COLOR = "#2a9d4a"
DOWN_COLOR = "#d6392b"

# matplotlib accepts "tab:blue"/"tab:purple"/etc (its own tab10 palette
# shorthand) -- Plotly's color validator does not. Adapters (e.g.
# viz.poc_adapter) are written against matplotlib's own color names
# since chart.py (the original, matplotlib renderer) was built first;
# translated here rather than touching every adapter's color choices.
_MPL_TAB_COLORS = {
    "tab:blue": "#1f77b4", "tab:orange": "#ff7f0e", "tab:green": "#2ca02c",
    "tab:red": "#d62728", "tab:purple": "#9467bd", "tab:brown": "#8c564b",
    "tab:pink": "#e377c2", "tab:gray": "#7f7f7f", "tab:olive": "#bcbd22",
    "tab:cyan": "#17becf",
}


def _color(c: str) -> str:
    return _MPL_TAB_COLORS.get(c, c)


def _nearest_index(ts_arr: np.ndarray, target_ts: pd.Timestamp) -> int | None:
    """Same contract as chart.py's own `_nearest_index` -- None (marker
    dropped, never relocated) if `target_ts` is more than two bar-widths
    away from anything in `ts_arr`."""
    if len(ts_arr) == 0:
        return None
    target64 = np.datetime64(pd.Timestamp(target_ts))
    diffs = np.abs(ts_arr - target64)
    idx = int(np.argmin(diffs))
    bar_width = np.median(np.diff(ts_arr)) if len(ts_arr) > 1 else np.timedelta64(1, "m")
    if diffs[idx] > 2 * bar_width:
        return None
    return idx


def _bucket_fraction_index(starts: np.ndarray, ends: np.ndarray, target_ts: pd.Timestamp) -> float | None:
    """Locates `target_ts` WITHIN its containing bucket as a continuous
    x position, not a bar index -- bucket `i` occupies [i-0.5, i+0.5),
    so a timestamp a quarter of the way through bucket `i` lands at
    `i - 0.5 + 0.25`. Unlike `_nearest_index` (which snaps a 1-minute
    marker to its single nearest bar, since a 1-minute bar's own width
    is the chart's finest resolution anyway), an hourly bucket is wide
    enough that snapping would visibly misplace an entry/exit fill that
    happened, say, 50 minutes into the hour. `starts`/`ends` are a
    bucket's own `ts`/`bucket_end` (NOT assumed to be a fixed 60-minute
    width -- the day's last bucket is the partial 15:15-15:30 one).

    Same drop contract as `_nearest_index`: returns None if `target_ts`
    falls more than one bucket-width outside the nearest bucket's own
    span (e.g. a marker from a day not in the displayed window)."""
    if len(starts) == 0:
        return None
    target64 = np.datetime64(pd.Timestamp(target_ts))
    median_width = np.median((ends - starts).astype("timedelta64[s]").astype(float))
    if median_width <= 0:
        median_width = 3600.0

    le_mask = starts <= target64
    if not le_mask.any():
        gap = (starts[0] - target64).astype("timedelta64[s]").astype(float)
        if gap > 2 * median_width:
            return None
        return -0.5

    i = int(np.flatnonzero(le_mask)[-1])
    width = (ends[i] - starts[i]).astype("timedelta64[s]").astype(float)
    if target64 >= ends[i]:
        overshoot = (target64 - ends[i]).astype("timedelta64[s]").astype(float)
        if overshoot > 2 * median_width:
            return None
        return i + 0.5
    if width <= 0:
        return float(i)
    frac = (target64 - starts[i]).astype("timedelta64[s]").astype(float) / width
    return i - 0.5 + min(max(frac, 0.0), 1.0)


def build_plotly_chart(
    combined_bars: pd.DataFrame, entity_id: str, trade_date: dt.date, scale_label: str,
    overlay: Overlay | None = None,
) -> go.Figure:
    """`combined_bars`: [ts, open, high, low, close, volume, trade_date]
    -- one or more trading days concatenated in ascending order (see
    `viz.data.fetch_raw_multi_day_bars`'s own `combined` output; a
    single-day DataFrame with a constant `trade_date` column works too).
    Day boundaries are derived from `trade_date` changing, not guessed
    from timestamp gaps -- correct even if a lookback day was skipped
    (missing archive data) and the next day follows non-consecutively."""
    if combined_bars.empty:
        raise ValueError(f"no bars to plot for {entity_id} around {trade_date}")

    bars = combined_bars.sort_values("ts").reset_index(drop=True)
    n = len(bars)
    x = np.arange(n)
    ts_arr = bars["ts"].to_numpy()

    is_up = bars["close"] >= bars["open"]
    vol_colors = np.where(is_up, UP_COLOR, DOWN_COLOR)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=x, open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"],
            increasing_line_color=UP_COLOR, decreasing_line_color=DOWN_COLOR,
            increasing_fillcolor=UP_COLOR, decreasing_fillcolor=DOWN_COLOR,
            name="price", showlegend=False,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(x=x, y=bars["volume"], marker_color=vol_colors, name="volume", showlegend=False),
        row=2, col=1,
    )

    # --- day boundaries: vertical separators + date labels, derived from
    # trade_date changing, not from a fixed bar-count assumption ---
    day_groups = bars.groupby("trade_date", sort=False)
    boundary_starts = []
    for day_value, grp in day_groups:
        start_idx = grp.index[0]
        boundary_starts.append((start_idx, day_value))
    for start_idx, day_value in boundary_starts[1:]:
        fig.add_vline(x=start_idx - 0.5, line_width=1.5, line_dash="solid", line_color="#888888", row="all")
    for start_idx, day_value in boundary_starts:
        fig.add_annotation(
            x=start_idx, y=1.0, yref="y domain", yanchor="bottom", row=1, col=1,
            text=f"<b>{day_value}</b>", showarrow=False, font=dict(size=11, color="#555555"),
        )

    # --- overlay (optional, study-agnostic) -- NO text panel, per instruction ---
    if overlay is not None:
        for band in overlay.bands:
            fig.add_hrect(
                y0=band.low, y1=band.high, fillcolor=_color(band.color), opacity=band.alpha,
                line_width=0, row=1, col=1,
            )
        for level in overlay.levels:
            dash = "dash" if level.linestyle in ("--", "dashed") else "dot"
            fig.add_hline(
                y=level.price, line_color=_color(level.color), line_dash=dash, line_width=1.3, row=1, col=1,
                annotation_text=f"{level.label} {level.price:.2f}", annotation_position="right",
                annotation_font_color=_color(level.color), annotation_font_size=10,
            )
        for vm in overlay.vmarkers:
            idx = _nearest_index(ts_arr, vm.ts)
            if idx is None:
                continue
            vdash = "dot" if vm.linestyle == ":" else "dash"
            fig.add_vline(x=idx, line_color=_color(vm.color), line_dash=vdash, line_width=1.0, row="all")
            fig.add_annotation(
                x=idx, y=1.0, yref="y domain", yanchor="bottom", textangle=-60, row=1, col=1,
                text=vm.label, showarrow=False, font=dict(size=9, color=_color(vm.color)), xanchor="left",
            )
        for pm in overlay.price_markers:
            idx = _nearest_index(ts_arr, pm.ts)
            if idx is None:
                continue
            symbol = "triangle-up" if pm.kind == "entry" else "triangle-down"
            color = "blue" if pm.kind == "entry" else "black"
            label = pm.label or f"{pm.kind.upper()} {pm.price:.2f}"
            fig.add_trace(
                go.Scatter(
                    x=[idx], y=[pm.price], mode="markers+text", marker=dict(symbol=symbol, size=14, color=color),
                    text=[label], textposition="top center" if pm.kind == "entry" else "bottom center",
                    textfont=dict(color=color, size=10), showlegend=False,
                ),
                row=1, col=1,
            )

    # --- x-axis: integer index with HH:MM tick labels (candles may span
    # multiple days; a plain datetime axis would show large overnight
    # gaps -- same reasoning chart.py's own matplotlib renderer uses) ---
    tick_every = max(1, n // 40)
    tick_idx = list(range(0, n, tick_every))
    tick_text = [pd.Timestamp(ts_arr[i]).strftime("%m-%d %H:%M") for i in tick_idx]

    title = f"{entity_id} -- {trade_date}"
    if overlay is not None and overlay.title_suffix:
        title += f" -- {overlay.title_suffix}"

    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left"),
        dragmode="pan",
        xaxis2=dict(tickmode="array", tickvals=tick_idx, ticktext=tick_text, rangeslider=dict(visible=False)),
        xaxis=dict(rangeslider=dict(visible=False)),
        height=700,
        margin=dict(t=60, b=40, l=50, r=120),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.add_annotation(
        text=scale_label, xref="paper", yref="paper", x=0.5, y=-0.12, showarrow=False,
        font=dict(size=11, color="firebrick" if ("UNRESOLVED" in scale_label or "NO DATA" in scale_label)
                  else "gray"),
    )
    return fig


def build_hourly_chart(
    combined_bars: pd.DataFrame, entity_id: str, trade_date: dt.date, scale_label: str,
    overlay: Overlay | None = None,
) -> go.Figure:
    """Hourly-candle view of the SAME RAW-scale window `build_plotly_chart`
    shows at 1-minute resolution -- the POC lookback window with its
    intraday shape still visible, between the 1-minute (trade-day detail)
    and daily (50-day trend filter) views. `combined_bars`: `viz.data.
    fetch_raw_hourly_bars`'s own `combined` output (`ts`, `bucket_end`,
    open/high/low/close/volume, `trade_date`) -- `bucket_end` is REQUIRED
    (not optional the way it would be for a fixed-width bar) because
    buckets are anchored at the 09:15 session open, so each day's LAST
    bucket is the PARTIAL 15:15-15:30 one (15 minutes, not 60), and an
    entry/exit marker landing inside a bucket needs that bucket's own
    actual span, not an assumed 60-minute one, to be placed correctly.

    Day boundaries: identical convention to `build_plotly_chart` (derived
    from `trade_date` changing). Overlay markers: identical Level/Band/
    VMarker/PriceMarker objects, but vmarkers/price_markers are placed at
    a FRACTIONAL x position via `_bucket_fraction_index` -- the real
    point within the bucket's own time span the event occurred at,
    rather than snapped to the bucket's center the way `_nearest_index`
    would (fine for a 1-minute bar's own width, visibly wrong for an
    hour-wide one). Partial buckets (any bucket whose own `bucket_end -
    ts` is under 60 minutes -- the session-close one on every day, or a
    rarer mid-day one if the archive has a gap) are flagged directly on
    the x-axis tick label with a trailing `*`, explained in the caption,
    rather than drawn with a narrower candle body (Plotly's candlestick
    trace has no per-candle width control) or silently left looking like
    a normal hour."""
    if combined_bars.empty:
        raise ValueError(f"no bars to plot for {entity_id} around {trade_date}")

    bars = combined_bars.sort_values("ts").reset_index(drop=True)
    n = len(bars)
    x = np.arange(n)
    starts = bars["ts"].to_numpy()
    ends = bars["bucket_end"].to_numpy()

    is_up = bars["close"] >= bars["open"]
    vol_colors = np.where(is_up, UP_COLOR, DOWN_COLOR)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=x, open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"],
            increasing_line_color=UP_COLOR, decreasing_line_color=DOWN_COLOR,
            increasing_fillcolor=UP_COLOR, decreasing_fillcolor=DOWN_COLOR,
            name="price", showlegend=False,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(x=x, y=bars["volume"], marker_color=vol_colors, name="volume", showlegend=False),
        row=2, col=1,
    )

    # --- day boundaries: identical convention to build_plotly_chart ---
    day_groups = bars.groupby("trade_date", sort=False)
    boundary_starts = []
    for day_value, grp in day_groups:
        start_idx = grp.index[0]
        boundary_starts.append((start_idx, day_value))
    for start_idx, day_value in boundary_starts[1:]:
        fig.add_vline(x=start_idx - 0.5, line_width=1.5, line_dash="solid", line_color="#888888", row="all")
    for start_idx, day_value in boundary_starts:
        fig.add_annotation(
            x=start_idx, y=1.0, yref="y domain", yanchor="bottom", row=1, col=1,
            text=f"<b>{day_value}</b>", showarrow=False, font=dict(size=11, color="#555555"),
        )

    # --- overlay (optional, study-agnostic) -- NO text panel, per instruction ---
    if overlay is not None:
        for band in overlay.bands:
            fig.add_hrect(
                y0=band.low, y1=band.high, fillcolor=_color(band.color), opacity=band.alpha,
                line_width=0, row=1, col=1,
            )
        for level in overlay.levels:
            dash = "dash" if level.linestyle in ("--", "dashed") else "dot"
            fig.add_hline(
                y=level.price, line_color=_color(level.color), line_dash=dash, line_width=1.3, row=1, col=1,
                annotation_text=f"{level.label} {level.price:.2f}", annotation_position="right",
                annotation_font_color=_color(level.color), annotation_font_size=10,
            )
        for vm in overlay.vmarkers:
            xpos = _bucket_fraction_index(starts, ends, vm.ts)
            if xpos is None:
                continue
            vdash = "dot" if vm.linestyle == ":" else "dash"
            fig.add_vline(x=xpos, line_color=_color(vm.color), line_dash=vdash, line_width=1.0, row="all")
            fig.add_annotation(
                x=xpos, y=1.0, yref="y domain", yanchor="bottom", textangle=-60, row=1, col=1,
                text=vm.label, showarrow=False, font=dict(size=9, color=_color(vm.color)), xanchor="left",
            )
        for pm in overlay.price_markers:
            xpos = _bucket_fraction_index(starts, ends, pm.ts)
            if xpos is None:
                continue
            symbol = "triangle-up" if pm.kind == "entry" else "triangle-down"
            color = "blue" if pm.kind == "entry" else "black"
            label = pm.label or f"{pm.kind.upper()} {pm.price:.2f}"
            fig.add_trace(
                go.Scatter(
                    x=[xpos], y=[pm.price], mode="markers+text", marker=dict(symbol=symbol, size=14, color=color),
                    text=[label], textposition="top center" if pm.kind == "entry" else "bottom center",
                    textfont=dict(color=color, size=10), showlegend=False,
                ),
                row=1, col=1,
            )

    # --- x-axis: integer index with HH:MM tick labels; every PARTIAL
    # bucket gets its own tick (unioned with the evenly-spaced ones, not
    # just whichever happens to land on the regular stride) and a
    # trailing "*", so the handling called for in instruction -- "say in
    # the chart ... how you handled it" -- is visible at the exact candle
    # it applies to, not just in a general caption ---
    bucket_minutes = (ends - starts).astype("timedelta64[s]").astype(float) / 60.0
    is_partial = bucket_minutes < 59.0
    tick_every = max(1, n // 40)
    tick_idx = sorted(set(range(0, n, tick_every)) | set(int(i) for i in np.flatnonzero(is_partial)))
    tick_text = [
        pd.Timestamp(starts[i]).strftime("%m-%d %H:%M") + (" *" if is_partial[i] else "")
        for i in tick_idx
    ]

    title = f"{entity_id} -- hourly, {n} candles ending {trade_date}"
    if overlay is not None and overlay.title_suffix:
        title += f" -- {overlay.title_suffix}"

    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left"),
        dragmode="pan",
        xaxis2=dict(tickmode="array", tickvals=tick_idx, ticktext=tick_text, rangeslider=dict(visible=False),
                     tickangle=-45),
        xaxis=dict(rangeslider=dict(visible=False)),
        height=700,
        margin=dict(t=60, b=60, l=50, r=120),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.add_annotation(
        text=(
            f"{scale_label}  |  1-hour buckets anchored at the 09:15 session open -- each day's LAST "
            f"bucket is the partial 15:15-15:30 one (15 min, not 60); marked with '*' on the axis above."
        ),
        xref="paper", yref="paper", x=0.5, y=-0.16, showarrow=False,
        font=dict(size=11, color="firebrick" if ("UNRESOLVED" in scale_label or "NO DATA" in scale_label)
                  else "gray"),
    )
    return fig


def build_daily_chart(
    daily_bars: pd.DataFrame, entity_id: str, trade_date: dt.date, scale_note: str,
    poc_price_adjusted: float | None = None, prev_high_adjusted: float | None = None,
) -> go.Figure:
    """Daily-candle view for seeing the context a daily-timeframe
    condition (the 50-day trend filter, in particular) actually used --
    invisible on a 1-minute chart. `daily_bars`: `viz.data.
    fetch_daily_bars`'s own output (`trade_date`, `adjusted_open/high/
    low/close`, `sma`), ENTITY-ADJUSTED scale throughout. `poc_price_
    adjusted`/`prev_high_adjusted` must ALREADY be converted to this
    same adjusted scale (`viz.data.adjust_raw_level_for_daily_chart`) --
    this function does not convert anything itself, so a caller cannot
    accidentally pass a RAW-scale level through unconverted and have it
    silently plot at the wrong level."""
    if daily_bars.empty:
        raise ValueError(f"no daily bars to plot for {entity_id} ending {trade_date}")

    bars = daily_bars.sort_values("trade_date").reset_index(drop=True)
    n = len(bars)
    x = np.arange(n)
    dates = pd.to_datetime(bars["trade_date"])

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x, open=bars["adjusted_open"], high=bars["adjusted_high"], low=bars["adjusted_low"],
        close=bars["adjusted_close"], increasing_line_color=UP_COLOR, decreasing_line_color=DOWN_COLOR,
        increasing_fillcolor=UP_COLOR, decreasing_fillcolor=DOWN_COLOR, name="price", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=bars["sma"], mode="lines", line=dict(color="#e8a33d", width=1.6),
        name="50-day MA (trend filter)",
    ))

    if poc_price_adjusted is not None:
        fig.add_hline(y=poc_price_adjusted, line_color=_color("tab:blue"), line_dash="dash", line_width=1.3,
                       annotation_text=f"POC {poc_price_adjusted:.2f}", annotation_position="right",
                       annotation_font_color=_color("tab:blue"), annotation_font_size=10)
    if prev_high_adjusted is not None:
        fig.add_hline(y=prev_high_adjusted, line_color=_color("tab:purple"), line_dash="dash", line_width=1.3,
                       annotation_text=f"PREV_HIGH {prev_high_adjusted:.2f}", annotation_position="right",
                       annotation_font_color=_color("tab:purple"), annotation_font_size=10)

    trade_rows = bars.index[dates.dt.date == trade_date]
    if len(trade_rows):
        idx = int(trade_rows[0])
        fig.add_vline(x=idx, line_color="black", line_dash="dot", line_width=1.3)
        fig.add_annotation(x=idx, y=1.0, yref="y domain", yanchor="bottom", text=f"<b>{trade_date}</b>",
                            showarrow=False, font=dict(size=10, color="black"))

    tick_every = max(1, n // 20)
    tick_idx = list(range(0, n, tick_every))
    tick_text = [dates.iloc[i].strftime("%Y-%m-%d") for i in tick_idx]

    fig.update_layout(
        title=dict(text=f"{entity_id} -- daily, {n} trading days ending {trade_date}", x=0.01, xanchor="left"),
        dragmode="pan",
        xaxis=dict(tickmode="array", tickvals=tick_idx, ticktext=tick_text, rangeslider=dict(visible=False)),
        yaxis=dict(title="Price (entity-adjusted)"),
        height=550,
        margin=dict(t=60, b=40, l=50, r=130),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.add_annotation(
        text=scale_note, xref="paper", yref="paper", x=0.5, y=-0.16, showarrow=False,
        font=dict(size=10, color="gray"),
    )
    return fig
