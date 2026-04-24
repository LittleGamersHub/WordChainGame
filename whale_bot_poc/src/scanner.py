"""Wallet scanner.

Filter wallets by trade count and win rate, then rank by realized profit.
Mirrors the post's one-prompt ask: "100+ trades, 70%+ WR, rank by profit,
return top N".
"""

from __future__ import annotations

from dataclasses import dataclass

from .mock_data import Wallet


@dataclass
class WalletStats:
    address: str
    n_trades: int
    win_rate: float
    profit_usd: float
    avg_hold: float


def _stats(w: Wallet) -> WalletStats:
    n = len(w.trades)
    wins = sum(1 for t in w.trades if t.won)
    profit = sum(t.pnl for t in w.trades)
    avg_hold = sum(t.t_exit - t.t_enter for t in w.trades) / max(1, n)
    return WalletStats(
        address=w.address,
        n_trades=n,
        win_rate=wins / n if n else 0.0,
        profit_usd=profit,
        avg_hold=avg_hold,
    )


def scan(
    wallets: list[Wallet],
    min_trades: int = 100,
    min_win_rate: float = 0.70,
    top_n: int = 50,
) -> list[WalletStats]:
    passing = []
    for w in wallets:
        s = _stats(w)
        if s.n_trades >= min_trades and s.win_rate >= min_win_rate:
            passing.append(s)
    passing.sort(key=lambda s: s.profit_usd, reverse=True)
    return passing[:top_n]
