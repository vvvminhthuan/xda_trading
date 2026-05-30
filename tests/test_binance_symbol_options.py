from app.adapters.binance import BinanceAdapter


def test_binance_adapter_sorts_top_volume_options():
    """Kiểm tra helper lấy 10 symbol có quote volume cao nhất."""
    adapter = BinanceAdapter()
    options = [
        {"symbol": f"COIN{i}/USDT:USDT", "quote_volume": float(i), "percentage": 0.0}
        for i in range(12)
    ]

    top = adapter.top_volume_options(options, limit=10)

    assert [item["symbol"] for item in top] == [
        "COIN11/USDT:USDT",
        "COIN10/USDT:USDT",
        "COIN9/USDT:USDT",
        "COIN8/USDT:USDT",
        "COIN7/USDT:USDT",
        "COIN6/USDT:USDT",
        "COIN5/USDT:USDT",
        "COIN4/USDT:USDT",
        "COIN3/USDT:USDT",
        "COIN2/USDT:USDT",
    ]


def test_binance_adapter_sorts_top_mover_options_by_absolute_percentage():
    """Kiểm tra helper lấy symbol dao động mạnh nhất theo trị tuyệt đối percentage."""
    adapter = BinanceAdapter()
    options = [
        {"symbol": "A/USDT:USDT", "percentage": 3.0, "quote_volume": 1.0},
        {"symbol": "B/USDT:USDT", "percentage": -15.0, "quote_volume": 1.0},
        {"symbol": "C/USDT:USDT", "percentage": 12.0, "quote_volume": 1.0},
    ]

    top = adapter.top_mover_options(options, limit=2)

    assert [item["symbol"] for item in top] == ["B/USDT:USDT", "C/USDT:USDT"]


def test_binance_adapter_resolves_quote_volume_fallbacks():
    """Kiểm tra quote volume ưu tiên từ ticker và fallback về info/baseVolume."""
    adapter = BinanceAdapter()

    assert adapter._resolve_ticker_quote_volume({"quoteVolume": "100"}) == 100.0
    assert adapter._resolve_ticker_quote_volume({"info": {"quoteVolume": "90"}}) == 90.0
    assert adapter._resolve_ticker_quote_volume({"baseVolume": "80"}) == 80.0
    assert adapter._resolve_ticker_quote_volume({}) == 0.0
