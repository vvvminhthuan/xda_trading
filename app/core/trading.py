from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class TradingType(Enum):
    """Các loại chế độ giao dịch"""
    REVERSAL = "reversal"        # Reversal - bắt điểm quay đầu trong sóng futures
    SWING = "swing"              # Swing - timeframe lớn độ nhiễu thấp, ưu tiên xu hướng
    CONSERVATIVE = "conservative"  # Bảo thủ - chỉ tín hiệu cực mạnh
    AGGRESSIVE = "aggressive"     # Tích cực - nhiều tín hiệu hơn
    SCALPING = "scalping"        # Scalp - timeframe nhỏ

@dataclass
class TradingConfig:
    """Cấu hình cho từng chế độ giao dịch"""
    #4=> ❗ Không check timeframe lớn → dễ bị “bẫy”
    #7=> Scalping cần vol trung bình–cao, Swing cần vol ổn định, không quá nhiễu
    mode_type: TradingType
    min_win_probability: float #1. 👉 Xác suất thắng tối thiểu (%) để cho phép vào lệnh càng cao → càng “kén” lệnh giảm số trade nhưng tăng chất lượng. EMA trend +30, RSI oversold +20, MACD cross +25, Volume spike +15
    min_score: int #2. 👉 Điểm tổng hợp từ signal engine, lọc tín hiệu yếu kết hợp nhiều indicator
    primary_timeframes: List[str] #3. 👉 Khung thời gian chính để vào lệnh nơi bạn tìm entry =>tín hiệu chính
    safe_timeframes: List[str] #4. 👉 Khung lớn để xác nhận xu hướngtránh trade ngược trend, giảm false signal
    risk_per_trade: float #5. 👉 % vốn risk cho mỗi lệnh
    target_profit_pct: float #6. 👉 Mục tiêu lợi nhuận của vị thế theo mode, ví dụ 0.10 là 10%
    leverage: float #7. 👉 Đòn bẩy futures dùng để quy đổi lợi nhuận vị thế sang phần trăm biến động giá
    atr_multiplier: float #8. 👉 Hệ số ATR dùng làm buffer stop loss để giảm nhiễu và hạn chế bị quét SL
    min_risk_reward_ratio: float #9. 👉 Tỷ lệ reward/risk tối thiểu để signal được gửi
    max_signals_per_hour: int #6. 👉 Giới hạn số tín hiệu mỗi giờ tránh overtrading, giảm spam signal
    volatility_filter: float #7. 👉 lọc theo độ biến động Đo thị trường đang yên (low vol) hay nhiễu mạnh (high vol), Quyết định có nên trade không hoặc giảm/tăng risk. Dùng ATR vol = ATR_14 / close   # volatility ratio vol < 0.002:=> thị trường quá yên → bỏ qua (khó có lợi nhuận). vol > 0.02:=> quá nhiễu → giảm risk hoặc không trade
    trend_strength: float #8. 🔥 Độ mạnh xu hướng df.ta.adx() 20=>sideway 20–40=>trend vừa >40=>trend mạnh
    drawdown_limit: float #9. Dừng toàn bộ hệ thống Tổng tiền có thể chấp nhận được để dừng toàn bộ lệnh con. Tránh cháy túi// Tạm Thời chưa dùng     
    weights: Dict[str, float] = field(default_factory=lambda: {
        'trend': 0.25,          # 25% - Xu hướng chính
        'momentum': 0.30,       # 30% - Động lực (quan trọng nhất cho timing)  
        'volatility': 0.20,     # 20% - Biến động và S/R
        'volume': 0.15,         # 15% - Xác nhận volume
        'sr': 0.10              # 10% - Support/Resistance
    })
     
class Trading:
    """
    Quản lý các chế độ giao dịch khác nhau.
    Cho phép chuyển đổi giữa các strategies tùy theo điều kiện thị trường.
    """
    
    MODES = {
        TradingType.REVERSAL: TradingConfig(
            mode_type=TradingType.REVERSAL,
            min_win_probability=65.0,
            min_score=50,
            primary_timeframes=['3m'],
            safe_timeframes=['15m', '1h'],
            risk_per_trade=1.0,
            target_profit_pct=0.15,
            leverage=1.0,
            atr_multiplier=1.8,
            min_risk_reward_ratio=1.5,
            max_signals_per_hour=4,
            volatility_filter=0.15,
            trend_strength=45.0,
            drawdown_limit=5.0,
            weights = {
                'trend': 0.10,      # 10% - Không để trend lớn lấn át tín hiệu quay đầu
                'momentum': 0.35,   # 35% - RSI/Stochastic/Williams %R quyết định timing đảo chiều
                'volatility': 0.20, # 20% - Bollinger/ATR xác nhận vùng bật hoặc bị từ chối
                'volume': 0.15,     # 15% - Xác nhận lực hấp thụ hoặc lực đẩy sau đảo chiều
                'sr': 0.20          # 20% - Swing high/low, pivot và Fibonacci là vùng reversal chính
            }
        ),

        TradingType.CONSERVATIVE: TradingConfig(
            mode_type=TradingType.CONSERVATIVE, 
            min_win_probability=80.0, 
            min_score=70, 
            primary_timeframes=['3m'],
            safe_timeframes=['1h', '2h'], 
            risk_per_trade=0.5,
            target_profit_pct=0.20,
            leverage=1.0,
            atr_multiplier=2.0,
            min_risk_reward_ratio=1.5,
            max_signals_per_hour=2, 
            volatility_filter=0.20,
            trend_strength=60.0, 
            drawdown_limit=5.0,
            weights = {
                'trend': 0.25,      # 25% - Xu hướng chính
                'momentum': 0.30,   # 30% - Động lực (quan trọng nhất cho timing)
                'volatility': 0.20, # 20% - Biến động và S/R
                'volume': 0.15,     # 15% - Xác nhận volume
                'sr': 0.10          # 10% - Support/Resistance
            }
        ),
        
        TradingType.AGGRESSIVE: TradingConfig(
            mode_type=TradingType.AGGRESSIVE,
            min_win_probability=65.0,
            min_score=50,
            primary_timeframes=['3m'],
            safe_timeframes=['1h', '2h'],
            risk_per_trade=1.5,
            target_profit_pct=0.15,
            leverage=1.0,
            atr_multiplier=1.8,
            min_risk_reward_ratio=1.5,
            max_signals_per_hour=8, 
            volatility_filter=0.15,
            trend_strength=50.0, 
            drawdown_limit=8.0,
            weights = {
                'trend': 0.25,      # 25% - Xu hướng chính
                'momentum': 0.30,   # 30% - Động lực (quan trọng nhất cho timing)
                'volatility': 0.20, # 20% - Biến động và S/R
                'volume': 0.15,     # 15% - Xác nhận volume
                'sr': 0.10          # 10% - Support/Resistance
            }
        ),
        
        TradingType.SCALPING: TradingConfig(
            mode_type=TradingType.SCALPING,
            min_win_probability=70.0,
            min_score=60,
            primary_timeframes=['1m'],
            safe_timeframes=['1h', '2h'],
            risk_per_trade=2.0,
            target_profit_pct=0.10,
            leverage=1.0,
            atr_multiplier=1.5,
            min_risk_reward_ratio=1.5,
            max_signals_per_hour=15, 
            volatility_filter=0.10,
            trend_strength=55.0, 
            drawdown_limit=5.0,
            weights = {
                'trend': 0.25,      # 25% - Xu hướng chính
                'momentum': 0.30,   # 30% - Động lực (quan trọng nhất cho timing)
                'volatility': 0.20, # 20% - Biến động và S/R
                'volume': 0.15,     # 15% - Xác nhận volume
                'sr': 0.10          # 10% - Support/Resistance
            }
        ),
        
        TradingType.SWING: TradingConfig(
            mode_type=TradingType.SWING,
            min_win_probability=75.0,
            min_score=65,
            primary_timeframes=['1h'],
            safe_timeframes=['2h'],
            risk_per_trade=1.0,
            target_profit_pct=0.25,
            leverage=1.0,
            atr_multiplier=2.5,
            min_risk_reward_ratio=1.5,
            max_signals_per_hour=1, 
            volatility_filter=0.25,
            trend_strength=60.0, 
            drawdown_limit=10.0,
            weights = {
                'trend': 0.25,      # 25% - Xu hướng chính
                'momentum': 0.30,   # 30% - Động lực (quan trọng nhất cho timing)
                'volatility': 0.20, # 20% - Biến động và S/R
                'volume': 0.15,     # 15% - Xác nhận volume
                'sr': 0.10          # 10% - Support/Resistance
            }
        )
    }
    
    def __init__(self, mode_type: TradingType = TradingType.REVERSAL):
        self.current_mode = mode_type
        self.config = self.MODES[mode_type]
        self.current_drawdown_pct = 0.0
        
    def switch_mode(self, new_mode: TradingType):
        """Chuyển đổi chế độ giao dịch"""
        self.current_mode = new_mode
        self.config = self.MODES[new_mode]
        print(f"🔄 Chuyển sang chế độ: {new_mode.value.upper()}")
        
    def should_send_signal(self, win_prob: float, score: int) -> bool:
        """Kiểm tra xem có nên gửi tín hiệu không dựa trên chế độ hiện tại"""
        if self.is_drawdown_limit_reached():
            return False
        return (win_prob >= self.config.min_win_probability and 
                score >= self.config.min_score)

    def update_drawdown(self, drawdown_pct: float):
        """Cập nhật mức drawdown hiện tại để risk guard có thể chặn signal mới.

        Tham số:
        - drawdown_pct: Phần trăm sụt giảm tài khoản hiện tại, dùng số dương.
        """
        self.current_drawdown_pct = max(0.0, float(drawdown_pct))

    def is_drawdown_limit_reached(self) -> bool:
        """Kiểm tra drawdown hiện tại đã chạm giới hạn của mode hay chưa."""
        limit = self.config.drawdown_limit
        return limit > 0 and self.current_drawdown_pct >= limit
                
    def get_timeframes(self) -> Dict[str, List[str]]:
        """Trả về timeframes cho chế độ hiện tại"""
        return {
            'primary': self.config.primary_timeframes,
            'safe': self.config.safe_timeframes
        }
        
    def get_risk_config(self) -> Dict[str, float]:
        """Trả về cấu hình risk cho chế độ hiện tại"""
        return {
            'risk_per_trade': self.config.risk_per_trade,
            'min_win_prob': self.config.min_win_probability,
            'min_score': self.config.min_score,
            'target_profit_pct': self.config.target_profit_pct,
            'leverage': self.config.leverage,
            'atr_multiplier': self.config.atr_multiplier,
            'min_risk_reward_ratio': self.config.min_risk_reward_ratio,
            'volatility_filter': self.config.volatility_filter,
            'trend_strength': self.config.trend_strength,
            'drawdown_limit': self.config.drawdown_limit
        }
    def get_timeframe(self) -> List:
        return self.config.primary_timeframes + self.config.safe_timeframes
