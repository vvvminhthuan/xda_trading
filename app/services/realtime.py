import asyncio
import time
from typing import Awaitable, Callable
from pandas import DataFrame

from app.adapters.binance import BinanceAdapter
from app.adapters.discord import DiscordAdapter
from app.constants.discord_constants import (
    DISCORD_SYMBOL_OPTIONS,
    DISCORD_TOP_MOVERS_10_VALUE,
    DISCORD_TOP_VOLUME_10_VALUE,
)
from app.models.embed import Embed
from app.models.signal import SignalStrength, TradingSignal
from app.services.discord.formatters import format_analysis_summary_embed
from app.services.discord_message_queue import DiscordMessageQueueService
from app.services.signal_verification import SignalVerificationService
from app.services.trading import TradingService
from app.strategies.futures import FuturesStrategy
from app.constants import trading as tc

from app.core.trading import Trading, TradingType

class RealtimeService:
    """Dịch vụ theo dõi dữ liệu thời gian thực từ sàn giao dịch. Hiện tại chỉ hỗ trợ Binance thông qua BinanceAdapter."""
    
    def __init__(self, discord_adapter: DiscordAdapter):
        self.discord_adapter = discord_adapter
        self.discord_message_queue = DiscordMessageQueueService(discord_adapter)
        self.binance_adapter = BinanceAdapter()  # Lưu trữ dữ liệu nến theo thời gian thực
        self.stats = {
            'total_signals': 0,
            'signals_per_timeframe': {},
            'uptime_start': None
        }
        self.trading_service = None  # Sẽ được khởi tạo sau khi kiểm tra kết nối Binance
        self.trading_core = Trading()
        self.strategies = {}
        self.futures = FuturesStrategy(self.trading_core) # Giữ tương thích với luồng single-symbol cũ.
        self.signal_verification = SignalVerificationService()
        self.symbol_market_options = []
        self.watch_mode = "single_symbol"
        self.discord_analysis_log_enabled = False
        self.signal_action_sender = None
        self.is_running = False
        self.is_stopped = False

    async def initialize(self):
        """Khởi tạo kết nối và kiểm tra kết nối với Binance."""
        if not await self.binance_adapter.is_connected():
            raise ConnectionError("Không thể kết nối tới Binance. Vui lòng kiểm tra API key và kết nối mạng.")

        await self.refresh_symbol_market_options()
        timeframes = self.trading_core.get_timeframe()
        self.trading_service = TradingService(self.binance_adapter, timeframes, self.on_signal)
        self.discord_message_queue.start()
        await self.discord_message_queue.enqueue("✅ Kết nối Binance thành công! Bot đã sẵn sàng theo dõi dữ liệu thời gian thực.")
        await self.trading_service.initialize()  # Khởi tạo TradingService sau khi đã kiểm tra kết nối Binance
        
        self._ensure_strategy(self.current_symbol())
        self._sync_strategies_from_history()
        print("✅ RealtimeService đã được khởi tạo thành công!")
        
        # Gởi test signal lên Discord để xác nhận kết nối thành công nếu cần thiết
    async def run(self):
        """Chạy dịch vụ theo dõi thời gian thực."""
        # Cập nhật thời gian bắt đầu hoạt động của bot
        self.stats['uptime_start'] = time.time()
        self.is_running = True
        self.is_stopped = False
        try:
            while self.is_running and self.trading_service:
                await self.trading_service.start()
                if self.is_running:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("🔴 RealtimeService đã bị hủy")
            self.is_running = False
            raise
        except Exception as e:
            print(f"❌ Lỗi khi chạy TradingService: {e}")
        finally:
            await self.stop()

    async def on_signal(self, data_frame: DataFrame, timeframe: str, symbol: str):
        """Callback khi có nến mới từ Binance. 
        Kiểm tra tín hiệu và gởi thông báo nếu có tín hiệu đủ điều kiện."""

        # Cập nhật dữ liệu vào strategy riêng của symbol để không lẫn dữ liệu multi-symbol.
        strategy = self._ensure_strategy(symbol)
        strategy.update_data(timeframe=timeframe, df=data_frame)
        self.signal_verification.update_by_latest_candle(symbol, timeframe, data_frame)
        trading_signal = strategy.analyze(timeframe=timeframe, symbol=symbol)
        await self._send_analysis_summary_if_enabled(strategy, timeframe)
        # Kiểm tra tín hiệu dựa trên dữ liệu nến mới nhất và các khung thời gian khác
        print(f"📊 Có nến mới cho {symbol} trên timeframe {timeframe}...")
        if trading_signal and strategy.validate_signal(trading_signal):
            self.stats['total_signals'] += 1
            if timeframe not in self.stats['signals_per_timeframe']:
                self.stats['signals_per_timeframe'][timeframe] = 0
            self.stats['signals_per_timeframe'][timeframe] += 1 
            verification = self.signal_verification.create(
                trading_signal,
                self.trading_core.current_mode.value,
                data_frame
            )
            await self._send_signal(trading_signal)
            if self.signal_action_sender:
                await self.signal_action_sender(trading_signal, verification)
    
    async def stop(self):
        """Dừng dịch vụ theo dõi thời gian thực."""
        if self.is_stopped:
            return
        self.is_running = False
        if self.trading_service:
            await self.trading_service.stop()
            self.trading_service = None
        await self.discord_message_queue.stop()
        self.is_stopped = True
        print("✅ RealtimeService đã được dừng!")

    async def switch_symbol(self, symbol: str) -> str:
        """Đổi symbol hoặc watchlist đang theo dõi và nạp lại dữ liệu timeframe hiện tại."""
        if symbol in {DISCORD_TOP_VOLUME_10_VALUE, DISCORD_TOP_MOVERS_10_VALUE} and not self.symbol_market_options:
            await self.refresh_symbol_market_options()
        if symbol not in self.symbol_options():
            return f"Symbol `{symbol}` không nằm trong danh sách được phép."
        if not self.trading_service:
            return "Trading service chưa sẵn sàng để đổi symbol."
        symbols = self._resolve_symbol_selection(symbol)
        if not symbols:
            return f"Không tìm thấy symbol phù hợp cho lựa chọn `{symbol}`."
        await self.trading_service.prepare_symbols(symbols)
        self.watch_mode = self._resolve_watch_mode(symbol)
        self._rebuild_strategies(symbols)
        self._sync_strategies_from_history()
        self.trading_service.start_watchers()
        if len(symbols) == 1:
            return f"Đã đổi symbol sang `{symbols[0]}`."
        return f"Đã đổi watchlist `{self.watch_mode}` với {len(symbols)} symbol."

    def switch_mode(self, mode: str) -> str:
        """Đổi mode giao dịch từ Discord command hoặc logic điều phối runtime."""
        normalized_mode = mode.lower()
        if normalized_mode not in self.mode_options():
            return f"Mode `{mode}` không hợp lệ."
        trading_type = TradingType(normalized_mode)
        self.trading_core.switch_mode(trading_type)
        self._rebuild_strategies(self.current_symbols())
        self._sync_strategies_from_history()
        return f"Đã đổi mode sang `{normalized_mode}`."

    def status(self) -> str:
        """Trả về trạng thái ngắn gọn của bot để Discord command hiển thị."""
        status = self.status_data()
        return (
            f"Mode: {status['mode']} | "
            f"Symbol: {status['symbol']} | "
            f"Watch: {status['watch_mode']} ({status['watch_symbol_count']}) | "
            f"Signals: {status['total_signals']} | "
            f"Verified: {status['verified_signals']} | "
            f"Win rate: {status['win_rate']:.1f}%"
        )

    def status_data(self) -> dict:
        """Trả dữ liệu trạng thái dạng dict để Discord control panel render ổn định."""
        verification_stats = self.signal_verification.stats()
        return {
            'mode': self.trading_core.current_mode.value,
            'symbol': self.current_symbol(),
            'watch_mode': self.watch_mode,
            'analysis_log_enabled': self.discord_analysis_log_enabled,
            'watch_symbols': self.current_symbols(),
            'watch_symbol_count': len(self.current_symbols()),
            'total_signals': self.stats['total_signals'],
            'verified_signals': verification_stats['total_signals'],
            'win_rate': verification_stats['win_rate'],
            'take_profit': verification_stats['take_profit'],
            'stop_loss': verification_stats['stop_loss'],
            'expired': verification_stats['expired'],
            'open_signals': verification_stats['open'],
            'waiting_entry': verification_stats['waiting_entry'],
            'confirmed_signals': verification_stats['confirmed'],
            'skipped_signals': verification_stats['skipped'],
            'pending_responses': verification_stats['pending_response'],
        }

    def set_signal_action_sender(self, sender: Callable[[TradingSignal, object], Awaitable[bool]]):
        """Inject callback gửi signal action panel từ Discord app bot.

        Tham số:
        - sender: Hàm async nhận TradingSignal và SignalVerification để gửi UI xác nhận.
        """
        self.signal_action_sender = sender

    def set_analysis_log(self, state: str) -> str:
        """Bật hoặc tắt gửi analysis summary lên Discord theo slash command `/log`.

        Tham số:
        - state: Chuỗi `on` hoặc `off` lấy từ Discord command.

        Trả về:
        - Message ngắn để phản hồi user trên Discord.
        """
        normalized_state = state.lower()
        if normalized_state not in {"on", "off"}:
            return "Giá trị log không hợp lệ. Dùng `/log on` hoặc `/log off`."
        self.discord_analysis_log_enabled = normalized_state == "on"
        return f"Đã {'bật' if self.discord_analysis_log_enabled else 'tắt'} analysis summary lên Discord."

    def confirm_signal(self, verification_id: str, user_id: int | str) -> str:
        """Ghi nhận user xác nhận signal từ Discord action panel."""
        verification = self.signal_verification.confirm(verification_id, user_id)
        if not verification:
            return "Không tìm thấy signal cần xác nhận."
        return (
            f"Đã xác nhận signal `{verification.symbol}` `{verification.timeframe}`. "
            "Bot chỉ ghi nhận/paper tracking, chưa vào lệnh thật."
        )

    def skip_signal(self, verification_id: str, user_id: int | str) -> str:
        """Ghi nhận user bỏ qua signal từ Discord action panel."""
        verification = self.signal_verification.skip(verification_id, user_id)
        if not verification:
            return "Không tìm thấy signal cần bỏ qua."
        return f"Đã bỏ qua signal `{verification.symbol}` `{verification.timeframe}`."

    def current_symbol(self) -> str:
        """Lấy symbol đang được TradingService theo dõi."""
        if self.trading_service:
            return self.trading_service.symbol
        return tc.SYMBOL

    def current_symbols(self) -> list[str]:
        """Lấy watchlist symbol hiện tại."""
        if self.trading_service:
            return self.trading_service.symbols
        return [tc.SYMBOL]

    def mode_options(self) -> list[str]:
        """Trả danh sách mode hợp lệ cho Discord select menu."""
        return [mode.value for mode in TradingType]

    def symbol_options(self) -> list[str]:
        """Trả danh sách symbol hợp lệ cho Discord select menu."""
        symbols = DISCORD_SYMBOL_OPTIONS or [
            option["symbol"] for option in self.symbol_market_options
        ] or [self.current_symbol()]
        if self.current_symbol() not in symbols:
            symbols = [self.current_symbol(), *symbols]
        return [
            DISCORD_TOP_VOLUME_10_VALUE,
            DISCORD_TOP_MOVERS_10_VALUE,
            *symbols,
        ][:25]

    def symbol_select_options(self) -> list[dict]:
        """Trả danh sách option label/value để Discord select hiển thị symbol và phần trăm dao động."""
        options = self.symbol_market_options or [{
            "symbol": self.current_symbol(),
            "label": f"{self.current_symbol()} (config)",
            "percentage": 0.0,
        }]
        current_symbol = self.current_symbol()
        if not any(option["symbol"] == current_symbol for option in options):
            options = [{
                "symbol": current_symbol,
                "label": f"{current_symbol} (current)",
                "percentage": 0.0,
            }, *options]
        special_options = [
            {
                "label": "Top 10 Volume",
                "value": DISCORD_TOP_VOLUME_10_VALUE,
                "description": "Theo dõi 10 symbol có volume cao nhất",
            },
            {
                "label": "Top 10 Movers",
                "value": DISCORD_TOP_MOVERS_10_VALUE,
                "description": "Theo dõi 10 symbol dao động mạnh nhất",
            },
        ]
        symbol_options = [
            {
                "label": option["label"],
                "value": option["symbol"],
                "description": self._format_symbol_option_description(option),
            }
            for option in options[:23]
        ]
        return [*special_options, *symbol_options]

    async def refresh_symbol_market_options(self) -> list[dict]:
        """Cập nhật cache symbol từ Binance để control panel có dữ liệu dao động mới."""
        options = await self.binance_adapter.fetch_symbol_market_options()
        if DISCORD_SYMBOL_OPTIONS:
            allowed_symbols = set(DISCORD_SYMBOL_OPTIONS)
            options = [
                option for option in options
                if option["symbol"] in allowed_symbols
            ] or [
                {
                    "symbol": symbol,
                    "label": f"{symbol} (env)",
                    "percentage": 0.0,
                    "quote_volume": 0.0,
                }
                for symbol in DISCORD_SYMBOL_OPTIONS[:100]
            ]
        self.symbol_market_options = options
        return self.symbol_market_options

    def _format_symbol_option_description(self, option: dict) -> str:
        """Tạo mô tả ngắn cho option symbol trên Discord select."""
        percentage = float(option.get("percentage", 0.0))
        sign = "+" if percentage >= 0 else ""
        return f"Dao động 24h/ngày trước: {sign}{percentage:.2f}%"
    
    def print_stats(self):
        """In thống kê hiện tại"""
        if not self.stats['uptime_start']:
            return

        uptime = time.time() - self.stats['uptime_start']
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        
        print(f"\n📊 THỐNG KÊ BOT (Uptime: {hours}h {minutes}m)")
        print(f"📈 Tổng signals: {self.stats['total_signals']}")
        for timeframe in self.stats['signals_per_timeframe']:
            print(f"⏰ Signals trên {timeframe}: {self.stats['signals_per_timeframe'][timeframe]}")
        verification_stats = self.signal_verification.stats()
        print(f"✅ Signal TP: {verification_stats['take_profit']}")
        print(f"🛑 Signal SL: {verification_stats['stop_loss']}")
        print(f"⌛ Signal hết hạn: {verification_stats['expired']}")
        print(f"🎯 Accuracy: {verification_stats['win_rate']:.1f}%")
        print("👋"*2, "=" * 60,"👋"*2)
    
    async def _send_signal(self, signal: TradingSignal):
        """Tạo Discord embed từ TradingSignal và gửi thông báo tín hiệu."""
        embed = Embed()
        embed.color = self._resolve_signal_color(signal)
        if self.trading_core.current_mode == TradingType.REVERSAL:
            reversal_label = "Quay đầu lên" if signal.signal_type.value == "LONG" else "Quay đầu xuống"
            embed.title = f"⏰ {signal.symbol} REVERSAL {signal.signal_type.value} - {reversal_label} ⏰"
        else:
            embed.title = f"⏰ {signal.symbol} Có xu hướng {signal.signal_type.value} ⏰"
        embed.fields = signal.to_embed_fields()
        embed.fields.insert(0, {
            "name": "Mode",
            "value": self.trading_core.current_mode.value,
            "inline": True,
        })

        await self.discord_message_queue.enqueue(embed)

    def _resolve_signal_color(self, signal: TradingSignal) -> int:
        """Chọn màu Discord embed theo chất lượng tín hiệu và mode hiện tại.

        Tham số:
        - signal: TradingSignal đã được strategy tạo, có score, strength và hướng LONG/SHORT.

        Trả về:
        - Mã màu dạng integer hex để Discord embed hiển thị trực quan chất lượng signal.
        """
        if self.trading_core.current_mode == TradingType.REVERSAL and signal.strength in {
            SignalStrength.STRONG,
            SignalStrength.VERY_STRONG,
        }:
            if signal.signal_type.value == "SHORT":
                return 0xE74C3C
            return 0x2ECC71
        if signal.strength == SignalStrength.VERY_STRONG or signal.score >= 85:
            return 0x2ECC71
        if signal.strength == SignalStrength.STRONG or signal.score >= 70:
            return 0x3498DB
        if signal.strength == SignalStrength.MODERATE or signal.score >= 50:
            return 0xF1C40F
        return 0x95A5A6

    async def _send_analysis_summary_if_enabled(self, strategy: FuturesStrategy, timeframe: str):
        """Gửi analysis summary lên Discord nếu user đã bật `/log on` và timeframe là primary."""
        if not self.discord_analysis_log_enabled:
            return
        if timeframe not in self.trading_core.config.primary_timeframes:
            return
        analysis = strategy.last_analysis.get(timeframe)
        if not analysis:
            return
        await self.discord_message_queue.enqueue(format_analysis_summary_embed(analysis))

    def _resolve_symbol_selection(self, value: str) -> list[str]:
        """Chuyển lựa chọn Discord thành watchlist symbol cụ thể.

        Tham số:
        - value: Symbol đơn hoặc special option như TOP_VOLUME_10/TOP_MOVERS_10.

        Trả về:
        - Danh sách symbol đã được giới hạn theo lựa chọn.
        """
        if value == DISCORD_TOP_VOLUME_10_VALUE:
            return [
                option["symbol"]
                for option in self.binance_adapter.top_volume_options(self.symbol_market_options, limit=10)
            ]
        if value == DISCORD_TOP_MOVERS_10_VALUE:
            return [
                option["symbol"]
                for option in self.binance_adapter.top_mover_options(self.symbol_market_options, limit=10)
            ]
        return [value]

    def _resolve_watch_mode(self, value: str) -> str:
        """Quy đổi lựa chọn Discord thành tên watch mode hiển thị trong control panel."""
        if value == DISCORD_TOP_VOLUME_10_VALUE:
            return "top_volume_10"
        if value == DISCORD_TOP_MOVERS_10_VALUE:
            return "top_movers_10"
        return "single_symbol"

    def _ensure_strategy(self, symbol: str) -> FuturesStrategy:
        """Lấy hoặc tạo FuturesStrategy riêng cho symbol để tránh lẫn market data."""
        if symbol not in self.strategies:
            self.strategies[symbol] = FuturesStrategy(self.trading_core)
        self.futures = self.strategies[symbol]
        return self.strategies[symbol]

    def _rebuild_strategies(self, symbols: list[str]):
        """Tạo lại strategy theo watchlist hiện tại, dùng khi đổi mode hoặc đổi watchlist."""
        self.strategies = {
            symbol: FuturesStrategy(self.trading_core)
            for symbol in symbols
        }
        self.futures = self.strategies[symbols[0]] if symbols else FuturesStrategy(self.trading_core)

    def _sync_strategies_from_history(self):
        """Nạp dữ liệu lịch sử đúng symbol/timeframe vào strategy tương ứng."""
        if not self.trading_service:
            return
        for symbol in self.current_symbols():
            strategy = self._ensure_strategy(symbol)
            frames = self.trading_service.frames_for_symbol(symbol)
            for timeframe in self.trading_core.get_timeframe():
                data_frame = frames.get(timeframe=timeframe)
                if not data_frame.empty:
                    strategy.update_data(timeframe=timeframe, df=data_frame)
