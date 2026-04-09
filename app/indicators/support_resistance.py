import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Dict, Any, List, Tuple
from .base_indicator import BaseIndicator

class SupportResistance(BaseIndicator):
    """
    Phân tích Support/Resistance, Fibonacci Retracements, Pivot Points.
    Ý nghĩa: Tìm các vùng giá quan trọng để vào lệnh và đặt target.
    """
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các mức hỗ trợ kháng cự"""
        if not self.validate_data(df, 50):
            return df
        
        # Pivot Points (Daily)
        self._add_pivot_points(df)
        
        # Fibonacci levels
        self._add_fibonacci_levels(df)
        
        # Dynamic Support/Resistance từ Swing High/Low
        self._add_swing_levels(df)
        
        return df
    
    def _add_pivot_points(self, df: pd.DataFrame):
        """Thêm Pivot Points (PP, R1, R2, S1, S2)"""
        if len(df) < 1:
            return
            
        # Sử dụng High, Low, Close của ngày hôm trước (hoặc session trước)
        high = df['high'].rolling(window=20).max()
        low = df['low'].rolling(window=20).min() 
        close = df['close']
        
        # Standard Pivot Points
        df['PP'] = (high + low + close) / 3
        df['R1'] = 2 * df['PP'] - low
        df['R2'] = df['PP'] + (high - low)
        df['S1'] = 2 * df['PP'] - high
        df['S2'] = df['PP'] - (high - low)
        
    def _add_fibonacci_levels(self, df: pd.DataFrame, lookback=50):
        """Thêm Fibonacci Retracement levels"""
        if len(df) < lookback:
            return
            
        # Tìm Swing High và Swing Low trong lookback periods
        swing_high = df['high'].rolling(window=lookback).max()
        swing_low = df['low'].rolling(window=lookback).min()
        
        # Fibonacci ratios
        fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        for ratio in fib_ratios:
            # Fibonacci Retracement (từ high về low)
            df[f'FIB_{int(ratio*1000)}'] = swing_high - (swing_high - swing_low) * ratio
            
    def _add_swing_levels(self, df: pd.DataFrame, window=10):
        """Tìm Swing High/Low để làm Support/Resistance động"""
        if len(df) < window * 2:
            return
            
        # Swing High: Local maxima
        df['SwingHigh'] = df['high'].rolling(window=window, center=True).apply(
            lambda x: x.iloc[window//2] if x.iloc[window//2] == x.max() else np.nan
        )
        
        # Swing Low: Local minima  
        df['SwingLow'] = df['low'].rolling(window=window, center=True).apply(
            lambda x: x.iloc[window//2] if x.iloc[window//2] == x.min() else np.nan
        )
        
    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Phân tích tín hiệu Support/Resistance"""
        if len(df) < 5:
            return {'score': 0, 'sr_condition': 'UNKNOWN', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        sr_condition = 'NEUTRAL'
        
        current_price = latest['close']
        
        # 1. Pivot Points Analysis
        if 'PP' in df.columns:
            pp = latest['PP']
            r1 = latest['R1'] 
            s1 = latest['S1']
            
            # Price near Pivot levels
            pp_distance = abs(current_price - pp) / pp * 100
            r1_distance = abs(current_price - r1) / r1 * 100
            s1_distance = abs(current_price - s1) / s1 * 100
            
            if pp_distance < 0.5:  # Within 0.5% of Pivot
                score += 25
                reasons.append(f"Gần Pivot Point ({pp:.2f})")
                sr_condition = 'PIVOT_TEST'
                
            elif r1_distance < 0.5:  # Near Resistance 1
                score += 30
                reasons.append(f"Test R1 ({r1:.2f})")
                sr_condition = 'RESISTANCE_TEST'
                
            elif s1_distance < 0.5:  # Near Support 1
                score += 30
                reasons.append(f"Test S1 ({s1:.2f})")
                sr_condition = 'SUPPORT_TEST'
        
        # 2. Fibonacci Levels
        fib_levels = ['FIB_236', 'FIB_382', 'FIB_500', 'FIB_618', 'FIB_786']
        for fib_col in fib_levels:
            if fib_col in df.columns:
                fib_level = latest[fib_col]
                if pd.notna(fib_level):
                    distance = abs(current_price - fib_level) / fib_level * 100
                    if distance < 0.8:  # Within 0.8% of Fib level
                        fib_ratio = fib_col.split('_')[1]
                        score += 35
                        reasons.append(f"Test Fibonacci {fib_ratio}% ({fib_level:.2f})")
                        sr_condition = 'FIBONACCI_TEST'
                        break
        
        # 3. Swing High/Low Analysis
        if 'SwingHigh' in df.columns and 'SwingLow' in df.columns:
            # Tìm nearest swing levels
            recent_df = df.tail(20)  # 20 nến gần nhất
            
            recent_swing_highs = recent_df['SwingHigh'].dropna()
            recent_swing_lows = recent_df['SwingLow'].dropna()
            
            # Check if price is near recent swing levels
            for swing_high in recent_swing_highs:
                distance = abs(current_price - swing_high) / swing_high * 100
                if distance < 1.0:  # Within 1% of swing high
                    score += 25
                    reasons.append(f"Test Swing High ({swing_high:.2f})")
                    sr_condition = 'SWING_RESISTANCE'
                    break
            
            for swing_low in recent_swing_lows:
                distance = abs(current_price - swing_low) / swing_low * 100
                if distance < 1.0:  # Within 1% of swing low
                    score += 25
                    reasons.append(f"Test Swing Low ({swing_low:.2f})")
                    sr_condition = 'SWING_SUPPORT'
                    break
        
        # 4. Multiple timeframe confluence
        # (Nếu cùng 1 level được test trên nhiều timeframe -> score cao hơn)
        confluence_bonus = 0
        if len(reasons) >= 2:  # Có ít nhất 2 lý do S/R
            confluence_bonus = 20
            reasons.append("Confluence multiple S/R levels")
        
        return {
            'score': score + confluence_bonus,
            'sr_condition': sr_condition, 
            'reasons': reasons,
            'key_levels': {
                'pivot': latest.get('PP'),
                'r1': latest.get('R1'),
                's1': latest.get('S1')
            }
        }