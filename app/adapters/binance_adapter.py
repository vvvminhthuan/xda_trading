import ccxt.pro as ccxt
import gc
from app.constants import trading_constants as tc
from typing import List, AsyncGenerator

class BinanceAdapter:
    """Dịch vụ kết nối và lấy dữ liệu từ Binance thông qua ccxt.pro
    Cung cấp các phương thức để lấy dữ liệu OHLCV và theo dõi dữ liệu theo thời gian thực."""
    
    def __init__(self):
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

    def is_connected(self) -> bool:
        """Kiểm tra kết nối với Binance bằng cách lấy thông tin tài khoản."""
        try:
            balance = self.exchange.fetch_balance()
            print(f"✅ Kết nối Binance thành công! Số dư tài khoản: {balance['total']['USDT']} USDT")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối Binance: {e}")
            return False
        
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> List[List]:
        """Lấy dữ liệu OHLCV từ Binance và lưu vào CandleFrames"""
        try:
            print(f"✅ Đã cập nhật dữ liệu OHLCV cho {symbol} - {timeframe}")
            return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"❌ Lỗi khi lấy OHLCV cho {symbol} - {timeframe}: {e}")
            return [None]
    
    async def watch_ohlcv(self, symbol: str, timeframe: str) -> AsyncGenerator[List[List], None]:
        """Theo dõi dữ liệu OHLCV theo thời gian thực và gọi callback khi có nến mới."""
        try:
            while True:
                ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
                if ohlcv:
                    yield ohlcv[-1]  # Chỉ lấy nến mới nhất
        except ccxt.NetworkError as e:
            print(f"❌ Lỗi mạng khi theo dõi OHLCV cho {symbol} - {timeframe}: {e}")
        except ccxt.ExchangeError as e:
            print(f"❌ Lỗi sàn giao dịch khi theo dõi OHLCV cho {symbol} - {timeframe}: {e}")
        except Exception as e:
            print(f"❌ Lỗi khi theo dõi OHLCV cho {symbol} - {timeframe}: {e}")
    
    async def close(self):
        """Đóng kết nối với Binance nếu cần thiết. Phải sử dụng ở các dịch vụs khác gọi lớp dịch vụ này."""
        if self.exchange:
            await self.exchange.close()
            print("✅ Kết nối Binance đã được đóng.")
            gc.collect()  # Giải phóng bộ nhớ sau khi đóng kết nối

            