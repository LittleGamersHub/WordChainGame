# whale_bot_poc

A **simulation-only** proof-of-concept that mirrors the architecture described
in a popular social-media post about a "Polymarket whale copy bot": a wallet
scanner, three independent scoring agents, a consensus filter, an exit policy,
and a paper trader.

There are two data modes:

1. **Synthetic** (`run_demo.py`) — generates fake markets and fake wallet
   histories entirely in memory. Runs offline, reproducible.
2. **Live read from Polymarket** (`fetch_and_scan.py`) — hits Polymarket's
   public, unauthenticated APIs (Gamma, CLOB, Data) over HTTPS GET only.
   No keys, no signing, no order placement, no wallet setup. The bot still
   "trades" entirely in memory.

The goal is to show the plumbing — scan → score → consensus → enter → exit
→ PnL report — in a way you can read in an afternoon and run on a laptop.

## Layout

```
whale_bot_poc/
  src/
    mock_data.py      # synthetic markets + wallets + trades
    scanner.py        # rank wallets by trade count, win rate, profit
    agents.py         # arbitrage / convergence / whale-copy scoring agents
    consensus.py      # 2-of-3 full, 1-of-3 half, disagree skip
    exit_policy.py    # 85% of expected move OR 3x volume spike OR stop
    paper_trader.py   # walk-forward simulator, tracks PnL
    run_demo.py       # end-to-end entry point (synthetic)
    polymarket_reader.py    # read-only HTTP client for Polymarket public APIs
    polymarket_adapter.py   # Polymarket JSON -> simulator's Market / Wallet
    fetch_and_scan.py       # live-data CLI (scan + optional paper-trade)
  tests/              # unit tests for scanner, consensus, exit, adapter
```

## Run

From the repository root. No pip dependencies required for the synthetic
demo; only `pytest` for the tests.

```bash
# Synthetic: 14k wallets, 50 whales, 120 markets, 96 time steps
python -m whale_bot_poc.src.run_demo

# Live read from Polymarket (public read-only endpoints):
python -m whale_bot_poc.src.fetch_and_scan --markets 10 --min-volume 250000
python -m whale_bot_poc.src.fetch_and_scan --markets 10 --paper-trade

# Tests
python -m pytest whale_bot_poc/tests -q
```

### What `fetch_and_scan` does

1. `GET gamma-api.polymarket.com/markets` — lists active, high-volume markets.
2. For each market, `GET data-api.polymarket.com/trades?market=<cid>` —
   paginates real on-chain trades.
3. Converts each market's trade stream into a bucketed YES-price path.
4. Groups trades by wallet, pairs BUYs with SELLs to reconstruct closed trades.
5. Runs the scanner to rank wallets by profit with a WR/trade-count filter.
6. Optionally paper-trades the three-agent consensus strategy against the
   reconstructed price paths.

No data is written anywhere. No orders are placed. No wallets are signed with.

## What the numbers mean

The demo prints a scanner report (top ranked "whales" on synthetic data) and a
paper-trading report (PnL, win rate, per-trade Sharpe, exit-reason breakdown).
Because the whale skill distribution is a synthetic input to the data
generator, the scanner will always find the whales — that proves the ranking
code works, not that a real scanner on real Polymarket data would.

Treat the paper-trading output the same way: it tells you the simulator is
wired correctly. It does not forecast real returns.

## What this POC is still missing before any real use

- Order routing, slippage model, gas/fees, partial fills, queue position.
- Risk limits, per-market exposure caps, kill switches.
- Persistence, observability, reconnection logic, alerting.
- Point-in-time correctness: `fetch_and_scan` reconstructs price paths from
  historical trades, so a scanner run "sees" the future of the market during
  the walk-forward. Usable for exploration, not for backtesting claims of
  edge. A real backtest needs strict as-of queries.
- Any form of live capital. Do not add that without a thorough review.

## An LLM in the loop

`agents.py` uses deterministic scoring so the POC is reproducible without any
API key. If you want to swap one of the three agents for a Claude-powered
version, keep the same `Observation -> Signal` contract. The consensus and
exit layers do not need to know.
