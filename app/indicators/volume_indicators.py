import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
from .base_indicator import BaseIndicator

class VolumeIndicators(BaseIndicator):
    """
    Chỉ báo khối lượng: Volume, OBV, VWAP, Volume Profile.
    Ý nghĩa: Xác nhận sức mạnh của price action, phát hiện smart money.
    """
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các chỉ báo khối lượng"""
        if not self.validate_data(df):
            return df
        
        # On Balance Volume (OBV)
        df['OBV'] = ta.obv(df['close'], df['volume'])
        
        # Volume Weighted Average Price (VWAP)
        df['VWAP'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        
        # Volume Simple Moving Average
        df['Volume_SMA_20'] = ta.sma(df['volume'], length=20)
        
        # Price Volume Trend (PVT)
        df['PVT'] = ta.pvt(df['close'], df['volume'])
        
        # Accumulation/Distribution Line
        df['AD'] = ta.ad(df['high'], df['low'], df['close'], df['volume'])
        
        return df
    
    def get_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Phân tích tín hiệu từ volume"""
        if len(df) < 3:
            return {'score': 0, 'volume_condition': 'UNKNOWN', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        volume_condition = 'NORMAL'
        
        # 1. Volume Spike Analysis (Smart Money Detection)
        if 'Volume_SMA_20' in df.columns:
            vol_avg = latest['Volume_SMA_20']
            current_vol = latest['volume']
            
            # Volume spike với price movement cùng chiều
            if current_vol > vol_avg * 2:  # Volume gấp đôi trung bình
                price_change = (latest['close'] - prev['close']) / prev['close']
                
                if abs(price_change) > 0.01:  # Price change > 1%
                    score += 40
                    direction = "tăng" if price_change > 0 else "giảm"
                    reasons.append(f"Volume spike xác nhận {direction} giá")
                    volume_condition = 'VOLUME_SPIKE'
                else:
                    score += 10
                    reasons.append("Volume spike nhưng giá sideway")
                    volume_condition = 'VOLUME_SPIKE_NEUTRAL'
            
            # Low volume (lack of conviction)
            elif current_vol < vol_avg * 0.5:
                score -= 10
                reasons.append("Volume thấp - thiếu conviction")
                volume_condition = 'LOW_VOLUME'
        
        # 2. OBV Divergence
        if 'OBV' in df.columns and len(df) >= 5:
            obv_current = latest['OBV']
            obv_prev = df.iloc[-3]['OBV']  # So sánh với 3 nến trước
            price_current = latest['close']
            price_prev = df.iloc[-3]['close']
            
            # Bullish divergence: Price giảm, OBV tăng
            if price_current < price_prev and obv_current > obv_prev:
                score += 35
                reasons.append("OBV Bullish Divergence")
                volume_condition = 'BULLISH_DIVERGENCE'
            
            # Bearish divergence: Price tăng, OBV giảm
            elif price_current > price_prev and obv_current < obv_prev:
                score += 35
                reasons.append("OBV Bearish Divergence")
                volume_condition = 'BEARISH_DIVERGENCE'
        
        # 3. VWAP Analysis
        if 'VWAP' in df.columns:
            price_vs_vwap = (latest['close'] - latest['VWAP']) / latest['VWAP'] * 100
            
            if abs(price_vs_vwap) > 2:  # Price khác VWAP > 2%
                score += 15
                if price_vs_vwap > 0:
                    reasons.append(f"Giá trên VWAP {price_vs_vwap:.1f}% (Bullish bias)")
                else:
                    reasons.append(f"Giá dưới VWAP {price_vs_vwap:.1f}% (Bearish bias)")
        
        # 4. Accumulation/Distribution Analysis
        if 'AD' in df.columns:
            ad_current = latest['AD']
            ad_prev = prev['AD']
            
            if ad_current > ad_prev:
                score += 20
                reasons.append("A/D Line tăng - Accumulation")
            else:
                score += 10
                reasons.append("A/D Line giảm - Distribution")
        
        return {
            'score': score,
            'volume_condition': volume_condition,
            'reasons': reasons,
            'volume_ratio': latest['volume'] / latest.get('Volume_SMA_20', 1) if 'Volume_SMA_20' in df.columns else 1
        }