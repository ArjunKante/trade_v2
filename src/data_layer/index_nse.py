"""NSE's own daily all-indices close file -- real Nifty 50 level history,
needed for beta. Same domain (nsearchives.nseindia.com), same NSE data usage
terms already assessed in Phase 1; not the bot-protected index-constituent
API the prior project hit, just a plain daily CSV archive like bhavcopy.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import duckdb
import pandas as pd
import requests

URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SOURCE_NAME = "NSE_INDEX_CLOSE_ALL"


class NoDataForDate(Exception):
    pass


def fetch_and_parse(trade_date: dt.date, raw_dir: Path, sleep_seconds: float = 0.8) -> pd.DataFrame:
    dest = raw_dir / f"ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"
    if not dest.exists():
        url = URL.format(ddmmyyyy=trade_date.strftime("%d%m%Y"))
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.nseindia.com/"}, timeout=30)
        time.sleep(sleep_seconds)
        if resp.status_code == 404:
            raise NoDataForDate(f"no index file for {trade_date}")
        resp.raise_for_status()
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)

    raw = pd.read_csv(dest)
    raw.columns = [c.strip() for c in raw.columns]
    return raw


def load_index_day(con: duckdb.DuckDBPyConnection, trade_date: dt.date, raw_dir: Path) -> int:
    already = con.execute(
        "SELECT status FROM fetch_log WHERE source = ? AND trade_date = ?", [SOURCE_NAME, trade_date]
    ).fetchone()
    if already and already[0] in ("ok", "no_data"):
        return 0
    try:
        raw = fetch_and_parse(trade_date, raw_dir)
    except NoDataForDate:
        con.execute("DELETE FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_NAME, trade_date])
        con.execute("INSERT INTO fetch_log VALUES (?, ?, 'no_data', 0, ?)", [SOURCE_NAME, trade_date, dt.datetime.now()])
        return 0

    row = raw[raw["Index Name"] == "Nifty 50"]
    if row.empty:
        con.execute("DELETE FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_NAME, trade_date])
        con.execute("INSERT INTO fetch_log VALUES (?, ?, 'no_data', 0, ?)", [SOURCE_NAME, trade_date, dt.datetime.now()])
        return 0

    r = row.iloc[0]
    now = dt.datetime.now()
    con.execute(
        "INSERT INTO index_eod VALUES ('NIFTY50', ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        [trade_date, float(r["Open Index Value"]), float(r["High Index Value"]),
         float(r["Low Index Value"]), float(r["Closing Index Value"]), trade_date, now, SOURCE_NAME],
    )
    con.execute("DELETE FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_NAME, trade_date])
    con.execute("INSERT INTO fetch_log VALUES (?, ?, 'ok', 1, ?)", [SOURCE_NAME, trade_date, now])
    return 1


def backfill_index_range(con: duckdb.DuckDBPyConnection, start: dt.date, end: dt.date, raw_dir: Path) -> dict:
    stats = {"ok": 0, "no_data": 0}
    d = start
    while d <= end:
        if d.weekday() < 5:
            already = con.execute(
                "SELECT status FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_NAME, d]
            ).fetchone()
            if not (already and already[0] in ("ok", "no_data")):
                n = load_index_day(con, d, raw_dir)
                status = con.execute(
                    "SELECT status FROM fetch_log WHERE source=? AND trade_date=?", [SOURCE_NAME, d]
                ).fetchone()[0]
                stats[status] = stats.get(status, 0) + 1
        d += dt.timedelta(days=1)
    return stats
