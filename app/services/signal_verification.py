from datetime import timedelta
from typing import Any, Dict, List

from pandas import DataFrame

from app.models.signal import TradingSignal
from app.models.signal_verification import SignalVerification, SignalVerificationStatus


class SignalVerificationService:
    """Kiểm chứng TradingSignal bằng high/low của các nến thật từ watch_ohlcv."""

    def __init__(self, expires_after_candles: int = 12, prefer_stop_loss: bool = True):
        self.expires_after_candles = expires_after_candles
        self.prefer_stop_loss = prefer_stop_loss
        self.verifications: List[SignalVerification] = []

    def create(self, signal: TradingSignal, mode: str, data_frame: DataFrame) -> SignalVerification:
        """Lưu snapshot signal và nến nguồn ngay khi strategy tạo tín hiệu."""
        source_candle = self._latest_candle_snapshot(data_frame)
        expires_after = self._resolve_expiration(signal.timeframe)
        verification = SignalVerification.from_signal(
            signal=signal,
            mode=mode,
            source_candle=source_candle,
            expires_after=expires_after,
        )
        self.verifications.append(verification)
        return verification

    def update_by_latest_candle(self, symbol: str, timeframe: str, data_frame: DataFrame):
        """Cập nhật các signal đang mở/chờ bằng nến mới nhất của symbol và timeframe."""
        if data_frame.empty:
            return
        candle = self._latest_candle_snapshot(data_frame)
        for verification in self._active_verifications(symbol, timeframe):
            if candle["timestamp"] <= verification.created_at:
                continue
            verification.update_by_candle(candle, prefer_stop_loss=self.prefer_stop_loss)

    def confirm(self, verification_id: str, user_id: int | str) -> SignalVerification | None:
        """Ghi nhận người dùng xác nhận signal theo verification id.

        Tham số:
        - verification_id: Mã snapshot signal cần xác nhận.
        - user_id: Discord user id đã thực hiện thao tác.

        Trả về:
        - SignalVerification nếu tìm thấy, ngược lại trả None.
        """
        verification = self.find(verification_id)
        if not verification:
            return None
        verification.confirm(user_id)
        return verification

    def skip(self, verification_id: str, user_id: int | str) -> SignalVerification | None:
        """Ghi nhận người dùng bỏ qua signal và hủy kiểm chứng nếu signal còn active."""
        verification = self.find(verification_id)
        if not verification:
            return None
        verification.cancel(user_id, decision="skipped")
        return verification

    def find(self, verification_id: str) -> SignalVerification | None:
        """Tìm snapshot kiểm chứng theo mã định danh."""
        for verification in self.verifications:
            if verification.verification_id == verification_id:
                return verification
        return None

    def stats(self) -> Dict[str, Any]:
        """Thống kê kết quả kiểm chứng signal bằng dữ liệu thị trường thật."""
        closed = [
            item for item in self.verifications
            if item.status in {
                SignalVerificationStatus.TAKE_PROFIT,
                SignalVerificationStatus.STOP_LOSS,
                SignalVerificationStatus.EXPIRED,
                SignalVerificationStatus.CANCELLED,
            }
        ]
        take_profit = len([item for item in closed if item.status == SignalVerificationStatus.TAKE_PROFIT])
        stop_loss = len([item for item in closed if item.status == SignalVerificationStatus.STOP_LOSS])
        expired = len([item for item in closed if item.status == SignalVerificationStatus.EXPIRED])
        entry_matched = len([
            item for item in self.verifications
            if item.status in {
                SignalVerificationStatus.OPEN,
                SignalVerificationStatus.TAKE_PROFIT,
                SignalVerificationStatus.STOP_LOSS,
            }
        ])
        resolved = take_profit + stop_loss
        return {
            "total_signals": len(self.verifications),
            "entry_matched": entry_matched,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "expired": expired,
            "win_rate": (take_profit / resolved * 100) if resolved else 0.0,
            "pnl": sum(item.pnl for item in closed),
            "open": len([item for item in self.verifications if item.status == SignalVerificationStatus.OPEN]),
            "waiting_entry": len([
                item for item in self.verifications
                if item.status == SignalVerificationStatus.WAITING_ENTRY
            ]),
            "confirmed": len([
                item for item in self.verifications
                if item.user_decision == "confirmed"
            ]),
            "skipped": len([
                item for item in self.verifications
                if item.user_decision == "skipped"
            ]),
            "pending_response": len([
                item for item in self.verifications
                if item.user_decision == "pending"
            ]),
        }

    def _active_verifications(self, symbol: str, timeframe: str) -> List[SignalVerification]:
        """Lấy các signal còn cần đối chiếu theo symbol và timeframe."""
        return [
            item for item in self.verifications
            if item.symbol == symbol
            and item.timeframe == timeframe
            and item.status in {
                SignalVerificationStatus.WAITING_ENTRY,
                SignalVerificationStatus.OPEN,
            }
        ]

    def _latest_candle_snapshot(self, data_frame: DataFrame) -> Dict[str, Any]:
        """Chuyển nến mới nhất trong DataFrame thành snapshot đơn giản để lưu lịch sử."""
        latest = data_frame.iloc[-1]
        timestamp = data_frame.index[-1].to_pydatetime()
        return {
            "timestamp": timestamp,
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["close"]),
            "volume": float(latest["volume"]),
        }

    def _resolve_expiration(self, timeframe: str) -> timedelta:
        """Tính thời gian hết hạn signal dựa trên timeframe và số nến cho phép chờ entry."""
        unit = timeframe[-1]
        amount = int(timeframe[:-1])
        if unit == "m":
            return timedelta(minutes=amount * self.expires_after_candles)
        if unit == "h":
            return timedelta(hours=amount * self.expires_after_candles)
        if unit == "d":
            return timedelta(days=amount * self.expires_after_candles)
        return timedelta(minutes=self.expires_after_candles)
