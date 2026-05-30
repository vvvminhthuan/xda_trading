from datetime import datetime

from app.models.signal import SignalStrength, SignalType, TradingSignal


def test_trading_signal_calculates_risk_reward():
    """Kiểm tra TradingSignal tự tính risk/reward và tạo field Discord hợp lệ."""
    signal = TradingSignal(
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        signal_type=SignalType.LONG,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        confidence_score=75.0,
        strength=SignalStrength.STRONG,
        strategy_name="TestStrategy",
        timestamp=datetime.utcnow(),
        score=80,
        quantity=1.0,
        indicators={"trend": 20},
        reason="Test reason",
    )

    assert signal.risk_reward_ratio == 2.0
    assert signal.is_valid
    assert signal.to_dict()["signal_type"] == "LONG"
    assert len(signal.to_embed_fields()) > 0


def test_trading_signal_embed_shows_reversal_entry_context():
    """Kiểm tra Discord embed hiển thị điểm vào tốt và bối cảnh reversal nếu có metadata."""
    signal = TradingSignal(
        symbol="BTC/USDT:USDT",
        timeframe="3m",
        signal_type=SignalType.LONG,
        entry_price=99.5,
        stop_loss=89.5,
        take_profit=114.425,
        confidence_score=70.0,
        strength=SignalStrength.STRONG,
        strategy_name="TestStrategy",
        timestamp=datetime.utcnow(),
        score=62,
        quantity=1.0,
        indicators={
            "entry_basis": "Retest hỗ trợ s1",
            "entry_reference_level": 99.0,
            "trend_context": "NEUTRAL_SAFE_TREND",
        },
        reason="Test reason",
    )

    fields = {field["name"]: field["value"] for field in signal.to_embed_fields()}

    assert fields["Điểm vào tốt"] == "Retest hỗ trợ s1"
    assert fields["Bối cảnh trend"] == "Xu hướng lớn chưa rõ"
    assert fields["Level tham chiếu"] == "99.0"
