"""src/fibo_live/outcomes.py: the 100-trade gate, and the LIVE/REPLAY split
required at evaluation. Every test writes to its own tmp_path log file --
never the real data/fibo_live/v1/events.jsonl -- via record_outcome's and
evaluate's log_path override.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fibo_live.clock import LIVE, REPLAY
from fibo_live.config import SEALED_AMENDED_MEAN_NET_R
from fibo_live.outcomes import record_outcome, evaluate


def _log_trade(log_path, i, run_mode, entry=100.0, stop=95.0, exit_price=110.0):
    record_outcome(
        entity_id=f"E{i}", symbol=f"SYM{i}", trade_date=dt.date(2026, 10, 1), rank=10,
        triggered=True, run_mode=run_mode, entry_ts=dt.datetime(2026, 10, 1, 10, 0),
        entry_price=entry, stop=stop, target=120.0, qty=100,
        exit_ts=dt.datetime(2026, 10, 1, 15, 15), exit_price=exit_price, exit_reason="TARGET",
        log_path=log_path,
    )


def test_below_min_trades_shows_count_only(tmp_path):
    log_path = tmp_path / "events.jsonl"
    for i in range(5):
        _log_trade(log_path, i, LIVE)
    result = evaluate(log_path=log_path)
    assert result == {"n_completed": 5, "evaluated": False, "min_trades": 100}


def test_untriggered_outcomes_do_not_count_toward_the_gate(tmp_path):
    log_path = tmp_path / "events.jsonl"
    for i in range(100):
        _log_trade(log_path, i, LIVE)
    for i in range(50):
        record_outcome(entity_id=f"N{i}", symbol=f"NOTRIG{i}", trade_date=dt.date(2026, 10, 1),
                        rank=10, triggered=False, run_mode=LIVE, log_path=log_path)
    result = evaluate(log_path=log_path)
    assert result["n_completed"] == 100
    assert result["evaluated"] is True


def test_combined_live_replay_breakdown_reported_separately(tmp_path):
    log_path = tmp_path / "events.jsonl"
    # 60 LIVE trades, same R each; 40 REPLAY trades, a different (much
    # lower) R each -- deliberately different so the split is visible.
    for i in range(60):
        _log_trade(log_path, i, LIVE, entry=100.0, stop=95.0, exit_price=110.0)
    for i in range(60, 100):
        _log_trade(log_path, i, REPLAY, entry=100.0, stop=95.0, exit_price=101.0)

    result = evaluate(log_path=log_path)
    assert result["evaluated"] is True
    assert result["n_completed"] == 100
    assert result["live"]["n"] == 60
    assert result["replay"]["n"] == 40
    # LIVE's gross move is bigger than REPLAY's -> LIVE mean net R > REPLAY mean net R
    assert result["live"]["mean_net_r"] > result["replay"]["mean_net_r"]
    assert result["combined"]["n"] == 100
    assert result["live_vs_replay_diff"] is not None
    assert result["material_difference"] is True  # the gap here is deliberately large


def test_no_material_difference_when_live_and_replay_are_close(tmp_path):
    log_path = tmp_path / "events.jsonl"
    for i in range(50):
        _log_trade(log_path, i, LIVE, entry=100.0, stop=95.0, exit_price=110.0)
    for i in range(50, 100):
        _log_trade(log_path, i, REPLAY, entry=100.0, stop=95.0, exit_price=110.0)

    result = evaluate(log_path=log_path)
    assert result["material_difference"] is False
    assert abs(result["live_vs_replay_diff"]) < 1e-9


def test_combined_mean_matches_the_old_top_level_fields(tmp_path):
    """Backward compatibility: mean_net_r/t_stat/diff_vs_sealed at the top
    level must equal the combined sub-dict's own values."""
    log_path = tmp_path / "events.jsonl"
    for i in range(100):
        # vary the exit price so net R isn't identical across trades --
        # otherwise variance is exactly 0 and t_stat is NaN, which breaks
        # equality comparison (NaN != NaN) without actually testing anything.
        _log_trade(log_path, i, LIVE if i % 2 == 0 else REPLAY, exit_price=108.0 + (i % 7))
    result = evaluate(log_path=log_path)
    assert result["mean_net_r"] == result["combined"]["mean_net_r"]
    assert result["t_stat"] == result["combined"]["t_stat"]
    assert not (result["t_stat"] is None)
    assert result["diff_vs_sealed"] == result["combined"]["mean_net_r"] - SEALED_AMENDED_MEAN_NET_R
