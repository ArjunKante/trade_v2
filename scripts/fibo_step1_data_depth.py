"""Step 1 of the Fibo module build: report how far back Angel One SmartAPI's
1-minute and 15-minute historical bars actually go for 3 sample stocks (one
large, two mid-liquidity, from src/fibo/universe.py's 2026 top-50-by-
turnover ranking), the real max-candles-per-request behavior, and the
observed rate limit. DIAGNOSTIC ONLY -- downloads nothing to storage.

METHODOLOGY, found live during this run (not assumed from docs) -- TWO
CORRECTIONS recorded here because both were wrong on the first attempt:

1. A request with a date range far exceeding the true limit does NOT
   error -- it silently returns a TRUNCATED response anchored to
   `todate` (confirmed: identical output for 800/1600/3200-day windows
   ending on the same date). An earlier version of this script walked
   backward in large (640-day) chunks assuming each chunk's full
   requested range came back; it did not, leaving ~600-day gaps between
   chunks unprobed. Fixed by using small (10-day) windows everywhere below
   -- always under the truncation threshold, so a request either returns
   its full window or is genuinely empty.
2. A first small-window binary search (bounded at "search ceiling 4000
   days ago") reported "no boundary found" for every symbol -- but a
   direct manual probe at 2016-01-15 (well inside that range) came back
   EMPTY while the binary search's own days-ago arithmetic had claimed
   data existed there. The actual bug: the search's upper bound (4000
   days ago from 'now') landed past the true boundary, but the search
   only ever tested has_data(4000) once and treated True as "goes back at
   least this far" without the intermediate steps being checked against
   real calendar dates. Fixed by re-deriving the bracket directly in
   calendar-date terms (verified empty at 2015-08-10, verified populated
   at 2017-01-15 for RELIANCE) and binary-searching between those
   CONFIRMED, not assumed, endpoints for every symbol/interval.

Reuses fibo.auth.login()'s single authenticated (and logger-neutralized)
client for every call -- never constructs a second SmartConnect, so the
credential-safety neutralization (see fibo/auth.py) covers every call here.
"""
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo.auth import login, _redact

THROTTLE_SECONDS = 0.4
RATE_LIMIT_KEYWORDS = ("rate", "too many", "exceed", "access denied", "throttl")
PROBE_WINDOW_DAYS = 10
BRACKET_EMPTY = dt.date(2015, 8, 10)   # confirmed empty for RELIANCE/ONE_MINUTE below
BRACKET_HAS_DATA = dt.date(2017, 1, 15)  # confirmed populated for RELIANCE/ONE_MINUTE below

SYMBOLS = [
    ("RELIANCE", 2885, "large"),
    ("INDIGO", 11195, "mid-liquidity (rank 25/50, 2026 universe)"),
    ("MCX", 31181, "mid-liquidity (rank 40/50, 2026 universe)"),
]
INTERVALS = ["ONE_MINUTE", "FIFTEEN_MINUTE"]

rate_limit_events = []
request_log = []


def _looks_rate_limited(msg: str) -> bool:
    low = (msg or "").lower()
    return any(k in low for k in RATE_LIMIT_KEYWORDS)


def has_data(client, token, interval, target_date, window_days=PROBE_WINDOW_DAYS, context=""):
    to = dt.datetime.combine(target_date, dt.time(15, 30))
    frm = to - dt.timedelta(days=window_days)
    params = {"exchange": "NSE", "symboltoken": str(token), "interval": interval,
              "fromdate": frm.strftime("%Y-%m-%d %H:%M"), "todate": to.strftime("%Y-%m-%d %H:%M")}
    request_log.append(dt.datetime.now())
    try:
        resp = client.getCandleData(params)
    except Exception as e:
        err = _redact(f"{type(e).__name__}: {e}")
        if _looks_rate_limited(err):
            rate_limit_events.append((dt.datetime.now(), context))
        time.sleep(THROTTLE_SECONDS)
        return False
    ok = isinstance(resp, dict) and resp.get("status") is True and bool(resp.get("data"))
    if not ok and _looks_rate_limited(str(resp.get("message") if isinstance(resp, dict) else resp)):
        rate_limit_events.append((dt.datetime.now(), context))
    time.sleep(THROTTLE_SECONDS)
    return ok


def measure_truncation(client, token, interval):
    to = dt.datetime.now()
    frm = to - dt.timedelta(days=3000)
    params = {"exchange": "NSE", "symboltoken": str(token), "interval": interval,
              "fromdate": frm.strftime("%Y-%m-%d %H:%M"), "todate": to.strftime("%Y-%m-%d %H:%M")}
    request_log.append(dt.datetime.now())
    resp = client.getCandleData(params)
    time.sleep(THROTTLE_SECONDS)
    data = resp.get("data") or []
    if not data:
        return None
    first = dt.datetime.fromisoformat(data[0][0])
    last = dt.datetime.fromisoformat(data[-1][0])
    return {"n_candles": len(data), "span_days": (last - first).days, "first": data[0][0], "last": data[-1][0]}


def find_boundary(client, token, interval, symbol):
    lo, hi = BRACKET_EMPTY, BRACKET_HAS_DATA
    n_req = 0
    # verify the shared bracket actually holds for THIS symbol/interval before trusting it
    if has_data(client, token, interval, lo, context=f"{symbol}/{interval} bracket check"):
        return None, f"bracket assumption wrong: data already present at {lo} -- needs a wider search", 1
    n_req += 1
    if not has_data(client, token, interval, hi, context=f"{symbol}/{interval} bracket check"):
        return None, f"bracket assumption wrong: still empty at {hi} -- needs a wider search", 2
    n_req += 2

    while (hi - lo).days > 3:
        mid = lo + (hi - lo) // 2
        if has_data(client, token, interval, mid, context=f"{symbol}/{interval} binary search"):
            hi = mid
        else:
            lo = mid
        n_req += 1
    return (lo, hi), f"empty at {lo}, has data at {hi}", n_req


def main():
    result = login()
    if not result.ok:
        print(f"LOGIN FAILED: {result.status}")
        return
    client = result.client
    print("login OK\n", flush=True)

    print("=== Per-request truncation (measured, not assumed) ===", flush=True)
    for interval in INTERVALS:
        info = measure_truncation(client, 2885, interval)
        if info:
            print(f"{interval}: an oversized (3000-day) request silently returns only {info['n_candles']} "
                  f"candles, spanning {info['span_days']} calendar days ending at 'todate' "
                  f"({info['first']} .. {info['last']}) -- NOT an error, a silent truncation.", flush=True)

    print("\n=== Earliest available data per symbol (10-day-window binary search, immune to truncation) ===", flush=True)
    total_requests = 2 * len(INTERVALS)
    for symbol, token, tag in SYMBOLS:
        for interval in INTERVALS:
            bounds, detail, n_req = find_boundary(client, token, interval, symbol)
            total_requests += n_req
            if bounds:
                lo, hi = bounds
                print(f"{symbol} ({tag}) / {interval}: earliest usable data ~{hi} ({detail})", flush=True)
            else:
                print(f"{symbol} ({tag}) / {interval}: {detail}", flush=True)

    print(f"\n=== Summary ===", flush=True)
    print(f"Total historical-data requests this run: {total_requests}", flush=True)
    if len(request_log) >= 2:
        gaps = [(b - a).total_seconds() for a, b in zip(request_log, request_log[1:])]
        print(f"Observed inter-request gap: min={min(gaps):.2f}s, mean={sum(gaps)/len(gaps):.2f}s "
              f"(includes {THROTTLE_SECONDS}s throttle + API round-trip).", flush=True)
    if rate_limit_events:
        print(f"Rate-limit-shaped errors observed: {len(rate_limit_events)}", flush=True)
        for when, ctx in rate_limit_events:
            print(f"  {when.strftime('%H:%M:%S')} during {ctx}", flush=True)
    else:
        print(f"No rate-limit error observed at ~{THROTTLE_SECONDS}s/request over {total_requests} requests.", flush=True)


if __name__ == "__main__":
    main()
