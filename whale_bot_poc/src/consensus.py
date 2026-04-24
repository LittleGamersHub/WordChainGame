"""Consensus filter.

Rules from the post:
    - 2 of 3 agree   -> full size
    - 1 signal alone -> half size
    - disagreement   -> no trade
"""

from __future__ import annotations

from dataclasses import dataclass

from .agents import Signal


@dataclass
class Decision:
    direction: int  # -1, 0, +1
    size_mult: float  # 0, 0.5, or 1.0
    expected_move: float
    votes: tuple[int, int, int]
    reasons: tuple[str, str, str]


def combine(signals: tuple[Signal, Signal, Signal]) -> Decision:
    votes = tuple(s.direction for s in signals)
    reasons = tuple(s.rationale for s in signals)
    pos = sum(1 for v in votes if v == +1)
    neg = sum(1 for v in votes if v == -1)

    # Disagreement: any long and any short among the active voters.
    if pos > 0 and neg > 0:
        return Decision(0, 0.0, 0.0, votes, reasons)

    active = [s for s in signals if s.direction != 0]
    if not active:
        return Decision(0, 0.0, 0.0, votes, reasons)

    direction = active[0].direction
    exp_move = sum(s.expected_move for s in active) / len(active)

    if len(active) >= 2:
        return Decision(direction, 1.0, exp_move, votes, reasons)
    return Decision(direction, 0.5, exp_move, votes, reasons)
