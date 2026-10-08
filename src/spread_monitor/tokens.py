"""Resolves plain NSE trading symbols to Angel One instrument tokens.

Deliberately self-contained rather than importing src/fibo/download.py's
resolve_entity_tokens: that function resolves via this project's own
entity/ISIN history (fibo's concern), whereas this module only needs a
direct symbol -> token lookup against Angel's current instrument master.
Duplicating the ~10-line lookup keeps this package decoupled from Fibo's
code, per instruction not to touch it.

The instrument master (OpenAPIScripMaster.json) is tens of MB and does
not change intraday, so it is cached to disk once per IST trading date
(data/cache/angel_scrip_master_<date>.json) and reused for every run on
that date; it is re-downloaded only when the cached copy is from a
previous day. Stale dated copies are removed when a fresh one is
written, so the cache does not accumulate one file per trading day
forever.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ANGEL_SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"

IST = ZoneInfo("Asia/Kolkata")
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_GLOB = "angel_scrip_master_*.json"


def _cache_path(today: dt.date) -> Path:
    return CACHE_DIR / f"angel_scrip_master_{today:%Y-%m-%d}.json"


def _load_scrip_master(today: dt.date | None = None) -> list[dict]:
    """Today's instrument master, from disk cache if today's copy already
    exists, else freshly downloaded and cached (replacing any older
    dated copy)."""
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


def resolve_tokens(symbols: list[str]) -> tuple[dict[str, str], list[str]]:
    """(token_map, missing) where token_map is {symbol: token} for every
    symbol found in Angel's NSE-EQ instrument master, and `missing` lists
    any symbol not found -- never silently dropped."""
    master = _load_scrip_master()
    by_key = {row["symbol"]: row["token"] for row in master
              if row.get("exch_seg") == "NSE" and row.get("symbol", "").endswith("-EQ")}

    token_map, missing = {}, []
    for symbol in symbols:
        key = f"{symbol}-EQ"
        if key in by_key:
            token_map[symbol] = by_key[key]
        else:
            missing.append(symbol)
    return token_map, missing
