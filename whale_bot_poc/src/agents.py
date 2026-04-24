"""Three independent scoring agents.

Each agent returns a signal in {-1, 0, +1} for a given market observation:
    +1 = enter YES
    -1 = enter NO
     0 = no opinion

They are deterministic by design so the POC is reproducible without an LLM
in the loop. The `Signal` dataclass carries an "expected_move" estimate that
the exit policy uses to decide when to take profit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mock_data import Market


@dataclass
class Observation:
    market: Market
    t: int
    whale_positions: dict[str, str]  # wallet -> side ("YES"/"NO") if active


@dataclass
class Signal:
    direction: int  # -1, 0, +1
    confidence: float  # 0..1
    expected_move: float  # absolute price delta the agent expects from entry
    rationale: str


def _price_window(market: Market, t: int, lookback: int = 8) -> list[float]:
    start = max(0, t - lookback)
    return market.price_path[start : t + 1]


def arbitrage_agent(obs: Observation) -> Signal:
    """Fade extreme short-term moves, betting on mean reversion.

    If the 8-step return is large and price is off the 50/50 line, take the
    opposite side. Expected move is the drift back toward the window mean.
    """
    w = _price_window(obs.market, obs.t)
    if len(w) < 4:
        return Signal(0, 0.0, 0.0, "not enough history")
    ret = w[-1] - w[0]
    mean = sum(w) / len(w)
    if abs(ret) < 0.06:
        return Signal(0, 0.0, 0.0, "no dislocation")
    direction = -1 if ret > 0 else 1
    expected = abs(mean - w[-1]) + 0.02
    return Signal(direction, min(1.0, abs(ret) * 6), expected, f"fade {ret:+.3f}")


def convergence_agent(obs: Observation) -> Signal:
    """Trend-follow: once a market commits above 0.6 or below 0.4, push it.

    Expected move is the distance to the nearer resolution edge.
    """
    w = _price_window(obs.market, obs.t, lookback=12)
    if len(w) < 6:
        return Signal(0, 0.0, 0.0, "not enough history")
    price = w[-1]
    slope = (w[-1] - w[0]) / len(w)
    if price > 0.60 and slope > 0:
        return Signal(+1, min(1.0, (price - 0.5) * 2), 1.0 - price, "committed YES")
    if price < 0.40 and slope < 0:
        return Signal(-1, min(1.0, (0.5 - price) * 2), price, "committed NO")
    return Signal(0, 0.0, 0.0, "uncommitted")


def whale_copy_agent(obs: Observation) -> Signal:
    """Vote with the whales currently positioned on this market.

    If 2+ whales sit on the same side, follow them. Expected move is a
    conservative 0.15 — the post's "73% of max, cut at 85%" heuristic only
    needs a direction and a ballpark.
    """
    if not obs.whale_positions:
        return Signal(0, 0.0, 0.0, "no whales active")
    yes = sum(1 for s in obs.whale_positions.values() if s == "YES")
    no = sum(1 for s in obs.whale_positions.values() if s == "NO")
    if yes >= 2 and yes > no:
        return Signal(+1, min(1.0, yes / 5), 0.15, f"{yes} whales long YES")
    if no >= 2 and no > yes:
        return Signal(-1, min(1.0, no / 5), 0.15, f"{no} whales long NO")
    return Signal(0, 0.0, 0.0, "no whale consensus")


ALL_AGENTS = (arbitrage_agent, convergence_agent, whale_copy_agent)
