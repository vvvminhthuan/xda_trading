# Discord
import os

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_BLOCK_TIME = int(os.getenv('DISCORD_BLOCK_TIME', 12))  # Thời gian chặn gửi message tiếp theo (giây)
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID', '')
DISCORD_CONTROL_CHANNEL_ID = os.getenv('DISCORD_CONTROL_CHANNEL_ID', '')
DISCORD_ALLOWED_USER_IDS = [
    user_id.strip()
    for user_id in os.getenv('DISCORD_ALLOWED_USER_IDS', '').split(',')
    if user_id.strip()
]
DISCORD_SYMBOL_OPTIONS = [
    symbol.strip()
    for symbol in os.getenv('DISCORD_SYMBOL_OPTIONS', '').split(',')
    if symbol.strip()
]

DISCORD_TOP_VOLUME_10_VALUE = "TOP_VOLUME_10"
DISCORD_TOP_MOVERS_10_VALUE = "TOP_MOVERS_10"
DISCORD_SPECIAL_SYMBOL_VALUES = {
    DISCORD_TOP_VOLUME_10_VALUE,
    DISCORD_TOP_MOVERS_10_VALUE,
}
