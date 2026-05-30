import ccxt.pro as ccxt
import gc
import asyncio
from app.constants import trading as tc
from typing import Any, Dict, List, AsyncGenerator

class BinanceAdapter:
    """Dịch vụ kết nối và lấy dữ liệu từ Binance thông qua ccxt.pro
    Cung cấp các phương thức để lấy dữ liệu OHLCV và theo dõi dữ liệu theo thời gian thực.
    Kiem tra kết nối và xử lý lỗi khi sau khi tạo một đối tượng BinanceAdapter."""
    
    def __init__(self):
        exchange_config = {
            'apiKey': tc.BINANCE_API_KEY,
            'secret': tc.BINANCE_SECRET,
            'rateLimit': 1200,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Binance Futures
                'adjustForTimeDifference': True,
                'recvWindow': 10000,
            }
        }
        self.exchange = ccxt.binance({
            **exchange_config
        })
        # if tc.BINANCE_SANDBOX or tc.USE_TESTNET:
        #     self.exchange.set_sandbox_mode(True)

    async def is_connected(self) -> bool:
        """Kiểm tra kết nối với Binance bằng cách lấy thông tin tài khoản."""
        try:
            balance = await self.exchange.fetch_balance()
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
            return []

    async def fetch_symbol_market_options(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Lấy danh sách symbol futures từ Binance kèm phần trăm dao động ticker.

        Tham số:
        - limit: Số lượng symbol tối đa trả về để cache runtime chọn top list.

        Trả về:
        - Danh sách dict gồm symbol, label, percentage và quote_volume.
        """
        try:
            # `load_markets` tải metadata symbol từ ccxt, phù hợp để lọc futures/swap USDT active.
            markets = await self.exchange.load_markets()
            symbols = [
                symbol for symbol, market in markets.items()
                if self._is_supported_futures_symbol(symbol, market)
            ]
            if not symbols:
                return self._fallback_symbol_options()

            # `fetch_tickers` lấy ticker hàng loạt để đọc percentage 24h/ngày trước cho control panel.
            tickers = await self.exchange.fetch_tickers()
            options = []
            for symbol in symbols:
                ticker = tickers.get(symbol) or {}
                percentage = self._resolve_ticker_percentage(ticker)
                if percentage is None:
                    continue
                options.append({
                    "symbol": symbol,
                    "label": self._format_symbol_label(symbol, percentage),
                    "percentage": percentage,
                    "quote_volume": self._resolve_ticker_quote_volume(ticker),
                })

            options.sort(key=lambda item: abs(item["percentage"]), reverse=True)
            return self._ensure_current_symbol_option(options[:limit], limit)
        except Exception as e:
            print(f"❌ Lỗi khi lấy danh sách symbol Binance: {e}")
            return self._fallback_symbol_options()
    
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

    async def watch_ticker(self, symbol: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Theo dõi ticker realtime để paper trading kiểm tra entry, stop loss và take profit."""
        try:
            while True:
                ticker = await self.exchange.watch_ticker(symbol)
                if ticker:
                    yield ticker
        except ccxt.NetworkError as e:
            print(f"❌ Lỗi mạng khi theo dõi ticker cho {symbol}: {e}")
        except ccxt.ExchangeError as e:
            print(f"❌ Lỗi sàn giao dịch khi theo dõi ticker cho {symbol}: {e}")
        except Exception as e:
            print(f"❌ Lỗi khi theo dõi ticker cho {symbol}: {e}")

    def _is_supported_futures_symbol(self, symbol: str, market: Dict[str, Any]) -> bool:
        """Kiểm tra market Binance có phù hợp để hiển thị trong control panel hay không."""
        if not market.get("active", True):
            return False
        if market.get("quote") != "USDT":
            return False
        return bool(market.get("swap") or market.get("future") or market.get("linear")) and ":USDT" in symbol

    def _resolve_ticker_percentage(self, ticker: Dict[str, Any]) -> float | None:
        """Lấy phần trăm dao động từ ticker ccxt và fallback bằng open/last nếu cần."""
        percentage = ticker.get("percentage")
        if percentage is not None:
            return self._safe_float(percentage)
        open_price = ticker.get("open")
        last_price = ticker.get("last")
        if open_price and last_price:
            open_value = self._safe_float(open_price)
            last_value = self._safe_float(last_price)
            if open_value:
                return (last_value - open_value) / open_value * 100
        return None

    def _resolve_ticker_quote_volume(self, ticker: Dict[str, Any]) -> float:
        """Lấy quote volume từ ticker để xếp hạng thanh khoản symbol.

        Tham số:
        - ticker: Dữ liệu ticker do ccxt trả về, có thể chứa quoteVolume trực tiếp hoặc trong info.

        Trả về:
        - Quote volume dạng float; trả 0.0 nếu exchange không cung cấp dữ liệu phù hợp.
        """
        for key in ("quoteVolume", "quote_volume"):
            value = ticker.get(key)
            if value is not None:
                return self._safe_float(value)
        info = ticker.get("info") or {}
        for key in ("quoteVolume", "quote_volume"):
            value = info.get(key)
            if value is not None:
                return self._safe_float(value)
        base_volume = ticker.get("baseVolume")
        return self._safe_float(base_volume) if base_volume is not None else 0.0

    def top_volume_options(self, options: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """Lấy danh sách symbol có quote volume cao nhất.

        Tham số:
        - options: Danh sách option symbol đã có `quote_volume`.
        - limit: Số lượng symbol tối đa cần lấy.

        Trả về:
        - Danh sách option được sắp xếp giảm dần theo quote volume.
        """
        return sorted(
            options,
            key=lambda item: self._safe_float(item.get("quote_volume", 0.0)),
            reverse=True,
        )[:limit]

    def top_mover_options(self, options: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """Lấy danh sách symbol có dao động phần trăm tuyệt đối cao nhất."""
        return sorted(
            options,
            key=lambda item: abs(self._safe_float(item.get("percentage", 0.0))),
            reverse=True,
        )[:limit]

    def _safe_float(self, value: Any) -> float:
        """Chuyển dữ liệu exchange sang float và fallback 0.0 nếu giá trị không hợp lệ."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _format_symbol_label(self, symbol: str, percentage: float) -> str:
        """Tạo label ngắn cho Discord select, gồm symbol và phần trăm dao động."""
        sign = "+" if percentage >= 0 else ""
        return f"{symbol} ({sign}{percentage:.2f}%)"

    def _ensure_current_symbol_option(self, options: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Đảm bảo symbol mặc định trong config luôn có trong danh sách select."""
        if any(option["symbol"] == tc.SYMBOL for option in options):
            return options[:limit]
        return [
            {
                "symbol": tc.SYMBOL,
                "label": f"{tc.SYMBOL} (config)",
                "percentage": 0.0,
                "quote_volume": 0.0,
            },
            *options,
        ][:limit]

    def _fallback_symbol_options(self) -> List[Dict[str, Any]]:
        """Tạo option fallback khi Binance không trả được danh sách symbol."""
        return [{
            "symbol": tc.SYMBOL,
            "label": f"{tc.SYMBOL} (config)",
            "percentage": 0.0,
            "quote_volume": 0.0,
        }]
    
    async def close(self):
        """Đóng kết nối với Binance nếu cần thiết. Phải sử dụng ở các dịch vụs khác gọi lớp dịch vụ này."""
        if not self.exchange:
            return
        exchange = self.exchange
        self.exchange = None
        try:
            await exchange.close()
            print("✅ Kết nối Binance đã được đóng.")
        except (asyncio.CancelledError, RuntimeError) as e:
            print(f"⚠️  Bỏ qua lỗi khi đóng Binance trong lúc shutdown: {e}")
        finally:
            gc.collect()  # Giải phóng bộ nhớ sau khi đóng kết nối

            
