"""End-to-end demo: generate data, scan for whales, paper-trade, print report."""

from __future__ import annotations

import argparse
import time

from . import mock_data, scanner, paper_trader


def _fmt_usd(x: float) -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}${abs(x):,.2f}"


def _sharpe(pnls: list[float]) -> float:
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    var = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
    std = var ** 0.5
    return mean / std if std > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description="Whale copy bot POC (simulation only).")
    ap.add_argument("--wallets", type=int, default=14_000)
    ap.add_argument("--whales", type=int, default=50)
    ap.add_argument("--markets", type=int, default=120)
    ap.add_argument("--path-len", type=int, default=96)
    ap.add_argument("--cash", type=float, default=600.0)
    ap.add_argument("--base-size", type=float, default=50.0)
    ap.add_argument("--min-trades", type=int, default=100)
    ap.add_argument("--min-wr", type=float, default=0.70)
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    print("=" * 70)
    print("whale_bot_poc — simulation only, no real funds, no real venues")
    print("=" * 70)

    print(f"\nGenerating {args.markets} markets, {args.wallets} wallets...")
    t0 = time.time()
    markets = mock_data.generate_markets(args.markets, args.path_len, seed=args.seed)
    wallets = mock_data.generate_wallets(args.wallets, args.whales, seed=args.seed + 1)
    mock_data.simulate_trades(wallets, markets, seed=args.seed + 2)
    print(f"  data generation:  {time.time() - t0:.2f}s")

    print(
        f"\nScanning for wallets with >={args.min_trades} trades, "
        f">={args.min_wr:.0%} win rate..."
    )
    t0 = time.time()
    top = scanner.scan(
        wallets,
        min_trades=args.min_trades,
        min_win_rate=args.min_wr,
        top_n=args.top_n,
    )
    print(f"  scan:             {time.time() - t0:.2f}s")
    print(f"  wallets passing:  {len(top)}")

    if top:
        top20_profit = sum(s.profit_usd for s in top[:20])
        print(f"  top-20 profit:    {_fmt_usd(top20_profit)}")
        print("\n  top 5 ranked:")
        for i, s in enumerate(top[:5], 1):
            print(
                f"   {i:>2}. {s.address[:10]}…  "
                f"trades={s.n_trades:<4d}  wr={s.win_rate:.0%}  "
                f"pnl={_fmt_usd(s.profit_usd)}  avg_hold={s.avg_hold:.1f}"
            )

    whale_addrs = {s.address for s in top}
    whales = [w for w in wallets if w.address in whale_addrs]

    print(f"\nPaper-trading {args.path_len} steps across {args.markets} markets...")
    t0 = time.time()
    port = paper_trader.run(
        markets,
        whales,
        starting_cash=args.cash,
        base_size=args.base_size,
    )
    print(f"  simulation:       {time.time() - t0:.2f}s")

    wins = sum(1 for t in port.closed if t.won)
    losses = len(port.closed) - wins
    pnls = [t.pnl for t in port.closed]
    exit_reasons: dict[str, int] = {}
    for t in port.closed:
        exit_reasons[t.reason] = exit_reasons.get(t.reason, 0) + 1

    print("\n" + "-" * 70)
    print("RESULT")
    print("-" * 70)
    print(f"  starting cash:    ${port.starting_cash:,.2f}")
    print(f"  ending cash:      ${port.cash:,.2f}")
    print(f"  net pnl:          {_fmt_usd(port.pnl)}")
    print(f"  trades:           {len(port.closed)}  (wins {wins}, losses {losses})")
    print(f"  win rate:         {port.win_rate:.1%}")
    print(f"  per-trade sharpe: {_sharpe(pnls):.2f}")
    print("  exit breakdown:")
    for reason, n in sorted(exit_reasons.items(), key=lambda kv: -kv[1]):
        print(f"    {reason:<40s} {n}")
    print("-" * 70)
    print("These are synthetic results on synthetic data. They prove the")
    print("plumbing works. They do not predict real market performance.")


if __name__ == "__main__":
    main()
