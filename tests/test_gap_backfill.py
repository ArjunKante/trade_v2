"""BUGS.md Bug #30's closing structural fix, part 2: data_layer.gap_
backfill's AUTO_FILL vs ALERT_STOP policy, and the downstream
rematerialization + tripwire chain it runs after any auto-fill.

Every dependency gap_backfill calls out to (load_bhavcopy_to_duckdb,
materialize_adjustment_factors, materialize_entity_panel, both tripwire
asserts, find_missing_trading_days) is monkeypatched on the gap_backfill
module itself -- these tests are about the POLICY and WIRING, not a
re-test of any of those functions' own behavior (each has its own
coverage elsewhere). No real warehouse, network, or filesystem touched
(WINDOW_FILL_AUDIT_LOG is redirected to tmp_path in every test that can
reach it).

The blocking set is DERIVED from each SealedWindow's own
result_recorded_at field (user instruction, 2026-11-18: "the rule is 'a
window blocks once it has a recorded result,' not a fixed list of
dates"), not hardcoded per-window branches -- test_generic_derivation_*
below proves classify_gap treats a synthetic, newly-recorded window the
same way it treats the real one, with no code change needed.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_layer import gap_backfill as gb  # noqa: E402
from data_layer.margin_tripwire import FrozenTableResumedError, HoldoutWindowPriceRevisionError  # noqa: E402
from data_layer.price_gap_detector import REASON_MISSING, MissingTradingDay  # noqa: E402

TODAY = dt.date(2026, 11, 18)


@pytest.fixture(autouse=True)
def _redirect_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(gb, "WINDOW_FILL_AUDIT_LOG", tmp_path / "window_fill_audit_log.txt")


# --------------------------------------------------------------------------
# classify_gap
# --------------------------------------------------------------------------

def test_recent_ordinary_gap_is_auto_filled():
    d = gb.classify_gap(dt.date(2026, 11, 10), as_of=TODAY)  # 8 days old
    assert d.action == gb.ACTION_AUTO_FILL


def test_gap_exactly_at_the_age_boundary_is_auto_filled():
    boundary = TODAY - dt.timedelta(days=gb.RECENT_GAP_MAX_AGE_DAYS)
    d = gb.classify_gap(boundary, as_of=TODAY)
    assert d.action == gb.ACTION_AUTO_FILL


def test_gap_one_day_past_the_age_boundary_is_alert_stop():
    too_old = TODAY - dt.timedelta(days=gb.RECENT_GAP_MAX_AGE_DAYS + 1)
    d = gb.classify_gap(too_old, as_of=TODAY)
    assert d.action == gb.ACTION_ALERT_STOP
    assert d.why == gb.REASON_TOO_OLD


def test_gap_inside_the_first_sealed_holdout_window_is_alert_stop_even_if_recent():
    """This window HAS a recorded result (3.50) -- must block regardless
    of age. Pins `as_of` close to the window so the date would otherwise
    pass the age check."""
    inside = gb.HOLDOUT_WINDOW_START + dt.timedelta(days=5)
    d = gb.classify_gap(inside, as_of=inside + dt.timedelta(days=3))
    assert d.action == gb.ACTION_ALERT_STOP
    assert "first sealed holdout" in d.why


def test_gap_inside_the_open_second_window_is_auto_filled_not_blocked():
    """The real, current state: MOMENTUM_WINDOW_2 has no recorded result
    yet, so a recent gap inside it is an ordinary operational miss, same
    as any other -- NOT blocked just because of its date. This is the
    real policy actually in force today (2026-11-18); see this module's
    own docstring for why an earlier design that blocked this
    unconditionally made auto-fill unreachable forever."""
    inside = gb.MOMENTUM_WINDOW_2_START + dt.timedelta(days=2)
    d = gb.classify_gap(inside, as_of=inside + dt.timedelta(days=3))
    assert d.action == gb.ACTION_AUTO_FILL


def test_generic_derivation_a_synthetic_window_with_a_recorded_result_blocks(monkeypatch):
    """Proves the blocking set is DERIVED from result_recorded_at, not a
    hardcoded list naming specific windows: a brand-new synthetic window
    with a recorded result blocks, with zero changes to classify_gap."""
    synthetic = gb.SealedWindow(
        name="synthetic test window", start=dt.date(2030, 1, 1), end=dt.date(2030, 6, 30),
        result_recorded_at=dt.datetime(2030, 7, 1),
    )
    monkeypatch.setattr(gb, "SEALED_WINDOWS", gb.SEALED_WINDOWS + [synthetic])
    d = gb.classify_gap(dt.date(2030, 3, 1), as_of=dt.date(2030, 3, 5))
    assert d.action == gb.ACTION_ALERT_STOP
    assert d.why == "synthetic test window"


def test_generic_derivation_a_synthetic_window_without_a_recorded_result_does_not_block(monkeypatch):
    synthetic = gb.SealedWindow(
        name="synthetic open window", start=dt.date(2030, 1, 1), end=None, result_recorded_at=None,
    )
    monkeypatch.setattr(gb, "SEALED_WINDOWS", gb.SEALED_WINDOWS + [synthetic])
    d = gb.classify_gap(dt.date(2030, 3, 1), as_of=dt.date(2030, 3, 5))
    assert d.action == gb.ACTION_AUTO_FILL


# --------------------------------------------------------------------------
# run_gap_check_and_autofill
# --------------------------------------------------------------------------

class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))


def _patch_chain(monkeypatch, missing, tripwire_a_raises=None, tripwire_b_raises=None):
    monkeypatch.setattr(gb, "find_missing_trading_days", lambda con: missing)
    load_calls = []
    monkeypatch.setattr(gb, "load_bhavcopy_to_duckdb",
                         lambda con, d, raw_dir, series_include=None: (load_calls.append(d), 100)[1])
    materialize_af = _Recorder()
    materialize_ep = _Recorder()
    monkeypatch.setattr(gb, "materialize_adjustment_factors", materialize_af)
    monkeypatch.setattr(gb, "materialize_entity_panel", materialize_ep)

    def _assert_a(con):
        if tripwire_a_raises:
            raise tripwire_a_raises("in-window revision")

    def _assert_b(con):
        if tripwire_b_raises:
            raise tripwire_b_raises("feed resumed")

    monkeypatch.setattr(gb, "assert_no_in_window_price_revision", _assert_a)
    monkeypatch.setattr(gb, "assert_corporate_actions_and_lineage_still_frozen", _assert_b)
    return load_calls, materialize_af, materialize_ep


def test_no_gaps_found_does_nothing(monkeypatch):
    load_calls, materialize_af, materialize_ep = _patch_chain(monkeypatch, [])
    result = gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)
    assert result == {"auto_filled": [], "alert": [], "rows_loaded": 0}
    assert load_calls == []
    assert materialize_af.calls == []


def test_recent_gap_is_filled_and_downstream_chain_rebuilt(monkeypatch):
    recent = TODAY - dt.timedelta(days=5)
    load_calls, materialize_af, materialize_ep = _patch_chain(
        monkeypatch, [MissingTradingDay(recent, REASON_MISSING)]
    )
    logged = []
    result = gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=logged.append)
    assert load_calls == [recent]
    assert len(materialize_af.calls) == 1
    assert len(materialize_ep.calls) == 1
    assert result["auto_filled"] == [recent]
    assert result["rows_loaded"] == 100
    assert any("margin tripwire passed" in m for m in logged)


def test_old_gap_alone_raises_and_fills_nothing(monkeypatch):
    old = TODAY - dt.timedelta(days=90)
    load_calls, materialize_af, materialize_ep = _patch_chain(
        monkeypatch, [MissingTradingDay(old, REASON_MISSING)]
    )
    with pytest.raises(gb.GapRequiresHumanDecisionError):
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)
    assert load_calls == []
    assert materialize_af.calls == []


def test_gap_inside_the_recorded_window_alone_raises_and_fills_nothing(monkeypatch):
    sealed = gb.HOLDOUT_WINDOW_START + dt.timedelta(days=1)
    load_calls, materialize_af, materialize_ep = _patch_chain(
        monkeypatch, [MissingTradingDay(sealed, REASON_MISSING)]
    )
    with pytest.raises(gb.GapRequiresHumanDecisionError):
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=sealed + dt.timedelta(days=2), log=print)
    assert load_calls == []


def test_mixed_gaps_fills_the_easy_one_then_raises_for_the_hard_one(monkeypatch):
    """A recent, fillable gap must not be held hostage by an unrelated
    old/sealed gap elsewhere in history -- it gets filled first, and the
    exception for the other one is raised only after."""
    recent = TODAY - dt.timedelta(days=2)
    old = TODAY - dt.timedelta(days=400)
    load_calls, materialize_af, materialize_ep = _patch_chain(
        monkeypatch, [MissingTradingDay(recent, REASON_MISSING), MissingTradingDay(old, REASON_MISSING)]
    )
    with pytest.raises(gb.GapRequiresHumanDecisionError) as exc_info:
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)
    assert load_calls == [recent]  # the recent one WAS filled
    assert len(materialize_af.calls) == 1  # downstream chain WAS rebuilt for it
    assert old.isoformat() in str(exc_info.value)
    assert recent.isoformat() not in str(exc_info.value)  # only the unresolved one is named


@pytest.mark.parametrize("error_cls", [HoldoutWindowPriceRevisionError, FrozenTableResumedError])
def test_tripwire_failure_after_autofill_raises_tripwire_failed_error(monkeypatch, error_cls):
    recent = TODAY - dt.timedelta(days=3)
    kwargs = {"tripwire_a_raises": error_cls} if error_cls is HoldoutWindowPriceRevisionError \
        else {"tripwire_b_raises": error_cls}
    _patch_chain(monkeypatch, [MissingTradingDay(recent, REASON_MISSING)], **kwargs)
    with pytest.raises(gb.TripwireFailedAfterBackfillError):
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)


# --------------------------------------------------------------------------
# Audit trail for a fill inside the open (not-yet-recorded) second window
# --------------------------------------------------------------------------

def test_fill_inside_the_open_window_is_audit_logged(monkeypatch):
    inside = gb.MOMENTUM_WINDOW_2_START + dt.timedelta(days=1)
    _patch_chain(monkeypatch, [MissingTradingDay(inside, REASON_MISSING)])
    logged = []
    gb.run_gap_check_and_autofill(
        con=None, raw_dir=Path("."), as_of=inside + dt.timedelta(days=1), log=logged.append
    )
    assert gb.WINDOW_FILL_AUDIT_LOG.exists()
    content = gb.WINDOW_FILL_AUDIT_LOG.read_text(encoding="utf-8")
    assert inside.isoformat() in content
    assert "second sealed momentum window" in content
    assert "100 rows" in content  # row count only
    assert any("audit-logged" in m for m in logged)


def test_fill_outside_any_window_is_not_audit_logged(monkeypatch):
    as_of = dt.date(2026, 9, 1)  # well before MOMENTUM_WINDOW_2_START (2026-10-23)
    ordinary = as_of - dt.timedelta(days=5)
    _patch_chain(monkeypatch, [MissingTradingDay(ordinary, REASON_MISSING)])
    gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=as_of, log=print)
    assert not gb.WINDOW_FILL_AUDIT_LOG.exists()


def test_audit_log_entry_carries_no_price_or_entity_data(monkeypatch):
    """Dates and row counts only -- the exact guarantee this module's
    docstring states. A regression that started interpolating a price,
    symbol, or entity_id into the audit line would show up here as an
    unexpected token."""
    inside = gb.MOMENTUM_WINDOW_2_START + dt.timedelta(days=1)
    _patch_chain(monkeypatch, [MissingTradingDay(inside, REASON_MISSING)])
    gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=inside + dt.timedelta(days=1), log=print)
    content = gb.WINDOW_FILL_AUDIT_LOG.read_text(encoding="utf-8")
    for forbidden in ("close", "ISIN", "entity_id", "symbol", "RELIANCE"):
        assert forbidden not in content
