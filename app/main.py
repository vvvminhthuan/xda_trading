import asyncio
import signal
import sys
from app.services.realtime import RealtimeService 
from app.adapters.discord import DiscordAdapter
from app.services.discord_bot import DiscordBotService
from app.constants import validate_config

def setup_event_loop():
    """Cấu hình event loop cho Windows"""
    if sys.platform == 'win32':
        # Fix Windows asyncio issue
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def log_background_task_result(task: asyncio.Task):
    """Ghi log lỗi của task nền để lỗi Discord app bot không bị bỏ qua."""
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as e:
        print(f"❌ Discord app bot lỗi: {e}")

async def stop_discord_app_bot(discord_bot: DiscordBotService | None, discord_bot_task: asyncio.Task | None):
    """Dừng Discord app bot và chờ task nền kết thúc trước khi event loop đóng."""
    if discord_bot and discord_bot_task and not discord_bot_task.done():
        await discord_bot.stop()
    if not discord_bot_task:
        return
    if not discord_bot_task.done():
        discord_bot_task.cancel()
    await asyncio.gather(discord_bot_task, return_exceptions=True)

def register_shutdown_signals(shutdown_event: asyncio.Event):
    """Đăng ký SIGINT/SIGTERM để shutdown async có thời gian đóng websocket/session."""
    loop = asyncio.get_running_loop()

    def request_shutdown():
        print("\n🔴 Đã nhận yêu cầu dừng bot, đang shutdown...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: request_shutdown())

async def main():
    """Entry point chính"""
    bot = None
    discord_bot = None
    discord_bot_task = None
    realtime_task = None
    shutdown_event = asyncio.Event()
    setup_event_loop()
    register_shutdown_signals(shutdown_event)
    discord = DiscordAdapter()
    try:
        print("🚀 Khởi tạo bot...")
        validate_config()
        
        discord_connected = await discord.is_connected()
        if not discord_connected:
            print("❌ Lỗi kết nối Discord. Vui lòng kiểm tra cấu hình.")
            sys.exit(1)
        bot = RealtimeService(discord)
        await bot.initialize()
        discord_bot = DiscordBotService(
            on_symbol_change=bot.switch_symbol,
            on_mode_change=bot.switch_mode,
            on_status=bot.status_data,
            on_symbol_options=bot.symbol_options,
            on_symbol_select_options=bot.symbol_select_options,
            on_symbol_options_refresh=bot.refresh_symbol_market_options,
            on_mode_options=bot.mode_options,
            on_log_change=bot.set_analysis_log,
            on_signal_confirm=bot.confirm_signal,
            on_signal_skip=bot.skip_signal,
        )
        if discord_bot.has_token():
            bot.set_signal_action_sender(discord_bot.send_signal_action_panel)
            # `asyncio.create_task` chạy Discord gateway song song với watcher Binance.
            discord_bot_task = asyncio.create_task(
                discord_bot.start(),
                name="discord_app_bot"
            )
            discord_bot_task.add_done_callback(log_background_task_result)
        print("✅ Bot đã được khởi tạo thành công!")

        realtime_task = asyncio.create_task(bot.run(), name="realtime_service")
        shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown_signal")
        done, pending = await asyncio.wait(
            {realtime_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        if realtime_task in done:
            await realtime_task
    except Exception as e:
        print(f"\n🛑 Lỗi khi chạy bot: {e}")  
    finally:
        if realtime_task and not realtime_task.done():
            realtime_task.cancel()
            await asyncio.gather(realtime_task, return_exceptions=True)
        if bot:
            bot.print_stats()  # In thống kê trước khi dừng
            await bot.stop()
        await stop_discord_app_bot(discord_bot, discord_bot_task)
        await discord.close()
          # Đảm bảo đóng session aiohttp khi bot dừng

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Bot đã dừng. Tạm biệt!👋")
    except asyncio.CancelledError:
        print("\n🛑 Bot đã bị hủy!")
    except Exception as e:
        print(f"\n💥 Lỗi khởi động: {e}")
