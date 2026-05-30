from .trading import *
from .indicator_constants import *
from .discord_constants import *
from .app_constants import *

def validate_config():
    """Validate environment config"""
    errors = []
    
    if not SYMBOL:
        errors.append("SYMBOL is required")
    
    if not TIMEFRAMES:
        errors.append("TIMEFRAMES is required")
        
    if ACCOUNT_BALANCE <= 0:
        errors.append("ACCOUNT_BALANCE must be positive")
    
    # Validate Exchange ID
    if EXCHANGE_ID.lower() not in SUPPORTED_EXCHANGES:
        errors.append(f"EXCHANGE_ID must be one of: {SUPPORTED_EXCHANGES}")
        
    # Validate Discord (optional warning)
    if not DISCORD_WEBHOOK_URL or 'YOUR_WEBHOOK_HERE' in DISCORD_WEBHOOK_URL:
        print("⚠️  DISCORD_WEBHOOK_URL not configured - notifications disabled")
        
    # Validate credentials nếu không phải paper trading
    if not ENABLE_PAPER_TRADING:
        creds = get_exchange_credentials()
        if not creds.get('apiKey') or not creds.get('secret'):
            errors.append(f"API credentials required for live trading on {EXCHANGE_ID}")
            
        # Special check cho exchanges cần passphrase
        if EXCHANGE_ID.lower() in ['okx', 'kucoin'] and not creds.get('passphrase'):
            errors.append(f"{EXCHANGE_ID.upper()} requires passphrase for API access")
        
    if errors:
        raise ValueError(f"Configuration errors: {'; '.join(errors)}")
    
    print("✅ Configuration validated successfully")
    print(f"📊 Exchange: {EXCHANGE_ID} ({'Testnet' if USE_TESTNET or BINANCE_SANDBOX else 'Live'})")
    print(f"💰 Symbol: {SYMBOL}")
    print(f"📱 Paper Trading: {'ON' if ENABLE_PAPER_TRADING else 'OFF'}")
