"""
Models cho tín hiệu trading
Định nghĩa cấu trúc tín hiệu và các thông tin liên quan
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

class SignalType(Enum):
    """Loại tín hiệu"""
    LONG = "LONG"
    SHORT = "SHORT"

class SignalStrength(Enum):
    """Mức độ mạnh của tín hiệu"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

@dataclass
class TradingSignal:
    """
    Đại diện cho một tín hiệu trading
    """
    symbol: str
    timeframe: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    strength: SignalStrength
    strategy_name: str
    timestamp: datetime
    score: float
    quantity: float
    
    # Thông tin chi tiết
    indicators: Dict[str, Any]
    notes: str = ""
    risk_reward_ratio: Optional[float] = None
    position_size: Optional[float] = None
    reason: str=""
    
    def __post_init__(self):
        """Tính toán risk/reward ratio"""
        if self.signal_type == SignalType.LONG:
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
        else:
            risk = abs(self.stop_loss - self.entry_price)
            reward = abs(self.entry_price - self.take_profit)
        
        self.risk_reward_ratio = reward / risk if risk > 0 else 0
    
    @property
    def is_valid(self) -> bool:
        """Kiểm tra tín hiệu có hợp lệ không"""
        return (
            self.confidence_score >= 50 and
            self.risk_reward_ratio >= 1.5 and
            self.entry_price > 0 and
            self.stop_loss > 0 and
            self.take_profit > 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'signal_type': self.signal_type.value,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'confidence_score': self.confidence_score,
            'score': self.score,
            'quantity': self.quantity,
            'strength': self.strength.value,
            'strategy_name': self.strategy_name,
            'timestamp': self.timestamp.isoformat(),
            'risk_reward_ratio': self.risk_reward_ratio,
            'position_size': self.position_size,
            'indicators': self.indicators,
            'notes': self.notes,
            'reason': self.reason
        }

    def to_embed_fields(self) -> List[Dict[str, Any]]:
        """Tạo danh sách field tiếng Việt để gửi tín hiệu lên Discord embed."""
        fields = [
            {"name": "Symbol", "value": self.symbol, "inline": True},
            {"name": "Timeframe", "value": self.timeframe, "inline": True},
            {"name": "Tín hiệu", "value": self.signal_type.value, "inline": True},
            {"name": "Entry", "value": str(self.entry_price), "inline": True},
            {"name": "Stop Loss", "value": str(self.stop_loss), "inline": True},
            {"name": "Take Profit", "value": str(self.take_profit), "inline": True},
            {"name": "Quantity", "value": str(self.quantity), "inline": True},
            {"name": "Risk/Reward", "value": f"{self.risk_reward_ratio:.2f}", "inline": True},
            {"name": "Confidence", "value": f"{self.confidence_score:.1f}%", "inline": True},
            {"name": "Score", "value": str(self.score), "inline": True},
            {"name": "Độ mạnh", "value": self.strength.name, "inline": True},
            {"name": "Strategy", "value": self.strategy_name, "inline": True},
            {"name": "Lý do", "value": self.reason or self.notes or "Không có ghi chú", "inline": False},
        ]
        entry_basis = self.indicators.get("entry_basis") if isinstance(self.indicators, dict) else None
        if entry_basis:
            fields.insert(4, {"name": "Điểm vào tốt", "value": str(entry_basis), "inline": True})
        trend_context = self.indicators.get("trend_context") if isinstance(self.indicators, dict) else None
        if trend_context:
            from app.services.discord.formatters import format_trend_context

            fields.insert(5, {"name": "Bối cảnh trend", "value": format_trend_context(trend_context), "inline": True})
        entry_reference = self.indicators.get("entry_reference_level") if isinstance(self.indicators, dict) else None
        if entry_reference:
            fields.insert(6, {"name": "Level tham chiếu", "value": str(entry_reference), "inline": True})
        return fields
