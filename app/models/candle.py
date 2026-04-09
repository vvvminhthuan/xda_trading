"""
Models cho dữ liệu nến (OHLCV)
Định nghĩa cấu trúc dữ liệu nến và các phương thức xử lý
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import pandas as pd
from app.constants import MAX_CANDLES_LIMIT 

@dataclass
class Candle:
    """
    Đại diện cho một nến trong biểu đồ
    """
    def __init__(self, timestamp: int, open: float, high: float, low: float, close: float, volume: float):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    
    @property
    def datetime(self) -> datetime:
        """Chuyển đổi timestamp sang datetime"""
        return datetime.fromtimestamp(self.timestamp / 1000)
    
    @property
    def is_bullish(self) -> bool:
        """Kiểm tra nến tăng"""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Kiểm tra nến giảm"""
        return self.close < self.open
    
    @property
    def body_size(self) -> float:
        """Kích thước thân nến"""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        """Bóng trên"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        """Bóng dưới"""
        return min(self.open, self.close) - self.low

class CandleData:
    """
    Quản lý tập hợp dữ liệu nến
    """
    def __init__(self, symbol: str, timeframe: str, max_size: int = MAX_CANDLES_LIMIT):
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_size = max_size
        self.candles: List[Candle] = []
        self._df: Optional[pd.DataFrame] = None
        self._is_dirty = True
    
    def add_candle(self, candle: Candle):
        """Thêm nến mới"""
        self.candles.append(candle)
        if len(self.candles) > self.max_size:
            self.candles.pop(0)
        self._is_dirty = True
    
    def add_candles(self, candles: List[Candle]):
        """Thêm nhiều nến"""
        for candle in candles:
            self.add_candle(candle)
    
    @property
    def df(self) -> pd.DataFrame:
        """Chuyển đổi sang DataFrame để tính toán indicator"""
        if self._is_dirty or self._df is None:
            data = []
            for candle in self.candles:
                data.append({
                    'timestamp': candle.timestamp,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                })
            self._df = pd.DataFrame(data)
            self._df['datetime'] = pd.to_datetime(self._df['timestamp'], unit='ms')
            self._df.set_index('datetime', inplace=True)
            self._is_dirty = False
        return self._df
    
    @property
    def latest_candle(self) -> Optional[Candle]:
        """Nến mới nhất"""
        return self.candles[-1] if self.candles else None
    
    def get_recent_candles(self, count: int) -> List[Candle]:
        """Lấy n nến gần nhất"""
        return self.candles[-count:] if len(self.candles) >= count else self.candles