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
    
    def get_signal(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
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
        direction = 'NEUTRAL'
        if self.has_columns(df, [rsi_col]):
            rsi_current = latest[rsi_col]
            rsi_prev = prev[rsi_col]
            
            # RSI quá bán và đảo chiều tăng
            if rsi_current < RSI_OVERSOLD and rsi_current > rsi_prev:
                score += 35
                reasons.append(f"RSI bật từ vùng quá bán ({rsi_current:.1f})")
                condition = 'OVERSOLD_REVERSAL'
                direction = 'UP'

            # RSI vừa thoát quá bán, thường là điểm xác nhận sớm cho reversal LONG.
            elif rsi_prev <= RSI_OVERSOLD and RSI_OVERSOLD < rsi_current <= 40 and rsi_current > rsi_prev:
                score += 25
                reasons.append(f"RSI hồi phục khỏi vùng quá bán ({rsi_current:.1f})")
                condition = 'OVERSOLD_RECOVERY'
                direction = 'UP'
            
            # RSI quá mua và đảo chiều giảm
            elif rsi_current > RSI_OVERBOUGHT and rsi_current < rsi_prev:
                score += 35
                reasons.append(f"RSI quay đầu từ vùng quá mua ({rsi_current:.1f})")
                condition = 'OVERBOUGHT_REVERSAL'
                direction = 'DOWN'

            # RSI vừa rơi khỏi quá mua, thường là điểm xác nhận sớm cho reversal SHORT.
            elif RSI_OVERBOUGHT > rsi_current >= 60 and rsi_prev >= RSI_OVERBOUGHT and rsi_current < rsi_prev:
                score += 25
                reasons.append(f"RSI bị từ chối khỏi vùng quá mua ({rsi_current:.1f})")
                condition = 'OVERBOUGHT_REJECTION'
                direction = 'DOWN'
            
            # RSI ở trung tính nhưng có momentum mạnh
            elif 40 <= rsi_current <= 60:
                if abs(rsi_current - rsi_prev) > 5:
                    score += 15
                    direction = "UP" if rsi_current > rsi_prev else "DOWN"
                    direction_label = "tăng" if direction == "UP" else "giảm"
                    reasons.append(f"RSI momentum {direction_label} mạnh")
        
        # 2. Stochastic %K %D Cross
        if self.has_columns(df, ['STOCHk_14_3_3', 'STOCHd_14_3_3']):
            k_current = latest['STOCHk_14_3_3']
            d_current = latest['STOCHd_14_3_3']
            k_prev = prev['STOCHk_14_3_3']
            d_prev = prev['STOCHd_14_3_3']
            
            # Bullish cross dưới 20 (oversold)
            if k_current > d_current and k_prev <= d_prev and k_current < 20:
                score += 25
                reasons.append("Stoch bullish cross vùng oversold")
                condition = 'OVERSOLD_REVERSAL'
                direction = 'UP'
            
            # Bearish cross trên 80 (overbought)
            elif k_current < d_current and k_prev >= d_prev and k_current > 80:
                score += 25
                reasons.append("Stoch bearish cross vùng overbought")
                condition = 'OVERBOUGHT_REVERSAL'
                direction = 'DOWN'
        
        # 3. Williams %R Confirmation
        if self.has_columns(df, ['WILLR_14']):
            willr = latest['WILLR_14']
            if willr < -80:  # Oversold
                score += 10
                reasons.append("Williams %R xác nhận oversold")
            elif willr > -20:  # Overbought
                score += 10
                reasons.append("Williams %R xác nhận overbought")
        
        result = {
            'score': score,
            'condition': condition,
            'direction': direction,
            'reasons': reasons
        }
        self._print_debug_signal(latest, prev, result, symbol)
        return result

    def _print_debug_signal(self, latest: pd.Series, prev: pd.Series, signal: Dict[str, Any], symbol: str = ""):
        """In chi tiết giá trị momentum và điểm vừa được tính."""
        rsi_col = f'RSI_{RSI_PERIOD}'
        print(
            f"{self._debug_prefix(symbol)}⚡ INDICATOR MOMENTUM | "
            f"rsi={self._debug_number(latest.get(rsi_col))} "
            f"rsi_prev={self._debug_number(prev.get(rsi_col))} "
            f"stoch_k={self._debug_number(latest.get('STOCHk_14_3_3'))} "
            f"stoch_d={self._debug_number(latest.get('STOCHd_14_3_3'))} "
            f"stoch_k_prev={self._debug_number(prev.get('STOCHk_14_3_3'))} "
            f"stoch_d_prev={self._debug_number(prev.get('STOCHd_14_3_3'))} "
            f"willr={self._debug_number(latest.get('WILLR_14'))} "
            f"score={signal.get('score', 0)} "
            f"direction={signal.get('direction', 'NEUTRAL')} "
            f"condition={signal.get('condition', 'NEUTRAL')} "
            f"reasons={self._debug_reasons(signal.get('reasons', []))}"
        )
