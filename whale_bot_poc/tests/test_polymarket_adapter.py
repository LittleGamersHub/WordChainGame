"""Adapter tests use synthetic payloads shaped like Polymarket responses."""

from whale_bot_poc.src.polymarket_adapter import (
    market_from_api,
    wallets_from_trades,
)


def _make_gamma_market(cid="0xabc", question="Will X happen?", resolved_yes=None):
    m = {"conditionId": cid, "question": question}
    if resolved_yes is not None:
        m["outcomePrices"] = [str(1.0 if resolved_yes else 0.0),
                              str(0.0 if resolved_yes else 1.0)]
    return m


def _trade(wallet, cid, side, price, size, ts, outcome_index=0):
    return {
        "proxyWallet": wallet,
        "market": cid,
        "side": side,
        "price": price,
        "size": size,
        "timestamp": ts,
        "outcomeIndex": outcome_index,
    }


def test_market_from_api_builds_price_path():
    gm = _make_gamma_market(resolved_yes=True)
    trades = [
        _trade("w1", "0xabc", "BUY", 0.50, 100, 1_000_000),
        _trade("w2", "0xabc", "BUY", 0.55, 120, 1_000_500),
        _trade("w3", "0xabc", "BUY", 0.62, 80, 1_001_000),
        _trade("w4", "0xabc", "BUY", 0.71, 90, 1_001_500),
        _trade("w5", "0xabc", "BUY", 0.83, 60, 1_002_000),
    ]
    m = market_from_api(gm, trades, path_len=16)
    assert m is not None
    assert m.market_id == "0xabc"
    assert len(m.price_path) == 16
    assert m.price_path[-1] == 1.0  # pinned to resolution
    assert m.resolution == 1


def test_market_from_api_returns_none_with_insufficient_trades():
    gm = _make_gamma_market()
    m = market_from_api(gm, [], path_len=16)
    assert m is None


def test_wallets_from_trades_pairs_buy_with_sell():
    gm = _make_gamma_market(resolved_yes=True)
    base = 1_000_000
    trades = [
        _trade("whale", "0xabc", "BUY", 0.50, 100, base),
        _trade("other", "0xabc", "BUY", 0.40, 50, base + 500),
        _trade("other2", "0xabc", "BUY", 0.65, 50, base + 1_500),
        _trade("whale", "0xabc", "SELL", 0.80, 100, base + 3_000),
    ]
    market = market_from_api(gm, trades, path_len=16)
    wallets = wallets_from_trades(trades, {market.market_id: market})
    assert len(wallets) >= 1
    whale = next(w for w in wallets if w.address == "whale")
    assert len(whale.trades) == 1
    closed = whale.trades[0]
    assert closed.entry_price == 0.50
    assert closed.exit_price == 0.80
    assert closed.pnl > 0


def test_wallets_from_trades_closes_open_entry_at_final_price():
    gm = _make_gamma_market(resolved_yes=True)
    base = 1_000_000
    trades = [
        _trade("whale", "0xabc", "BUY", 0.50, 100, base),
        # Fill out the price path with other actors so the market builds.
        _trade("a", "0xabc", "BUY", 0.60, 10, base + 1_000),
        _trade("b", "0xabc", "BUY", 0.70, 10, base + 2_000),
        _trade("c", "0xabc", "BUY", 0.85, 10, base + 3_000),
    ]
    market = market_from_api(gm, trades, path_len=16)
    wallets = wallets_from_trades(trades, {market.market_id: market})
    whale = next(w for w in wallets if w.address == "whale")
    assert len(whale.trades) == 1
    # Final pinned price is 1.0 because resolved_yes=True.
    assert whale.trades[0].exit_price == 1.0


def test_unknown_market_ids_are_dropped():
    trades = [_trade("w1", "0xdoesnotexist", "BUY", 0.5, 10, 1_000_000)]
    wallets = wallets_from_trades(trades, market_index={})
    assert wallets == []
