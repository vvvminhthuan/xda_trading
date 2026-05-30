import asyncio
from typing import Dict, List

from app.adapters.binance import BinanceAdapter
from app.models.candle_frame import CandleFrames
from app.constants import trading as tc

class TradingService:
    """Dịch vụ chính để quản lý các hoạt động trading, 
    bao gồm việc lấy dữ liệu từ Binance và gửi thông báo đến Discord."""
    
    def __init__(self, binance_adapter: BinanceAdapter, timeframes: List, callback: callable = None):
        self.binance_adapter = binance_adapter
        self.callback = callback
        self.candle_frames_by_symbol: Dict[str, CandleFrames] = {}
        self.symbol = tc.SYMBOL
        self.symbols = [tc.SYMBOL]
        self.candle_frames = self._frames_for_symbol(self.symbol)
        self.timeframes = timeframes
        self.tasks: Dict[str, asyncio.Task] = {}  # Quản lý task theo symbol/timeframe để dừng rõ ràng.
        self.is_running = False
        self.is_stopped = False
        self.retry_delay_seconds = 3

    async def initialize(self):
        """Khởi tạo kết nối và kiểm tra kết nối với Binance."""
        if not await self.binance_adapter.is_connected():
            raise ConnectionError("Không thể kết nối tới Binance. Vui lòng kiểm tra API key và kết nối mạng.")
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                await self._history(symbol, timeframe)
        print("✅ TradingService đã được khởi tạo thành công!")

    async def start(self):
        """Bắt đầu theo dõi dữ liệu OHLCV theo thời gian thực 
        và gọi callback khi có tín hiệu đủ điều kiện."""
        print(f"🚀 Bắt đầu theo dõi {len(self.symbols)} symbol: {', '.join(self.symbols[:5])}")
        try:
            self._start_watchers()
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        except asyncio.CancelledError:
            print(f"🔴 TradingService watcher đã bị hủy")
            self.is_running = False
            await self._cancel_watchers()
            raise
        except Exception as e:
            print(f"❌ Lỗi khi khởi chạy watcher cho watchlist {self.symbols} : {e}")

    def _start_watchers(self):
        """Tạo watcher task cho từng timeframe mà không block luồng gọi hiện tại."""
        self.is_running = True
        self.is_stopped = False
        for symbol in self.symbols:
            for tf in self.timeframes:
                task_key = self._task_key(symbol, tf)
                if task_key in self.tasks and not self.tasks[task_key].done():
                    continue
                task = asyncio.create_task(
                    self._watch(symbol, tf),
                    name=f"{symbol}_{tf}_watcher"
                )
                self.tasks[task_key] = task

    async def _history(self, symbol: str, timeframe: str, limit: int = 1000):
        """Lấy dữ liệu lịch sử OHLCV từ Binance."""
        ohlcv_rows = await self.binance_adapter.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not self._is_valid_ohlcv_rows(ohlcv_rows):
            raise ValueError(f"Dữ liệu OHLCV history không hợp lệ cho {symbol} {timeframe}")
        self._frames_for_symbol(symbol).set(timeframe, ohlcv_rows)
        print(f"📊 Đã lấy dữ liệu lịch sử cho {symbol} trên timeframe {timeframe}")
    
    async def _watch(self, symbol: str, timeframe: str):
        """Theo dõi dữ liệu OHLCV theo thời gian thực và cập nhật vào CandleFrames."""
        print(f"🔍 Bắt đầu theo dõi nến mới cho {symbol} trên timeframe {timeframe}...")
        while self.is_running:
            try:
                async for ohlcv in self.binance_adapter.watch_ohlcv(symbol, timeframe):
                    if not self.is_running:
                        break
                    if not self._is_valid_ohlcv_row(ohlcv):
                        print(f"⚠️  Bỏ qua nến OHLCV không hợp lệ cho {symbol} {timeframe}: {ohlcv}")
                        continue
                    frames = self._frames_for_symbol(symbol)
                    is_new_candle = frames.is_new_closed_candle(timeframe, ohlcv)
                    frames.append(timeframe, ohlcv)

                    # Chỉ gọi strategy khi timestamp đổi để tránh spam signal trên cùng một nến.
                    if self.callback and is_new_candle:
                        await self.callback(frames.get(timeframe), timeframe, symbol)
                if self.is_running:
                    await asyncio.sleep(self.retry_delay_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"❌ Watcher {symbol} {timeframe} lỗi, thử lại sau {self.retry_delay_seconds}s: {e}")
                await asyncio.sleep(self.retry_delay_seconds)

    async def switch_symbol(self, symbol: str):
        """Đổi symbol runtime bằng cách dừng watcher cũ, tải history mới và chạy lại watcher."""
        await self.switch_symbols([symbol])

    async def switch_symbols(self, symbols: List[str]):
        """Đổi watchlist runtime, nạp history rồi bắt đầu watcher realtime."""
        await self.prepare_symbols(symbols)
        self.start_watchers()

    async def prepare_symbols(self, symbols: List[str]):
        """Chuẩn bị watchlist mới nhưng chưa start watcher realtime.

        Tham số:
        - symbols: Danh sách symbol cần theo dõi. Mỗi symbol sẽ được fetch OHLCV history vào CandleFrames riêng.
        """
        cleaned_symbols = self._normalize_symbols(symbols)
        if not cleaned_symbols:
            raise ValueError("Watchlist không có symbol hợp lệ.")
        await self.stop(close_adapter=False)
        self.symbols = cleaned_symbols
        self.symbol = cleaned_symbols[0]
        self.candle_frames_by_symbol = {}
        self.candle_frames = self._frames_for_symbol(self.symbol)
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                await self._history(symbol, timeframe)

    def start_watchers(self):
        """Bắt đầu watcher realtime sau khi service khác đã sync strategy từ history mới."""
        self._start_watchers()

    async def stop(self, close_adapter: bool = True):
        """Dừng tất cả các task đang chạy."""
        if self.is_stopped and not self.tasks:
            return
        self.is_running = False
        print(f"🔍 {len(self.tasks)} tasks đang chạy chuẩn bị dừng...")
        await self._cancel_watchers()
        if close_adapter:
            await self.binance_adapter.close()  # Đảm bảo đóng kết nối với Binance khi dừng dịch vụ
        self.is_stopped = True
        print("✅ Tất cả tasks đã được dừng!")

    async def _cancel_watchers(self):
        """Hủy toàn bộ watcher task và chờ chúng thoát trước khi shutdown hoặc restart symbol."""
        for task in self.tasks.values():
            print(f"📴 Task: {task.get_name()} - Done: {task.done()}")
            if not task.done():
                print(f"🔴 Dừng task: {task.get_name()}")
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()

    def _is_valid_ohlcv_rows(self, rows: List[List]) -> bool:
        """Kiểm tra danh sách nến OHLCV history có đủ dữ liệu để tạo DataFrame.

        Tham số:
        - rows: Danh sách nến từ exchange, mỗi nến cần có timestamp, open, high, low, close, volume.

        Trả về:
        - True nếu danh sách không rỗng và mọi nến có format hợp lệ.
        """
        return bool(rows) and all(self._is_valid_ohlcv_row(row) for row in rows)

    def _is_valid_ohlcv_row(self, row: List) -> bool:
        """Kiểm tra một nến OHLCV có đủ 6 giá trị và không chứa giá trị rỗng."""
        return isinstance(row, list) and len(row) >= 6 and all(value is not None for value in row[:6])

    def _frames_for_symbol(self, symbol: str) -> CandleFrames:
        """Lấy CandleFrames riêng của từng symbol để dữ liệu nhiều symbol không ghi đè nhau."""
        if symbol not in self.candle_frames_by_symbol:
            self.candle_frames_by_symbol[symbol] = CandleFrames()
        return self.candle_frames_by_symbol[symbol]

    def frames_for_symbol(self, symbol: str) -> CandleFrames:
        """Trả CandleFrames của một symbol cho service khác đọc dữ liệu đúng scope symbol."""
        return self._frames_for_symbol(symbol)

    def _task_key(self, symbol: str, timeframe: str) -> str:
        """Tạo key task theo symbol và timeframe để quản lý watcher multi-symbol."""
        return f"{symbol}:{timeframe}"

    def _normalize_symbols(self, symbols: List[str]) -> List[str]:
        """Chuẩn hóa watchlist, bỏ symbol rỗng và giữ nguyên thứ tự xuất hiện đầu tiên."""
        normalized = []
        for symbol in symbols:
            if symbol and symbol not in normalized:
                normalized.append(symbol)
        return normalized
