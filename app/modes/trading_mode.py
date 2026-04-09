from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class TradingModeType(Enum):
    """Các loại chế độ giao dịch"""
    CONSERVATIVE = "conservative"  # Bảo thủ - chỉ tín hiệu cực mạnh
    AGGRESSIVE = "aggressive"     # Tích cực - nhiều tín hiệu hơn
    SCALPING = "scalping"        # Scalp - timeframe nhỏ
    SWING = "swing"              # Swing - timeframe lớn

@dataclass
class TradingModeConfig:
    """Cấu hình cho từng chế độ giao dịch"""
    mode_type: TradingModeType
    min_win_probability: float
    min_score: int
    primary_timeframes: List[str]
    safe_timeframes: List[str]
    risk_per_trade: float
    max_signals_per_hour: int
    
class TradingMode:
    """
    Quản lý các chế độ giao dịch khác nhau.
    Cho phép chuyển đổi giữa các strategies tùy theo điều kiện thị trường.
    """
    
    MODES = {
        TradingModeType.CONSERVATIVE: TradingModeConfig(
            mode_type=TradingModeType.CONSERVATIVE,
            min_win_probability=80.0,
            min_score=70,
            primary_timeframes=['3m', '5m'],
            safe_timeframes=['1h', '4h'], 
            risk_per_trade=0.5,
            max_signals_per_hour=2
        ),
        
        TradingModeType.AGGRESSIVE: TradingModeConfig(
            mode_type=TradingModeType.AGGRESSIVE,
            min_win_probability=65.0,
            min_score=50,
            primary_timeframes=['1m', '3m'],
            safe_timeframes=['1h', '2h'],
            risk_per_trade=1.5,
            max_signals_per_hour=8
        ),
        
        TradingModeType.SCALPING: TradingModeConfig(
            mode_type=TradingModeType.SCALPING,
            min_win_probability=70.0,
            min_score=60,
            primary_timeframes=['1m'],
            safe_timeframes=['5m', '15m'],
            risk_per_trade=2.0,
            max_signals_per_hour=15
        ),
        
        TradingModeType.SWING: TradingModeConfig(
            mode_type=TradingModeType.SWING,
            min_win_probability=75.0,
            min_score=65,
            primary_timeframes=['1h', '2h'],
            safe_timeframes=['4h', '1d'],
            risk_per_trade=1.0,
            max_signals_per_hour=1
        )
    }
    
    def __init__(self, mode_type: TradingModeType = TradingModeType.CONSERVATIVE):
        self.current_mode = mode_type
        self.config = self.MODES[mode_type]
        
    def switch_mode(self, new_mode: TradingModeType):
        """Chuyển đổi chế độ giao dịch"""
        self.current_mode = new_mode
        self.config = self.MODES[new_mode]
        print(f"🔄 Chuyển sang chế độ: {new_mode.value.upper()}")
        
    def should_send_signal(self, win_prob: float, score: int) -> bool:
        """Kiểm tra xem có nên gửi tín hiệu không dựa trên chế độ hiện tại"""
        return (win_prob >= self.config.min_win_probability and 
                score >= self.config.min_score)
                
    def get_timeframes(self) -> Dict[str, List[str]]:
        """Trả về timeframes cho chế độ hiện tại"""
        return {
            'primary': self.config.primary_timeframes,
            'safe': self.config.safe_timeframes
        }
        
    def get_risk_config(self) -> Dict[str, float]:
        """Trả về cấu hình risk cho chế độ hiện tại"""
        return {
            'risk_per_trade': self.config.risk_per_trade,
            'min_win_prob': self.config.min_win_probability,
            'min_score': self.config.min_score
        }