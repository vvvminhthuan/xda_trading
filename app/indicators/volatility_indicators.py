import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from .base_indicator import BaseIndicator
from app.constants.indicator_constants import *

class VolatilityIndicators(BaseIndicator):
    """
    Chỉ báo biến động: Bollinger Bands, ATR, Donchian Channel.
    Ý nghĩa: Đo lường mức độ biến động của giá để đặt Stop Loss phù hợp.
    """
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các chỉ báo biến động"""
        if not self.validate_data(df):
            return df
        
        # Bollinger Bands
        bb_data = ta.bbands(df['close'], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bb_data is not None:
            df = pd.concat([df, bb_data], axis=1)
        
        # Average True Range (ATR)
        df[f'ATR_{ATR_PERIOD}'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD)
        df[f'ATRr_{ATR_PERIOD}'] = ta.atr(df['high'], df['low'], df['close'], length=ATR_PERIOD) / df['close'] * 100
        
        # Donchian Channel
        donchian_data = ta.donchian(df['high'], df['low'], lower_length=20, upper_length=20)
        if donchian_data is not None:
            df = pd.concat([df, donchian_data], axis=1)
            
        # Keltner Channel
        kc_data = ta.kc(df['high'], df['low'], df['close'])
        if kc_data is not None:
            df = pd.concat([df, kc_data], axis=1)
        
        return df
    
    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Phân tích tín hiệu từ volatility"""
        if len(df) < 3:
            return {'score': 0, 'volatility_state': 'UNKNOWN', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        volatility_state = 'NORMAL'
        
        bb_upper = f'BBU_{BOLLINGER_PERIOD}_{BOLLINGER_STD}'
        bb_lower = f'BBL_{BOLLINGER_PERIOD}_{BOLLINGER_STD}'
        bb_middle = f'BBM_{BOLLINGER_PERIOD}_{BOLLINGER_STD}'
        
        # 1. Bollinger Bands Squeeze/Expansion
        if all(col in df.columns for col in [bb_upper, bb_lower, bb_middle]):
            bb_width = latest[bb_upper] - latest[bb_lower]
            bb_width_prev = prev[bb_upper] - prev[bb_lower]
            
            # Price touching Bollinger Bands (Support/Resistance levels)
            if latest['low'] <= latest[bb_lower]:
                score += 30
                reasons.append("Chạm dải dưới Bollinger (Support động)")
                volatility_state = 'SUPPORT_TEST'
                
            elif latest['high'] >= latest[bb_upper]:
                score += 30
                reasons.append("Chạm dải trên Bollinger (Resistance động)")
                volatility_state = 'RESISTANCE_TEST'
            
            # Bollinger Squeeze (Low volatility -> potential breakout)
            elif bb_width < bb_width_prev * 0.8:
                score += 20
                reasons.append("Bollinger Squeeze - Chuẩn bị breakout")
                volatility_state = 'SQUEEZE'
            
            # Bollinger Expansion (High volatility)
            elif bb_width > bb_width_prev * 1.2:
                score += 15
                reasons.append("Bollinger Expansion - Biến động cao")
                volatility_state = 'EXPANSION'
        
        # 2. ATR Analysis (Risk management)
        atr_col = f'ATR_{ATR_PERIOD}'
        atr_pct_col = f'ATRr_{ATR_PERIOD}'
        
        if atr_pct_col in df.columns:
            atr_pct = latest[atr_pct_col]
            
            # High volatility warning
            if atr_pct > 3.0:  # ATR > 3% của giá
                score += 10
                reasons.append(f"Biến động cao (ATR: {atr_pct:.2f}%)")
                volatility_state = 'HIGH_VOLATILITY'
                
            # Low volatility (good for tight stops)
            elif atr_pct < 1.0:
                score += 15
                reasons.append(f"Biến động thấp (ATR: {atr_pct:.2f}%)")
                volatility_state = 'LOW_VOLATILITY'
        
        # 3. Keltner Channel Analysis
        if 'KCUe_20_2' in df.columns and 'KCLe_20_2' in df.columns:
            # Price breaking out of Keltner Channel
            if latest['close'] > latest['KCUe_20_2']:
                score += 25
                reasons.append("Breakout trên Keltner Channel")
            elif latest['close'] < latest['KCLe_20_2']:
                score += 25
                reasons.append("Breakdown dưới Keltner Channel")
        
        return {
            'score': score,
            'volatility_state': volatility_state,
            'reasons': reasons,
            'atr_value': latest.get(atr_col, 0),
            'atr_percentage': latest.get(atr_pct_col, 0)
        }