from whale_bot_poc.src import mock_data, scanner


def test_scan_respects_thresholds():
    markets = mock_data.generate_markets(n_markets=30, path_len=40, seed=1)
    wallets = mock_data.generate_wallets(n_wallets=500, n_whales=20, seed=2)
    mock_data.simulate_trades(wallets, markets, seed=3)

    top = scanner.scan(wallets, min_trades=100, min_win_rate=0.70, top_n=50)

    for s in top:
        assert s.n_trades >= 100
        assert s.win_rate >= 0.70
    profits = [s.profit_usd for s in top]
    assert profits == sorted(profits, reverse=True)


def test_scan_returns_empty_when_no_wallet_qualifies():
    markets = mock_data.generate_markets(n_markets=5, path_len=20, seed=1)
    wallets = mock_data.generate_wallets(n_wallets=10, n_whales=0, seed=2)
    mock_data.simulate_trades(wallets, markets, seed=3)

    top = scanner.scan(wallets, min_trades=10_000, min_win_rate=0.99, top_n=50)
    assert top == []
