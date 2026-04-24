"""Convert Polymarket API responses into the simulator's data shapes.

Polymarket's Data API returns per-trade records; the simulator expects a
price_path per market and Trade objects per wallet. We bucket trades into
time steps and reconstruct a YES-token price path from executed trade prices.

Because real trades don't have a clean exit in the same market (a wallet can
sell the same token later, partially, or never), we synthesise an exit from
the next opposite-side trade by the same wallet in the same market, or fall
back to the market's last observed price.

This module is intentionally conservative: fields may be missing, prices
may be strings, timestamps may be unix seconds or ISO — we coerce what we
can and drop the rest.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .mock_data import Market, Trade, Wallet


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _ts(x: Any) -> int:
    """Coerce timestamp to unix seconds (int)."""
    if x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    s = str(x)
    try:
        return int(float(s))
    except ValueError:
        return 0


def market_from_api(
    gamma_market: dict[str, Any],
    trades_for_market: list[dict[str, Any]],
    path_len: int = 96,
) -> Market | None:
    """Build a Market from a Gamma market record + its trade list.

    price_path is constructed by bucketing trades into `path_len` equal-width
    time buckets between the first and last trade, taking the average YES-side
    executed price in each bucket and forward-filling empty buckets.
    """
    cid = gamma_market.get("conditionId")
    question = gamma_market.get("question", "")
    if not cid:
        return None

    yes_prices: list[tuple[int, float, float]] = []  # (ts, price, size)
    for t in trades_for_market:
        p = _f(t.get("price"))
        sz = _f(t.get("size"))
        ts = _ts(t.get("timestamp") or t.get("ts"))
        outcome_idx = t.get("outcomeIndex")
        # Normalise to the YES-token price. If this trade was on the NO token,
        # convert to the implied YES price (1 - p).
        if outcome_idx in (1, "1"):
            p = max(0.0, min(1.0, 1.0 - p))
        if 0.0 < p < 1.0 and ts > 0:
            yes_prices.append((ts, p, sz))

    if len(yes_prices) < 4:
        return None

    yes_prices.sort(key=lambda x: x[0])
    t_first, t_last = yes_prices[0][0], yes_prices[-1][0]
    if t_last <= t_first:
        return None
    bucket = max(1, (t_last - t_first) // path_len)

    price_buckets: list[list[tuple[float, float]]] = [[] for _ in range(path_len)]
    vol_buckets: list[float] = [0.0] * path_len
    for ts, p, sz in yes_prices:
        idx = min(path_len - 1, (ts - t_first) // bucket)
        price_buckets[idx].append((p, sz))
        vol_buckets[idx] += sz

    price_path: list[float] = []
    last = yes_prices[0][1]
    for b in price_buckets:
        if b:
            total_sz = sum(sz for _, sz in b) or 1.0
            avg = sum(p * sz for p, sz in b) / total_sz
            last = avg
        price_path.append(last)

    # If the market has resolved, pin the terminal price.
    outcome_prices = gamma_market.get("outcomePrices")
    if isinstance(outcome_prices, list) and outcome_prices:
        resolved = _f(outcome_prices[0])
        if resolved in (0.0, 1.0):
            price_path[-1] = resolved
            resolution = int(resolved)
        else:
            resolution = 1 if price_path[-1] >= 0.5 else 0
    else:
        resolution = 1 if price_path[-1] >= 0.5 else 0

    return Market(
        market_id=cid,
        question=question,
        resolution=resolution,
        price_path=price_path,
        volume_path=vol_buckets,
    )


def wallets_from_trades(
    all_trades: list[dict[str, Any]],
    market_index: dict[str, Market],
) -> list[Wallet]:
    """Group trades by wallet, pair entries with synthetic exits.

    An "entry" is the first trade by a wallet on a given market/side; the
    "exit" is the next trade by the same wallet on the opposite side of the
    same market. Trades without a matching exit are closed at the market's
    final observed price.
    """
    by_wallet_market: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in all_trades:
        addr = t.get("proxyWallet") or t.get("user")
        cid = t.get("market") or t.get("conditionId")
        if not addr or not cid or cid not in market_index:
            continue
        by_wallet_market[(addr, cid)].append(t)

    wallets: dict[str, Wallet] = {}
    for (addr, cid), trades in by_wallet_market.items():
        trades.sort(key=lambda t: _ts(t.get("timestamp")))
        mkt = market_index[cid]
        t_first = _ts(trades[0].get("timestamp"))
        t_last = _ts(trades[-1].get("timestamp"))
        span = max(1, t_last - t_first)

        open_side: str | None = None
        open_entry: tuple[float, int, float] | None = None  # price, step, size
        for tr in trades:
            side = (tr.get("side") or "").upper()
            price = _f(tr.get("price"))
            size = _f(tr.get("size"))
            ts = _ts(tr.get("timestamp"))
            step = int((ts - t_first) / span * (len(mkt.price_path) - 1))
            # Normalise NO-token trades into YES-space.
            if tr.get("outcomeIndex") in (1, "1"):
                price = 1.0 - price
                side = "SELL" if side == "BUY" else "BUY"

            if side == "BUY" and open_entry is None:
                open_side = "YES"
                open_entry = (price, step, size)
            elif side == "SELL" and open_entry is not None:
                entry_price, t_enter, entry_size = open_entry
                tr_obj = Trade(
                    wallet=addr,
                    market_id=cid,
                    side=open_side or "YES",
                    entry_price=entry_price,
                    exit_price=price,
                    size_usd=entry_size * entry_price,
                    t_enter=t_enter,
                    t_exit=step,
                )
                wallets.setdefault(addr, Wallet(address=addr, skill=0.0)).trades.append(tr_obj)
                open_entry = None
                open_side = None

        # Any still-open entry: exit at market's last price.
        if open_entry is not None:
            entry_price, t_enter, entry_size = open_entry
            final_step = len(mkt.price_path) - 1
            tr_obj = Trade(
                wallet=addr,
                market_id=cid,
                side=open_side or "YES",
                entry_price=entry_price,
                exit_price=mkt.price_path[final_step],
                size_usd=entry_size * entry_price,
                t_enter=t_enter,
                t_exit=final_step,
            )
            wallets.setdefault(addr, Wallet(address=addr, skill=0.0)).trades.append(tr_obj)

    return list(wallets.values())
