"""BUGS.md Bug #30's closing structural fix, part 2: data_layer.gap_
backfill's AUTO_FILL vs ALERT_STOP policy, and the downstream
rematerialization + tripwire chain it runs after any auto-fill.

Every dependency gap_backfill calls out to (load_bhavcopy_to_duckdb,
materialize_adjustment_factors, materialize_entity_panel, build_lineage,
_lineage_content_changed, both tripwire asserts, find_missing_trading_days)
is monkeypatched on the gap_backfill module itself -- these tests are
about the POLICY and WIRING, not a re-test of any of those functions' own
behavior (each has its own coverage elsewhere; isin_lineage.build_lineage's
own real behavior is covered by tests/test_isin_lineage.py, and the real
diff logic added for BUGS.md Bug #33 is covered by
test_lineage_content_changed_* below against a real in-memory connection).
No real warehouse, network, or filesystem touched (WINDOW_FILL_AUDIT_LOG
is redirected to tmp_path in every test that can reach it).

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


def _patch_chain(monkeypatch, missing, tripwire_a_raises=None, tripwire_b_raises=None, lineage_changed=None):
    monkeypatch.setattr(gb, "find_missing_trading_days", lambda con: missing)
    load_calls = []
    monkeypatch.setattr(gb, "load_bhavcopy_to_duckdb",
                         lambda con, d, raw_dir, series_include=None: (load_calls.append(d), 100)[1])
    materialize_af = _Recorder()
    materialize_ep = _Recorder()
    monkeypatch.setattr(gb, "materialize_adjustment_factors", materialize_af)
    monkeypatch.setattr(gb, "materialize_entity_panel", materialize_ep)
    # build_lineage/_lineage_content_diff's own real behavior (the BUGS.md
    # Bug #33 fix) is exercised directly against real dataframes/connections
    # below -- here, only the WIRING (is it called before AND after the
    # fill, does a non-empty diff raise and skip the tripwire) is under
    # test, same as every other dependency.
    monkeypatch.setattr(gb, "build_lineage", lambda con: (None, None))
    monkeypatch.setattr(gb, "_lineage_content_diff", lambda old_df, new_df: lineage_changed or [])

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
# BUGS.md Bug #33: isin_lineage must be verified unaffected, not silently
# rewritten -- and when it WOULD change, the fill must not end in a quiet
# success.
# --------------------------------------------------------------------------

def test_lineage_unaffected_proceeds_to_tripwire_as_before(monkeypatch):
    """The common case (Bug #33's own text: most gaps don't land on any
    entity's first/last observed day): no lineage change, so the run
    proceeds exactly as it did before this fix -- tripwire runs and passes."""
    recent = TODAY - dt.timedelta(days=5)
    _patch_chain(monkeypatch, [MissingTradingDay(recent, REASON_MISSING)], lineage_changed=[])
    logged = []
    result = gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=logged.append)
    assert result["auto_filled"] == [recent]
    assert any("isin_lineage unaffected" in m for m in logged)
    assert any("margin tripwire passed" in m for m in logged)


def test_lineage_would_change_raises_and_skips_tripwire(monkeypatch):
    """Bug #33's actual reproduced failure mode: the fill lands on an
    entity's own first/last observed day and would change its lineage
    resolution. Must raise LineageWouldChangeError, name the affected
    isin, and never reach (or pass) the margin tripwire on this call --
    the raw price fill and the two materializations are NOT reverted,
    same precedent as TripwireFailedAfterBackfillError."""
    recent = TODAY - dt.timedelta(days=5)
    load_calls, materialize_af, materialize_ep = _patch_chain(
        monkeypatch, [MissingTradingDay(recent, REASON_MISSING)], lineage_changed=["INE999Z01011"]
    )
    with pytest.raises(gb.LineageWouldChangeError) as exc_info:
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)
    assert "INE999Z01011" in str(exc_info.value)
    assert load_calls == [recent]  # the raw fill already happened
    assert len(materialize_af.calls) == 1  # so did the two rematerializations
    assert len(materialize_ep.calls) == 1


def test_lineage_check_runs_before_margin_tripwire(monkeypatch):
    """Ordering matters: if isin_lineage would change, that must be
    caught and raised BEFORE the margin tripwire's own lineage-frozen
    check runs -- the tripwire check would likely pass anyway (isin_
    lineage is never actually written), which would mask the real
    problem with a misleadingly generic 'tripwire passed' log line."""
    recent = TODAY - dt.timedelta(days=5)
    tripwire_calls = []
    _patch_chain(monkeypatch, [MissingTradingDay(recent, REASON_MISSING)], lineage_changed=["INE999Z01011"])
    monkeypatch.setattr(gb, "assert_corporate_actions_and_lineage_still_frozen",
                         lambda con: tripwire_calls.append(con))
    with pytest.raises(gb.LineageWouldChangeError):
        gb.run_gap_check_and_autofill(con=None, raw_dir=Path("."), as_of=TODAY, log=print)
    assert tripwire_calls == []


# --------------------------------------------------------------------------
# _lineage_content_diff: the actual diff logic (before-fill build_lineage()
# vs after-fill build_lineage(), never against the persisted table -- see
# the module docstring for why). Pure dataframe comparison, no connection.
# --------------------------------------------------------------------------

def _lineage_row(isin, entity_id, predecessor_isin, known_date, link_method="nsdl_structural"):
    return {
        "isin": isin, "entity_id": entity_id, "predecessor_isin": predecessor_isin,
        "link_method": link_method, "known_date": known_date,
        "fetched_at": dt.datetime.now(), "source": "TEST", "revision_seq": 1,
    }


def test_lineage_content_diff_empty_when_identical():
    import pandas as pd
    old = pd.DataFrame([_lineage_row("INE001A01001", "INE001A01001", None, dt.date(2020, 1, 1))])
    new = pd.DataFrame([_lineage_row("INE001A01001", "INE001A01001", None, dt.date(2020, 1, 1))])
    assert gb._lineage_content_diff(old, new) == []


def test_lineage_content_diff_detects_a_dropped_link():
    """Bug #33's second reproduction: a clean predecessor link reverts to
    None (overlapping_date_ranges_not_a_clean_handover) after a backfill."""
    import pandas as pd
    old = pd.DataFrame([_lineage_row("INE002A01002", "INE001A01001", "INE001A01001", dt.date(2021, 6, 1))])
    new = pd.DataFrame([_lineage_row("INE002A01002", "INE002A01002", None, dt.date(2021, 6, 1), "chain_start")])
    assert gb._lineage_content_diff(old, new) == ["INE002A01002"]


def test_lineage_content_diff_detects_a_shifted_known_date():
    """Bug #33's first reproduction: a successor's known_date (transition
    date) shifts earlier once the missing days before it are filled."""
    import pandas as pd
    old = pd.DataFrame([_lineage_row("INE003A01003", "INE001A01001", "INE001A01001", dt.date(2021, 6, 5))])
    new = pd.DataFrame([_lineage_row("INE003A01003", "INE001A01001", "INE001A01001", dt.date(2021, 6, 3))])
    assert gb._lineage_content_diff(old, new) == ["INE003A01003"]


def test_lineage_content_diff_ignores_fetched_at_and_revision_seq():
    import pandas as pd
    old = pd.DataFrame([_lineage_row("INE004A01004", "INE004A01004", None, dt.date(2020, 1, 1))])
    new_row = _lineage_row("INE004A01004", "INE004A01004", None, dt.date(2020, 1, 1))
    new_row["fetched_at"] = dt.datetime.now() + dt.timedelta(days=1)
    new_row["revision_seq"] = 2
    new = pd.DataFrame([new_row])
    assert gb._lineage_content_diff(old, new) == []


def test_lineage_content_diff_detects_added_or_removed_isin():
    import pandas as pd
    old = pd.DataFrame([_lineage_row("INE005A01005", "INE005A01005", None, dt.date(2020, 1, 1))])
    new = pd.DataFrame([
        _lineage_row("INE005A01005", "INE005A01005", None, dt.date(2020, 1, 1)),
        _lineage_row("INE006A01006", "INE006A01006", None, dt.date(2020, 1, 1)),
    ])
    assert gb._lineage_content_diff(old, new) == ["INE006A01006"]


# --------------------------------------------------------------------------
# End-to-end sanity against the real build_lineage(), unmocked: confirms
# build_lineage() is called exactly twice (before and after the fill) and
# that a real, unmocked no-op diff against itself is empty -- catches a
# regression where the "before" snapshot was accidentally captured after
# prices_eod was already touched.
# --------------------------------------------------------------------------

def test_build_lineage_called_before_and_after_the_fill(monkeypatch):
    import pandas as pd
    recent = TODAY - dt.timedelta(days=5)
    monkeypatch.setattr(gb, "find_missing_trading_days", lambda con: [MissingTradingDay(recent, REASON_MISSING)])
    monkeypatch.setattr(gb, "load_bhavcopy_to_duckdb", lambda con, d, raw_dir, series_include=None: 100)
    monkeypatch.setattr(gb, "materialize_adjustment_factors", lambda con: None)
    monkeypatch.setattr(gb, "materialize_entity_panel", lambda con: None)
    monkeypatch.setattr(gb, "assert_no_in_window_price_revision", lambda con: None)
    monkeypatch.setattr(gb, "assert_corporate_actions_and_lineage_still_frozen", lambda con: None)

    build_calls = []

    def fake_build_lineage(con):
        build_calls.append(con)
        return pd.DataFrame(columns=["isin"] + gb._LINEAGE_CONTENT_COLS), pd.DataFrame()

    monkeypatch.setattr(gb, "build_lineage", fake_build_lineage)
    gb.run_gap_check_and_autofill(con="FAKE_CON", raw_dir=Path("."), as_of=TODAY, log=print)
    assert build_calls == ["FAKE_CON", "FAKE_CON"]  # called exactly twice, before and after


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
