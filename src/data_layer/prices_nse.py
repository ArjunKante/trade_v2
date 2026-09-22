"""NSE bhavcopy (UDiFF) fetcher and loader.

Format cutover, per NSE Circular No. 62424 (2024-06-12): the old CM bhavcopy
CSV was discontinued 2024-07-08; UDiFF has been available in parallel since
2024-06-21. Both legacy and UDiFF carry ISIN, which is the join key here —
NSE symbols get recycled across delisted/relisted companies over the years.

Rate limit: NSE has no published hard number for archive downloads, but 3
req/sec with 0.5-1s sleep between requests is the conservative convention
used by every open-source NSE client (jugaad-data, nsepy, nselib) and avoids
tripping the WAF that fronts nsearchives.nseindia.com.
"""
from __future__ import annotations

import datetime as dt
import io
import time
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import requests

UDIFF_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
LEGACY_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mmm}/cm{dd}{mmm}{yyyy}bhav.csv.zip"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SOURCE_UDIFF = "NSE_BHAVCOPY_UDIFF"
SOURCE_LEGACY = "NSE_BHAVCOPY_LEGACY"

# Verified live 2026-09-19 (bisection against real HTTP responses, matching the
# prior project's independently-documented findings in trade-info/DESIGN.md):
#   legacy: 200 through 2024-07-05, 404 from 2024-07-08 (2024-07-06/07 is a weekend)
#   UDiFF:  200 from 2024-01-01 (NSE backfilled UDiFF five+ months before its
#           nominal 2024-06-21 go-live), 404 on 2023-12-29
# Overlap window for cross-parser validation: 2024-01-01 through 2024-07-05.
LEGACY_LAST_DATE = dt.date(2024, 7, 5)
UDIFF_FIRST_DATE = dt.date(2024, 1, 1)

_UDIFF_COLUMN_MAP = {
    "TradDt": "trade_date",
    "ISIN": "isin",
    "TckrSymb": "symbol",
    "SctySrs": "series",
    "OpnPric": "open",
    "HghPric": "high",
    "LwPric": "low",
    "ClsPric": "close",
    "LastPric": "last",
    "PrvsClsgPric": "prev_close",
    "TtlTradgVol": "volume",
    "TtlTrfVal": "turnover",
    "TtlNbOfTxsExctd": "n_trades",
}

_LEGACY_COLUMN_MAP = {
    "TIMESTAMP": "trade_date",
    "ISIN": "isin",
    "SYMBOL": "symbol",
    "SERIES": "series",
    "OPEN": "open",
    "HIGH": "high",
    "LOW": "low",
    "CLOSE": "close",
    "LAST": "last",
    "PREVCLOSE": "prev_close",
    "TOTTRDQTY": "volume",
    "TOTTRDVAL": "turnover",
    "TOTALTRADES": "n_trades",
}

_TABLE_COLUMN_ORDER = [
    "isin", "trade_date", "symbol", "series", "open", "high", "low", "close",
    "last", "prev_close", "volume", "turnover", "n_trades", "known_date",
    "fetched_at", "source", "revision_seq",
]


def format_for_date(trade_date: dt.date) -> str:
    """Which bhavcopy format is authoritative for a given trading day.
    Both are real and fetchable in [2024-01-01, 2024-07-05]; UDiFF is
    preferred there since it's the format that will keep being published."""
    return SOURCE_LEGACY if trade_date < UDIFF_FIRST_DATE else SOURCE_UDIFF


class NoDataForDate(Exception):
    """404 from the archive: a holiday, weekend, or genuinely unpublished day."""


def _zip_dest_path(trade_date: dt.date, raw_dir: Path, source: str) -> Path:
    yyyymmdd = trade_date.strftime("%Y%m%d")
    prefix = "BhavCopy_NSE_CM_0_0_0" if source == SOURCE_UDIFF else "legacy_cm"
    return raw_dir / f"{prefix}_{yyyymmdd}.csv.zip"


def fetch_raw_zip(
    trade_date: dt.date, raw_dir: Path, source: str | None = None, sleep_seconds: float = 0.8
) -> tuple[Path, str]:
    """Download and cache the raw bhavcopy zip for one trading day. Returns (local_path, source_used)."""
    source = source or format_for_date(trade_date)
    dest = _zip_dest_path(trade_date, raw_dir, source)
    if dest.exists():
        return dest, source

    if source == SOURCE_UDIFF:
        url = UDIFF_URL.format(yyyymmdd=trade_date.strftime("%Y%m%d"))
    else:
        url = LEGACY_URL.format(
            yyyy=trade_date.strftime("%Y"),
            mmm=trade_date.strftime("%b").upper(),
            dd=trade_date.strftime("%d"),
        )

    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": "https://www.nseindia.com/"},
        timeout=30,
    )
    time.sleep(sleep_seconds)
    if resp.status_code == 404:
        raise NoDataForDate(f"No bhavcopy for {trade_date} via {source} (holiday or unpublished): {url}")
    resp.raise_for_status()
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest, source


class TradeDateMismatch(Exception):
    """The file's own embedded date field disagrees with the date we requested it for."""


def parse_bhavcopy_zip(
    zip_path: Path, source: str, expected_trade_date: dt.date, series_include: list[str] | None = None
) -> pd.DataFrame:
    """Parse a bhavcopy zip (either format) into the standard schema. CM equity segment only.

    trade_date is taken from expected_trade_date (the date we requested this file
    for), not parsed from the file's own embedded date column. Legacy files are
    inconsistent about that column's year format across the archive's history --
    real example found live: 2020-07-13's file uses "13-Jul-20" (2-digit year)
    while 2024-07-05's uses "05-JUL-2024" (4-digit) -- so trusting it as the
    source of truth means every legacy year needs its own format guess. Since
    a bhavcopy file is always for exactly one trading day, the date we asked
    for is already the authoritative value; the embedded column is only used
    as a loose cross-check that we got the right file back.
    """
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        raw = pd.read_csv(io.BytesIO(zf.read(csv_name)))

    if source == SOURCE_UDIFF:
        raw = raw[raw["Sgmt"] == "CM"].copy()
        col_map = _UDIFF_COLUMN_MAP
    else:
        col_map = _LEGACY_COLUMN_MAP

    if series_include:
        series_col = "SctySrs" if source == SOURCE_UDIFF else "SERIES"
        raw = raw[raw[series_col].isin(series_include)].copy()

    # loose cross-check against the file's own date field before discarding it
    raw_date_col = raw.rename(columns=col_map)["trade_date"]
    sample = pd.to_datetime(raw_date_col.iloc[0], format="mixed", dayfirst=False).date()
    if sample.month != expected_trade_date.month or sample.day != expected_trade_date.day:
        raise TradeDateMismatch(
            f"requested {expected_trade_date} but file's own date field reads {sample} (day/month differ)"
        )

    df = raw.rename(columns=col_map)[list(col_map.values())].copy()
    df["trade_date"] = expected_trade_date
    df["known_date"] = df["trade_date"]  # published EOD on trade_date; usable from trade_date+1 by convention
    df["fetched_at"] = dt.datetime.now()
    df["source"] = source
    df["revision_seq"] = 1
    return df[_TABLE_COLUMN_ORDER]


def _log_fetch(con: duckdb.DuckDBPyConnection, source: str, trade_date: dt.date, status: str, rows: int) -> None:
    con.execute(
        "DELETE FROM fetch_log WHERE source = ? AND trade_date = ?", [source, trade_date]
    )
    con.execute(
        "INSERT INTO fetch_log VALUES (?, ?, ?, ?, ?)",
        [source, trade_date, status, rows, dt.datetime.now()],
    )


def load_bhavcopy_to_duckdb(
    con: duckdb.DuckDBPyConnection,
    trade_date: dt.date,
    raw_dir: Path,
    series_include: list[str] | None = None,
    source: str | None = None,
) -> int:
    """Fetch+parse+load one trading day. Idempotent: skips if already loaded for that
    trade_date, and records every attempt (including holidays/errors) in fetch_log so
    a resumed backfill never re-requests a day it already resolved."""
    source = source or format_for_date(trade_date)
    already = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [source, trade_date]
    ).fetchone()
    if already and already[0] in ("ok", "no_data"):
        return 0

    try:
        zip_path, used_source = fetch_raw_zip(trade_date, raw_dir, source=source)
    except NoDataForDate:
        _log_fetch(con, source, trade_date, "no_data", 0)
        return 0

    df = parse_bhavcopy_zip(zip_path, used_source, trade_date, series_include=series_include)
    existing = con.execute(
        "SELECT COUNT(*) FROM prices_eod WHERE trade_date = ? AND source = ?", [trade_date, used_source]
    ).fetchone()[0]
    if existing:
        _log_fetch(con, source, trade_date, "ok", 0)
        return 0
    con.register("df_new", df)
    con.execute("INSERT INTO prices_eod SELECT * FROM df_new")
    con.unregister("df_new")
    _log_fetch(con, source, trade_date, "ok", len(df))
    return len(df)


def backfill_range(
    con: duckdb.DuckDBPyConnection,
    start: dt.date,
    end: dt.date,
    raw_dir: Path,
    series_include: list[str] | None = None,
    progress_every: int = 50,
) -> dict:
    """Resumable day-by-day backfill over [start, end], weekdays only. Safe to
    interrupt and re-run: fetch_log means every already-resolved day is skipped
    without a network call."""
    stats = {"ok": 0, "no_data": 0, "skipped_already_logged": 0, "total_rows": 0}
    d = start
    n_processed = 0
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri; weekends 404 anyway but this saves the request
            source = format_for_date(d)
            already = con.execute(
                "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [source, d]
            ).fetchone()
            if already and already[0] in ("ok", "no_data"):
                stats["skipped_already_logged"] += 1
            else:
                rows = load_bhavcopy_to_duckdb(con, d, raw_dir, series_include=series_include, source=source)
                status = con.execute(
                    "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [source, d]
                ).fetchone()[0]
                stats[status] = stats.get(status, 0) + 1
                stats["total_rows"] += rows
                n_processed += 1
                if n_processed % progress_every == 0:
                    print(f"backfill progress: {d} done ({stats})", flush=True)
        d += dt.timedelta(days=1)
    return stats
