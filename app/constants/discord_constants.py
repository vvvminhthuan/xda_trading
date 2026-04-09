# Discord
import os

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_BLOCK_TIME = int(os.getenv('DISCORD_BLOCK_TIME', 12))  # Thời gian chặn gửi message tiếp theo (giây)