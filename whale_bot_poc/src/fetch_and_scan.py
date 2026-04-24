"""Fetch real Polymarket market + trade data and run the wallet scanner.

Read-only. No wallet, no keys, no order placement. Everything downloaded is
public data; everything the bot "trades" is paper (simulated in memory).

Example:
    python -m whale_bot_poc.src.fetch_and_scan --markets 10 --min-volume 250000
"""

from __future__ import annotations

import argparse
import time

from . import paper_trader, scanner
from .polymarket_adapter import market_from_api, wallets_from_trades
from .polymarket_reader import PolymarketReader


def _fmt_usd(x: float) -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}${abs(x):,.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch live Polymarket data and run the scanner + paper trader."
    )
    ap.add_argument("--markets", type=int, default=10, help="number of markets to pull")
    ap.add_argument("--min-volume", type=float, default=100_000.0)
    ap.add_argument("--trades-per-market", type=int, default=2_000)
    ap.add_argument("--path-len", type=int, default=96)
    ap.add_argument("--min-trades", type=int, default=20, help="scanner min trade count")
    ap.add_argument("--min-wr", type=float, default=0.60, help="scanner min win rate")
    ap.add_argument("--top-n", type=int, default=25)
    ap.add_argument("--cash", type=float, default=600.0)
    ap.add_argument("--base-size", type=float, default=50.0)
    ap.add_argument("--paper-trade", action="store_true", help="also run the paper trader")
    args = ap.parse_args()

    print("=" * 70)
    print("fetch_and_scan — read-only Polymarket pull + paper-trade simulation")
    print("=" * 70)

    reader = PolymarketReader()

    print(f"\nFetching up to {args.markets} active markets (min_volume ${args.min_volume:,.0f})...")
    t0 = time.time()
    raw_markets = reader.fetch_markets(
        limit=max(args.markets * 3, 50),
        active=True,
        closed=False,
        min_volume=args.min_volume,
    )
    raw_markets = raw_markets[: args.markets]
    print(f"  gamma pull:      {time.time() - t0:.2f}s   markets={len(raw_markets)}")

    markets = []
    all_trades = []
    for i, rm in enumerate(raw_markets, 1):
        cid = rm.get("conditionId")
        if not cid:
            continue
        t1 = time.time()
        trades = reader.fetch_all_trades_for_market(cid, max_trades=args.trades_per_market)
        print(
            f"  [{i:>2}/{len(raw_markets)}] {cid[:12]}…  "
            f"trades={len(trades):<5d}  ({time.time() - t1:.2f}s)  "
            f"{(rm.get('question') or '')[:60]}"
        )
        mkt = market_from_api(rm, trades, path_len=args.path_len)
        if mkt is None:
            continue
        markets.append(mkt)
        # Tag every trade with its market id for the adapter.
        for t in trades:
            t.setdefault("market", cid)
        all_trades.extend(trades)

    if not markets:
        print("\nNo usable markets after adaptation.")
        return

    market_index = {m.market_id: m for m in markets}
    wallets = wallets_from_trades(all_trades, market_index)
    print(f"\n  wallets built:    {len(wallets)}  from {len(all_trades)} raw trades")

    print(
        f"\nScanning wallets (>= {args.min_trades} trades, "
        f">= {args.min_wr:.0%} win rate)..."
    )
    top = scanner.scan(
        wallets,
        min_trades=args.min_trades,
        min_win_rate=args.min_wr,
        top_n=args.top_n,
    )
    print(f"  passing:          {len(top)}")
    for i, s in enumerate(top[:10], 1):
        print(
            f"   {i:>2}. {s.address[:10]}…  "
            f"trades={s.n_trades:<4d}  wr={s.win_rate:.0%}  "
            f"pnl={_fmt_usd(s.profit_usd)}  avg_hold={s.avg_hold:.1f}"
        )

    if not args.paper_trade:
        print("\n(Pass --paper-trade to also run the simulator against these whales.)")
        return

    whale_addrs = {s.address for s in top}
    whales = [w for w in wallets if w.address in whale_addrs]
    print(f"\nPaper-trading {args.path_len} steps with {len(whales)} whales...")
    port = paper_trader.run(
        markets,
        whales,
        starting_cash=args.cash,
        base_size=args.base_size,
    )
    wins = sum(1 for t in port.closed if t.won)

    print("\n" + "-" * 70)
    print("RESULT (paper)")
    print("-" * 70)
    print(f"  starting cash:    ${port.starting_cash:,.2f}")
    print(f"  ending cash:      ${port.cash:,.2f}")
    print(f"  net pnl:          {_fmt_usd(port.pnl)}")
    print(f"  trades:           {len(port.closed)}  (wins {wins}, "
          f"losses {len(port.closed) - wins})")
    print(f"  win rate:         {port.win_rate:.1%}")
    print("-" * 70)
    print("Real market data, simulated fills. No orders were placed.")


if __name__ == "__main__":
    main()
