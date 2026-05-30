import pandas as pd
from pandas import DataFrame
from datetime import datetime
from collections import deque
from typing import Dict, Optional
from app.models.signal import SignalStrength, SignalType, TradingSignal
from app.indicators import *
from app.constants import trading as tc
from app.strategies.base import BaseStrategy
from app.core.trading import Trading, TradingType

class FuturesStrategy(BaseStrategy):
    """
    Chiến lược Futures đa khung thời gian với hệ thống scoring tổng hợp.
    Tích hợp đầy đủ các chỉ báo kỹ thuật và chế độ giao dịch linh hoạt.
    """
    
    def __init__(self, trading_core: Trading, **config):
        super().__init__(**config)
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.trading_core = trading_core
        self.signal_timestamps = deque()
        self.last_analysis: Dict[str, dict] = {}
        
        # Initialize indicators
        self.trend_indicator = TrendIndicators()
        self.momentum_indicator = MomentumIndicators() 
        self.volatility_indicator = VolatilityIndicators()
        self.volume_indicator = VolumeIndicators()
        self.sr_indicator = SupportResistance()
        
    def update_data(self, timeframe: str, df: DataFrame):
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
        
    def analyze(self, timeframe: str = '1m', symbol: str | None = None) -> Optional[TradingSignal]:
        """Main analysis function tích hợp multi-timeframe và indicators"""
        runtime_symbol = symbol or tc.SYMBOL
        if timeframe not in self.trading_core.config.primary_timeframes: #Không phải khung thời gian của cấu hình thì bỏ qua
            return None

        # Phân tích primary timeframe trước để Discord summary vẫn có dữ liệu debug
        # ngay cả khi safe trend từ khung lớn đang neutral và không được tạo signal.
        if timeframe not in self.market_data or len(self.market_data[timeframe]) < 10:
            return None
            
        df = self.market_data[timeframe]
        safe_trend = self.is_safe_trend(runtime_symbol)
        
        # Lấy signals từ tất cả indicators
        trend_signal = self.trend_indicator.get_signal(df, symbol=runtime_symbol)
        momentum_signal = self.momentum_indicator.get_signal(df, symbol=runtime_symbol)
        volatility_signal = self.volatility_indicator.get_signal(df, symbol=runtime_symbol)
        volume_signal = self.volume_indicator.get_signal(df, symbol=runtime_symbol)
        sr_signal = self.sr_indicator.get_signal(df, symbol=runtime_symbol)

        if self.trading_core.current_mode == TradingType.REVERSAL:
            return self._analyze_reversal(
                runtime_symbol,
                timeframe,
                safe_trend,
                trend_signal,
                momentum_signal,
                volatility_signal,
                volume_signal,
                sr_signal,
            )

        total_score = self._calculate_weighted_score(
            trend_signal, momentum_signal, volatility_signal,
            volume_signal, sr_signal, safe_trend
        )
        
        win_prob = self._score_to_win_probability(total_score['score'])
        self._print_score_breakdown(runtime_symbol, timeframe, safe_trend, total_score, win_prob)

        volume_confirmed = self._is_volume_confirmed(safe_trend, volume_signal)
        risk_filters = self._risk_filter_status(trend_signal, volatility_signal)
        risk_passed = all(risk_filters.values())
        mode_threshold_passed = self.trading_core.should_send_signal(win_prob, total_score['score'])
        rate_limit_passed = self._can_send_signal()
        filters = {
            "safe_trend": safe_trend != 'NEUTRAL',
            "volume_confirmed": volume_confirmed,
            "trend_filter": risk_filters["trend_filter"],
            "volatility_filter": risk_filters["volatility_filter"],
            "mode_threshold": mode_threshold_passed,
            "rate_limit": rate_limit_passed,
        }
        analysis = self._build_analysis(
            runtime_symbol,
            timeframe,
            safe_trend,
            total_score,
            win_prob,
            [trend_signal, momentum_signal, volatility_signal, volume_signal, sr_signal],
            filters,
            "No signal",
        )

        if safe_trend == 'NEUTRAL':
            analysis["decision"] = "No signal: safe trend neutral"
            self._store_analysis(timeframe, analysis)
            return None
        
        if not volume_confirmed:
            analysis["decision"] = "No signal: volume not confirmed"
            self._store_analysis(timeframe, analysis)
            return None
        if not risk_passed:
            analysis["decision"] = "No signal: risk filters failed"
            self._store_analysis(timeframe, analysis)
            return None
        
        # 5. Kiểm tra điều kiện gửi signal theo trading mode
        if not mode_threshold_passed:
            analysis["decision"] = "No signal: mode threshold failed"
            self._store_analysis(timeframe, analysis)
            return None
        if not rate_limit_passed:
            analysis["decision"] = "No signal: rate limit"
            self._store_analysis(timeframe, analysis)
            return None
            
        # 6. Tạo trading signal
        signal = self._create_trading_signal(
            runtime_symbol, timeframe, safe_trend, total_score, win_prob, volatility_signal
        )
        self.signal_timestamps.append(datetime.utcnow())
        analysis["decision"] = f"Signal {signal.signal_type.value}"
        self._store_analysis(timeframe, analysis)
        return signal

    def _analyze_reversal(
        self,
        symbol: str,
        timeframe: str,
        safe_trend: str,
        trend_signal: dict,
        momentum_signal: dict,
        volatility_signal: dict,
        volume_signal: dict,
        sr_signal: dict,
    ) -> Optional[TradingSignal]:
        """Phân tích riêng cho mode reversal để tìm điểm quay đầu lên hoặc quay đầu xuống.

        Tham số:
        - symbol: Symbol runtime đang được phân tích.
        - timeframe: Khung thời gian chính dùng để tìm điểm entry.
        - safe_trend: Xu hướng khung lớn, chỉ dùng làm bối cảnh rủi ro.
        - trend_signal, momentum_signal, volatility_signal, volume_signal, sr_signal:
          Kết quả từ các indicator hiện có.

        Trả về:
        - TradingSignal nếu đủ điều kiện reversal và vượt qua validate cơ bản.
        - None nếu chưa đủ xác nhận hoặc bị filter chặn.
        """
        action = self._resolve_reversal_action(momentum_signal, volatility_signal, sr_signal)
        total_score = self._calculate_weighted_score(
            trend_signal, momentum_signal, volatility_signal,
            volume_signal, sr_signal, safe_trend
        )
        trend_context = self._resolve_reversal_trend_context(action, safe_trend)
        self._apply_reversal_bonus(
            total_score,
            action,
            momentum_signal,
            volatility_signal,
            volume_signal,
            sr_signal,
            safe_trend,
        )
        win_prob = self._score_to_win_probability(total_score['score'])
        self._print_score_breakdown(symbol, timeframe, safe_trend, total_score, win_prob)

        volume_confirmed = self._is_reversal_volume_confirmed(action, volume_signal)
        mode_threshold_passed = self.trading_core.should_send_signal(win_prob, total_score['score'])
        rate_limit_passed = self._can_send_signal()
        filters = {
            "safe_trend": True,
            "volume_confirmed": volume_confirmed,
            "trend_filter": True,
            "volatility_filter": True,
            "mode_threshold": mode_threshold_passed,
            "rate_limit": rate_limit_passed,
            "reversal_action": action is not None,
        }
        analysis = self._build_analysis(
            symbol,
            timeframe,
            safe_trend,
            total_score,
            win_prob,
            [trend_signal, momentum_signal, volatility_signal, volume_signal, sr_signal],
            filters,
            "No signal",
        )
        analysis["reversal_action"] = action.value if action else "NONE"
        analysis["trend_context"] = trend_context

        if action is None:
            analysis["decision"] = "No signal: reversal confirmation missing"
            self._print_reversal_decision(symbol, timeframe, analysis)
            self._store_analysis(timeframe, analysis)
            return None
        if not volume_confirmed:
            analysis["decision"] = "No signal: reversal volume not confirmed"
            self._print_reversal_decision(symbol, timeframe, analysis)
            self._store_analysis(timeframe, analysis)
            return None
        if not mode_threshold_passed:
            analysis["decision"] = "No signal: reversal mode threshold failed"
            self._print_reversal_decision(symbol, timeframe, analysis)
            self._store_analysis(timeframe, analysis)
            return None
        if not rate_limit_passed:
            analysis["decision"] = "No signal: rate limit"
            self._print_reversal_decision(symbol, timeframe, analysis)
            self._store_analysis(timeframe, analysis)
            return None

        signal = self._create_trading_signal(
            symbol,
            timeframe,
            safe_trend,
            total_score,
            win_prob,
            volatility_signal,
            action,
            sr_signal,
            trend_context,
        )
        self.signal_timestamps.append(datetime.utcnow())
        analysis["decision"] = f"Signal {signal.signal_type.value}"
        self._print_reversal_decision(symbol, timeframe, analysis)
        self._store_analysis(timeframe, analysis)
        return signal
    
    def _calculate_weighted_score(self, trend, momentum, volatility, volume, sr, safe_trend):
        """Tính điểm tổng hợp với trọng số cho từng loại indicator"""
        
        # Trọng số cho từng nhóm indicator
        weights = self.trading_core.config.weights
        
        # Tính điểm từng nhóm
        trend_score = trend['score'] * weights['trend']
        momentum_score = momentum['score'] * weights['momentum']
        volatility_score = volatility['score'] * weights['volatility']
        volume_score = volume['score'] * weights['volume'] 
        sr_score = sr['score'] * weights['sr']
        
        total_score = trend_score + momentum_score + volatility_score + volume_score + sr_score
        alignment_bonus = 0
        
        # Bonus nếu trend alignment không thay đổi
        if ((safe_trend == 'UP' and trend['direction'] == 'UP') or 
            (safe_trend == 'DOWN' and trend['direction'] == 'DOWN')):
            alignment_bonus = 15
            total_score += alignment_bonus  # Bonus alignment
            
        # Collect all reasons
        all_reasons = []
        for signal in [trend, momentum, volatility, volume, sr]:
            all_reasons.extend(signal.get('reasons', []))
            
        raw_breakdown = {
            'trend': int(trend.get('score', 0)),
            'momentum': int(momentum.get('score', 0)),
            'volatility': int(volatility.get('score', 0)),
            'volume': int(volume.get('score', 0)),
            'sr': int(sr.get('score', 0)),
        }
        weighted_breakdown = {
            'trend': trend_score,
            'momentum': momentum_score,
            'volatility': volatility_score,
            'volume': volume_score,
            'sr': sr_score,
        }
        return {
            'score': min(100, int(total_score)),  # Cap at 100
            'raw_score': total_score,
            'alignment_bonus': alignment_bonus,
            'reasons': all_reasons,
            'raw_breakdown': raw_breakdown,
            'weighted_breakdown': weighted_breakdown,
            'breakdown': weighted_breakdown,
        }
    
    def _score_to_win_probability(self, score: int) -> float:
        """Chuyển đổi score thành tỷ lệ thắng dự kiến"""
        # Base probability + score contribution
        # Score 0-100 -> Win Prob 45-85%
        base_prob = 45.0
        max_additional = 40.0
        
        win_prob = base_prob + (score / 100.0) * max_additional
        return min(85.0, max(45.0, win_prob))

    def _resolve_reversal_action(self, momentum_signal: dict, volatility_signal: dict, sr_signal: dict) -> Optional[SignalType]:
        """Xác định hướng LONG/SHORT cho mode reversal từ momentum, volatility và S/R.

        Tham số:
        - momentum_signal: Kết quả MomentumIndicators, dùng condition/direction để nhận biết quá mua/quá bán quay đầu.
        - volatility_signal: Kết quả VolatilityIndicators, dùng Bollinger/Keltner direction hoặc state.
        - sr_signal: Kết quả SupportResistance, dùng vùng support/resistance gần giá.

        Trả về:
        - SignalType.LONG nếu đủ xác nhận quay đầu lên.
        - SignalType.SHORT nếu đủ xác nhận quay đầu xuống.
        - None nếu tín hiệu chưa rõ hoặc hai hướng mâu thuẫn.
        """
        momentum_condition = momentum_signal.get("condition", "NEUTRAL")
        momentum_direction = momentum_signal.get("direction", "NEUTRAL")
        volatility_state = volatility_signal.get("volatility_state", "NORMAL")
        volatility_direction = volatility_signal.get("direction", "NEUTRAL")
        sr_condition = sr_signal.get("sr_condition", "NEUTRAL")

        bullish_momentum = momentum_condition in {"OVERSOLD_REVERSAL", "OVERSOLD_RECOVERY"}
        bearish_momentum = momentum_condition in {"OVERBOUGHT_REVERSAL", "OVERBOUGHT_REJECTION"}
        neutral_level_test = sr_condition in {"FIBONACCI_TEST", "PIVOT_TEST"}
        support_confirmed = sr_condition in {"SUPPORT_TEST", "SWING_SUPPORT"} or (
            neutral_level_test and momentum_direction == "UP"
        )
        resistance_confirmed = sr_condition in {"RESISTANCE_TEST", "SWING_RESISTANCE"} or (
            neutral_level_test and momentum_direction == "DOWN"
        )
        bullish_volatility = volatility_state == "SUPPORT_TEST" or volatility_direction == "UP"
        bearish_volatility = volatility_state == "RESISTANCE_TEST" or volatility_direction == "DOWN"

        bullish = bullish_momentum and (support_confirmed or bullish_volatility)
        bearish = bearish_momentum and (resistance_confirmed or bearish_volatility)
        if bullish and not bearish:
            return SignalType.LONG
        if bearish and not bullish:
            return SignalType.SHORT
        return None

    def _is_reversal_volume_confirmed(self, action: Optional[SignalType], volume_signal: dict) -> bool:
        """Kiểm tra volume cho mode reversal theo hướng quay đầu dự kiến.

        Tham số:
        - action: Hướng reversal đã xác định, LONG hoặc SHORT.
        - volume_signal: Kết quả VolumeIndicators, dùng volume_condition và direction.

        Trả về:
        - True nếu volume không yếu và không ngược hướng reversal.
        - False nếu volume thấp, chưa có action, hoặc volume ngược hướng rõ ràng.
        """
        if action is None:
            return False
        volume_condition = volume_signal.get('volume_condition')
        volume_direction = volume_signal.get('direction', 'NEUTRAL')
        if volume_condition == 'LOW_VOLUME':
            return False
        if volume_direction == 'NEUTRAL':
            return True
        return (action == SignalType.LONG and volume_direction == 'UP') or (
            action == SignalType.SHORT and volume_direction == 'DOWN'
        )

    def _apply_reversal_bonus(
        self,
        score_data: dict,
        action: Optional[SignalType],
        momentum_signal: dict,
        volatility_signal: dict,
        volume_signal: dict,
        sr_signal: dict,
        safe_trend: str,
    ):
        """Cộng điểm confluence cho mode reversal khi đã có hướng và volume ủng hộ.

        Tham số:
        - score_data: Dữ liệu score tổng hợp sẽ được cập nhật tại chỗ.
        - action: Hướng reversal đã xác định.
        - volume_signal: Kết quả VolumeIndicators để xét bonus volume cùng hướng.

        Trả về:
        - Không trả về; cập nhật score_data tại chỗ để giữ breakdown indicator gốc.
        """
        if action is None:
            return
        bonus = 0
        bonus_reasons = []
        momentum_condition = momentum_signal.get("condition", "NEUTRAL")
        volatility_state = volatility_signal.get("volatility_state", "NORMAL")
        sr_condition = sr_signal.get("sr_condition", "NEUTRAL")
        volume_direction = volume_signal.get('direction', 'NEUTRAL')
        volume_condition = volume_signal.get('volume_condition', 'NORMAL')
        if (
            action == SignalType.LONG and momentum_condition in {"OVERSOLD_REVERSAL", "OVERSOLD_RECOVERY"}
        ) or (
            action == SignalType.SHORT and momentum_condition in {"OVERBOUGHT_REVERSAL", "OVERBOUGHT_REJECTION"}
        ):
            bonus += 10
            bonus_reasons.append("momentum")
        if (
            action == SignalType.LONG and sr_condition in {"SUPPORT_TEST", "SWING_SUPPORT", "FIBONACCI_TEST", "PIVOT_TEST"}
        ) or (
            action == SignalType.SHORT and sr_condition in {"RESISTANCE_TEST", "SWING_RESISTANCE", "FIBONACCI_TEST", "PIVOT_TEST"}
        ):
            bonus += 8
            bonus_reasons.append("S/R")
        if (
            action == SignalType.LONG and volatility_state == "SUPPORT_TEST"
        ) or (
            action == SignalType.SHORT and volatility_state == "RESISTANCE_TEST"
        ):
            bonus += 6
            bonus_reasons.append("volatility")
        if (
            (action == SignalType.LONG and volume_direction == 'UP') or
            (action == SignalType.SHORT and volume_direction == 'DOWN')
        ):
            bonus += 5
            bonus_reasons.append("volume")
        elif volume_condition in {"BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "VOLUME_SPIKE_NEUTRAL"}:
            bonus += 2
            bonus_reasons.append("volume-neutral")
        if self._resolve_reversal_trend_context(action, safe_trend) == "COUNTER_SAFE_TREND":
            bonus -= 5
            bonus_reasons.append("counter-trend-risk")
        bonus = max(0, bonus)
        score_data['alignment_bonus'] = score_data.get('alignment_bonus', 0) + bonus
        score_data['raw_score'] = score_data.get('raw_score', 0) + bonus
        score_data['score'] = min(100, int(score_data.get('score', 0) + bonus))
        if bonus:
            score_data.setdefault('reasons', []).append(
                f"Reversal confluence bonus +{bonus} ({', '.join(bonus_reasons)})"
            )

    def _resolve_reversal_trend_context(self, action: Optional[SignalType], safe_trend: str) -> str:
        """Mô tả quan hệ giữa hướng reversal và safe trend để hiển thị trong analysis.

        Tham số:
        - action: Hướng reversal dự kiến.
        - safe_trend: Xu hướng khung lớn hiện tại.

        Trả về:
        - Chuỗi mô tả signal thuận trend, ngược trend, neutral hoặc chưa có action.
        """
        if action is None:
            return "NO_ACTION"
        if safe_trend == "NEUTRAL":
            return "NEUTRAL_SAFE_TREND"
        if action == SignalType.LONG and safe_trend == "UP":
            return "WITH_SAFE_TREND"
        if action == SignalType.SHORT and safe_trend == "DOWN":
            return "WITH_SAFE_TREND"
        return "COUNTER_SAFE_TREND"

    def _print_reversal_decision(self, symbol: str, timeframe: str, analysis: dict):
        """In log quyết định reversal để đối chiếu nhanh với Discord analysis summary.

        Tham số:
        - symbol: Symbol runtime đang được phân tích.
        - timeframe: Khung thời gian chính của reversal.
        - analysis: Dữ liệu analysis đã có decision, reversal_action, trend_context và filters.

        Trả về:
        - Không trả về; chỉ in log terminal phục vụ debug realtime.
        """
        filters = analysis.get("filters", {})
        print(
            f"{symbol} | 🔁 REVERSAL "
            f"timeframe={timeframe} action={analysis.get('reversal_action', 'NONE')} "
            f"context={analysis.get('trend_context', 'n/a')} "
            f"safe_trend={analysis.get('safe_trend', 'NEUTRAL')} "
            f"volume={'pass' if filters.get('volume_confirmed') else 'fail'} "
            f"threshold={'pass' if filters.get('mode_threshold') else 'fail'} "
            f"rate_limit={'pass' if filters.get('rate_limit') else 'fail'} "
            f"decision={analysis.get('decision', 'No signal')}"
        )

    def _print_score_breakdown(self, symbol: str, timeframe: str, safe_trend: str, score_data: dict, win_prob: float):
        """In chi tiết điểm mỗi lần strategy tính score để dễ theo dõi chất lượng signal.

        Tham số:
        - symbol: Symbol runtime đang được phân tích.
        - timeframe: Khung thời gian đang phân tích.
        - safe_trend: Hướng xu hướng an toàn lấy từ khung lớn.
        - score_data: Dữ liệu điểm tổng hợp và breakdown từng nhóm indicator.
        - win_prob: Tỷ lệ thắng dự kiến được quy đổi từ score.
        """
        breakdown = score_data.get('breakdown', {})
        raw_breakdown = score_data.get('raw_breakdown', {})
        mode = self.trading_core.current_mode.value
        print(
            f"{symbol} | 📊 SCORE "
            f"mode={mode} timeframe={timeframe} safe_trend={safe_trend} | "
            f"raw_trend={raw_breakdown.get('trend', 0)} "
            f"raw_momentum={raw_breakdown.get('momentum', 0)} "
            f"raw_volatility={raw_breakdown.get('volatility', 0)} "
            f"raw_volume={raw_breakdown.get('volume', 0)} "
            f"raw_sr={raw_breakdown.get('sr', 0)} | "
            f"weighted_trend={breakdown.get('trend', 0):.2f} "
            f"weighted_momentum={breakdown.get('momentum', 0):.2f} "
            f"weighted_volatility={breakdown.get('volatility', 0):.2f} "
            f"weighted_volume={breakdown.get('volume', 0):.2f} "
            f"weighted_sr={breakdown.get('sr', 0):.2f} "
            f"alignment={score_data.get('alignment_bonus', 0)} | "
            f"raw={score_data.get('raw_score', 0):.2f} "
            f"score={score_data.get('score', 0)} "
            f"confidence={win_prob:.1f}%"
        )

    def _is_volume_confirmed(self, safe_trend: str, volume_signal: dict) -> bool:
        """Kiểm tra volume có ủng hộ hướng xu hướng chính hay không trước khi tạo signal."""
        volume_direction = volume_signal.get('direction', 'NEUTRAL')
        volume_condition = volume_signal.get('volume_condition')
        if volume_condition == 'LOW_VOLUME':
            return False
        if volume_direction == 'NEUTRAL':
            return True
        return (safe_trend == 'UP' and volume_direction == 'UP') or (safe_trend == 'DOWN' and volume_direction == 'DOWN')

    def _can_send_signal(self) -> bool:
        """Giới hạn số signal trong một giờ theo cấu hình mode hiện tại."""
        now = datetime.utcnow()
        while self.signal_timestamps and (now - self.signal_timestamps[0]).total_seconds() > 3600:
            self.signal_timestamps.popleft()
        return len(self.signal_timestamps) < self.trading_core.config.max_signals_per_hour

    def _passes_risk_filters(self, trend_signal: dict, volatility_signal: dict) -> bool:
        """Kiểm tra ngưỡng risk guard của mode hiện tại trước khi tạo signal.

        Tham số:
        - trend_signal: Kết quả từ TrendIndicators, dùng điểm trend để lọc xu hướng yếu.
        - volatility_signal: Kết quả từ VolatilityIndicators, dùng ATR percentage để lọc thị trường quá yên.

        Trả về:
        - True nếu trend và volatility đạt ngưỡng cấu hình của mode hiện tại.
        """
        return all(self._risk_filter_status(trend_signal, volatility_signal).values())

    def _risk_filter_status(self, trend_signal: dict, volatility_signal: dict) -> Dict[str, bool]:
        """Trả trạng thái pass/fail cho từng risk filter để log và gửi Discord summary."""
        config = self.trading_core.config
        trend_score = float(trend_signal.get('score', 0) or 0)
        atr_percentage = volatility_signal.get('atr_percentage', 0) or 0
        if pd.isna(atr_percentage):
            atr_percentage = 0
        atr_percentage = float(atr_percentage)
        return {
            "trend_filter": not (config.trend_strength > 0 and trend_score < config.trend_strength),
            "volatility_filter": not (config.volatility_filter > 0 and atr_percentage < config.volatility_filter),
        }
    
    def _create_trading_signal(
        self,
        symbol,
        timeframe,
        safe_trend,
        score_data,
        win_prob,
        volatility_signal,
        action=None,
        sr_signal: dict | None = None,
        trend_context: str | None = None,
    ):
        """Tạo TradingSignal object với đầy đủ thông tin.

        Tham số:
        - symbol: Symbol runtime của signal.
        - timeframe: Khung thời gian tạo signal.
        - safe_trend: Xu hướng khung lớn, dùng cho các mode trend-following khi action chưa được truyền.
        - score_data: Điểm tổng hợp và breakdown indicator.
        - win_prob: Xác suất thắng dự kiến từ score.
        - volatility_signal: Dữ liệu ATR để tính SL/TP.
        - action: Hướng LONG/SHORT đã xác định sẵn, dùng cho mode reversal.

        Trả về:
        - TradingSignal đã tính entry, stop loss, take profit, quantity và risk/reward.
        """
        
        df = self.market_data[timeframe]
        latest = df.iloc[-1]
        
        if action is None:
            action = SignalType.LONG if safe_trend == 'UP' else SignalType.SHORT
        close_price = float(latest['close'])
        atr = volatility_signal.get('atr_value', close_price * 0.01)
        if pd.isna(atr) or atr <= 0:
            atr = close_price * 0.01
        entry_data = {
            "entry_price": close_price,
            "basis": "Close của nến xác nhận",
            "reference_level": close_price,
        }
        if self.trading_core.current_mode == TradingType.REVERSAL:
            entry_data = self._calculate_reversal_entry_price(
                symbol,
                timeframe,
                action,
                latest,
                atr,
                sr_signal or {},
            )
        entry_price = entry_data["entry_price"]

        sl, tp = self._calculate_exit_prices(symbol, action, entry_price, atr)
        
        # Position sizing based on risk
        risk_config = self.trading_core.get_risk_config()
        risk_usd = tc.ACCOUNT_BALANCE * (risk_config['risk_per_trade'] / 100)
        price_distance = abs(entry_price - sl)
        quantity = risk_usd / price_distance if price_distance > 0 else 0
        
        indicators = dict(score_data.get('breakdown', {}))
        if self.trading_core.current_mode == TradingType.REVERSAL:
            indicators.update({
                "entry_basis": entry_data.get("basis", "Close của nến xác nhận"),
                "entry_reference_level": round(float(entry_data.get("reference_level", entry_price)), 4),
                "trend_context": trend_context or self._resolve_reversal_trend_context(action, safe_trend),
            })
        return TradingSignal(
            symbol=symbol,
            timeframe=timeframe,
            signal_type=action,
            entry_price=round(entry_price, 4),
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            confidence_score=round(win_prob, 1),
            strength=self._resolve_strength(score_data['score']),
            strategy_name=self.name,
            timestamp=datetime.utcnow(),
            score=score_data['score'],
            quantity=round(quantity, 4),
            indicators=indicators,
            reason=self._format_reasons(score_data['reasons'][:3])  # Top 3 reasons
        )

    def _calculate_reversal_entry_price(
        self,
        symbol: str,
        timeframe: str,
        action: SignalType,
        latest: pd.Series,
        atr: float,
        sr_signal: dict,
    ) -> dict:
        """Tính điểm vào tốt hơn cho reversal dựa trên vùng retest gần nhất.

        Tham số:
        - symbol: Symbol runtime dùng để log khi phân tích nhiều cặp.
        - timeframe: Khung thời gian đang tạo signal.
        - action: Hướng reversal LONG hoặc SHORT.
        - latest: Nến mới nhất đã có indicator.
        - atr: ATR hiện tại dùng làm buffer retest.
        - sr_signal: Kết quả SupportResistance, chứa key_levels để chọn vùng hỗ trợ/kháng cự.

        Trả về:
        - Dict gồm entry_price, basis và reference_level để tạo TradingSignal và hiển thị Discord.
        """
        close_price = float(latest['close'])
        key_levels = sr_signal.get("key_levels", {}) if sr_signal else {}
        buffer = min(max(atr * 0.15, close_price * 0.0005), close_price * 0.002)
        max_retest_distance = max(atr * 0.5, close_price * 0.002)
        levels = self._reversal_entry_candidates(latest, key_levels)

        if action == SignalType.LONG:
            support_levels = [
                (name, level) for name, level in levels
                if level > 0 and level <= close_price
            ]
            if support_levels:
                name, level = max(support_levels, key=lambda item: item[1])
                entry = min(close_price, level + buffer)
                entry = max(entry, close_price - max_retest_distance)
                basis = f"Retest hỗ trợ {name}"
            else:
                entry = close_price
                level = close_price
                basis = "Close của nến xác nhận"
        else:
            resistance_levels = [
                (name, level) for name, level in levels
                if level > 0 and level >= close_price
            ]
            if resistance_levels:
                name, level = min(resistance_levels, key=lambda item: item[1])
                entry = max(close_price, level - buffer)
                entry = min(entry, close_price + max_retest_distance)
                basis = f"Retest kháng cự {name}"
            else:
                entry = close_price
                level = close_price
                basis = "Close của nến xác nhận"

        print(
            f"{symbol} | 🎯 ENTRY "
            f"mode=reversal timeframe={timeframe} action={action.value} "
            f"close={close_price:.4f} entry={entry:.4f} basis={basis}"
        )
        return {
            "entry_price": float(entry),
            "basis": basis,
            "reference_level": float(level),
        }

    def _reversal_entry_candidates(self, latest: pd.Series, key_levels: dict) -> list[tuple[str, float]]:
        """Tập hợp các level có thể dùng làm vùng retest cho reversal.

        Tham số:
        - latest: Nến mới nhất chứa các cột indicator động như Bollinger.
        - key_levels: Các level support/resistance do SupportResistance trả về.

        Trả về:
        - Danh sách tuple tên level và giá trị hợp lệ.
        """
        candidates = []
        for name in [
            "s1",
            "r1",
            "pivot",
            "nearest_fib",
            "nearest_swing_low",
            "nearest_swing_high",
            "val",
            "vah",
            "poc",
        ]:
            value = key_levels.get(name)
            if pd.notna(value) and value:
                candidates.append((name, float(value)))
        for column in latest.index:
            if str(column).startswith("BBL_") or str(column).startswith("BBU_"):
                value = latest.get(column)
                if pd.notna(value) and value:
                    candidates.append((str(column), float(value)))
        return candidates

    def _calculate_exit_prices(self, symbol: str, action: SignalType, entry_price: float, atr: float) -> tuple[float, float]:
        """Tính stop loss và take profit theo mode hiện tại và buffer ATR chống nhiễu.

        Tham số:
        - symbol: Symbol runtime dùng để prefix log khi theo dõi nhiều symbol.
        - action: Hướng signal LONG hoặc SHORT.
        - entry_price: Giá vào lệnh lấy từ close của nến mới nhất.
        - atr: Giá trị ATR dùng để tạo khoảng đệm stop loss.

        Trả về:
        - Tuple gồm stop_loss và take_profit đã tính theo target profit, leverage và risk/reward.
        """
        config = self.trading_core.config
        leverage = max(config.leverage, 1.0)
        min_risk_reward_ratio = max(config.min_risk_reward_ratio, 0.01)
        price_move_pct = config.target_profit_pct / leverage
        risk_price_move_pct = price_move_pct / min_risk_reward_ratio
        percent_stop_distance = entry_price * risk_price_move_pct
        atr_stop_distance = atr * config.atr_multiplier
        stop_loss_distance = max(percent_stop_distance, atr_stop_distance)

        if action == SignalType.LONG:
            stop_loss = entry_price - stop_loss_distance
            take_profit = entry_price * (1 + price_move_pct)
        else:
            stop_loss = entry_price + stop_loss_distance
            take_profit = entry_price * (1 - price_move_pct)

        print(
            f"{symbol} | 🎯 EXIT "
            f"mode={self.trading_core.current_mode.value} action={action.value} | "
            f"entry={entry_price:.4f} atr={atr:.4f} "
            f"target_profit={config.target_profit_pct * 100:.1f}% "
            f"leverage={leverage:.1f}x "
            f"price_move={price_move_pct * 100:.2f}% "
            f"sl_distance={stop_loss_distance:.4f} "
            f"tp={take_profit:.4f} sl={stop_loss:.4f}"
        )
        return stop_loss, take_profit

    def _resolve_strength(self, score: int) -> SignalStrength:
        """Quy đổi điểm tín hiệu sang mức độ mạnh của tín hiệu."""
        if score >= 85:
            return SignalStrength.VERY_STRONG
        if score >= 70:
            return SignalStrength.STRONG
        if score >= 50:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
    
    def _format_reasons(self, reasons: list) -> str:
        """Format reasons thành string ngắn gọn"""
        if not reasons:
            return "Multiple technical confirmations"
        return " | ".join(reasons[:3])
    
    def is_safe_trend(self, symbol: str = "") -> str:
        """Kiểm tra Safe Trend từ khung thời gian lớn"""
        safe_timeframes = self.trading_core.get_timeframes()['safe']
        
        for tf in safe_timeframes:
            if tf in self.market_data and len(self.market_data[tf]) > 10:
                df = self.market_data[tf]
                trend_signal = self.trend_indicator.get_signal(df, symbol=symbol)
                
                if trend_signal['strength'] == 'STRONG':
                    return trend_signal['direction']
                    
        return 'NEUTRAL'

    def _store_analysis(self, timeframe: str, analysis: dict):
        """Lưu analysis cuối cùng theo timeframe để RealtimeService gửi Discord summary nếu cần."""
        self.last_analysis[timeframe] = analysis

    def _build_analysis(
        self,
        symbol: str,
        timeframe: str,
        safe_trend: str,
        score_data: dict | None,
        win_prob: float | None,
        indicator_signals,
        filters: dict,
        decision: str,
    ) -> dict:
        """Tạo dữ liệu tóm tắt phân tích cho log Discord, tách rõ raw score và weighted score."""
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": self.trading_core.current_mode.value,
            "safe_trend": safe_trend,
            "score": score_data.get("score", 0) if score_data else 0,
            "confidence": win_prob or 0.0,
            "raw_score": score_data.get("raw_breakdown", {}) if score_data else {},
            "weighted_score": score_data.get("weighted_breakdown", {}) if score_data else {},
            "alignment_bonus": score_data.get("alignment_bonus", 0) if score_data else 0,
            "reasons": score_data.get("reasons", []) if score_data else [],
            "filters": filters,
            "decision": decision,
        }
    
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
        
        if risk == 0 or reward/risk < self.trading_core.config.min_risk_reward_ratio:
            return False
            
        return True
