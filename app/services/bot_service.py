from app.services.discord_service import DiscordService
from app.services.ohlcv_service import OHLCVService
from app.strategies.futures_strategy import MultiTimeframeFuturesStrategy
from app.constants import trading_constants as tc 
import time
import asyncio

class BotService:
    """Quản lý các service chính của bot, bao gồm Discord, 
        Strategy và Ohlcv service khác sẽ được khởi tạo trong tương lai.
    """
    def __init__(self):
        self.ohlcv_service = None
        self.discord_service = DiscordService()
        self.strategy = MultiTimeframeFuturesStrategy()

        self.stats = {
            'total_signals': 0,
            'signals_per_timeframe': {},
            'uptime_start': None
        }
    
    async def initialize(self):
        """Khởi tạo các services và kết nối cần thiết."""
        print("🚀 Khởi động Trading Bot...")
        print(f"📊 Symbol: {tc.SYMBOL}")
        print(f"⏰ Timeframes: {tc.TIMEFRAMES}")
        # print(f"💰 Account Balance: ${tc.ACCOUNT_BALANCE}") Không cần thiết
        print(f"🎯 Min Win Rate: {tc.MIN_WIN_PROBABILITY_TO_TRADE}%")

        # Test Discord connection
        is_connected = await self.discord_service.test_connection()
        if not is_connected:
            print("❌ Lỗi kết nối Discord")
            raise RuntimeError("Không thể kết nối đến Discord")

        # Khởi tạo OHLCV Service
        self.ohlcv_service = OHLCVService(self.strategy, self.on_signal_generated)
        
        # Initialize exchange trước
        if not await self.ohlcv_service.initialize_exchange():
            raise Exception("Không thể khởi tạo exchange")
        
        self.stats['uptime_start'] = time.time()
        print("✅ Bot đã sẵn sàng!")


    async def on_signal_generated(self, signal, timeframe: str):
        """Callback khi có tín hiệu mới từ strategy."""
        if not signal:
            return
        
        # Validate signal
        if not self.strategy.validate_signal(signal):
            print(f"❌ Signal không hợp lệ: {signal.symbol} {signal.action}")
            return
        # Cập nhật thống kê
        self.stats['total_signals'] += 1
        if timeframe not in self.stats['signals_per_timeframe']:
            self.stats['signals_per_timeframe'][timeframe] = 0
        self.stats['signals_per_timeframe'][timeframe] += 1
        
        # Log signal
        print(f"🎯 [SIGNAL #{self.stats['total_signals']}] {signal.action} {signal.symbol}")
        print(f"   📈 Win Prob: {signal.win_probability}% | Score: {signal.score}")
        print(f"   💰 Entry: ${signal.entry_price} | TP: ${signal.take_profit} | SL: ${signal.stop_loss}")
        print(f"   📊 Timeframe: {timeframe} | Reason: {signal.reason}")
        
        # Gửi notification lên Discord
        success = await self.discord_service.send_signal(signal)
        if not success:
            print("❌ Lỗi gửi Discord")
        else:
            print("✅ Đã gửi Discord thành công!")
    
    async def print_stats(self):
        """In thống kê hiện tại"""
        if not self.stats['uptime_start']:
            return
        
        uptime = time.time() - self.stats['uptime_start']
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        
        print(f"\n📊 THỐNG KÊ BOT (Uptime: {hours}h {minutes}m)")
        print(f"📈 Tổng signals: {self.stats['total_signals']}")
        print(f"⏰ Signals theo timeframe: {self.stats['signals_per_timeframe']}")
        print(f"🎯 Trading mode: {self.strategy.trading_mode.current_mode.value}")
        print("=" * 50)
        
    async def shutdown(self):
        """Đóng tất cả connections"""
        print("\n🔄 Đang đóng bot...")
        
        if self.ohlcv_service:
            await self.ohlcv_service.stop_task()
            await self.ohlcv_service.cleanup()
            
        await self.print_stats()
        print("✅ Bot đã đóng an toàn!")

    async def run(self):
        """Bot khởi chạy chính, quản lý vòng đời của bot và xử lý các sự kiện."""
        
        try:
            await self.initialize()            
            # Chạy all watchers
            await self.ohlcv_service.start_all_watchers()        
            
        except KeyboardInterrupt:
            await self.discord_service.send_error_notification("Người dùng đã dừng bot bằng cách nhấn Ctrl+C.")
            print("\n🛑 Người dùng dừng bot...")
            await self.shutdown()
        except asyncio.CancelledError:
            pass  # Cho phép hủy bỏ cleanly
        except Exception as e:
            print(f"\n💥 Lỗi hệ thống: {e}")
            await self.discord_service.send_error_notification(str(e))
        finally:
            await self.discord_service.send_error_notification("Bot đã dừng hoạt động.")
            await self.shutdown()