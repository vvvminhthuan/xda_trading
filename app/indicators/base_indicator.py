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
    def get_signal(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """
        Phân tích tín hiệu từ chỉ báo.
        Returns:
            Dictionary chứa thông tin tín hiệu và điểm số
        """
        pass
    
    def validate_data(self, df: pd.DataFrame, min_periods: int = 20) -> bool:
        """Kiểm tra dữ liệu có đủ để tính toán không"""
        required_columns = {'open', 'high', 'low', 'close', 'volume'}
        return len(df) >= min_periods and not df.empty and required_columns.issubset(df.columns)

    def has_columns(self, df: pd.DataFrame, columns: list[str]) -> bool:
        """Kiểm tra các cột indicator đã tồn tại và giá trị dòng cuối không bị NaN."""
        if not all(column in df.columns for column in columns):
            return False
        return not df[columns].tail(1).isna().any().any()

    def _debug_number(self, value, precision: int = 4) -> str:
        """Định dạng số để in log indicator, tránh lỗi khi giá trị thiếu hoặc NaN."""
        if value is None or pd.isna(value):
            return "unknown"
        try:
            return f"{float(value):.{precision}f}"
        except (TypeError, ValueError):
            return str(value)

    def _debug_reasons(self, reasons: list, limit: int = 5) -> str:
        """Chuyển danh sách lý do cộng điểm thành chuỗi ngắn để in log."""
        if not reasons:
            return "none"
        return " | ".join(str(reason) for reason in reasons[:limit])

    def _debug_prefix(self, symbol: str) -> str:
        """Tạo prefix symbol cho log khi bot theo dõi nhiều symbol cùng lúc."""
        return f"{symbol} | " if symbol else ""
