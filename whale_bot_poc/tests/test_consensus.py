from whale_bot_poc.src.agents import Signal
from whale_bot_poc.src.consensus import combine


def _s(direction, expected_move=0.1, conf=0.5, why=""):
    return Signal(direction=direction, confidence=conf, expected_move=expected_move, rationale=why)


def test_two_of_three_agree_is_full_size():
    d = combine((_s(+1), _s(+1), _s(0)))
    assert d.direction == +1
    assert d.size_mult == 1.0


def test_all_three_agree_is_full_size():
    d = combine((_s(-1), _s(-1), _s(-1)))
    assert d.direction == -1
    assert d.size_mult == 1.0


def test_single_voter_is_half_size():
    d = combine((_s(+1), _s(0), _s(0)))
    assert d.direction == +1
    assert d.size_mult == 0.5


def test_disagreement_skips_trade():
    d = combine((_s(+1), _s(-1), _s(0)))
    assert d.direction == 0
    assert d.size_mult == 0.0


def test_all_neutral_skips_trade():
    d = combine((_s(0), _s(0), _s(0)))
    assert d.direction == 0
    assert d.size_mult == 0.0


def test_expected_move_averages_active_agents():
    d = combine((_s(+1, 0.2), _s(+1, 0.4), _s(0)))
    assert abs(d.expected_move - 0.3) < 1e-9
