import asyncio
import sys
import time
from app.services.bot_service import BotService


bot = BotService()

def setup_event_loop():
    """Cấu hình event loop cho Windows"""
    if sys.platform == 'win32':
        # Fix Windows asyncio issue
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    """Entry point chính"""
    setup_event_loop()
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n👋 Người dùng đã dừng bot!")
        
    except Exception as e:
        print(f"\n🛑 Lỗi khi chạy bot: {e}")
    finally:
        await bot.shutdown()   

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Tạm biệt!")
    except asyncio.CancelledError:
        print("\n🛑 Bot đã bị hủy!")
    except Exception as e:
        print(f"\n💥 Lỗi khởi động: {e}")
    finally:
        print("✅ Bot đã tắt hoàn toàn.")