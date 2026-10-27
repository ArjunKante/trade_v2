"""Streamlit research browser for INSPECTING PAST, CLOSED strategy
studies -- NOT the live-trading dashboard (that's scripts/serve_screener.py,
a separate file, deliberately untouched by this one).

    streamlit run scripts/research_app.py

Every study offered here is already closed (DEV failed, or -- if DEV
ever passes a future study -- TEST read once and reported). This tool
never recomputes a result that would change what a study already
concluded; strategy adapters (src/viz/<study>_adapter.py) recompute
overlays PURELY FOR DISPLAY from the same pure functions the real
backtest used, the identical thing the CLI (scripts/plot_trade.py)
already does. **No sealed TEST window is ever read here** -- every
per-study date picker below is hard-bounded to that study's own DEV
window, sourced from that study's own test_seal module, not re-typed.
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import streamlit as st

from data_layer.db import get_read_connection as get_warehouse_con
from fibo.intraday_db import get_read_connection as get_intraday_con

from viz.chart import plot_trade_chart

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = ROOT / "data" / "warehouse.duckdb"
INTRADAY_DB = ROOT / "data" / "fibo_intraday.duckdb"

st.set_page_config(page_title="Strategy Research Browser", layout="wide")


# ---------------------------------------------------------------------
# DB connections -- cached as a resource (not re-opened per rerun)
# ---------------------------------------------------------------------

@st.cache_resource
def _connections():
    return get_warehouse_con(WAREHOUSE_DB), get_intraday_con(INTRADAY_DB)


# ---------------------------------------------------------------------
# POC -- the only study wired up so far (build-POC-first, per instruction)
# ---------------------------------------------------------------------

@st.cache_data
def _load_poc_trades() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "poc" / "dev_trades.csv")
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


@st.cache_data
def _load_poc_verdict() -> dict:
    """Reads the ALREADY-RECORDED inference result -- never recomputes
    it. mean_net_r/CI come straight from data/poc/dev_inference.pkl
    (Stage 2 of scripts/poc_dev_run.py, produced before the run was
    stopped); the DEV_PASS/closure text is the same conclusion already
    committed to POC_FINDINGS.md, not re-derived here."""
    with open(ROOT / "data" / "poc" / "dev_inference.pkl", "rb") as f:
        inf = pickle.load(f)
    return {
        "headline": "CLOSED -- DEV FAILS (NO EDGE)",
        "mean_net_r": inf["mean_net_r"], "ci_low": inf["ci_low"], "ci_high": inf["ci_high"],
        "n_trades": inf["n_trades"], "n_days": inf["n_days"],
        "summary": (
            "Mean net R is negative with a 97.5% bootstrap CI excluding zero on the "
            "NEGATIVE side -- the gate's first condition already fails, so the remaining "
            "conditions (both null percentiles, ex-best-year, bands 1-100) cannot change "
            "the verdict. The TIMING null was stopped at 200/500 seeds once the gate was "
            "already decided (reported as partial, not a finished comparison); the "
            "SELECTION null never started. The entire loss is transaction-cost drag "
            "(mean gross R ~ 0), concentrated in a tail of trades whose stop distance "
            "happened to be a few paise wide. **The sealed TEST window was never read.** "
            "Full detail: POC_FINDINGS.md."
        ),
        "findings_doc": "POC_FINDINGS.md",
    }


@st.cache_data
def _poc_jump_dates() -> dict:
    """Whole-warehouse scan, identical for every (entity, date) call --
    cached ONCE per app session instead of repeated on every chart click
    (found costing ~20s per click before this fix)."""
    from fibo.jump_guard import combined_unexplained_jump_dates
    warehouse_con, _ = _connections()
    return combined_unexplained_jump_dates(warehouse_con)


@st.cache_data
def _poc_rank_lookup() -> dict:
    """Same reasoning as `_poc_jump_dates` -- the full annual-reconstitution
    universe is identical for every call, cached once."""
    from fibo.universe import effective_universe, reconstitute_annually
    from poc.backtest import STUB_YEAR, TOP_N
    warehouse_con, _ = _connections()
    universe = effective_universe(reconstitute_annually(warehouse_con, top_n=TOP_N), stub_year=STUB_YEAR)
    return {(r["year"], r["entity_id"]): r["rank"] for _, r in universe.iterrows()}


@st.cache_data
def _poc_adapter_cached(_warehouse_con, _intraday_con, entity_id: str, trade_date: dt.date) -> dict:
    """Cached per (entity_id, trade_date) -- re-rendering the SAME
    entity-day (e.g. toggling the zoom window, changing the outcome
    filter) is common and should not re-run the adapter's own touch/
    confirm/entry/exit recomputation each time. `_warehouse_con`/
    `_intraday_con` are excluded from the cache key (leading underscore,
    st.cache_data's own convention) -- a duckdb connection isn't a
    meaningful part of the key and isn't reliably hashable anyway."""
    from viz.poc_adapter import build_poc_overlay
    return build_poc_overlay(
        _warehouse_con, _intraday_con, entity_id, trade_date,
        jump_dates_by_entity=_poc_jump_dates(), rank_lookup=_poc_rank_lookup(),
    )


def _poc_adapter(warehouse_con, intraday_con, entity_id: str, trade_date: dt.date) -> dict:
    return _poc_adapter_cached(warehouse_con, intraday_con, entity_id, trade_date)


def _poc_dev_bounds() -> tuple[dt.date, dt.date]:
    from poc.test_seal import DEV_END, DEV_START
    return DEV_START, DEV_END


# ---------------------------------------------------------------------
# Study registry -- every study the user asked for is listed; only ones
# with BOTH exported trade records AND a built viz adapter are usable.
# ---------------------------------------------------------------------

STUDIES: dict[str, dict] = {
    "poc": {
        "label": "POC (point of control) bounce",
        "available": True,
        "trades_loader": _load_poc_trades,
        "verdict_loader": _load_poc_verdict,
        "adapter": _poc_adapter,
        "dev_bounds": _poc_dev_bounds,
        "outcome_col": "outcome",
        "net_r_col": "net_r",
    },
    "fibo": {
        "label": "Fibo (ORB + golden zone)",
        "available": False,
        "unavailable_reason": (
            "Trade records exist (`data/fibo_step5_dev_results.pkl`, DEV only, 67 trades) but no "
            "`src/viz/fibo_adapter.py` has been built yet. **Note**: `data/fibo_test_results.pkl` "
            "(188 trades) looks like the sealed TEST window's own results -- this tool will never "
            "load that file, even once a Fibo adapter exists."
        ),
    },
    "box_v1": {
        "label": "Box theory V1",
        "available": False,
        "unavailable_reason": "Trade records exist (`data/box_theory/dev_trades.pkl`, 182,703 rows, "
                               "FAST+SLOW configs) but no viz adapter has been built yet.",
    },
    "box_v2": {
        "label": "Box theory V2",
        "available": False,
        "unavailable_reason": "Trade records exist (`data/box_theory/v2/v2_dev_trades.pkl`) but no "
                               "viz adapter has been built yet.",
    },
    "darvas": {
        "label": "Darvas Box theory",
        "available": False,
        "unavailable_reason": "Trade records exist (`data/darvas/dev_backtest.pkl`, 757 trades) but "
                               "no viz adapter has been built yet.",
    },
    "fvg": {
        "label": "Fair Value Gap (FVG)",
        "available": False,
        "unavailable_reason": "Trade records exist (`data/fvg/dev/fvg_dev_trades.pkl`, configs A/B, "
                               "54,482 + 28,801 rows) but no viz adapter has been built yet.",
    },
    "ipo_listing": {
        "label": "IPO listing",
        "available": False,
        "unavailable_reason": (
            "**No per-trade records were ever exported.** `data/ipo_listing/dev_run_results.json` is "
            "aggregate-only (win rate, mean R, null percentiles) -- `scripts/ipo_listing_dev_run.py` "
            "never pickles a trade-level DataFrame. Would need that script changed to persist one; "
            "not done, since that touches a closed study's own code."
        ),
    },
}


# ---------------------------------------------------------------------
# Sidebar: study -> stock -> date
# ---------------------------------------------------------------------

st.sidebar.title("Research Browser")
st.sidebar.caption("Closed studies only. Read-only. No sealed TEST window is ever reachable here.")

study_key = st.sidebar.selectbox(
    "Study", list(STUDIES.keys()), format_func=lambda k: STUDIES[k]["label"],
)
study = STUDIES[study_key]

if not study["available"]:
    st.title(study["label"])
    st.warning(f"**Not available in this browser yet.**\n\n{study['unavailable_reason']}")
    st.stop()

warehouse_con, intraday_con = _connections()
trades = study["trades_loader"]()
verdict = study["verdict_loader"]()
dev_start, dev_end = study["dev_bounds"]()

st.title(study["label"])
st.error(f"### {verdict['headline']}\n\n"
         f"**Mean net R** = {verdict['mean_net_r']:+.4f}  "
         f"**97.5% CI** = [{verdict['ci_low']:+.4f}, {verdict['ci_high']:+.4f}]  "
         f"({verdict['n_trades']:,} trades, {verdict['n_days']:,} distinct days)\n\n"
         f"{verdict['summary']}")

entities = sorted(trades["entity_id"].unique())
# Pre-seed the WIDGETS' OWN session_state keys, once, before they ever
# render -- this is the only point in the script where that's legal.
# After this, both widgets are addressed ONLY by `key=`, never by
# `index=`/`value=` (a keyed widget ignores those on every run after
# the first anyway, once its own session_state entry exists -- found
# live: the table-click handler below updating a SEPARATE "current_*"
# key and expecting these widgets to follow it silently did nothing,
# because index=/value= are first-render-only once a key owns the slot).
if "entity_id_widget" not in st.session_state or st.session_state["entity_id_widget"] not in entities:
    st.session_state["entity_id_widget"] = entities[0]
if "trade_date_widget" not in st.session_state:
    st.session_state["trade_date_widget"] = trades["trade_date"].iloc[0]


def _on_table_select() -> None:
    """`on_select` CALLBACK (not inline post-widget code) -- this is the
    only Streamlit-supported way to let the trade table drive the
    entity/date widgets' own values. A callback runs in a dedicated
    phase BEFORE the main script body re-executes, so writing to
    `entity_id_widget`/`trade_date_widget` here is legal; doing the
    identical write inline, after those widgets had already rendered in
    the same run, is exactly what raises `StreamlitWidgetAlready
    InstantiatedError` (hit live, same root cause as the index=/value=
    issue above -- both are instances of "a keyed widget's value can
    only be set from outside itself via a callback or before its first
    render, never from code after it runs in the same pass")."""
    sel_rows = st.session_state["trades_table"]["selection"]["rows"]
    if sel_rows and "_filtered_for_select" in st.session_state:
        picked = st.session_state["_filtered_for_select"].iloc[sel_rows[0]]
        st.session_state["entity_id_widget"] = picked["entity_id"]
        st.session_state["trade_date_widget"] = picked["trade_date"]


entity_id = st.sidebar.selectbox("Stock (entity_id)", entities, key="entity_id_widget")
trade_date = st.sidebar.date_input(
    "Date", min_value=dev_start, max_value=dev_end, key="trade_date_widget",
    help=f"Bounded to this study's own DEV window ({dev_start} to {dev_end}) -- "
         f"the sealed TEST window is never reachable here.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("Zoom window")
zoom_on = st.sidebar.checkbox("Zoom to a sub-window of the session", value=False)
window = None
if zoom_on:
    zoom_start = st.sidebar.time_input("From", value=dt.time(9, 15))
    zoom_end = st.sidebar.time_input("To", value=dt.time(10, 30))
    window = (zoom_start, zoom_end)

st.sidebar.markdown("---")
st.sidebar.subheader("Filter trade table")
outcome_col, net_r_col = study["outcome_col"], study["net_r_col"]
outcomes = sorted(trades[outcome_col].unique())
selected_outcomes = st.sidebar.multiselect("Outcome", outcomes, default=outcomes)
r_min, r_max = float(trades[net_r_col].min()), float(trades[net_r_col].max())
r_range = st.sidebar.slider("Net R range", min_value=r_min, max_value=r_max, value=(r_min, r_max))

filtered = trades[
    trades[outcome_col].isin(selected_outcomes)
    & trades[net_r_col].between(r_range[0], r_range[1])
].sort_values(net_r_col)


# ---------------------------------------------------------------------
# Main panel: chart (left/top) + trade numbers, table below
# ---------------------------------------------------------------------

col_chart, col_numbers = st.columns([3, 1])

# entity_id / trade_date already come straight from the sidebar widgets
# above (key="entity_id_widget"/"trade_date_widget") -- the trade
# table's own on_select callback (_on_table_select) is what keeps THOSE
# in sync with a clicked row; nothing further to reconcile here.
result = study["adapter"](warehouse_con, intraday_con, entity_id, trade_date)

with col_chart:
    st.subheader(f"{entity_id} -- {trade_date}")
    if result["bars"] is None or (hasattr(result["bars"], "empty") and result["bars"].empty):
        st.info(f"Nothing to plot for this entity-day. status={result['status']}  "
                f"detail={result['detail']}")
    else:
        bars = result["bars"][["ts", "open", "high", "low", "close", "volume"]]
        scale_label = "RAW rupee scale (resolved via the study adapter's own Section-3 lookback chain)"
        out_path = ROOT / "data" / "viz" / f"_app_{study_key}_{entity_id}_{trade_date}.png"
        try:
            saved = plot_trade_chart(
                bars, entity_id, trade_date, scale_label, overlay=result["overlay"],
                out_path=out_path, window=window,
            )
            st.image(str(saved), use_container_width=True)
        except ValueError as e:
            st.warning(str(e))

with col_numbers:
    st.subheader("Status")
    st.write(f"**{result['status']}**")
    for k, v in result["detail"].items():
        st.write(f"- {k}: {v}")
    if result["overlay"] is not None and result["overlay"].text_panel:
        st.text("\n".join(result["overlay"].text_panel))

st.markdown("---")
st.subheader(f"Trades ({len(filtered):,} of {len(trades):,} shown)")
st.caption("Click the checkbox at the left of a row to load its chart above.")
st.session_state["_filtered_for_select"] = filtered  # _on_table_select's own row lookup
st.dataframe(
    filtered, use_container_width=True, height=360,
    on_select=_on_table_select, selection_mode="single-row", key="trades_table",
)
