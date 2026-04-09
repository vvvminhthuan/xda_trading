import ccxt.pro as ccxt
import asyncio
import traceback
import gc
import pandas as pd
from typing import Dict, Callable, Optional, Any
from datetime import datetime
from app.models.candle import Candle, CandleData
from app.models.signal import TradingSignal
from app.constants import trading_constants as tc
from app.strategies.futures_strategy import MultiTimeframeFuturesStrategy

class OHLCVService:
    """
    Dịch vụ OHLCV realtime với CCXT Pro.
    Lấy dữ liệu các nến cũ, cập nhật nến mới và gửi tới strategy để phân tích.
    Xử lý dữ liệu và rate limiting cho signals.
    Cấu trúc:
    - DataFrame lưu trữ dữ liệu nến cho mỗi timeframe
    - Phân tích dữ liệu mới và tạo signals
    - Callback tới main bot khi có signal mới
    - Thống kê và logging chi tiết
    """
    
    def __init__(self, strategy: MultiTimeframeFuturesStrategy, signal_callback: Callable, CandleData=CandleData):
        self.exchange = None
        self.strategy = strategy
        self.signal_callback = signal_callback
        
        # Data storage cho mỗi timeframe
        self.dfs: Dict[str, pd.DataFrame] = {}
        self.last_timestamps: Dict[str, int] = {}
        
        # Rate limiting cho signals (tránh spam)
        self.last_signal_times: Dict[str, float] = {}
        self.signal_cooldown = 30  # 30 giây giữa các signals cùng timeframe

        # Task management
        self.tasks = [] 
        
        # Initialize DataFrames với proper columns
        for tf in tc.TIMEFRAMES:
            # Create empty DataFrame with DatetimeIndex
            self.dfs[tf] = pd.DataFrame(
                columns=['open', 'high', 'low', 'close', 'volume']
            )
            # Set empty DatetimeIndex
            self.dfs[tf].index = pd.DatetimeIndex([], name='datetime')
            
            self.last_timestamps[tf] = 0
            self.last_signal_times[tf] = 0

    async def initialize_exchange(self):
        """
        Khởi tạo kết nối exchange với CCXT Pro.
        """
        try:
            self.exchange = ccxt.binance({
                'apiKey': tc.BINANCE_API_KEY,
                'secret': tc.BINANCE_SECRET,
                'sandbox': False,  # Thử nghiêm vào lệnh trên testnet nếu cần
                'rateLimit': 1200,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Binance Futures
                }
            })
            # Test connection
            print(f"🔄 Kết nối đến binance...")
            await self.exchange.load_markets()
            
            print(f"✅ Đã tải markets từ binance, tổng symbols: {self.exchange.markets}")
            # Verify symbol exists
            if tc.SYMBOL not in self.exchange.markets:
                raise Exception(f"Symbol {tc.SYMBOL} không tồn tại trên binance")
                
            # Test WebSocket connection
            test_ticker = await self.exchange.watch_ticker(tc.SYMBOL)
            if test_ticker:
                print(f"✅ Kết nối đến binance thành công")
                print(f"📊 {tc.SYMBOL} Giá: ${test_ticker['last']:,.2f}")

                # Fetch historical data trước để bootstrap
                for timeframe in tc.TIMEFRAMES:
                    await self.manual_fetch_history(timeframe, tc.MAX_CANDLES_LIMIT)
                return True
            else:
                raise Exception("Không thể kiểm tra kết nối WebSocket")
                
        except Exception as e:
            print(f"❌ Lỗi khởi tạo exchange: {e}")
            print(f"Debug traceback: {traceback.format_exc()}")
            return False

    async def watch_timeframe(self, timeframe: str):
        """
        Watch OHLCV data cho một timeframe cụ thể qua WebSocket.
        Chạy trong vòng lặp vô hạn để duy trì kết nối.
        """
        if not self.exchange:
            print(f"❌ Exchange chưa được khởi tạo cho {timeframe}")
            return
            
        print(f"🔄 Watcher bắt đầu khung thời gian: {timeframe}")

        while True:
            try:
                # Watch OHLCV stream
                ohlcv = await self.exchange.watch_ohlcv(tc.SYMBOL, timeframe)
                if ohlcv:                    
                    # Process data mới
                    await self._process_ohlcv_data(timeframe, [ohlcv[-1]])  # Chỉ lấy candle mới nhất
                    
                else:
                    print(f"⚠️ Không nhận được data cho {timeframe}")
                    await asyncio.sleep(1)
            # except asyncio.CancelledError as e:
            #     print(f"💥 {timeframe} watcher bị hủy: {e}")
            #     raise

            except ccxt.NetworkError as e:
                print(f"⏳ Exchange lỗi mạng {timeframe}: {e}")
                
            except ccxt.ExchangeError as e:
                print(f"⏱️ Exchange lỗi {timeframe}: {e}")
                    
            except Exception as e:
                print(f"❌ Unexpected error {timeframe}: {e}")
                break
            finally:
                await self.exchange.close()  # Đóng kết nối khi có lỗi hoặc khi dừng
        
        print(f"🔴 {timeframe} watcher stopped")

    async def start_all_watchers(self):
        """
        Khởi chạy tất cả timeframe watchers đồng thời.
        """
        try:
            print(f"\n 🚀 Bắt đầu theo dõi {len(tc.TIMEFRAMES)} timeframes...")
            
            # Tạo tasks cho tất cả timeframes
            for timeframe in tc.TIMEFRAMES:
                task = asyncio.create_task(
                    self.watch_timeframe(timeframe),
                    name=f"watch_{timeframe}"
                )
                self.tasks.append(task)
            
            # Wait for all tasks
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
        except asyncio.CancelledError:
            print("🔄 Dừng các watcher do task bị hủy...")
        except Exception as e:
            print(f"❌ Lỗi start watchers: {e}")
            print(f"Debug traceback: {traceback.format_exc()}")
        finally:
            await self.stop_task()
            await self.cleanup()

    async def cleanup(self):
        """
        Cleanup resources khi dừng service.
        """
        try:
            if self.exchange:
                print("🧹 Đang dọn dẹp kết nối exchange...")
                await self.exchange.close()
                print("🧹 đã qua đây...")
                self.exchange = None
                
            # Force garbage collection
            gc.collect()
            
            print("✅ Đã hủy kết nối exchange và dọn dẹp tài nguyên")
            
        except Exception as e:
            print(f"⚠️ Lỗi dọn dẹp tài nguyên: {e}")

    def get_latest_prices(self) -> Dict[str, float]:
        """
        Lấy giá close mới nhất từ mỗi timeframe.
        """
        prices = {}
        for tf, df in self.dfs.items():
            if len(df) > 0:
                prices[tf] = float(df.iloc[-1]['close'])
        return prices

    async def _process_ohlcv_data(self, timeframe: str, ohlcv_data: list):
        """
        Xử lý dữ liệu OHLCV mới từ WebSocket.
        """
        if not ohlcv_data:
            return
            
        try:
            # Convert CCXT data to DataFrame
            new_candles = []
            latest_timestamp = 0
            
            for candle_array in ohlcv_data:
                # CCXT trả về data dạng array: [timestamp, open, high, low, close, volume]
                if len(candle_array) >= 6:
                    timestamp = int(candle_array[0])  # timestamp in milliseconds
                    open_price = float(candle_array[1])
                    high_price = float(candle_array[2]) 
                    low_price = float(candle_array[3])
                    close_price = float(candle_array[4])
                    volume = float(candle_array[5])
                    print(f"🔄 1.Nhận data mới cho {timeframe} | Số nến nhận được: {len(ohlcv_data)} {ohlcv_data[-1] if ohlcv_data else 'N/A'} | {self.last_timestamps[timeframe]}")
                    # Cập nhật lại nến nếu timestamp đã tồn tại (nến đang hình thành) 
                    # Các giá trị open, high, low, close, volume có thể thay đổi
                    # Chỉ xử lý nến mới (tránh duplicate)
                    if timestamp > self.last_timestamps[timeframe]:
                        new_candles.append({
                            'timestamp': timestamp,
                            'open': open_price,
                            'high': high_price,
                            'low': low_price,
                            'close': close_price,
                            'volume': volume
                        })
                        latest_timestamp = max(latest_timestamp, timestamp)
                    
            if not new_candles:
                return  # Không có data mới
                
            # Create DataFrame with proper DatetimeIndex
            new_df = pd.DataFrame(new_candles)
            
            # Convert timestamp to DatetimeIndex
            new_df['datetime'] = pd.to_datetime(new_df['timestamp'], unit='ms')
            new_df = new_df.set_index('datetime')
            new_df = new_df.drop('timestamp', axis=1)  # Remove original timestamp column
            
            # Merge với data cũ, remove duplicates
            if len(self.dfs[timeframe]) > 0:
                combined_df = pd.concat([self.dfs[timeframe], new_df])
                # Remove duplicates based on index (datetime)
                self.dfs[timeframe] = combined_df[~combined_df.index.duplicated(keep='last')]
            else:
                self.dfs[timeframe] = new_df
            
            # Sort theo datetime index để đảm bảo thứ tự đúng
            self.dfs[timeframe] = self.dfs[timeframe].sort_index()
            
            # Giới hạn số lượng nến trong memory
            if len(self.dfs[timeframe]) > tc.MAX_CANDLES_LIMIT:
                self.dfs[timeframe] = self.dfs[timeframe].tail(tc.MAX_CANDLES_LIMIT)
                
            # Update timestamp tracking
            if latest_timestamp > 0:
                self.last_timestamps[timeframe] = latest_timestamp
            
            # Gửi data tới strategy để phân tích
            await self._analyze_and_signal(timeframe)
            
            # Log progress (chỉ cho khung nhỏ để tránh spam)
            if new_candles:
                latest_candle = self.dfs[timeframe].iloc[-1]
                print(f"📊 {timeframe} | Open: ${latest_candle['open']:,.2f} | Close: ${latest_candle['close']:,.2f} | High: ${latest_candle['high']:,.2f} | Low: ${latest_candle['low']:,.2f}"
                    f"Vol: {latest_candle['volume']:,.0f} | "
                    f"Candles: {len(self.dfs[timeframe])}")
                    
        except Exception as e:
            print(f"❌ Lỗi xử lý data {timeframe}: {e}")
            print(f"Debug traceback: {traceback.format_exc()}")
    
    def _convert_ccxt_to_candle(self, candle_array: list) -> Optional[Candle]:
        """
        Convert CCXT candle array to Candle object.
        CCXT format: [timestamp, open, high, low, close, volume]
        """
        try:
            if len(candle_array) >= 6:
                candle_data = CandleData(
                    timestamp=int(candle_array[0]),
                    open=float(candle_array[1]),
                    high=float(candle_array[2]),
                    low=float(candle_array[3]),
                    close=float(candle_array[4]),
                    volume=float(candle_array[5])
                )
                return Candle(candle_data)
            return None
        except (ValueError, IndexError) as e:
            print(f"❌ Lỗi convert candle: {e}")
            return None
    
    async def _analyze_and_signal(self, timeframe: str):
        """
        Gửi data tới strategy và xử lý signals.
        """
        try:
            # Đảm bảo có đủ data để phân tích
            if len(self.dfs[timeframe]) < 50:  # Cần ít nhất 50 nến
                return
                
            # Update strategy với data mới
            self.strategy.update_data(timeframe, self.dfs[timeframe].copy())
            
            # Chỉ tạo signals từ khung nhỏ (trigger timeframes)
            if timeframe not in ['1m', '3m']:
                return
                
            # Rate limiting - tránh spam signals
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_signal_times[timeframe] < self.signal_cooldown:
                return
                
            # Analyze và tạo signal
            signal = self.strategy.analyze(timeframe)
            
            if signal:
                self.last_signal_times[timeframe] = current_time
                
                # Callback tới main bot
                await self.signal_callback(signal, timeframe)
                
        except Exception as e:
            print(f"❌ Lỗi phân tích {timeframe}: {e}")
            print(f"Debug traceback: {traceback.format_exc()}")

    async def manual_fetch_history(self, timeframe: str, limit: int = 100):
        """
        Fetch lịch sử để bootstrap data nếu cần.
        """
        if not self.exchange:
            return False
            
        try:
            print(f"📥 Lấy dữ liệu lịch sử {tc.SYMBOL} {timeframe} ({limit} nến)")
            
            ohlcv = await self.exchange.fetch_ohlcv(tc.SYMBOL, timeframe, limit=limit)
            
            if ohlcv:
                # Convert to DataFrame with DatetimeIndex
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('datetime')
                df = df.drop('timestamp', axis=1)
                df = df.sort_index()
                
                # Store in dfs
                self.dfs[timeframe] = df
                
                # Update last timestamp
                if len(df) > 0:
                    last_timestamp = int(df.index[-1].timestamp() * 1000)  # Convert back to ms
                    self.last_timestamps[timeframe] = last_timestamp
                
                print(f"✅ Đã tải {len(ohlcv)} nến lịch sử cho {timeframe}")
                return True
                
        except Exception as e:
            print(f"❌ Lỗi lấy dữ liệu lịch sử {timeframe}: {e}")
            print(f"Debug traceback: {traceback.format_exc()}")
            
        return False
    
    async def stop_task(self):
        """
        Dừng service một cách an toàn.
        """
        print("🛑 Đang dừng các watcher...")
        
        try:
            # Cancel tất cả running tasks trước
            # Cancel tasks có tên liên quan đến watchers
            print(f"🔍 {len(self.tasks)} tasks đang chạy")
            for task in self.tasks:
                print(f"📴 Task: {task.get_name()} | Done: {task.done()}")
                if not task.done():
                    print(f"📴 Cancelling task: {task.get_name()}")
                    task.cancel()
                        
            # Đợi tasks cancel
            await asyncio.gather(*self.tasks, return_exceptions=True)   
                
        except Exception as e:
            print(f"⚠️ Lỗi không thể hủy tasks: {e}")
            raise
        
        print("✅ Các Watcher đã được dừng an toàn")

    def _validate_dataframe_for_indicators(self, df: pd.DataFrame) -> bool:
        """
        Validate DataFrame có format đúng cho indicators
        """
        try:
            # Check if index is DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                print("⚠️ DataFrame index is not DatetimeIndex")
                return False
                
            # Check if index is sorted
            if not df.index.is_monotonic_increasing:
                print("⚠️ DataFrame index is not sorted")
                return False
                
            # Check required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"⚠️ Missing required columns: {set(required_cols) - set(df.columns)}")
                return False
                
            return True
            
        except Exception as e:
            print(f"⚠️ DataFrame validation error: {e}")
            return False