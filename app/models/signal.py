"""
Models cho tín hiệu trading
Định nghĩa cấu trúc tín hiệu và các thông tin liên quan
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
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
    
    # Thông tin chi tiết
    indicators: Dict[str, Any]
    notes: str = ""
    risk_reward_ratio: Optional[float] = None
    position_size: Optional[float] = None
    
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
            'strength': self.strength.value,
            'strategy_name': self.strategy_name,
            'timestamp': self.timestamp.isoformat(),
            'risk_reward_ratio': self.risk_reward_ratio,
            'position_size': self.position_size,
            'indicators': self.indicators,
            'notes': self.notes
        }