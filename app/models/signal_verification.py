from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from app.models.signal import SignalType, TradingSignal


class SignalVerificationStatus(Enum):
    """Trạng thái kiểm chứng tín hiệu bằng dữ liệu nến thật từ watch_ohlcv."""
    CREATED = "created"
    WAITING_ENTRY = "waiting_entry"
    OPEN = "open"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class SignalVerification:
    """Snapshot tín hiệu strategy và kết quả đối chiếu bằng high/low của các nến thật sau đó."""
    symbol: str
    timeframe: str
    mode: str
    strategy_name: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    score: float
    confidence_score: float
    risk_reward_ratio: float
    indicators: Dict[str, Any]
    reason: str
    created_at: datetime
    expires_at: datetime
    source_candle: Dict[str, Any]
    verification_id: str = field(default_factory=lambda: uuid4().hex)
    status: SignalVerificationStatus = SignalVerificationStatus.CREATED
    user_decision: str = "pending"
    user_id: Optional[str] = None
    responded_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    close_price: Optional[float] = None
    pnl: float = 0.0
    checked_candles: int = 0
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_signal(
        cls,
        signal: TradingSignal,
        mode: str,
        source_candle: Dict[str, Any],
        expires_after: timedelta,
    ) -> "SignalVerification":
        """Tạo snapshot kiểm chứng từ TradingSignal tại thời điểm strategy phát tín hiệu."""
        return cls(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            mode=mode,
            strategy_name=signal.strategy_name,
            signal_type=signal.signal_type,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            quantity=signal.quantity,
            score=signal.score,
            confidence_score=signal.confidence_score,
            risk_reward_ratio=signal.risk_reward_ratio or 0.0,
            indicators=signal.indicators,
            reason=signal.reason,
            created_at=signal.timestamp,
            expires_at=signal.timestamp + expires_after,
            source_candle=source_candle,
            status=SignalVerificationStatus.WAITING_ENTRY,
        )

    def update_by_candle(self, candle: Dict[str, Any], prefer_stop_loss: bool = True):
        """Đối chiếu một nến thật với entry, take profit và stop loss của signal."""
        candle_time = candle["timestamp"]
        high = float(candle["high"])
        low = float(candle["low"])
        self.checked_candles += 1

        if self.status == SignalVerificationStatus.WAITING_ENTRY and candle_time > self.expires_at:
            self.status = SignalVerificationStatus.EXPIRED
            self.closed_at = candle_time
            self.notes.append("Signal hết hiệu lực trước khi khớp entry.")
            return

        if self.status == SignalVerificationStatus.WAITING_ENTRY and self._entry_touched(high, low):
            self.status = SignalVerificationStatus.OPEN
            self.opened_at = candle_time
            self.notes.append("Giá đã chạm entry theo high/low của nến thật.")

        if self.status != SignalVerificationStatus.OPEN:
            return

        take_profit_touched = self._take_profit_touched(high, low)
        stop_loss_touched = self._stop_loss_touched(high, low)
        if take_profit_touched and stop_loss_touched:
            self.notes.append("Cùng một nến chạm cả take profit và stop loss.")
            if prefer_stop_loss:
                self._close(SignalVerificationStatus.STOP_LOSS, self.stop_loss, candle_time)
            else:
                self._close(SignalVerificationStatus.TAKE_PROFIT, self.take_profit, candle_time)
        elif take_profit_touched:
            self._close(SignalVerificationStatus.TAKE_PROFIT, self.take_profit, candle_time)
        elif stop_loss_touched:
            self._close(SignalVerificationStatus.STOP_LOSS, self.stop_loss, candle_time)

    def confirm(self, user_id: int | str):
        """Ghi nhận người dùng đã xác nhận theo dõi hoặc vào lệnh giả định cho signal.

        Tham số:
        - user_id: Discord user id đã bấm xác nhận.
        """
        self.user_decision = "confirmed"
        self.user_id = str(user_id)
        self.responded_at = datetime.utcnow()
        self.notes.append(f"User {self.user_id} đã xác nhận signal.")

    def cancel(self, user_id: int | str | None = None, decision: str = "cancelled"):
        """Hủy kiểm chứng signal khi người dùng bỏ qua hoặc logic điều phối yêu cầu dừng."""
        self.user_decision = decision
        if user_id is not None:
            self.user_id = str(user_id)
        self.responded_at = datetime.utcnow()
        if self.status in {SignalVerificationStatus.WAITING_ENTRY, SignalVerificationStatus.OPEN}:
            self.status = SignalVerificationStatus.CANCELLED
            self.closed_at = self.responded_at
        self.notes.append("Signal đã bị bỏ qua hoặc hủy bởi người dùng.")

    def _entry_touched(self, high: float, low: float) -> bool:
        """Kiểm tra high/low của nến thật có chạm entry hay không."""
        return low <= self.entry_price <= high

    def _take_profit_touched(self, high: float, low: float) -> bool:
        """Kiểm tra high/low của nến thật có chạm take profit hay không."""
        return low <= self.take_profit <= high

    def _stop_loss_touched(self, high: float, low: float) -> bool:
        """Kiểm tra high/low của nến thật có chạm stop loss hay không."""
        return low <= self.stop_loss <= high

    def _close(self, status: SignalVerificationStatus, price: float, closed_at: datetime):
        """Đóng kiểm chứng và tính PnL giả định theo quantity strategy cung cấp."""
        self.status = status
        self.closed_at = closed_at
        self.close_price = price
        direction = 1 if self.signal_type == SignalType.LONG else -1
        self.pnl = (price - self.entry_price) * self.quantity * direction
