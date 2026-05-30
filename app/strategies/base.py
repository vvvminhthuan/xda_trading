from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Dict, Any
from app.models.signal import TradingSignal

class BaseStrategy(ABC):
    """
    Lớp cơ sở cho tất cả các chiến lược giao dịch.
    Cho phép kế thừa và tùy chỉnh các thuật toán.
    """
    
    def __init__(self, **config):
        self.config = config
        self.name = self.__class__.__name__
        
    @abstractmethod
    def analyze(self, market_data: Dict[str, pd.DataFrame], **kwargs) -> Optional[TradingSignal]:
        """
        Phân tích dữ liệu thị trường và tạo tín hiệu.
        Args:
            market_data: Dictionary chứa DataFrame cho mỗi timeframe
            kwargs: Các tham số runtime bổ sung như symbol hoặc timeframe.
        Returns:
            TradingSignal object hoặc None
        """
        pass
    
    @abstractmethod
    def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Kiểm tra tính hợp lệ của tín hiệu trước khi gửi.
        Returns:
            True nếu tín hiệu hợp lệ
        """
        pass
    
    def get_risk_parameters(self) -> Dict[str, float]:
        """Trả về các tham số quản lý rủi ro"""
        return {
            'max_risk_per_trade': self.config.get('max_risk_per_trade', 1.0),
            'min_risk_reward_ratio': self.config.get('min_risk_reward_ratio', 1.5),
            'max_drawdown': self.config.get('max_drawdown', 10.0)
        }
