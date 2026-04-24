"""Synthetic Polymarket-like data generator.

Produces a closed universe of binary markets, a population of wallets, and
per-wallet trade histories. Skilled wallets bias their entries toward the
eventual winner; unskilled wallets trade near random. This gives the scanner
something to rank against ground truth.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Market:
    market_id: str
    question: str
    resolution: int  # 1 if YES resolved true, 0 if NO
    price_path: list[float] = field(default_factory=list)  # YES price over time
    volume_path: list[float] = field(default_factory=list)


@dataclass
class Trade:
    wallet: str
    market_id: str
    side: str  # "YES" or "NO"
    entry_price: float
    exit_price: float
    size_usd: float
    t_enter: int  # index into market.price_path
    t_exit: int

    @property
    def pnl(self) -> float:
        shares = self.size_usd / self.entry_price
        if self.side == "YES":
            return shares * (self.exit_price - self.entry_price)
        return shares * (self.entry_price - self.exit_price)

    @property
    def won(self) -> bool:
        return self.pnl > 0


@dataclass
class Wallet:
    address: str
    skill: float  # 0..1, probability of picking the correct side
    trades: list[Trade] = field(default_factory=list)


def _gen_price_path(resolution: int, length: int, rng: random.Random) -> list[float]:
    """Random walk that drifts toward the resolution value."""
    price = rng.uniform(0.35, 0.65)
    target = 0.98 if resolution == 1 else 0.02
    path = [price]
    for i in range(1, length):
        drift = (target - price) * 0.04
        noise = rng.gauss(0, 0.020)
        price = max(0.01, min(0.99, price + drift + noise))
        path.append(price)
    path[-1] = float(resolution)
    return path


def _gen_volume_path(length: int, rng: random.Random) -> list[float]:
    base = rng.uniform(5_000, 20_000)
    out = []
    for _ in range(length):
        spike = 1.0
        if rng.random() < 0.03:
            spike = rng.uniform(2.5, 5.0)
        out.append(base * rng.uniform(0.6, 1.4) * spike)
    return out


def generate_markets(
    n_markets: int = 120,
    path_len: int = 96,
    seed: int = 7,
) -> list[Market]:
    rng = random.Random(seed)
    markets: list[Market] = []
    for i in range(n_markets):
        resolution = 1 if rng.random() < 0.5 else 0
        m = Market(
            market_id=f"mkt_{i:04d}",
            question=f"Synthetic market #{i}",
            resolution=resolution,
            price_path=_gen_price_path(resolution, path_len, rng),
            volume_path=_gen_volume_path(path_len, rng),
        )
        markets.append(m)
    return markets


def generate_wallets(
    n_wallets: int = 14_000,
    n_whales: int = 50,
    seed: int = 11,
) -> list[Wallet]:
    """Most wallets are near-random; a small tail has genuine edge."""
    rng = random.Random(seed)
    wallets: list[Wallet] = []
    for i in range(n_wallets):
        if i < n_whales:
            skill = rng.uniform(0.82, 0.95)
        else:
            skill = rng.uniform(0.42, 0.58)
        wallets.append(Wallet(address=f"0x{i:040x}"[:42], skill=skill))
    rng.shuffle(wallets)
    return wallets


def simulate_trades(
    wallets: list[Wallet],
    markets: list[Market],
    seed: int = 23,
) -> None:
    """Populate each wallet.trades in-place.

    Trade count scales loosely with skill so the scanner's "100+ trades"
    threshold has real selectivity.
    """
    rng = random.Random(seed)
    for w in wallets:
        n_trades = int(rng.gauss(40 + w.skill * 120, 25))
        n_trades = max(1, n_trades)
        for _ in range(n_trades):
            m = rng.choice(markets)
            correct_side = "YES" if m.resolution == 1 else "NO"
            wrong_side = "NO" if correct_side == "YES" else "YES"
            side = correct_side if rng.random() < w.skill else wrong_side
            path = m.price_path
            # Skilled wallets enter earlier in the life of a market (when the
            # move is still ahead) and hold shorter.
            max_enter = len(path) - 10
            skill_bias = rng.uniform(0, 1) ** (1 + 3 * w.skill)
            t_enter = int(skill_bias * max_enter)
            hold = int(rng.uniform(2, 8) + (1 - w.skill) * 15)
            t_exit = min(len(path) - 1, t_enter + hold)
            entry_price = path[t_enter]
            exit_price = path[t_exit]
            size = rng.uniform(50, 500) * (1 + w.skill)
            w.trades.append(
                Trade(
                    wallet=w.address,
                    market_id=m.market_id,
                    side=side,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    size_usd=size,
                    t_enter=t_enter,
                    t_exit=t_exit,
                )
            )
