"""src/data_layer/nse_holidays.py: prefers the full local pkl
(data/raw/nse_cm_holidays.pkl, never committed) when present, falls back
to the trimmed, committed JSON (data/raw/nse_cm_holidays_fallback.json)
when it isn't -- the situation a GitHub Actions runner's fresh checkout
is actually in. Every test monkeypatches both module-level paths and
clears the lru_cache so tests never depend on, or pollute, whatever
pkl/json actually exists on the machine running them.
"""
import datetime as dt
import json
import pickle
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer import nse_holidays  # noqa: E402
from data_layer.nse_holidays import HolidayCalendarMissing, is_nse_holiday  # noqa: E402

REAL_FALLBACK_JSON = Path(__file__).resolve().parents[1] / "data" / "raw" / "nse_cm_holidays_fallback.json"


@pytest.fixture(autouse=True)
def _clear_cache():
    nse_holidays._load.cache_clear()
    yield
    nse_holidays._load.cache_clear()


def _write_pkl(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(data, f)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_raises_when_neither_pkl_nor_fallback_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_PKL", tmp_path / "missing.pkl")
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_FALLBACK_JSON", tmp_path / "missing.json")
    with pytest.raises(HolidayCalendarMissing):
        is_nse_holiday(dt.date(2026, 10, 20))


def test_uses_the_fallback_json_when_the_pkl_is_absent(tmp_path, monkeypatch):
    """THE scenario this fallback exists for: a GitHub Actions runner's
    fresh checkout, which never has the pkl."""
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_PKL", tmp_path / "missing.pkl")
    fallback_path = tmp_path / "fallback.json"
    _write_json(fallback_path, {"2026": ["2026-10-20"]})
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_FALLBACK_JSON", fallback_path)

    assert is_nse_holiday(dt.date(2026, 10, 20)) is True
    assert is_nse_holiday(dt.date(2026, 10, 19)) is False


def test_prefers_the_pkl_over_the_fallback_when_both_exist(tmp_path, monkeypatch):
    """The pkl is the laptop's own source of truth (more years, the
    actual origin the fallback was trimmed from) -- it wins if present,
    even if the fallback disagrees (it shouldn't in practice, but the
    precedence itself is what's being tested here)."""
    pkl_path = tmp_path / "real.pkl"
    _write_pkl(pkl_path, {2026: {dt.date(2026, 10, 20)}})
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_PKL", pkl_path)

    fallback_path = tmp_path / "fallback.json"
    _write_json(fallback_path, {"2026": []})  # deliberately disagrees
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_FALLBACK_JSON", fallback_path)

    assert is_nse_holiday(dt.date(2026, 10, 20)) is True


def test_fallback_raises_for_an_uncovered_year(tmp_path, monkeypatch):
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_PKL", tmp_path / "missing.pkl")
    fallback_path = tmp_path / "fallback.json"
    _write_json(fallback_path, {"2026": ["2026-10-20"]})
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_FALLBACK_JSON", fallback_path)

    with pytest.raises(HolidayCalendarMissing):
        is_nse_holiday(dt.date(2027, 1, 1))


def test_the_real_committed_fallback_resolves_a_known_holiday_on_the_runner_path(monkeypatch):
    """The actual file this project now ships, exercised exactly as a
    GitHub Actions runner would see it (no pkl at all) -- confirms
    2026-10-20 (Diwali-period NSE holiday, confirmed live against the
    laptop's own pkl while building this fallback) resolves correctly,
    and an ordinary trading day does not."""
    assert REAL_FALLBACK_JSON.exists(), "data/raw/nse_cm_holidays_fallback.json must be committed"
    monkeypatch.setattr(nse_holidays, "HOLIDAYS_PKL", Path("does-not-exist.pkl"))

    assert is_nse_holiday(dt.date(2026, 10, 20)) is True
    assert is_nse_holiday(dt.date(2026, 10, 19)) is False


def test_fallback_json_contains_no_price_data():
    """Sanity check on the committed file's own shape: every value under
    every year must be a plain ISO date string, nothing else -- no OHLC
    fields, no symbol/price keys could have snuck in."""
    raw = json.loads(REAL_FALLBACK_JSON.read_text(encoding="utf-8"))
    assert raw, "fallback calendar must not be empty"
    for year, dates in raw.items():
        assert year.isdigit()
        for value in dates:
            assert isinstance(value, str)
            dt.date.fromisoformat(value)  # raises ValueError if it's anything but a plain date string
