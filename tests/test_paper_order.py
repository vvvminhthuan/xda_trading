from datetime import datetime

from app.models.order import OrderStatus, PaperOrder
from app.models.signal import SignalType


def test_long_paper_order_reaches_take_profit():
    """Kiểm tra lệnh LONG giả định chuyển từ pending sang open rồi take profit."""
    order = PaperOrder(
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        signal_type=SignalType.LONG,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        quantity=2.0,
        strategy_name="TestStrategy",
        created_at=datetime.utcnow(),
    )

    order.update_by_price(100.0)
    order.update_by_price(110.0)

    assert order.status == OrderStatus.TAKE_PROFIT
    assert order.pnl == 20.0


def test_short_paper_order_reaches_stop_loss():
    """Kiểm tra lệnh SHORT giả định tính PnL âm khi chạm stop loss."""
    order = PaperOrder(
        symbol="BTC/USDT:USDT",
        timeframe="1m",
        signal_type=SignalType.SHORT,
        entry_price=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        quantity=1.0,
        strategy_name="TestStrategy",
        created_at=datetime.utcnow(),
    )

    order.update_by_price(100.0)
    order.update_by_price(105.0)

    assert order.status == OrderStatus.STOP_LOSS
    assert order.pnl == -5.0
