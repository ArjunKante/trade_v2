"""scripts/fibo_valid_observation_days.py's compute() -- the frozen
definition behind FIBO_FINDINGS.md Section 14's running counter. Tests
the definition directly against a synthetic events.jsonl, including the
exact edge case that motivated the "within the entry window" clause: a
LIVE setup event that exists but was logged outside 09:30-11:30 must NOT
count (the real AXISBANK 2026-10-19 case, discovered 3.5 hours late).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fibo_valid_observation_days as vod  # noqa: E402


def _write_events(path: Path, *events: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _watchlist_run(target_trade_date: str) -> dict:
    return {"kind": "watchlist_run", "target_trade_date": target_trade_date}


def _setup(trade_date: str, ts: str, run_mode: str = "LIVE") -> dict:
    return {"kind": "setup", "trade_date": trade_date, "ts": ts, "run_mode": run_mode}


def test_both_conditions_met_counts_as_valid(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    _write_events(
        log_path,
        _watchlist_run("2026-10-12"),
        _setup("2026-10-12", "2026-10-12T09:35:00"),
    )
    monkeypatch.setattr(vod, "EVENTS_LOG", log_path)
    monkeypatch.setattr(vod, "is_nse_holiday", lambda d: False)

    result = vod.compute(dt.date(2026, 10, 12), dt.date(2026, 10, 12))
    assert result["n_valid"] == 1
    assert result["rows"][0]["valid_observation_day"] is True


def test_setup_outside_entry_window_does_not_count(tmp_path, monkeypatch):
    """The literal AXISBANK 2026-10-19 case: SETUP_ON logged 14:59, 3.5
    hours after the 09:30-11:30 window closed -- must not count."""
    log_path = tmp_path / "events.jsonl"
    _write_events(
        log_path,
        _watchlist_run("2026-10-19"),
        _setup("2026-10-19", "2026-10-19T14:59:12"),
    )
    monkeypatch.setattr(vod, "EVENTS_LOG", log_path)
    monkeypatch.setattr(vod, "is_nse_holiday", lambda d: False)

    result = vod.compute(dt.date(2026, 10, 19), dt.date(2026, 10, 19))
    assert result["n_valid"] == 0
    row = result["rows"][0]
    assert row["evening_watchlist"] is True
    assert row["morning_in_window"] is False


def test_replay_setup_does_not_count_even_inside_window(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    _write_events(
        log_path,
        _watchlist_run("2026-10-20"),
        _setup("2026-10-20", "2026-10-20T10:00:00", run_mode="REPLAY"),
    )
    monkeypatch.setattr(vod, "EVENTS_LOG", log_path)
    monkeypatch.setattr(vod, "is_nse_holiday", lambda d: False)

    result = vod.compute(dt.date(2026, 10, 20), dt.date(2026, 10, 20))
    assert result["n_valid"] == 0


def test_no_evening_watchlist_does_not_count_even_with_in_window_morning(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    _write_events(
        log_path,
        _setup("2026-10-21", "2026-10-21T10:00:00"),
    )
    monkeypatch.setattr(vod, "EVENTS_LOG", log_path)
    monkeypatch.setattr(vod, "is_nse_holiday", lambda d: False)

    result = vod.compute(dt.date(2026, 10, 21), dt.date(2026, 10, 21))
    assert result["n_valid"] == 0
    assert result["rows"][0]["evening_watchlist"] is False


def test_weekend_and_holiday_excluded_from_denominator_entirely(tmp_path, monkeypatch):
    log_path = tmp_path / "events.jsonl"
    _write_events(log_path)  # no events at all
    monkeypatch.setattr(vod, "EVENTS_LOG", log_path)

    # 2026-10-17 Sat, 2026-10-18 Sun, 2026-10-20 a confirmed holiday
    monkeypatch.setattr(vod, "is_nse_holiday", lambda d: d == dt.date(2026, 10, 20))

    result = vod.compute(dt.date(2026, 10, 17), dt.date(2026, 10, 20))
    dates = [r["date"] for r in result["rows"]]
    assert dates == ["2026-10-19"]  # only the ordinary Monday remains
    assert result["n_trading_days"] == 1
