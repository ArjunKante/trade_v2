"""Local web app backend for browsing the fundamental screener's output --
research tool, single-user, localhost only. Reads the DuckDB warehouse
read_only, once, on server startup; every request after that is served
from the in-memory cache built here. No export step, no copy of the
warehouse, no per-request DB queries.

Deliberately does NOT compute anything the CLI tools (fundamental_
screener.py, fundamental_snapshot.py) don't already compute -- this module
is a thin JSON-serialization layer over run_screener() and
build_company_report(), plus a staleness-annotation pass, not a second
implementation of the screening or fundamentals logic.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from reports.fundamental_screener import run_screener
from reports.fundamental_snapshot import (
    build_company_report, compute_momentum_universe, compute_sector_valuation_snapshot, NOT_AVAILABLE,
)

ROOT = Path(__file__).resolve().parents[2]
SCREENER_LOG_DIR = ROOT / "data" / "screener_logs"
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# JSON-safe conversion: pandas/numpy objects never reach json.dumps directly
# ---------------------------------------------------------------------------

def to_jsonable(obj):
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        return [to_jsonable(row) for row in obj.to_dict(orient="records")]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, dt.date, dt.datetime)):
        if pd.isna(obj):
            return None
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, str):
        return obj
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def add_staleness(obj, as_of: pd.Timestamp):
    """Walks an already-jsonable structure; for every key ending in
    'known_date' with a real (non-null) ISO date value, adds a sibling
    '<same-prefix>staleness_days' key. Generic over the many known_date
    field names used across fundamental_snapshot.py's sections
    (known_date, latest_known_date, pl_known_date, shares_known_date, ...)."""
    if isinstance(obj, list):
        for v in obj:
            add_staleness(v, as_of)
        return obj
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key.endswith("known_date") and obj[key]:
                try:
                    kd = pd.Timestamp(obj[key])
                    staleness = (as_of - kd).days
                except (ValueError, TypeError):
                    staleness = None
                stale_key = key[: -len("known_date")] + "staleness_days"
                obj[stale_key] = staleness
        for v in obj.values():
            add_staleness(v, as_of)
        return obj
    return obj


# ---------------------------------------------------------------------------
# Cache construction (runs once, on startup)
# ---------------------------------------------------------------------------

def _latest_log_file() -> str | None:
    if not SCREENER_LOG_DIR.exists():
        return None
    logs = sorted(SCREENER_LOG_DIR.glob("fundamental_screener_*.txt"))
    logs = [p for p in logs if "diagnostics" not in p.name]
    if not logs:
        return None
    return str(logs[-1].relative_to(ROOT))


def build_cache(con: duckdb.DuckDBPyConnection, progress=print) -> dict:
    progress("Computing the current momentum universe (this is the slow step, ~1 minute)...")
    universe = compute_momentum_universe(con)

    progress("Running the screener over the current top decile...")
    result = run_screener(con, universe=universe)
    as_of = result["as_of"]
    n_universe = result["n_universe"]

    progress(f"Computing sector valuation snapshot, then detailed fundamentals for all {len(result['results'])} names...")
    sector_snapshot = compute_sector_valuation_snapshot(con, as_of)

    rows = []
    details = {}
    for i, r in enumerate(result["results"]):
        symbol = r["symbol"]
        tercile = None
        for c in r["checks"]:
            if c["check"] == "bottom_liquidity_tercile" and c.get("value"):
                tercile = c["value"]
        rows.append({
            "symbol": symbol,
            "name": r["name"] if r["name"] != NOT_AVAILABLE else None,
            "verdict": r["verdict"],
            "momentum_rank": r["momentum_rank"],
            "momentum_value": r["momentum_value"],
            "sector": r["sector"],
            "liquidity_tercile": tercile,
        })

        try:
            # Reuses the SAME universe/sector_snapshot computed once above --
            # never recomputed per company. Passing momentum_universe here is
            # the whole reason run_screener's universe parameter exists.
            report = build_company_report(con, symbol, momentum_universe=universe, sector_snapshot=sector_snapshot)
        except Exception as e:  # a company the snapshot tool can't resolve for any reason -- degrade, don't crash the whole server
            report = {"error": str(e)}

        detail = to_jsonable(report)
        screener_section = {
            "verdict": r["verdict"],
            "checks": to_jsonable(r["checks"]),
            "sector_known": r["sector_known"],
        }
        detail["screener"] = screener_section
        add_staleness(detail, as_of)
        details[symbol] = detail

        if (i + 1) % 25 == 0:
            progress(f"  ... {i + 1}/{len(result['results'])} detail reports built")

    rows_json = to_jsonable(rows)
    add_staleness(rows_json, as_of)

    log_file = _latest_log_file()
    meta = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "as_of_date": as_of.date().isoformat(),
        "n_universe": n_universe,
        "n_companies": len(rows),
        "log_file": log_file,
        "funnel": to_jsonable(result["funnel"]),
    }
    progress("Cache built.")
    return {"meta": meta, "companies": rows_json, "details": details}


# ---------------------------------------------------------------------------
# FastAPI app -- every route is served from the in-memory cache above; no
# route ever touches the DuckDB connection or recomputes anything.
# ---------------------------------------------------------------------------

def create_app(cache: dict) -> FastAPI:
    app = FastAPI(title="Fundamental Screener (local, read-only)")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "screener.html")

    @app.get("/api/meta")
    def meta():
        return JSONResponse(cache["meta"])

    @app.get("/api/companies")
    def companies():
        return JSONResponse(cache["companies"])

    @app.get("/api/company/{symbol}")
    def company(symbol: str):
        detail = cache["details"].get(symbol.upper())
        if detail is None:
            raise HTTPException(status_code=404, detail=f"{symbol} is not in the current top-decile cache.")
        return JSONResponse(detail)

    return app
