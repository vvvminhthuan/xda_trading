import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseIndicator(ABC):
    """
    Lớp cơ sở cho tất cả các chỉ báo kỹ thuật.
    Cho phép kế thừa và tùy chỉnh các tham số.
    """
    
    def __init__(self, **kwargs):
        self.params = kwargs
        
    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Tính toán chỉ báo và thêm vào DataFrame.
        Args:
            df: DataFrame chứa OHLCV
        Returns:
            DataFrame với các cột chỉ báo mới
        """
        pass
    
    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Phân tích tín hiệu từ chỉ báo.
        Returns:
            Dictionary chứa thông tin tín hiệu và điểm số
        """
        pass
    
    def validate_data(self, df: pd.DataFrame, min_periods: int = 20) -> bool:
        """Kiểm tra dữ liệu có đủ để tính toán không"""
        return len(df) >= min_periods and not df.empty