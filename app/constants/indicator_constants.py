"""
Constants cho các chỉ báo kỹ thuật
Chứa các tham số mặc định cho từng indicator
"""

# app/constants/indicator_constants.py

# EMA Settings
EMA_FAST = 12    # EMA ngắn hạn (12 periods)
EMA_SLOW = 26    # EMA dài hạn (26 periods)

# MACD Settings  
MACD_FAST = 12   # Đường EMA nhanh của MACD
MACD_SLOW = 26   # Đường EMA chậm của MACD  
MACD_SIGNAL = 9  # Đường tín hiệu của MACD

# Other common periods
SMA_FAST = 20
SMA_SLOW = 50
RSI_PERIOD = 14
STOCH_K = 14
STOCH_D = 3
BB_PERIOD = 20
BB_STD = 2

# Bollinger Bands
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0

# Support/Resistance
SR_LOOKBACK = 20
SR_MIN_TOUCHES = 2

# Volume indicators
VOLUME_SMA = 20

# Average True Range
ATR_PERIOD = 14  # Standard ATR period (14 candles)