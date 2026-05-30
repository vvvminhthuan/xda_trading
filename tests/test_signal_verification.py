from datetime import datetime, timedelta

import pandas as pd

from app.models.signal import SignalStrength, SignalType, TradingSignal
from app.models.signal_verification import SignalVerification, SignalVerificationStatus
from app.services.signal_verification import SignalVerificationService


def _signal(signal_type=SignalType.LONG):
    """Tạo TradingSignal mẫu để kiểm tra đối chiếu bằng nến thật."""
    return TradingSignal(
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        signal_type=signal_type,
        entry_price=100.0,
        stop_loss=95.0 if signal_type == SignalType.LONG else 105.0,
        take_profit=110.0 if signal_type == SignalType.LONG else 90.0,
        confidence_score=75.0,
        strength=SignalStrength.STRONG,
        strategy_name="TestStrategy",
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
        score=80,
        quantity=2.0,
        indicators={"trend": 20},
        reason="Test reason",
    )


def _frame(rows):
    """Tạo DataFrame OHLCV có index thời gian giống dữ liệu CandleFrames."""
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    return df


def test_signal_verification_long_take_profit_from_ohlcv():
    """Kiểm chứng LONG chạm entry rồi take profit bằng high/low của nến thật."""
    signal = _signal(SignalType.LONG)
    verification = SignalVerification.from_signal(
        signal=signal,
        mode="conservative",
        source_candle={"timestamp": signal.timestamp, "open": 101, "high": 102, "low": 99, "close": 100, "volume": 1},
        expires_after=timedelta(minutes=12),
    )

    verification.update_by_candle({"timestamp": datetime(2026, 1, 1, 0, 1), "high": 101, "low": 99})
    verification.update_by_candle({"timestamp": datetime(2026, 1, 1, 0, 2), "high": 111, "low": 101})

    assert verification.status == SignalVerificationStatus.TAKE_PROFIT
    assert verification.pnl == 20.0


def test_signal_verification_prefers_stop_loss_when_same_candle_hits_both():
    """Kiểm tra quy tắc bảo thủ khi cùng một nến chạm cả take profit và stop loss."""
    signal = _signal(SignalType.LONG)
    verification = SignalVerification.from_signal(
        signal=signal,
        mode="conservative",
        source_candle={"timestamp": signal.timestamp, "open": 101, "high": 102, "low": 99, "close": 100, "volume": 1},
        expires_after=timedelta(minutes=12),
    )

    verification.update_by_candle(
        {"timestamp": datetime(2026, 1, 1, 0, 1), "high": 111, "low": 94},
        prefer_stop_loss=True,
    )

    assert verification.status == SignalVerificationStatus.STOP_LOSS
    assert verification.pnl == -10.0


def test_signal_verification_service_updates_latest_candle():
    """Kiểm tra service lưu snapshot signal và cập nhật bằng nến mới nhất từ DataFrame."""
    service = SignalVerificationService()
    signal = _signal(SignalType.SHORT)
    source = _frame([
        {"timestamp": "2026-01-01 00:00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1},
    ])
    service.create(signal, "conservative", source)

    next_candle = _frame([
        {"timestamp": "2026-01-01 00:01:00", "open": 100, "high": 101, "low": 89, "close": 90, "volume": 1},
    ])
    service.update_by_latest_candle("BTC/USDT:USDT", "1m", next_candle)

    stats = service.stats()
    assert stats["take_profit"] == 1
    assert stats["win_rate"] == 100.0


def test_signal_verification_stats_calculates_accuracy_from_tp_and_sl():
    """Kiểm tra accuracy chỉ tính theo take profit và stop loss đã đóng."""
    service = SignalVerificationService()
    long_signal = _signal(SignalType.LONG)
    short_signal = _signal(SignalType.SHORT)
    source = _frame([
        {"timestamp": "2026-01-01 00:00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1},
    ])
    service.create(long_signal, "conservative", source)
    service.create(short_signal, "conservative", source)

    service.update_by_latest_candle("BTC/USDT:USDT", "1m", _frame([
        {"timestamp": "2026-01-01 00:01:00", "open": 100, "high": 111, "low": 99, "close": 110, "volume": 1},
    ]))
    service.update_by_latest_candle("BTC/USDT:USDT", "1m", _frame([
        {"timestamp": "2026-01-01 00:02:00", "open": 100, "high": 106, "low": 99, "close": 105, "volume": 1},
    ]))

    stats = service.stats()
    assert stats["take_profit"] == 1
    assert stats["stop_loss"] == 1
    assert stats["win_rate"] == 50.0
