"""Exit policy.

"Cut at 85% of the expected move. Or a 3x volume spike. Whichever comes first."

Also exits at resolution. A hard stop at -50% of expected_move keeps losers
from running unbounded.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mock_data import Market


@dataclass
class OpenPosition:
    market_id: str
    direction: int  # +1 YES, -1 NO
    entry_price: float
    size_usd: float
    t_enter: int
    expected_move: float
    entry_volume: float


@dataclass
class ExitDecision:
    should_exit: bool
    reason: str


def should_exit(pos: OpenPosition, market: Market, t: int) -> ExitDecision:
    if t >= len(market.price_path) - 1:
        return ExitDecision(True, "resolved")

    price = market.price_path[t]
    move = (price - pos.entry_price) * pos.direction

    if pos.expected_move > 0 and move >= 0.85 * pos.expected_move:
        return ExitDecision(True, "take-profit 85% of expected move")

    if pos.expected_move > 0 and move <= -0.50 * pos.expected_move:
        return ExitDecision(True, "hard stop -50% of expected move")

    vol = market.volume_path[t]
    if pos.entry_volume > 0 and vol >= 3.0 * pos.entry_volume:
        return ExitDecision(True, "3x volume spike")

    return ExitDecision(False, "hold")
