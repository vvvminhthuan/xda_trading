import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from .base_indicator import BaseIndicator
from app.constants.indicator_constants import *

class MomentumIndicators(BaseIndicator):
    """
    Chỉ báo động lực: RSI, Stochastic, Williams %R.
    Ý nghĩa: Đo lường tốc độ và sức mạnh của chuyển động giá (quá mua/quá bán).
    """
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các chỉ báo động lực"""
        if not self.validate_data(df, 20):
            return df
        
        # RSI - Chỉ số sức mạnh tương đối
        df[f'RSI_{RSI_PERIOD}'] = ta.rsi(df['close'], length=RSI_PERIOD)
        
        # Stochastic Oscillator
        stoch_data = ta.stoch(df['high'], df['low'], df['close'])
        if stoch_data is not None:
            df = pd.concat([df, stoch_data], axis=1)
        
        # Williams %R
        df['WILLR_14'] = ta.willr(df['high'], df['low'], df['close'], length=14)
        
        return df
    
    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Phân tích tín hiệu động lực"""
        if len(df) < 3:
            return {'score': 0, 'condition': 'NEUTRAL', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        condition = 'NEUTRAL'
        
        rsi_col = f'RSI_{RSI_PERIOD}'
        
        # 1. RSI Oversold/Overbought với Divergence
        if rsi_col in df.columns:
            rsi_current = latest[rsi_col]
            rsi_prev = prev[rsi_col]
            
            # RSI quá bán và đảo chiều tăng
            if rsi_current < RSI_OVERSOLD and rsi_current > rsi_prev:
                score += 35
                reasons.append(f"RSI bật từ vùng quá bán ({rsi_current:.1f})")
                condition = 'OVERSOLD_REVERSAL'
            
            # RSI quá mua và đảo chiều giảm
            elif rsi_current > RSI_OVERBOUGHT and rsi_current < rsi_prev:
                score += 35
                reasons.append(f"RSI quay đầu từ vùng quá mua ({rsi_current:.1f})")
                condition = 'OVERBOUGHT_REVERSAL'
            
            # RSI ở trung tính nhưng có momentum mạnh
            elif 40 <= rsi_current <= 60:
                if abs(rsi_current - rsi_prev) > 5:
                    score += 15
                    direction = "tăng" if rsi_current > rsi_prev else "giảm"
                    reasons.append(f"RSI momentum {direction} mạnh")
        
        # 2. Stochastic %K %D Cross
        if 'STOCHk_14_3_3' in df.columns and 'STOCHd_14_3_3' in df.columns:
            k_current = latest['STOCHk_14_3_3']
            d_current = latest['STOCHd_14_3_3']
            k_prev = prev['STOCHk_14_3_3']
            d_prev = prev['STOCHd_14_3_3']
            
            # Bullish cross dưới 20 (oversold)
            if k_current > d_current and k_prev <= d_prev and k_current < 20:
                score += 25
                reasons.append("Stoch bullish cross vùng oversold")
                condition = 'OVERSOLD_REVERSAL'
            
            # Bearish cross trên 80 (overbought)
            elif k_current < d_current and k_prev >= d_prev and k_current > 80:
                score += 25
                reasons.append("Stoch bearish cross vùng overbought")
                condition = 'OVERBOUGHT_REVERSAL'
        
        # 3. Williams %R Confirmation
        if 'WILLR_14' in df.columns:
            willr = latest['WILLR_14']
            if willr < -80:  # Oversold
                score += 10
                reasons.append("Williams %R xác nhận oversold")
            elif willr > -20:  # Overbought
                score += 10
                reasons.append("Williams %R xác nhận overbought")
        
        return {
            'score': score,
            'condition': condition,
            'reasons': reasons
        }