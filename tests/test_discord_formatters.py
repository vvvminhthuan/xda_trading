from datetime import datetime

from app.models.signal import SignalStrength, SignalType, TradingSignal
from app.services.discord.formatters import (
    format_analysis_summary_embed,
    format_control_panel,
    format_signal_action_panel,
    format_recommendation,
)


def test_format_control_panel_shows_analysis_log_state():
    """Kiểm tra control panel hiển thị trạng thái analysis log."""
    message = format_control_panel({
        "mode": "aggressive",
        "symbol": "BTC/USDT:USDT",
        "watch_mode": "single_symbol",
        "watch_symbols": ["BTC/USDT:USDT"],
        "watch_symbol_count": 1,
        "analysis_log_enabled": True,
    })

    assert "Analysis log: `on`" in message


def test_format_analysis_summary_embed_contains_raw_and_weighted_score():
    """Kiểm tra embed summary có đủ raw score, weighted score và filter."""
    embed = format_analysis_summary_embed({
        "symbol": "BTC/USDT:USDT",
        "timeframe": "3m",
        "mode": "aggressive",
        "safe_trend": "DOWN",
        "decision": "No signal",
        "score": 45,
        "confidence": 63.0,
        "alignment_bonus": 15,
        "raw_score": {"trend": 20, "momentum": 35, "volatility": 30, "volume": 40, "sr": 25},
        "weighted_score": {"trend": 5.0, "momentum": 10.5, "volatility": 6.0, "volume": 6.0, "sr": 2.5},
        "filters": {"safe_trend": True, "volume_confirmed": True, "trend_filter": False},
        "reasons": ["Giá dưới SMA 200"],
    })
    payload = embed()
    fields = {field["name"]: field["value"] for field in payload["fields"]}

    assert payload["title"] == "BTC/USDT:USDT | 3m Analysis Summary"
    assert "Trend: 20" in fields["Raw Score"]
    assert "Trend: 5.00" in fields["Weighted Score"]
    assert "Bộ lọc trend: chưa đạt" in fields["Bộ lọc"]


def test_format_analysis_summary_embed_marks_missing_filter_as_na():
    """Kiểm tra filter thiếu dữ liệu hiển thị n/a thay vì bị hiểu nhầm là fail."""
    embed = format_analysis_summary_embed({
        "symbol": "BTC/USDT:USDT",
        "timeframe": "3m",
        "filters": {"safe_trend": False},
    })
    payload = embed()
    fields = {field["name"]: field["value"] for field in payload["fields"]}

    assert "Xu hướng lớn: chưa đạt" in fields["Bộ lọc"]
    assert "Ngưỡng mode: không có dữ liệu" in fields["Bộ lọc"]


def test_format_analysis_summary_embed_shows_reversal_context():
    """Kiểm tra summary reversal hiển thị action, trend context và filter riêng."""
    embed = format_analysis_summary_embed({
        "symbol": "BTC/USDT:USDT",
        "timeframe": "3m",
        "mode": "reversal",
        "safe_trend": "UP",
        "decision": "Signal SHORT",
        "score": 78,
        "confidence": 76.2,
        "reversal_action": "SHORT",
        "trend_context": "COUNTER_SAFE_TREND",
        "filters": {
            "safe_trend": True,
            "volume_confirmed": True,
            "mode_threshold": True,
            "rate_limit": True,
            "reversal_action": True,
        },
    })
    payload = embed()
    fields = {field["name"]: field["value"] for field in payload["fields"]}

    assert fields["Hướng đảo chiều"] == "SHORT - Quay đầu xuống"
    assert fields["Bối cảnh xu hướng"] == "Ngược xu hướng lớn"
    assert "Hướng đảo chiều: đạt" in fields["Bộ lọc"]
    assert fields["Khuyến nghị"] == "Có tín hiệu nhưng ngược xu hướng lớn, chỉ cân nhắc với khối lượng nhỏ và quản trị rủi ro chặt."


def test_format_signal_action_panel_shows_reversal_entry_context():
    """Kiểm tra action panel hiển thị basis entry và trend context của reversal."""
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

    message = format_signal_action_panel(signal, "abcdef123456")

    assert "Entry basis: `Retest hỗ trợ s1`" in message
    assert "Reference level: `99.0`" in message
    assert "Bối cảnh xu hướng: `Xu hướng lớn chưa rõ`" in message


def test_format_recommendation_blocks_missing_reversal_confirmation():
    """Kiểm tra khuyến nghị tiếng Việt khi chưa có hướng đảo chiều rõ ràng."""
    recommendation = format_recommendation({
        "decision": "No signal: reversal confirmation missing",
        "filters": {
            "volume_confirmed": True,
            "reversal_action": False,
            "mode_threshold": False,
        },
        "trend_context": "WITH_SAFE_TREND",
    })

    assert recommendation == "Không nên vào lệnh vì chưa có hướng đảo chiều rõ ràng."
