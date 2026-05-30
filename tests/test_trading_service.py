import asyncio

import pytest

from app.services.trading import TradingService


class FakeBinanceAdapter:
    """Adapter giả lập để kiểm tra TradingService mà không gọi exchange thật."""

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000):
        """Trả dữ liệu rỗng nhằm mô phỏng lỗi fetch OHLCV từ exchange."""
        return []


class FakeMultiSymbolBinanceAdapter:
    """Adapter giả lập dữ liệu khác nhau cho từng symbol."""

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000):
        """Trả một nến hợp lệ có close khác nhau theo symbol."""
        close = 100.0 if symbol == "BTC/USDT:USDT" else 200.0
        return [[1000, close - 1, close + 1, close - 2, close, 10]]


class SpyTradingService(TradingService):
    """TradingService spy để kiểm tra prepare_symbols không tự start watcher."""

    def __init__(self, binance_adapter, timeframes):
        super().__init__(binance_adapter, timeframes)
        self.started_watchers = False

    def _start_watchers(self):
        """Ghi nhận việc start watcher thay vì tạo task thật trong test."""
        self.started_watchers = True


def test_trading_service_rejects_empty_history_data():
    """Kiểm tra TradingService không set dữ liệu history rỗng vào CandleFrames."""
    service = TradingService(FakeBinanceAdapter(), ["1m"])

    with pytest.raises(ValueError):
        asyncio.run(service._history("BTC/USDT:USDT", "1m"))


def test_trading_service_validates_ohlcv_row_format():
    """Kiểm tra TradingService chỉ nhận nến OHLCV đủ 6 giá trị không rỗng."""
    service = TradingService(FakeBinanceAdapter(), ["1m"])

    assert service._is_valid_ohlcv_row([1000, 1, 2, 0.5, 1.5, 10])
    assert not service._is_valid_ohlcv_row([1000, 1, 2])
    assert not service._is_valid_ohlcv_row([1000, 1, 2, None, 1.5, 10])


def test_trading_service_keeps_candle_frames_separated_by_symbol():
    """Kiểm tra dữ liệu hai symbol cùng timeframe không ghi đè nhau."""
    service = TradingService(FakeMultiSymbolBinanceAdapter(), ["1m"])

    asyncio.run(service._history("BTC/USDT:USDT", "1m"))
    asyncio.run(service._history("ETH/USDT:USDT", "1m"))

    btc_frame = service.frames_for_symbol("BTC/USDT:USDT").get("1m")
    eth_frame = service.frames_for_symbol("ETH/USDT:USDT").get("1m")

    assert btc_frame.iloc[-1]["close"] == 100.0
    assert eth_frame.iloc[-1]["close"] == 200.0


def test_trading_service_task_key_includes_symbol_and_timeframe():
    """Kiểm tra key watcher chứa cả symbol và timeframe để không trùng task multi-symbol."""
    service = TradingService(FakeBinanceAdapter(), ["1m"])

    assert service._task_key("BTC/USDT:USDT", "1m") == "BTC/USDT:USDT:1m"


def test_trading_service_prepare_symbols_does_not_start_watchers():
    """Kiểm tra prepare_symbols chỉ fetch history, chưa start watcher realtime."""
    service = SpyTradingService(FakeMultiSymbolBinanceAdapter(), ["1m"])

    asyncio.run(service.prepare_symbols(["BTC/USDT:USDT"]))

    assert not service.started_watchers
    assert service.frames_for_symbol("BTC/USDT:USDT").get("1m").iloc[-1]["close"] == 100.0
