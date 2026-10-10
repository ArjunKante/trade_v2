"""ONE-OFF LIVE TEST, run once during NSE market hours (per OPTIONS_FEASIBILITY.md's
'Status' section) -- NOT part of any build. Answers exactly one question: does
Angel One's getMarketData(mode="FULL", ...) -- the same call
scripts/snapshot_spreads.py already uses for equities -- return bid/ask depth
for a LIVE (not expired) NFO option contract?

This bears only on whether a FORWARD collector could be built starting now.
It cannot change OPTIONS_FEASIBILITY.md's verdict (BLOCKED -- INSUFFICIENT
DATA for retroactive/historical coverage), which depends on a separate,
already-confirmed fact (Angel's scrip master carries zero expired option
contracts) that this script does not re-test.

Places no order, computes no signal, touches no Fibo/swing/momentum result.
Writes its result to scripts/test_options_depth_result.txt and never prints
or logs any credential (reuses src/fibo/auth.login, the one hardened login
path in this project).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fibo.auth import login

ANGEL_SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
RESULT_PATH = ROOT / "scripts" / "test_options_depth_result.txt"


def log(lines: list[str]) -> None:
    text = "\n".join(lines)
    print(text, flush=True)
    RESULT_PATH.write_text(text + "\n", encoding="utf-8")


def pick_live_nifty_option() -> dict:
    master = requests.get(ANGEL_SCRIP_MASTER_URL, timeout=60).json()
    nifty_opts = [r for r in master if r.get("exch_seg") == "NFO" and r.get("instrumenttype") == "OPTIDX"
                  and r.get("name") == "NIFTY"]
    if not nifty_opts:
        raise RuntimeError("No live NIFTY option instruments found in today's scrip master.")
    nifty_opts.sort(key=lambda r: r["expiry"])
    nearest_expiry = nifty_opts[0]["expiry"]
    candidates = [r for r in nifty_opts if r["expiry"] == nearest_expiry]
    # pick the strike closest to a round 25000 as a liquid, representative near-the-money contract
    return sorted(candidates, key=lambda r: abs(float(r["strike"]) / 100 - 25000))[0]


def main() -> int:
    out = [f"=== Options depth test, run at {dt.datetime.now().isoformat()} ==="]

    contract = pick_live_nifty_option()
    out.append(f"Contract: {contract['symbol']} token={contract['token']} "
               f"expiry={contract['expiry']} strike={contract['strike']}")

    result = login()
    out.append(f"Login status: {result.ok} {result.status}")
    if not result.ok:
        log(out)
        return 1

    resp = result.client.getMarketData("FULL", {"NFO": [contract["token"]]})
    out.append(f"API status: {resp.get('status') if isinstance(resp, dict) else resp}")
    out.append(f"API message/errorcode: {resp.get('message')} / {resp.get('errorcode')}")

    data = (resp.get("data") or {}) if isinstance(resp, dict) else {}
    fetched = data.get("fetched") or []
    unfetched = data.get("unfetched") or []
    out.append(f"fetched: {len(fetched)}, unfetched: {len(unfetched)} ({unfetched})")

    if fetched:
        row = fetched[0]
        out.append("Top-level fields returned: " + ", ".join(sorted(row.keys())))
        depth = row.get("depth")
        out.append(f"'depth' field present: {depth is not None}")
        if depth:
            buy = depth.get("buy") or []
            sell = depth.get("sell") or []
            out.append(f"depth.buy entries: {len(buy)}, depth.sell entries: {len(sell)}")
            if buy:
                out.append(f"depth.buy[0] fields: {sorted(buy[0].keys())}")
            if sell:
                out.append(f"depth.sell[0] fields: {sorted(sell[0].keys())}")
            out.append(f"Best bid: {buy[0] if buy else None}")
            out.append(f"Best ask: {sell[0] if sell else None}")
        out.append(f"ltp: {row.get('ltp')}  open: {row.get('open')}")
        out.append("FULL RAW ROW (for audit, no credentials present in this payload): " + json.dumps(row))

    verdict = "YES - depth (bid/ask) present" if fetched and fetched[0].get("depth") and (
        (fetched[0]["depth"].get("buy") or []) or (fetched[0]["depth"].get("sell") or [])
    ) else "NO - no usable bid/ask depth returned"
    out.append(f"\nVERDICT: {verdict}")

    log(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
