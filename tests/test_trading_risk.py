from app.core.trading import Trading, TradingType


def test_trading_defaults_to_reversal_mode():
    """Kiểm tra Trading mặc định chạy mode reversal để ưu tiên bắt điểm quay đầu."""
    trading = Trading()

    assert trading.current_mode == TradingType.REVERSAL
    assert trading.config.weights["momentum"] > trading.config.weights["trend"]
    assert trading.config.weights["sr"] > trading.config.weights["trend"]


def test_trading_blocks_signal_when_drawdown_limit_reached():
    """Kiểm tra Trading chặn signal mới khi drawdown hiện tại chạm giới hạn mode."""
    trading = Trading(TradingType.CONSERVATIVE)

    trading.update_drawdown(trading.config.drawdown_limit)

    assert trading.is_drawdown_limit_reached()
    assert not trading.should_send_signal(win_prob=100.0, score=100)


def test_trading_allows_signal_when_drawdown_below_limit():
    """Kiểm tra Trading vẫn cho phép signal đủ điểm khi drawdown chưa chạm giới hạn."""
    trading = Trading(TradingType.CONSERVATIVE)

    trading.update_drawdown(trading.config.drawdown_limit - 0.1)

    assert not trading.is_drawdown_limit_reached()
    assert trading.should_send_signal(win_prob=100.0, score=100)
