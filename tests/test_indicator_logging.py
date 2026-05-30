from app.indicators.trend_indicators import TrendIndicators


def test_indicator_debug_prefix_includes_symbol():
    """Kiểm tra log indicator có prefix symbol khi chạy multi-symbol."""
    indicator = TrendIndicators()

    assert indicator._debug_prefix("BTC/USDT:USDT") == "BTC/USDT:USDT | "
    assert indicator._debug_prefix("") == ""
