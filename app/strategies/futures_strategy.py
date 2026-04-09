import pandas as pd
from typing import Dict, Optional
from app.models.signal import TradingSignal
from app.indicators import *
from app.constants import trading_constants as tc
from app.strategies.base_strategy import BaseStrategy
from app.modes.trading_mode import TradingMode, TradingModeType 

class MultiTimeframeFuturesStrategy(BaseStrategy):
    """
    Chiến lược Futures đa khung thời gian với hệ thống scoring tổng hợp.
    Tích hợp đầy đủ các chỉ báo kỹ thuật và chế độ giao dịch linh hoạt.
    """
    
    def __init__(self, **config):
        super().__init__(**config)
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.trading_mode = TradingMode(TradingModeType.CONSERVATIVE)
        
        # Initialize indicators
        self.trend_indicator = TrendIndicators()
        self.momentum_indicator = MomentumIndicators() 
        self.volatility_indicator = VolatilityIndicators()
        self.volume_indicator = VolumeIndicators()
        self.sr_indicator = SupportResistance()
        
    def update_data(self, timeframe: str, df: pd.DataFrame):
        """Cập nhật dữ liệu và tính toán tất cả indicators"""
        if len(df) < 50:
            self.market_data[timeframe] = df
            return
            
        # Tính toán tất cả indicators
        df = self.trend_indicator.calculate(df)
        df = self.momentum_indicator.calculate(df)
        df = self.volatility_indicator.calculate(df)
        df = self.volume_indicator.calculate(df)
        df = self.sr_indicator.calculate(df)
        
        self.market_data[timeframe] = df
        
    def analyze(self, timeframe: str = '1m') -> Optional[TradingSignal]:
        """Main analysis function tích hợp multi-timeframe và indicators"""
        
        # 1. Kiểm tra Safe Trend từ khung lớn
        safe_trend = self.is_safe_trend()
        if safe_trend == 'NEUTRAL':
            return None
            
        # 2. Phân tích từng loại indicator
        if timeframe not in self.market_data or len(self.market_data[timeframe]) < 10:
            return None
            
        df = self.market_data[timeframe]
        
        # Lấy signals từ tất cả indicators
        trend_signal = self.trend_indicator.get_signal(df)
        momentum_signal = self.momentum_indicator.get_signal(df)
        volatility_signal = self.volatility_indicator.get_signal(df)
        volume_signal = self.volume_indicator.get_signal(df)
        sr_signal = self.sr_indicator.get_signal(df)
        
        # 3. Tính tổng điểm với trọng số
        total_score = self._calculate_weighted_score(
            trend_signal, momentum_signal, volatility_signal,
            volume_signal, sr_signal, safe_trend
        )
        
        # 4. Quy đổi thành win probability
        win_prob = self._score_to_win_probability(total_score['score'])
        
        # 5. Kiểm tra điều kiện gửi signal theo trading mode
        if not self.trading_mode.should_send_signal(win_prob, total_score['score']):
            return None
            
        # 6. Tạo trading signal
        return self._create_trading_signal(
            timeframe, safe_trend, total_score, win_prob, volatility_signal
        )
    
    def _calculate_weighted_score(self, trend, momentum, volatility, volume, sr, safe_trend):
        """Tính điểm tổng hợp với trọng số cho từng loại indicator"""
        
        # Trọng số cho từng nhóm indicator
        weights = {
            'trend': 0.25,      # 25% - Xu hướng chính
            'momentum': 0.30,   # 30% - Động lực (quan trọng nhất cho timing)
            'volatility': 0.20, # 20% - Biến động và S/R
            'volume': 0.15,     # 15% - Xác nhận volume
            'sr': 0.10          # 10% - Support/Resistance
        }
        
        # Tính điểm từng nhóm
        trend_score = trend['score'] * weights['trend']
        momentum_score = momentum['score'] * weights['momentum']
        volatility_score = volatility['score'] * weights['volatility']
        volume_score = volume['score'] * weights['volume'] 
        sr_score = sr['score'] * weights['sr']
        
        total_score = trend_score + momentum_score + volatility_score + volume_score + sr_score
        
        # Bonus nếu trend alignment
        if ((safe_trend == 'UP' and trend['direction'] == 'UP') or 
            (safe_trend == 'DOWN' and trend['direction'] == 'DOWN')):
            total_score += 15  # Bonus alignment
            
        # Collect all reasons
        all_reasons = []
        for signal in [trend, momentum, volatility, volume, sr]:
            all_reasons.extend(signal.get('reasons', []))
            
        return {
            'score': min(100, int(total_score)),  # Cap at 100
            'reasons': all_reasons,
            'breakdown': {
                'trend': int(trend_score),
                'momentum': int(momentum_score),
                'volatility': int(volatility_score),
                'volume': int(volume_score),
                'sr': int(sr_score)
            }
        }
    
    def _score_to_win_probability(self, score: int) -> float:
        """Chuyển đổi score thành tỷ lệ thắng dự kiến"""
        # Base probability + score contribution
        # Score 0-100 -> Win Prob 45-85%
        base_prob = 45.0
        max_additional = 40.0
        
        win_prob = base_prob + (score / 100.0) * max_additional
        return min(85.0, max(45.0, win_prob))
    
    def _create_trading_signal(self, timeframe, safe_trend, score_data, win_prob, volatility_signal):
        """Tạo TradingSignal object với đầy đủ thông tin"""
        
        df = self.market_data[timeframe]
        latest = df.iloc[-1]
        
        action = 'LONG' if safe_trend == 'UP' else 'SHORT'
        entry_price = latest['close']
        
        # Risk management sử dụng ATR
        atr = volatility_signal.get('atr_value', entry_price * 0.01)
        atr_multiplier = 1.5  # Conservative stop loss
        
        if action == 'LONG':
            sl = entry_price - (atr * atr_multiplier)
            tp = entry_price + (atr * 3.0)  # 1:2 Risk Reward
        else:
            sl = entry_price + (atr * atr_multiplier)
            tp = entry_price - (atr * 3.0)
        
        # Position sizing based on risk
        risk_config = self.trading_mode.get_risk_config()
        risk_usd = tc.ACCOUNT_BALANCE * (risk_config['risk_per_trade'] / 100)
        price_distance = abs(entry_price - sl)
        quantity = risk_usd / price_distance if price_distance > 0 else 0
        
        return TradingSignal(
            symbol=tc.SYMBOL,
            action=action,
            score=score_data['score'],
            win_probability=round(win_prob, 1),
            entry_price=round(entry_price, 4),
            quantity=round(quantity, 4),
            take_profit=round(tp, 4),
            stop_loss=round(sl, 4),
            timeframe=timeframe,
            reason=self._format_reasons(score_data['reasons'][:3])  # Top 3 reasons
        )
    
    def _format_reasons(self, reasons: list) -> str:
        """Format reasons thành string ngắn gọn"""
        if not reasons:
            return "Multiple technical confirmations"
        return " | ".join(reasons[:3])
    
    def is_safe_trend(self) -> str:
        """Kiểm tra Safe Trend từ khung thời gian lớn"""
        safe_timeframes = self.trading_mode.get_timeframes()['safe']
        
        for tf in safe_timeframes:
            if tf in self.market_data and len(self.market_data[tf]) > 10:
                df = self.market_data[tf]
                trend_signal = self.trend_indicator.get_signal(df)
                
                if trend_signal['strength'] == 'STRONG':
                    return trend_signal['direction']
                    
        return 'NEUTRAL'
    
    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate signal trước khi gửi"""
        if not signal:
            return False
            
        # Basic validations
        if signal.quantity <= 0 or signal.entry_price <= 0:
            return False
            
        # Risk reward validation
        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        
        if risk == 0 or reward/risk < 1.5:  # Min 1:1.5 RR
            return False
            
        return True