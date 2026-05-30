import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from app.indicators.base_indicator import BaseIndicator
from app.constants import *

class TrendIndicators(BaseIndicator):
    """
    Chỉ báo xu hướng: EMA, SMA, MACD, Ichimoku Cloud.
    Ý nghĩa: Xác định xu hướng chính của thị trường (tăng/giảm/sideway).
    """
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các chỉ báo xu hướng"""
        if not self.validate_data(df, 50):
            return df
            
        # Moving Averages - Đường trung bình động
        df[f'EMA_{EMA_FAST}'] = ta.ema(df['close'], length=EMA_FAST)
        df[f'EMA_{EMA_SLOW}'] = ta.ema(df['close'], length=EMA_SLOW)
        df['SMA_50'] = ta.sma(df['close'], length=50)
        df['SMA_200'] = ta.sma(df['close'], length=200)
        
        # MACD - Chỉ báo hội tụ phân kỳ
        macd_data = ta.macd(df['close'], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd_data is not None:
            df = pd.concat([df, macd_data], axis=1)
        
        # Ichimoku Cloud - Mây Ichimoku
        ichimoku_data = ta.ichimoku(df['high'], df['low'], df['close'])
        if ichimoku_data is not None:
            df = pd.concat([df, ichimoku_data[0]], axis=1)
            
        return df
    
    def get_signal(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """Phân tích tín hiệu xu hướng"""
        if len(df) < 3:
            return {'score': 0, 'direction': 'NEUTRAL', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        direction = 'NEUTRAL'
        
        # 1. Golden Cross / Death Cross (EMA 7 cắt EMA 26)
        ema_fast_col = f'EMA_{EMA_FAST}'
        ema_slow_col = f'EMA_{EMA_SLOW}'
        if self.has_columns(df, [ema_fast_col, ema_slow_col]):
            if (latest[ema_fast_col] > latest[ema_slow_col] and 
                prev[ema_fast_col] <= prev[ema_slow_col]):
                score += 40
                reasons.append("Golden Cross EMA")
                direction = 'UP'
            elif (latest[ema_fast_col] < latest[ema_slow_col] and 
                  prev[ema_fast_col] >= prev[ema_slow_col]):
                score += 40
                reasons.append("Death Cross EMA")
                direction = 'DOWN'
        
        # 2. MACD Bullish/Bearish Crossover
        macd_col = f'MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}'
        signal_col = f'MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}'
        
        if self.has_columns(df, [macd_col, signal_col]):
            if (latest[macd_col] > latest[signal_col] and 
                prev[macd_col] <= prev[signal_col]):
                score += 30
                reasons.append("MACD Bullish Cross")
                if direction != 'DOWN': direction = 'UP'
            elif (latest[macd_col] < latest[signal_col] and 
                  prev[macd_col] >= prev[signal_col]):
                score += 30
                reasons.append("MACD Bearish Cross")
                if direction != 'UP': direction = 'DOWN'
        
        # 3. Price vs SMA 200 (Xu hướng dài hạn)
        if self.has_columns(df, ['SMA_200']):
            if latest['close'] > latest['SMA_200']:
                score += 20
                reasons.append("Giá trên SMA 200")
                if direction == 'NEUTRAL': direction = 'UP'
            else:
                score += 20
                reasons.append("Giá dưới SMA 200")
                if direction == 'NEUTRAL': direction = 'DOWN'
        result = {
            'score': score,
            'direction': direction,
            'reasons': reasons,
            'strength': 'STRONG' if score >= 60 else 'WEAK'
        }
        self._print_debug_signal(latest, prev, result, symbol)
        return result

    def _print_debug_signal(self, latest: pd.Series, prev: pd.Series, signal: Dict[str, Any], symbol: str = ""):
        """In chi tiết giá trị xu hướng và điểm trend vừa được tính."""
        ema_fast_col = f'EMA_{EMA_FAST}'
        ema_slow_col = f'EMA_{EMA_SLOW}'
        macd_col = f'MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}'
        signal_col = f'MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}'
        print(
            f"{self._debug_prefix(symbol)}📈 INDICATOR TREND | "
            f"close={self._debug_number(latest.get('close'))} "
            f"ema_fast={self._debug_number(latest.get(ema_fast_col))} "
            f"ema_slow={self._debug_number(latest.get(ema_slow_col))} "
            f"prev_ema_fast={self._debug_number(prev.get(ema_fast_col))} "
            f"prev_ema_slow={self._debug_number(prev.get(ema_slow_col))} "
            f"macd={self._debug_number(latest.get(macd_col))} "
            f"macd_signal={self._debug_number(latest.get(signal_col))} "
            f"sma200={self._debug_number(latest.get('SMA_200'))} "
            f"score={signal.get('score', 0)} "
            f"direction={signal.get('direction', 'NEUTRAL')} "
            f"strength={signal.get('strength', 'WEAK')} "
            f"reasons={self._debug_reasons(signal.get('reasons', []))}"
        )
        
