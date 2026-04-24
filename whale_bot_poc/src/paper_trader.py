"""Paper trader.

Walks forward through every market's price path. At each step it asks the
three agents for signals, runs them through consensus, opens positions at
full or half size, and exits per exit_policy. Tracks cash, trades, and PnL.

No network, no keys, no exchange. Pure simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agents import ALL_AGENTS, Observation
from .consensus import combine
from .exit_policy import OpenPosition, should_exit
from .mock_data import Market, Wallet


@dataclass
class ClosedTrade:
    market_id: str
    direction: int
    entry_price: float
    exit_price: float
    size_usd: float
    pnl: float
    reason: str
    t_enter: int
    t_exit: int

    @property
    def won(self) -> bool:
        return self.pnl > 0


@dataclass
class Portfolio:
    starting_cash: float
    cash: float
    base_size: float
    closed: list[ClosedTrade] = field(default_factory=list)
    open_positions: dict[str, OpenPosition] = field(default_factory=dict)

    @property
    def pnl(self) -> float:
        return sum(t.pnl for t in self.closed)

    @property
    def win_rate(self) -> float:
        if not self.closed:
            return 0.0
        return sum(1 for t in self.closed if t.won) / len(self.closed)


def _whale_positions_at(
    whales: list[Wallet],
    market_id: str,
    t: int,
) -> dict[str, str]:
    """Whales whose trade window covers timestamp t on this market."""
    out: dict[str, str] = {}
    for w in whales:
        for tr in w.trades:
            if tr.market_id == market_id and tr.t_enter <= t <= tr.t_exit:
                out[w.address] = tr.side
                break
    return out


def _pnl(direction: int, entry: float, exit_price: float, size_usd: float) -> float:
    shares = size_usd / entry if entry > 0 else 0.0
    if direction == +1:
        return shares * (exit_price - entry)
    return shares * (entry - exit_price)


def run(
    markets: list[Market],
    whales: list[Wallet],
    starting_cash: float = 600.0,
    base_size: float = 50.0,
    min_confidence: float = 0.0,
) -> Portfolio:
    port = Portfolio(starting_cash=starting_cash, cash=starting_cash, base_size=base_size)

    path_len = len(markets[0].price_path)
    for t in range(path_len):
        # Close anything that triggers an exit first.
        for mid, pos in list(port.open_positions.items()):
            mkt = next(m for m in markets if m.market_id == mid)
            decision = should_exit(pos, mkt, t)
            if decision.should_exit:
                exit_price = mkt.price_path[t]
                pnl = _pnl(pos.direction, pos.entry_price, exit_price, pos.size_usd)
                port.cash += pos.size_usd + pnl
                port.closed.append(
                    ClosedTrade(
                        market_id=mid,
                        direction=pos.direction,
                        entry_price=pos.entry_price,
                        exit_price=exit_price,
                        size_usd=pos.size_usd,
                        pnl=pnl,
                        reason=decision.reason,
                        t_enter=pos.t_enter,
                        t_exit=t,
                    )
                )
                del port.open_positions[mid]

        # Then look for new entries.
        for mkt in markets:
            if mkt.market_id in port.open_positions:
                continue
            whales_here = _whale_positions_at(whales, mkt.market_id, t)
            obs = Observation(market=mkt, t=t, whale_positions=whales_here)
            signals = tuple(agent(obs) for agent in ALL_AGENTS)
            decision = combine(signals)
            if decision.direction == 0 or decision.size_mult == 0:
                continue

            active_confidences = [s.confidence for s in signals if s.direction != 0]
            avg_conf = sum(active_confidences) / len(active_confidences)
            if avg_conf < min_confidence:
                continue

            stake = port.base_size * decision.size_mult
            if stake > port.cash:
                continue
            entry_price = mkt.price_path[t]
            port.cash -= stake
            port.open_positions[mkt.market_id] = OpenPosition(
                market_id=mkt.market_id,
                direction=decision.direction,
                entry_price=entry_price,
                size_usd=stake,
                t_enter=t,
                expected_move=decision.expected_move,
                entry_volume=mkt.volume_path[t],
            )

    # Force-close any survivors at the final price.
    final_t = path_len - 1
    for mid, pos in list(port.open_positions.items()):
        mkt = next(m for m in markets if m.market_id == mid)
        exit_price = mkt.price_path[final_t]
        pnl = _pnl(pos.direction, pos.entry_price, exit_price, pos.size_usd)
        port.cash += pos.size_usd + pnl
        port.closed.append(
            ClosedTrade(
                market_id=mid,
                direction=pos.direction,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                size_usd=pos.size_usd,
                pnl=pnl,
                reason="end-of-horizon",
                t_enter=pos.t_enter,
                t_exit=final_t,
            )
        )
        del port.open_positions[mid]

    return port
