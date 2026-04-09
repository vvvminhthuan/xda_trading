from pandas import DataFrame
import pandas as pd
from typing import Dict, List
from app.constants import *

class CandleFrames:
    """Lớp quản lý dữ liệu nến (OHLCV) cho nhiều khung thời gian khác nhau.
    Dữ liệu được lưu trữ trong một dictionary với key là timeframe và value là DataFrame chứa dữ liệu nến.
    """
    def __init__(self):
        self._data_frame: Dict[str, DataFrame] = {}
        self.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

    def get(self, timeframe: str) -> DataFrame:
        """Lấy dữ liệu theo khung thời gian."""
        return self._data_frame.get(timeframe, DataFrame())
    
    def set(self, timeframe: str, value: List[List]):
        """Cập nhật dữ liệu cho các khung thời gian."""
        if not all(col in value.columns for col in self.columns):
            raise ValueError(f"DataFrame cho timeframe {timeframe} thiếu cột cần thiết")
        df = value[self.columns].copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        self._data_frame[timeframe] = df.tail(MAX_CANDLES_LIMIT)  # Giữ lại 1000 nến gần nhất

    def append(self, timeframe: str, value: List):
        """
            Cập nhật dữ liệu cho một khung thời gian cụ thể. 
            cho một thời điểm timestamp cụ thể.
            @param value: Danh sách giá trị theo thứ tự
            ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        new_df = DataFrame([value], columns=self.columns)
        new_df.set_index('timestamp', inplace=True)
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        if timeframe in self._data_frame:
            df = self._data_frame[timeframe]
            df = pd.concat([df, new_df])
            df = df[~df.index.duplicated(keep='last')]
            df.sort_index(inplace=True)
            self._data_frame[timeframe] = df.tail(MAX_CANDLES_LIMIT)  # Giữ lại 1000 nến gần nhất
        else:
            self._data_frame[timeframe] = new_df
        