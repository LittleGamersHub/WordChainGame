from whale_bot_poc.src.exit_policy import OpenPosition, should_exit
from whale_bot_poc.src.mock_data import Market


def _mkt(prices, volumes):
    return Market(
        market_id="m",
        question="q",
        resolution=1,
        price_path=prices,
        volume_path=volumes,
    )


def test_takes_profit_at_85pct_of_expected_move():
    pos = OpenPosition(
        market_id="m",
        direction=+1,
        entry_price=0.50,
        size_usd=100.0,
        t_enter=0,
        expected_move=0.10,
        entry_volume=1_000.0,
    )
    # +0.09 clears the 85% threshold (0.085); +0.05 does not.
    mkt = _mkt([0.50, 0.55, 0.59, 0.60], [1_000, 1_000, 1_000, 1_000])
    assert should_exit(pos, mkt, 1).should_exit is False
    assert should_exit(pos, mkt, 2).should_exit is True


def test_triggers_hard_stop_on_adverse_move():
    pos = OpenPosition(
        market_id="m",
        direction=+1,
        entry_price=0.50,
        size_usd=100.0,
        t_enter=0,
        expected_move=0.10,
        entry_volume=1_000.0,
    )
    mkt = _mkt([0.50, 0.48, 0.44, 0.40], [1_000, 1_000, 1_000, 1_000])
    decision = should_exit(pos, mkt, 2)
    assert decision.should_exit is True
    assert "hard stop" in decision.reason


def test_triggers_on_volume_spike():
    pos = OpenPosition(
        market_id="m",
        direction=+1,
        entry_price=0.50,
        size_usd=100.0,
        t_enter=0,
        expected_move=0.50,  # big target so price alone won't trigger
        entry_volume=1_000.0,
    )
    mkt = _mkt([0.50, 0.51, 0.52, 0.53], [1_000, 1_500, 3_100, 3_500])
    assert should_exit(pos, mkt, 1).should_exit is False
    assert should_exit(pos, mkt, 2).should_exit is True


def test_force_exits_at_resolution():
    pos = OpenPosition(
        market_id="m",
        direction=+1,
        entry_price=0.50,
        size_usd=100.0,
        t_enter=0,
        expected_move=0.50,
        entry_volume=1_000.0,
    )
    mkt = _mkt([0.50, 0.51, 1.00], [1_000, 1_000, 1_000])
    assert should_exit(pos, mkt, 2).should_exit is True
