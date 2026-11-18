"""Fetch NSE's official CM-segment trading-holiday calendar for one year
and merge it into data_layer.nse_holidays' two sources -- the single
highest-value script this project was missing going into the
2026-12/2027-01 unattended window (OPERATIONS.md's "2027 NSE holiday
master" entry; PROJECT_CONTEXT.md Section 2's calendar-uncertain
momentum check-in). ONE COMMAND, no Claude Code required:

    python scripts/fetch_nse_holiday_calendar.py --year 2027

Proof run against a year that already exists and is trusted (writes
nothing):

    python scripts/fetch_nse_holiday_calendar.py --year 2026 --dry-run

SAFE BY CONSTRUCTION, not just by convention:
- An EMPTY response (NSE has not published that year's circular yet --
  the live, confirmed state for 2027 as of 2026-11-19: `year=2027`
  returns HTTP 200 with zero CM-segment entries, not an error) is a
  hard refusal, never written as a "zero holidays that year" calendar
  -- which would be far worse than the current HolidayCalendarMissing
  state: a confirmed-wrong "not a holiday" for every single day of
  that year, silently.
- Overwriting a year ALREADY present in either stored source requires
  `--force`, after the diff is printed -- this project's one source of
  truth for "is X a trading day" does not get silently replaced by a
  re-run.
- `--dry-run` writes nothing; it still reports whether the fresh fetch
  matches an already-stored year byte-for-byte, which is how this
  script is verified against 2026 in OPERATIONS_UNATTENDED.md.
- Never fabricates or guesses a date -- see data_layer.nse_holidays'
  own docstring for why that is a standing project rule, not a
  preference.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HOLIDAYS_PKL = ROOT / "data" / "raw" / "nse_cm_holidays.pkl"
HOLIDAYS_FALLBACK_JSON = ROOT / "data" / "raw" / "nse_cm_holidays_fallback.json"

HOME_URL = "https://www.nseindia.com/"
API_URL = "https://www.nseindia.com/api/holiday-master"
# Same User-Agent/warm-up-then-GET pattern data_layer.corporate_actions.
# fetch_raw_actions already uses against the same host -- nseindia.com
# rejects a bare, cookie-less request to the API directly.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class HolidayCalendarNotPublished(Exception):
    """Raised when NSE's API returns zero CM-segment holidays for the
    requested year -- the real, live behavior for an unpublished year
    (confirmed 2026-11-19 for 2027: `year=2027` returns an empty CM
    list, HTTP 200, not an error status). Never written as a
    "zero holidays" year -- see this module's own docstring."""


def fetch_cm_holidays(year: int) -> dict[dt.date, str]:
    """{date: description} for NSE's CM (equity Capital Market) segment
    only -- the same segment data_layer.nse_holidays.is_nse_holiday
    exists to confirm against. NSE's holiday-master response also
    carries CBM/CD/CMOT/COM/EGR/FO/IRD/MF/NDM/NTRP/SLBS segments
    (confirmed live, 2026-11-19); none of those are this project's
    concern."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    s.get(HOME_URL, timeout=30)
    time.sleep(0.8)
    resp = s.get(
        API_URL,
        params={"type": "trading", "year": str(year)},
        headers={"Accept": "application/json", "Referer": HOME_URL},
        timeout=30,
    )
    resp.raise_for_status()
    cm = resp.json().get("CM", [])
    if not cm:
        raise HolidayCalendarNotPublished(
            f"NSE's holiday-master API returned zero CM-segment entries for {year} "
            f"(HTTP {resp.status_code}). This means NSE has not published {year}'s "
            f"trading-holiday circular yet -- NOT that {year} genuinely has no "
            f"holidays. Nothing written; re-run this same command later (NSE "
            f"typically publishes the following year's circular in December)."
        )
    out: dict[dt.date, str] = {}
    for row in cm:
        d = dt.datetime.strptime(row["tradingDate"], "%d-%b-%Y").date()
        if d.year != year:
            continue  # defensive -- not observed live, never trusted silently either way
        out[d] = row.get("description", "")
    return out


def _load_pkl() -> dict[int, set[dt.date]]:
    if HOLIDAYS_PKL.exists():
        with open(HOLIDAYS_PKL, "rb") as f:
            return pickle.load(f)
    return {}


def _load_fallback() -> dict[int, set[dt.date]]:
    if HOLIDAYS_FALLBACK_JSON.exists():
        raw = json.loads(HOLIDAYS_FALLBACK_JSON.read_text(encoding="utf-8"))
        return {int(y): {dt.date.fromisoformat(s) for s in dates} for y, dates in raw.items()}
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="fetch and report only; write nothing")
    parser.add_argument("--force", action="store_true",
                         help="overwrite an already-stored year even if it differs from the fresh fetch")
    args = parser.parse_args()

    print(f"Fetching NSE's CM-segment trading-holiday calendar for {args.year}...")
    try:
        fetched = fetch_cm_holidays(args.year)
    except HolidayCalendarNotPublished as e:
        print(f"REFUSING TO WRITE: {e}")
        sys.exit(1)

    fetched_dates = set(fetched)
    print(f"Fetched {len(fetched_dates)} holiday(s) for {args.year}:")
    for d in sorted(fetched_dates):
        print(f"  {d}  {fetched[d]}")

    pkl_cal = _load_pkl()
    fallback_cal = _load_fallback()
    stored = pkl_cal.get(args.year)
    if stored is None:
        stored = fallback_cal.get(args.year)

    if stored is not None:
        added = fetched_dates - stored
        removed = stored - fetched_dates
        if added or removed:
            print(f"\nDIFFERS from the already-stored {args.year} calendar:")
            if added:
                print(f"  added:   {sorted(added)}")
            if removed:
                print(f"  removed: {sorted(removed)}")
            if not args.force:
                print(f"\nABORTING without writing -- pass --force to overwrite the stored "
                      f"{args.year} calendar with this fresh fetch anyway.")
                sys.exit(1)
        else:
            print(f"\nMATCHES the already-stored {args.year} calendar exactly ({len(stored)} dates) -- "
                  f"this fetch is confirmed correct against known-trusted data.")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    pkl_cal[args.year] = fetched_dates
    HOLIDAYS_PKL.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLIDAYS_PKL, "wb") as f:
        pickle.dump(pkl_cal, f)
    print(f"\nWrote {HOLIDAYS_PKL} ({len(pkl_cal)} year(s) total: {sorted(pkl_cal.keys())}).")

    fallback_cal[args.year] = fetched_dates
    fallback_out = {str(y): sorted(d.isoformat() for d in dates) for y, dates in fallback_cal.items()}
    HOLIDAYS_FALLBACK_JSON.write_text(json.dumps(fallback_out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {HOLIDAYS_FALLBACK_JSON} ({len(fallback_cal)} year(s) total: {sorted(fallback_cal.keys())}).")

    print(f"\nNEXT STEPS:")
    print(f"1. data_layer.nse_holidays._load() is lru_cache'd -- any ALREADY-RUNNING process "
          f"(a Streamlit research_app.py session, a long-lived job) will not see this update "
          f"until it restarts.")
    print(f"2. Commit the fallback JSON -- it is the one path this project's .gitignore carves "
          f"out, so a GitHub Actions runner's fresh checkout gets it too:")
    print(f"   git add data/raw/nse_cm_holidays_fallback.json")
    print(f'   git commit -m "Load {args.year} NSE holiday calendar"')


if __name__ == "__main__":
    main()
