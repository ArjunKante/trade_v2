"""Resolves which NIFTY index-option contracts to collect: the nearest 2
expiries, strikes within +/-5% of a given spot price, from Angel One's
instrument (scrip) master.

OWN CACHE, deliberately not shared with src/spread_monitor/tokens.py's
cache file: that module's cache-cleanup (`for stale in CACHE_DIR.glob(
"angel_scrip_master_*.json"): stale.unlink()`) would delete a same-
prefixed file belonging to this package on its own next run, and vice
versa, if the two modules' cache filenames collided. This module's cache
filename uses a disjoint prefix for exactly that reason -- the two
packages share a cache DIRECTORY (data/cache/) but never a cache FILE or
a cleanup glob. The fetch+cache logic itself is duplicated (not imported
from spread_monitor.tokens' private `_load_scrip_master`) for the same
decoupling reason spread_monitor.tokens' own docstring already states for
not importing fibo.download: small (~15 line), and keeping this package
free to change independently.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ANGEL_SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"

IST = ZoneInfo("Asia/Kolkata")
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_PREFIX = "options_depth_scrip_master_"
CACHE_GLOB = f"{CACHE_PREFIX}*.json"

NIFTY_50_INDEX_TOKEN = "99926000"  # Angel's NSE instrument-master token for the Nifty 50 index
N_NEAREST_EXPIRIES = 2
STRIKE_BAND_PCT = 0.05


@dataclass
class OptionContract:
    token: str
    symbol: str
    expiry: str          # as Angel's master states it, e.g. "13OCT2026"
    strike: float         # rupees (master states paise*100; divided here)
    option_type: str      # "CE" or "PE"


def _cache_path(today: dt.date) -> Path:
    return CACHE_DIR / f"{CACHE_PREFIX}{today:%Y-%m-%d}.json"


def _load_scrip_master(today: dt.date | None = None) -> list[dict]:
    today = today or dt.datetime.now(IST).date()
    cache_path = _cache_path(today)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    master = requests.get(ANGEL_SCRIP_MASTER_URL, timeout=180).json()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CACHE_DIR.glob(CACHE_GLOB):
        stale.unlink()
    cache_path.write_text(json.dumps(master), encoding="utf-8")
    return master


def _parse_expiry(expiry: str) -> dt.date:
    return dt.datetime.strptime(expiry, "%d%b%Y").date()


def nearest_expiries(today: dt.date, n: int = N_NEAREST_EXPIRIES) -> list[str]:
    """The `n` nearest NIFTY index-option expiries that have not yet
    passed `today`, from today's scrip master."""
    master = _load_scrip_master(today)
    nifty_opts = [r for r in master if r.get("exch_seg") == "NFO" and r.get("instrumenttype") == "OPTIDX"
                  and r.get("name") == "NIFTY"]
    future = sorted({r["expiry"] for r in nifty_opts if _parse_expiry(r["expiry"]) >= today}, key=_parse_expiry)
    return future[:n]


def contracts_for_snapshot(spot: float, today: dt.date | None = None,
                            n_expiries: int = N_NEAREST_EXPIRIES,
                            band_pct: float = STRIKE_BAND_PCT) -> list[OptionContract]:
    """Every NIFTY index-option contract (both CE and PE) across the
    `n_expiries` nearest expiries, with strike within +/-`band_pct` of
    `spot`. `spot` must be a live reading taken just before this call --
    the eligible strike set is point-in-time by construction, not a
    fixed list, since spot moves intraday between this collector's own
    3 daily snapshots."""
    today = today or dt.datetime.now(IST).date()
    master = _load_scrip_master(today)
    nifty_opts = [r for r in master if r.get("exch_seg") == "NFO" and r.get("instrumenttype") == "OPTIDX"
                  and r.get("name") == "NIFTY"]

    expiries = set(nearest_expiries(today, n_expiries))
    lo, hi = spot * (1 - band_pct), spot * (1 + band_pct)

    out = []
    for r in nifty_opts:
        if r["expiry"] not in expiries:
            continue
        strike = float(r["strike"]) / 100
        if not (lo <= strike <= hi):
            continue
        symbol = r["symbol"]
        option_type = symbol[-2:]
        if option_type not in ("CE", "PE"):
            continue
        out.append(OptionContract(token=r["token"], symbol=symbol, expiry=r["expiry"],
                                   strike=strike, option_type=option_type))
    return out
