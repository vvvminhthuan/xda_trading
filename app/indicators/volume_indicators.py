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

        self._add_volume_profile(df)
        
        return df

    def _add_volume_profile(self, df: pd.DataFrame, lookback: int = 100, bins: int = 24):
        """Tính POC, VAH và VAL cơ bản từ phân bố volume theo vùng giá gần nhất."""
        if len(df) < 20:
            return
        recent = df.tail(min(lookback, len(df)))
        price_min = recent['low'].min()
        price_max = recent['high'].max()
        if price_max <= price_min:
            return

        price_bins = pd.cut(recent['close'], bins=bins)
        volume_by_bin = recent.groupby(price_bins, observed=False)['volume'].sum()
        if volume_by_bin.empty:
            return

        poc_interval = volume_by_bin.idxmax()
        total_volume = volume_by_bin.sum()
        value_area = volume_by_bin.sort_values(ascending=False).cumsum() <= total_volume * 0.7
        selected_bins = volume_by_bin.sort_values(ascending=False)[value_area].index
        if len(selected_bins) == 0:
            selected_bins = [poc_interval]

        df.loc[df.index[-1], 'POC'] = float(poc_interval.mid)
        df.loc[df.index[-1], 'VAH'] = float(max(interval.right for interval in selected_bins))
        df.loc[df.index[-1], 'VAL'] = float(min(interval.left for interval in selected_bins))
    
    def get_signal(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """Phân tích tín hiệu từ volume"""
        if len(df) < 3:
            return {'score': 0, 'volume_condition': 'UNKNOWN', 'reasons': []}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        reasons = []
        volume_condition = 'NORMAL'
        direction = 'NEUTRAL'
        price_change = 0.0
        
        # 1. Volume Spike Analysis (Smart Money Detection)
        if self.has_columns(df, ['Volume_SMA_20']):
            vol_avg = latest['Volume_SMA_20']
            current_vol = latest['volume']
            
            # Volume spike với price movement cùng chiều
            if vol_avg > 0 and current_vol > vol_avg * 2:  # Volume gấp đôi trung bình
                price_change = (latest['close'] - prev['close']) / prev['close']
                
                if abs(price_change) > 0.01:  # Price change > 1%
                    score += 40
                    direction = "tăng" if price_change > 0 else "giảm"
                    reasons.append(f"Volume spike xác nhận {direction} giá")
                    direction = 'UP' if price_change > 0 else 'DOWN'
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
        if self.has_columns(df, ['OBV']) and len(df) >= 5:
            obv_current = latest['OBV']
            obv_prev = df.iloc[-3]['OBV']  # So sánh với 3 nến trước
            price_current = latest['close']
            price_prev = df.iloc[-3]['close']
            
            # Bullish divergence: Price giảm, OBV tăng
            if price_current < price_prev and obv_current > obv_prev:
                score += 35
                reasons.append("OBV Bullish Divergence")
                volume_condition = 'BULLISH_DIVERGENCE'
                direction = 'UP'
            
            # Bearish divergence: Price tăng, OBV giảm
            elif price_current > price_prev and obv_current < obv_prev:
                score += 35
                reasons.append("OBV Bearish Divergence")
                volume_condition = 'BEARISH_DIVERGENCE'
                direction = 'DOWN'
        
        # 3. VWAP Analysis
        if self.has_columns(df, ['VWAP']) and latest['VWAP'] != 0:
            price_vs_vwap = (latest['close'] - latest['VWAP']) / latest['VWAP'] * 100
            
            if abs(price_vs_vwap) > 2:  # Price khác VWAP > 2%
                score += 15
                if price_vs_vwap > 0:
                    reasons.append(f"Giá trên VWAP {price_vs_vwap:.1f}% (Bullish bias)")
                    if direction == 'NEUTRAL': direction = 'UP'
                else:
                    reasons.append(f"Giá dưới VWAP {price_vs_vwap:.1f}% (Bearish bias)")
                    if direction == 'NEUTRAL': direction = 'DOWN'
        
        # 4. Accumulation/Distribution Analysis
        if self.has_columns(df, ['AD']):
            ad_current = latest['AD']
            ad_prev = prev['AD']
            
            if ad_current > ad_prev:
                score += 20
                reasons.append("A/D Line tăng - Accumulation")
            else:
                score += 10
                reasons.append("A/D Line giảm - Distribution")
        
        volume_ratio = latest['volume'] / latest.get('Volume_SMA_20', 1) if self.has_columns(df, ['Volume_SMA_20']) and latest.get('Volume_SMA_20', 0) else 1
        result = {
            'score': score,
            'volume_condition': volume_condition,
            'direction': direction,
            'reasons': reasons,
            'volume_ratio': volume_ratio,
            'poc': latest.get('POC'),
            'vah': latest.get('VAH'),
            'val': latest.get('VAL')
        }
        self._print_debug_signal(latest, result, price_change, symbol)
        return result

    def _print_debug_signal(self, latest: pd.Series, signal: Dict[str, Any], price_change: float, symbol: str = ""):
        """In chi tiết giá trị volume và điểm vừa được tính."""
        print(
            f"{self._debug_prefix(symbol)}📦 INDICATOR VOLUME | "
            f"volume={self._debug_number(latest.get('volume'))} "
            f"volume_sma={self._debug_number(latest.get('Volume_SMA_20'))} "
            f"volume_ratio={self._debug_number(signal.get('volume_ratio'))} "
            f"price_change={self._debug_number(price_change * 100)}% "
            f"obv={self._debug_number(latest.get('OBV'))} "
            f"vwap={self._debug_number(latest.get('VWAP'))} "
            f"ad={self._debug_number(latest.get('AD'))} "
            f"poc={self._debug_number(signal.get('poc'))} "
            f"vah={self._debug_number(signal.get('vah'))} "
            f"val={self._debug_number(signal.get('val'))} "
            f"score={signal.get('score', 0)} "
            f"direction={signal.get('direction', 'NEUTRAL')} "
            f"condition={signal.get('volume_condition', 'UNKNOWN')} "
            f"reasons={self._debug_reasons(signal.get('reasons', []))}"
        )
