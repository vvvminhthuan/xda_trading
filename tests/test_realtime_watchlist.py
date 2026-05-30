from app.core.trading import Trading, TradingType
from app.services.realtime import RealtimeService
from app.constants.discord_constants import DISCORD_TOP_MOVERS_10_VALUE, DISCORD_TOP_VOLUME_10_VALUE


class FakeBinanceAdapter:
    """Adapter giả lập helper top list để kiểm tra resolver watchlist."""

    def top_volume_options(self, options, limit=10):
        """Trả option có volume cao nhất theo logic đơn giản phục vụ test."""
        return sorted(options, key=lambda item: item["quote_volume"], reverse=True)[:limit]

    def top_mover_options(self, options, limit=10):
        """Trả option có dao động mạnh nhất theo trị tuyệt đối phục vụ test."""
        return sorted(options, key=lambda item: abs(item["percentage"]), reverse=True)[:limit]


def _service():
    """Tạo RealtimeService tối thiểu không khởi tạo kết nối ngoài."""
    service = RealtimeService.__new__(RealtimeService)
    service.trading_core = Trading(TradingType.CONSERVATIVE)
    service.binance_adapter = FakeBinanceAdapter()
    service.symbol_market_options = [
        {"symbol": "A/USDT:USDT", "quote_volume": 10.0, "percentage": 1.0},
        {"symbol": "B/USDT:USDT", "quote_volume": 30.0, "percentage": -8.0},
        {"symbol": "C/USDT:USDT", "quote_volume": 20.0, "percentage": 12.0},
    ]
    service.strategies = {}
    return service


def test_realtime_service_rebuilds_strategy_per_symbol():
    """Kiểm tra mỗi symbol có một FuturesStrategy riêng để không lẫn market data."""
    service = _service()

    service._rebuild_strategies(["BTC/USDT:USDT", "ETH/USDT:USDT"])

    assert set(service.strategies) == {"BTC/USDT:USDT", "ETH/USDT:USDT"}
    assert service.strategies["BTC/USDT:USDT"] is not service.strategies["ETH/USDT:USDT"]


def test_realtime_service_resolves_top_watchlist_options():
    """Kiểm tra special option được resolve thành watchlist top volume hoặc top mover."""
    service = _service()

    assert service._resolve_symbol_selection(DISCORD_TOP_VOLUME_10_VALUE) == [
        "B/USDT:USDT",
        "C/USDT:USDT",
        "A/USDT:USDT",
    ]
    assert service._resolve_symbol_selection(DISCORD_TOP_MOVERS_10_VALUE) == [
        "C/USDT:USDT",
        "B/USDT:USDT",
        "A/USDT:USDT",
    ]


def test_realtime_service_toggles_discord_analysis_log():
    """Kiểm tra runtime flag gửi analysis summary có thể bật/tắt bằng command."""
    service = _service()
    service.discord_analysis_log_enabled = False

    assert service.set_analysis_log("on") == "Đã bật analysis summary lên Discord."
    assert service.discord_analysis_log_enabled
    assert service.set_analysis_log("off") == "Đã tắt analysis summary lên Discord."
    assert not service.discord_analysis_log_enabled
