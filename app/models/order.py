from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.models.signal import SignalType, TradingSignal


class OrderStatus(Enum):
    """Trạng thái vòng đời của một lệnh paper trading."""
    PENDING = "pending"
    OPEN = "open"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class PaperOrder:
    """Đại diện cho một lệnh giả định được tạo từ TradingSignal."""
    symbol: str
    timeframe: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    strategy_name: str
    created_at: datetime
    status: OrderStatus = OrderStatus.PENDING
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    close_price: Optional[float] = None
    pnl: float = 0.0

    @classmethod
    def from_signal(cls, signal: TradingSignal) -> "PaperOrder":
        """Tạo paper order từ tín hiệu strategy để kiểm chứng không cần vào lệnh thật."""
        return cls(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            signal_type=signal.signal_type,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            quantity=signal.quantity,
            strategy_name=signal.strategy_name,
            created_at=signal.timestamp,
        )

    def update_by_price(self, price: float, now: Optional[datetime] = None):
        """Cập nhật trạng thái lệnh theo giá hiện tại từ ticker realtime."""
        now = now or datetime.utcnow()
        if self.status == OrderStatus.PENDING and self._is_entry_matched(price):
            self.status = OrderStatus.OPEN
            self.opened_at = now
            return

        if self.status != OrderStatus.OPEN:
            return

        if self._is_take_profit(price):
            self._close(OrderStatus.TAKE_PROFIT, price, now)
        elif self._is_stop_loss(price):
            self._close(OrderStatus.STOP_LOSS, price, now)

    def cancel(self):
        """Hủy lệnh giả định khi người dùng bỏ qua hoặc tín hiệu không còn phù hợp."""
        if self.status in {OrderStatus.PENDING, OrderStatus.OPEN}:
            self.status = OrderStatus.CANCELLED
            self.closed_at = datetime.utcnow()

    def expire(self):
        """Đánh dấu lệnh hết hiệu lực khi quá thời gian theo dõi."""
        if self.status == OrderStatus.PENDING:
            self.status = OrderStatus.EXPIRED
            self.closed_at = datetime.utcnow()

    def _is_entry_matched(self, price: float) -> bool:
        """Kiểm tra giá hiện tại đã khớp vùng entry của LONG/SHORT hay chưa."""
        if self.signal_type == SignalType.LONG:
            return price <= self.entry_price
        return price >= self.entry_price

    def _is_take_profit(self, price: float) -> bool:
        """Kiểm tra giá hiện tại đã chạm take profit chưa."""
        if self.signal_type == SignalType.LONG:
            return price >= self.take_profit
        return price <= self.take_profit

    def _is_stop_loss(self, price: float) -> bool:
        """Kiểm tra giá hiện tại đã chạm stop loss chưa."""
        if self.signal_type == SignalType.LONG:
            return price <= self.stop_loss
        return price >= self.stop_loss

    def _close(self, status: OrderStatus, price: float, now: datetime):
        """Đóng lệnh và tính PnL giả định theo hướng LONG/SHORT."""
        self.status = status
        self.closed_at = now
        self.close_price = price
        direction = 1 if self.signal_type == SignalType.LONG else -1
        self.pnl = (price - self.entry_price) * self.quantity * direction
