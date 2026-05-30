import pandas as pd

from app.core.trading import Trading, TradingType
from app.indicators.volatility_indicators import VolatilityIndicators
from app.models.signal import SignalType
from app.strategies.futures import FuturesStrategy


class FakeIndicator:
    """Indicator giả lập trả signal cố định cho test strategy runtime."""

    def __init__(self, signal: dict):
        self.signal = signal

    def get_signal(self, df, symbol: str = "") -> dict:
        """Trả signal cố định để test không phụ thuộc indicator thật."""
        return self.signal


def test_futures_strategy_creates_signal_with_runtime_symbol():
    """Kiểm tra FuturesStrategy dùng symbol runtime thay vì symbol mặc định trong config."""
    strategy = FuturesStrategy(Trading(TradingType.CONSERVATIVE))
    strategy.market_data["1m"] = pd.DataFrame([{"close": 100.0}])

    signal = strategy._create_trading_signal(
        "ETH/USDT:USDT",
        "1m",
        "UP",
        {"score": 80, "breakdown": {}, "reasons": []},
        80.0,
        {"atr_value": 1.0},
    )

    assert signal.symbol == "ETH/USDT:USDT"
    assert signal.signal_type == SignalType.LONG


def test_futures_strategy_risk_filters_require_trend_and_volatility():
    """Kiểm tra risk filter chặn signal khi trend hoặc ATR percentage dưới ngưỡng mode."""
    strategy = FuturesStrategy(Trading(TradingType.CONSERVATIVE))

    assert not strategy._passes_risk_filters(
        {"score": strategy.trading_core.config.trend_strength - 1},
        {"atr_percentage": strategy.trading_core.config.volatility_filter},
    )
    assert not strategy._passes_risk_filters(
        {"score": strategy.trading_core.config.trend_strength},
        {"atr_percentage": strategy.trading_core.config.volatility_filter - 0.01},
    )
    assert strategy._passes_risk_filters(
        {"score": strategy.trading_core.config.trend_strength},
        {"atr_percentage": strategy.trading_core.config.volatility_filter},
    )


def test_futures_strategy_weighted_score_keeps_raw_and_weighted_breakdown():
    """Kiểm tra score tổng tách rõ điểm raw và điểm đã nhân trọng số."""
    strategy = FuturesStrategy(Trading(TradingType.AGGRESSIVE))

    score = strategy._calculate_weighted_score(
        {"score": 20, "direction": "DOWN", "reasons": ["Trend"]},
        {"score": 35, "reasons": ["Momentum"]},
        {"score": 30, "reasons": ["Volatility"]},
        {"score": 40, "reasons": ["Volume"]},
        {"score": 25, "reasons": ["SR"]},
        "DOWN",
    )

    assert score["raw_breakdown"]["trend"] == 20
    assert score["weighted_breakdown"]["trend"] == 5.0
    assert score["alignment_bonus"] == 15
    assert score["score"] == 45


def test_futures_strategy_neutral_safe_trend_keeps_analysis_breakdown():
    """Kiểm tra safe trend neutral vẫn lưu analysis đầy đủ nhưng không tạo signal."""
    strategy = FuturesStrategy(Trading(TradingType.AGGRESSIVE))
    strategy.market_data["3m"] = pd.DataFrame([{"close": 100.0} for _ in range(12)])
    strategy.is_safe_trend = lambda symbol="": "NEUTRAL"
    strategy.trend_indicator = FakeIndicator({
        "score": 60,
        "direction": "UP",
        "reasons": ["Trend tăng"],
    })
    strategy.momentum_indicator = FakeIndicator({
        "score": 55,
        "reasons": ["Momentum ổn"],
    })
    strategy.volatility_indicator = FakeIndicator({
        "score": 50,
        "atr_percentage": strategy.trading_core.config.volatility_filter,
        "reasons": ["Volatility đủ"],
    })
    strategy.volume_indicator = FakeIndicator({
        "score": 45,
        "direction": "NEUTRAL",
        "volume_condition": "NORMAL",
        "reasons": ["Volume trung tính"],
    })
    strategy.sr_indicator = FakeIndicator({
        "score": 40,
        "reasons": ["Gần hỗ trợ"],
    })

    signal = strategy.analyze("3m", symbol="CL/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is None
    assert analysis["symbol"] == "CL/USDT:USDT"
    assert analysis["safe_trend"] == "NEUTRAL"
    assert analysis["decision"] == "No signal: safe trend neutral"
    assert analysis["score"] > 0
    assert analysis["confidence"] > 0
    assert analysis["raw_score"]["trend"] == 60
    assert analysis["weighted_score"]["trend"] == 15.0
    assert analysis["filters"]["safe_trend"] is False
    assert "mode_threshold" in analysis["filters"]
    assert analysis["reasons"]


def _reversal_strategy(
    momentum_signal: dict,
    volatility_signal: dict,
    volume_signal: dict,
    sr_signal: dict,
    safe_trend: str = "NEUTRAL",
) -> FuturesStrategy:
    """Tạo FuturesStrategy mode reversal với indicator giả lập cho test điểm quay đầu."""
    strategy = FuturesStrategy(Trading(TradingType.REVERSAL))
    strategy.market_data["3m"] = pd.DataFrame([{"close": 100.0} for _ in range(12)])
    strategy.is_safe_trend = lambda symbol="": safe_trend
    strategy.trend_indicator = FakeIndicator({
        "score": 0,
        "direction": "NEUTRAL",
        "reasons": ["Trend chưa xác nhận"],
    })
    strategy.momentum_indicator = FakeIndicator(momentum_signal)
    strategy.volatility_indicator = FakeIndicator(volatility_signal)
    strategy.volume_indicator = FakeIndicator(volume_signal)
    strategy.sr_indicator = FakeIndicator(sr_signal)
    return strategy


def test_futures_strategy_reversal_creates_long_without_safe_trend():
    """Kiểm tra reversal tạo LONG khi quá bán bật lên tại vùng hỗ trợ dù safe trend neutral."""
    strategy = _reversal_strategy(
        {
            "score": 70,
            "condition": "OVERSOLD_REVERSAL",
            "direction": "UP",
            "reasons": ["RSI bật từ vùng quá bán"],
        },
        {
            "score": 30,
            "volatility_state": "SUPPORT_TEST",
            "direction": "UP",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải dưới Bollinger"],
        },
        {
            "score": 55,
            "direction": "UP",
            "volume_condition": "BULLISH_DIVERGENCE",
            "reasons": ["OBV Bullish Divergence"],
        },
        {
            "score": 80,
            "sr_condition": "SWING_SUPPORT",
            "reasons": ["Test Swing Low"],
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is not None
    assert signal.signal_type == SignalType.LONG
    assert analysis["reversal_action"] == "LONG"
    assert analysis["trend_context"] == "NEUTRAL_SAFE_TREND"
    assert analysis["decision"] == "Signal LONG"


def test_futures_strategy_reversal_creates_short_against_safe_trend():
    """Kiểm tra reversal tạo SHORT khi quá mua quay đầu tại kháng cự dù ngược safe trend."""
    strategy = _reversal_strategy(
        {
            "score": 70,
            "condition": "OVERBOUGHT_REVERSAL",
            "direction": "DOWN",
            "reasons": ["RSI quay đầu từ vùng quá mua"],
        },
        {
            "score": 30,
            "volatility_state": "RESISTANCE_TEST",
            "direction": "DOWN",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải trên Bollinger"],
        },
        {
            "score": 55,
            "direction": "DOWN",
            "volume_condition": "BEARISH_DIVERGENCE",
            "reasons": ["OBV Bearish Divergence"],
        },
        {
            "score": 80,
            "sr_condition": "SWING_RESISTANCE",
            "reasons": ["Test Swing High"],
        },
        safe_trend="UP",
    )

    signal = strategy.analyze("3m", symbol="ETH/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is not None
    assert signal.signal_type == SignalType.SHORT
    assert analysis["reversal_action"] == "SHORT"
    assert analysis["trend_context"] == "COUNTER_SAFE_TREND"
    assert analysis["decision"] == "Signal SHORT"


def test_futures_strategy_reversal_blocks_low_volume():
    """Kiểm tra reversal vẫn chặn signal khi volume thấp dù momentum và S/R đã xác nhận."""
    strategy = _reversal_strategy(
        {
            "score": 70,
            "condition": "OVERSOLD_REVERSAL",
            "direction": "UP",
            "reasons": ["RSI bật từ vùng quá bán"],
        },
        {
            "score": 30,
            "volatility_state": "SUPPORT_TEST",
            "direction": "UP",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải dưới Bollinger"],
        },
        {
            "score": 55,
            "direction": "UP",
            "volume_condition": "LOW_VOLUME",
            "reasons": ["Volume thấp"],
        },
        {
            "score": 80,
            "sr_condition": "SWING_SUPPORT",
            "reasons": ["Test Swing Low"],
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is None
    assert analysis["reversal_action"] == "LONG"
    assert analysis["filters"]["volume_confirmed"] is False
    assert analysis["decision"] == "No signal: reversal volume not confirmed"


def test_futures_strategy_reversal_accepts_rsi_recovery_with_realistic_score():
    """Kiểm tra reversal tạo LONG khi RSI vừa hồi khỏi quá bán với score thực tế hơn."""
    strategy = _reversal_strategy(
        {
            "score": 25,
            "condition": "OVERSOLD_RECOVERY",
            "direction": "UP",
            "reasons": ["RSI hồi phục khỏi vùng quá bán"],
        },
        {
            "score": 30,
            "volatility_state": "SUPPORT_TEST",
            "direction": "UP",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải dưới Bollinger"],
        },
        {
            "score": 35,
            "direction": "UP",
            "volume_condition": "BULLISH_DIVERGENCE",
            "reasons": ["OBV Bullish Divergence"],
        },
        {
            "score": 35,
            "sr_condition": "FIBONACCI_TEST",
            "reasons": ["Test Fibonacci 618%"],
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is not None
    assert signal.signal_type == SignalType.LONG
    assert analysis["reversal_action"] == "LONG"
    assert analysis["score"] >= strategy.trading_core.config.min_score
    assert analysis["decision"] == "Signal LONG"


def test_futures_strategy_reversal_blocks_neutral_rsi_momentum_direction():
    """Kiểm tra reversal không bắt tín hiệu chỉ vì RSI trung tính tăng mạnh."""
    strategy = _reversal_strategy(
        {
            "score": 15,
            "condition": "NEUTRAL",
            "direction": "UP",
            "reasons": ["RSI momentum tăng mạnh"],
        },
        {
            "score": 30,
            "volatility_state": "SUPPORT_TEST",
            "direction": "UP",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải dưới Bollinger"],
        },
        {
            "score": 35,
            "direction": "UP",
            "volume_condition": "BULLISH_DIVERGENCE",
            "reasons": ["OBV Bullish Divergence"],
        },
        {
            "score": 35,
            "sr_condition": "SUPPORT_TEST",
            "reasons": ["Test S1"],
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")
    analysis = strategy.last_analysis["3m"]

    assert signal is None
    assert analysis["reversal_action"] == "NONE"
    assert analysis["decision"] == "No signal: reversal confirmation missing"


def test_futures_strategy_reversal_long_uses_support_retest_entry():
    """Kiểm tra LONG reversal ưu tiên entry retest hỗ trợ thay vì luôn lấy close."""
    strategy = _reversal_strategy(
        {
            "score": 25,
            "condition": "OVERSOLD_RECOVERY",
            "direction": "UP",
            "reasons": ["RSI hồi phục khỏi vùng quá bán"],
        },
        {
            "score": 30,
            "volatility_state": "SUPPORT_TEST",
            "direction": "UP",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải dưới Bollinger"],
        },
        {
            "score": 35,
            "direction": "UP",
            "volume_condition": "BULLISH_DIVERGENCE",
            "reasons": ["OBV Bullish Divergence"],
        },
        {
            "score": 35,
            "sr_condition": "SUPPORT_TEST",
            "reasons": ["Test S1"],
            "key_levels": {"s1": 99.0},
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")

    assert signal is not None
    assert signal.entry_price < 100.0
    assert signal.indicators["entry_basis"] == "Retest hỗ trợ s1"
    assert signal.indicators["entry_reference_level"] == 99.0


def test_futures_strategy_reversal_short_uses_resistance_retest_entry():
    """Kiểm tra SHORT reversal ưu tiên entry retest kháng cự thay vì luôn lấy close."""
    strategy = _reversal_strategy(
        {
            "score": 25,
            "condition": "OVERBOUGHT_REJECTION",
            "direction": "DOWN",
            "reasons": ["RSI bị từ chối khỏi vùng quá mua"],
        },
        {
            "score": 30,
            "volatility_state": "RESISTANCE_TEST",
            "direction": "DOWN",
            "atr_percentage": 0.15,
            "atr_value": 1.0,
            "reasons": ["Chạm dải trên Bollinger"],
        },
        {
            "score": 35,
            "direction": "DOWN",
            "volume_condition": "BEARISH_DIVERGENCE",
            "reasons": ["OBV Bearish Divergence"],
        },
        {
            "score": 35,
            "sr_condition": "RESISTANCE_TEST",
            "reasons": ["Test R1"],
            "key_levels": {"r1": 101.0},
        },
    )

    signal = strategy.analyze("3m", symbol="BTC/USDT:USDT")

    assert signal is not None
    assert signal.entry_price > 100.0
    assert signal.indicators["entry_basis"] == "Retest kháng cự r1"
    assert signal.indicators["entry_reference_level"] == 101.0


def test_volatility_signal_keeps_bollinger_support_state_when_atr_low():
    """Kiểm tra ATR thấp không ghi đè trạng thái chạm Bollinger lower của reversal."""
    indicator = VolatilityIndicators()
    df = pd.DataFrame([
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
            "BBU_20_2.0": 103.0,
            "BBL_20_2.0": 97.0,
            "BBM_20_2.0": 100.0,
            "ATR_14": 0.8,
            "ATRr_14": 0.8,
        },
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
            "BBU_20_2.0": 103.0,
            "BBL_20_2.0": 97.0,
            "BBM_20_2.0": 100.0,
            "ATR_14": 0.8,
            "ATRr_14": 0.8,
        },
        {
            "open": 98.0,
            "high": 100.0,
            "low": 96.5,
            "close": 98.5,
            "volume": 1.0,
            "BBU_20_2.0": 103.0,
            "BBL_20_2.0": 97.0,
            "BBM_20_2.0": 100.0,
            "ATR_14": 0.8,
            "ATRr_14": 0.8,
        },
    ])

    signal = indicator.get_signal(df)

    assert signal["volatility_state"] == "SUPPORT_TEST"
    assert signal["direction"] == "UP"
