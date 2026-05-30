import os
from app.utils import helps

# Exchange Configuration
EXCHANGE_ID = os.getenv('EXCHANGE_ID', 'binance')
SYMBOL = os.getenv('SYMBOL', 'BTC/USDT:USDT')
TIMEFRAMES = helps.get_env_list('TIMEFRAMES', ['1m', '3m', '1h', '2h'])
MAX_CANDLES_LIMIT = helps.get_env_int('MAX_CANDLES_LIMIT', 1000)
SUPPORTED_EXCHANGES = ['binance', 'okx', 'bybit', 'kucoin']

# Account & Risk Management => Dùng ở core.trading
ACCOUNT_BALANCE = helps.get_env_float('ACCOUNT_BALANCE', 1000.0)
RISK_PER_TRADE_PERCENT = helps.get_env_float('RISK_PER_TRADE_PERCENT', 1.0)
MIN_WIN_PROBABILITY_TO_TRADE = helps.get_env_float('MIN_WIN_PROBABILITY_TO_TRADE', 70.0)
MAX_TRADES_PER_DAY = helps.get_env_int('MAX_TRADES_PER_DAY', 10)

# Binance API Credentials (chỉ cho specific exchanges)
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET = os.getenv('BINANCE_SECRET', '')
BINANCE_SANDBOX = helps.get_env_bool('BINANCE_SANDBOX', True)
USE_TESTNET = helps.get_env_bool('USE_TESTNET', True)




def get_exchange_credentials(exchange_id: str = None) -> dict:
    """
    Trả về credentials phù hợp cho từng sàn.
    Binance: apiKey, secret
    OKX: apiKey, secret, passphrase
    Bybit: apiKey, secret  
    """
    if not exchange_id:
        exchange_id = EXCHANGE_ID
    
    exchange_id = exchange_id.lower()
    
    if exchange_id == 'binance':
        return {
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET,
            'sandbox': BINANCE_SANDBOX,  # Binance testnet
            'options': {
                'defaultType': 'future',  # Binance Futures
            }
        }
    
    elif exchange_id == 'okx':
        return {
            'apiKey': os.getenv('OKX_API_KEY', ''),
            'secret': os.getenv('OKX_SECRET', ''),
            'passphrase': os.getenv('OKX_PASSPHRASE', ''),  # OKX cần passphrase
            'sandbox': helps.get_env_bool('OKX_SANDBOX', True)
        }
    
    elif exchange_id == 'bybit':
        return {
            'apiKey': os.getenv('BYBIT_API_KEY', ''),
            'secret': os.getenv('BYBIT_SECRET', ''),
            'testnet': helps.get_env_bool('BYBIT_TESTNET', True)  # Bybit testnet
        }
    
    elif exchange_id == 'kucoin':
        return {
            'apiKey': os.getenv('KUCOIN_API_KEY', ''),
            'secret': os.getenv('KUCOIN_SECRET', ''),
            'passphrase': os.getenv('KUCOIN_PASSPHRASE', ''),  # KuCoin cũng cần passphrase
            'sandbox': helps.get_env_bool('KUCOIN_SANDBOX', True)
        }
    
    else:
        # Generic fallback
        return {
            'apiKey': os.getenv(f'{exchange_id.upper()}_API_KEY', ''),
            'secret': os.getenv(f'{exchange_id.upper()}_SECRET', ''),
        }

