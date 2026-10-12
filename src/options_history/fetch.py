"""NSE F&O bhavcopy fetcher, NIFTY-options-only extraction, into this
module's own DuckDB file (data/options_history/options_history.duckdb --
NOT data/warehouse.duckdb; kept fully separate from Fibo/momentum/
per_stock, per instruction).

Mirrors src/data_layer/prices_nse.py's legacy/UDiFF fetch pattern --
same two-format split, same cutover dates, CONFIRMED LIVE identical to
the equity archive (OPTIONS_HISTORICAL_FEASIBILITY.md): legacy through
2024-07-05, UDiFF from 2024-01-01, GET required (HEAD is WAF-blocked).

BUG #15's FIX, applied here too, not re-derived: a 404 is recorded
`no_data` ONLY when `data_layer.nse_holidays.is_nse_holiday` CONFIRMS the
date is a real NSE holiday (reused read-only -- holidays are exchange-
wide, the same calendar governs the equity/CM segment that module was
built for and the F&O segment this module fetches, not two different
calendars). Every other 404 -- a transient failure, a date the calendar
can't verify -- is recorded `error` and retried on the next call, never
cached as a permanent (and possibly wrong) "holiday."

DOES NOT KEEP RAW FILES: downloads each day's zip to a throwaway path,
extracts NIFTY-option rows, verifies the extracted row count actually
landed in the database, THEN deletes the raw zip. The archive is
re-downloadable from NSE at any time -- there is no reason to keep a
~500KB-1MB whole-market file on disk once the ~20-50KB of it this module
actually wants has been pulled out and confirmed stored.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import time
import zipfile
from pathlib import Path

import duckdb
import requests

from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday

UDIFF_URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{yyyymmdd}_F_0000.csv.zip"
LEGACY_URL = "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{yyyy}/{mmm}/fo{dd}{mmm}{yyyy}bhav.csv.zip"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SOURCE_LEGACY = "NSE_FO_LEGACY"
SOURCE_UDIFF = "NSE_FO_UDIFF"
# Confirmed live, OPTIONS_HISTORICAL_FEASIBILITY.md -- identical boundary
# to the equity bhavcopy's own cutover (prices_nse.py), independently
# re-verified for F&O rather than assumed to match.
LEGACY_LAST_DATE = dt.date(2024, 7, 5)
UDIFF_FIRST_DATE = dt.date(2024, 1, 1)

RAW_TMP_DIR = Path(__file__).resolve().parents[2] / "data" / "options_history" / "_raw_tmp"

DB_COLUMNS = [
    "trade_date", "expiry_date", "strike", "option_type", "open", "high", "low", "close",
    "settle_price", "volume", "oi", "underlying_price", "contract_name", "source", "fetched_at",
]


class NoDataForDate(Exception):
    """404 from the archive -- a holiday, weekend, or a failed fetch. See
    module docstring: NOT assumed to mean "holiday" without checking."""


def format_for_date(trade_date: dt.date) -> str:
    return SOURCE_LEGACY if trade_date < UDIFF_FIRST_DATE else SOURCE_UDIFF


def _zip_path(trade_date: dt.date, source: str) -> Path:
    yyyymmdd = trade_date.strftime("%Y%m%d")
    prefix = "BhavCopy_NSE_FO_0_0_0" if source == SOURCE_UDIFF else "fo_legacy"
    return RAW_TMP_DIR / f"{prefix}_{yyyymmdd}.csv.zip"


def fetch_raw_zip(trade_date: dt.date, source: str | None = None, sleep_seconds: float = 0.8) -> tuple[Path, str]:
    """Downloads one day's whole-market F&O bhavcopy to RAW_TMP_DIR,
    returns (path, source_used). Caller is responsible for deleting the
    file once its extraction is verified -- this function never deletes
    anything itself."""
    source = source or format_for_date(trade_date)
    dest = _zip_path(trade_date, source)

    if source == SOURCE_UDIFF:
        url = UDIFF_URL.format(yyyymmdd=trade_date.strftime("%Y%m%d"))
    else:
        url = LEGACY_URL.format(
            yyyy=trade_date.strftime("%Y"), mmm=trade_date.strftime("%b").upper(), dd=trade_date.strftime("%d"),
        )

    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.nseindia.com/"}, timeout=30)
    time.sleep(sleep_seconds)
    if resp.status_code == 404:
        raise NoDataForDate(f"No F&O bhavcopy for {trade_date} via {source} (holiday, weekend, or fetch failure): {url}")
    resp.raise_for_status()
    RAW_TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest, source


def _parse_legacy(zip_path: Path, trade_date: dt.date) -> list[dict]:
    with zipfile.ZipFile(zip_path) as zf:
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        text = zf.read(name).decode("utf-8", errors="replace")
    rows = []
    for row in csv.DictReader(text.splitlines()):
        if row.get("INSTRUMENT") != "OPTIDX" or row.get("SYMBOL") != "NIFTY":
            continue
        rows.append({
            "trade_date": trade_date,
            "expiry_date": dt.datetime.strptime(row["EXPIRY_DT"], "%d-%b-%Y").date(),
            "strike": float(row["STRIKE_PR"]),
            "option_type": row["OPTION_TYP"],
            "open": float(row["OPEN"]), "high": float(row["HIGH"]), "low": float(row["LOW"]), "close": float(row["CLOSE"]),
            "settle_price": float(row["SETTLE_PR"]),
            "volume": int(float(row["CONTRACTS"])), "oi": int(float(row["OPEN_INT"])),
            "underlying_price": None,  # not carried in the legacy format
            "contract_name": f"NIFTY{row['EXPIRY_DT']}{row['STRIKE_PR']}{row['OPTION_TYP']}",
            "source": SOURCE_LEGACY, "fetched_at": dt.datetime.now(),
        })
    return rows


def _parse_udiff(zip_path: Path, trade_date: dt.date) -> list[dict]:
    with zipfile.ZipFile(zip_path) as zf:
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        text = zf.read(name).decode("utf-8", errors="replace")
    rows = []
    for row in csv.DictReader(text.splitlines()):
        if row.get("TckrSymb") != "NIFTY" or row.get("FinInstrmTp") != "IDO":
            continue
        underlying = row.get("UndrlygPric")
        rows.append({
            "trade_date": trade_date,
            "expiry_date": dt.datetime.strptime(row["XpryDt"], "%Y-%m-%d").date(),
            "strike": float(row["StrkPric"]),
            "option_type": row["OptnTp"],
            "open": float(row["OpnPric"]), "high": float(row["HghPric"]), "low": float(row["LwPric"]), "close": float(row["ClsPric"]),
            "settle_price": float(row["SttlmPric"]),
            "volume": int(float(row["TtlTradgVol"])), "oi": int(float(row["OpnIntrst"])),
            "underlying_price": float(underlying) if underlying not in (None, "") else None,
            "contract_name": row["FinInstrmNm"],
            "source": SOURCE_UDIFF, "fetched_at": dt.datetime.now(),
        })
    return rows


def parse_nifty_options(zip_path: Path, source: str, trade_date: dt.date) -> list[dict]:
    return _parse_udiff(zip_path, trade_date) if source == SOURCE_UDIFF else _parse_legacy(zip_path, trade_date)


def classify_404(trade_date: dt.date) -> str:
    """'no_data' iff data_layer.nse_holidays CONFIRMS trade_date is an
    NSE holiday; 'error' otherwise (including an unverifiable year --
    fails safe, Bug #15's exact convention, never assumes "not a
    holiday")."""
    try:
        return "no_data" if is_nse_holiday(trade_date) else "error"
    except HolidayCalendarMissing:
        return "error"
