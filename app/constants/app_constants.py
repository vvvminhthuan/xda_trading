from app.utils import helps
import os

# Bot Settings
SIGNAL_COOLDOWN_SECONDS = helps.get_env_int('SIGNAL_COOLDOWN_SECONDS', 30)
ENABLE_PAPER_TRADING = helps.get_env_bool('ENABLE_PAPER_TRADING', True)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
NOTIFY_ON_ERRORS = helps.get_env_bool('NOTIFY_ON_ERRORS', True)
NOTIFY_HOURLY_STATS = helps.get_env_bool('NOTIFY_HOURLY_STATS', True)

# Advanced
MAX_POSITION_SIZE = helps.get_env_float('MAX_POSITION_SIZE', 1000.0)