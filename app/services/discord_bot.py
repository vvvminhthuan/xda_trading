from typing import Awaitable, Callable, Dict, List, Optional

import discord
from discord.ext import commands

from app.constants.discord_constants import (
    DISCORD_ALLOWED_USER_IDS,
    DISCORD_BOT_TOKEN,
    DISCORD_CONTROL_CHANNEL_ID,
    DISCORD_GUILD_ID,
    DISCORD_SPECIAL_SYMBOL_VALUES,
    DISCORD_SYMBOL_OPTIONS,
    DISCORD_TOP_MOVERS_10_VALUE,
    DISCORD_TOP_VOLUME_10_VALUE,
)
from app.constants import trading as tc
from app.models.signal import TradingSignal
from app.models.signal_verification import SignalVerification
from app.services.discord.formatters import format_control_panel, format_signal_action_panel
from app.services.discord.interactions import SignalActionView, TradingControlView


AsyncOrSyncStringHandler = Callable[[str], Awaitable[str] | str]
StatusHandler = Callable[[], Dict[str, object]]
OptionHandler = Callable[[], List[str]]
SymbolSelectOptionHandler = Callable[[], Awaitable[List[Dict[str, str]]] | List[Dict[str, str]]]
SignalDecisionHandler = Callable[[str, int | str], Awaitable[str] | str]


class DiscordBotService:
    """Quản lý Discord app bot để người dùng đổi symbol, đổi mode và xem trạng thái."""

    def __init__(
        self,
        on_symbol_change: Optional[AsyncOrSyncStringHandler] = None,
        on_mode_change: Optional[AsyncOrSyncStringHandler] = None,
        on_status: Optional[StatusHandler] = None,
        on_symbol_options: Optional[OptionHandler] = None,
        on_symbol_select_options: Optional[SymbolSelectOptionHandler] = None,
        on_symbol_options_refresh: Optional[Callable[[], Awaitable[object]]] = None,
        on_mode_options: Optional[OptionHandler] = None,
        on_log_change: Optional[AsyncOrSyncStringHandler] = None,
        on_signal_confirm: Optional[SignalDecisionHandler] = None,
        on_signal_skip: Optional[SignalDecisionHandler] = None,
    ):
        self.token = DISCORD_BOT_TOKEN
        self.allowed_user_ids = set(DISCORD_ALLOWED_USER_IDS)
        self.on_symbol_change = on_symbol_change
        self.on_mode_change = on_mode_change
        self.on_status = on_status
        self.on_symbol_options = on_symbol_options
        self.on_symbol_select_options = on_symbol_select_options
        self.on_symbol_options_refresh = on_symbol_options_refresh
        self.on_mode_options = on_mode_options
        self.on_log_change = on_log_change
        self.on_signal_confirm = on_signal_confirm
        self.on_signal_skip = on_signal_skip
        self.control_channel_id = int(DISCORD_CONTROL_CHANNEL_ID) if DISCORD_CONTROL_CHANNEL_ID.isdigit() else None
        self.guild_id = int(DISCORD_GUILD_ID) if DISCORD_GUILD_ID.isdigit() else None
        self.synced_commands = False
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        if not self.allowed_user_ids:
            print("⚠️  DISCORD_ALLOWED_USER_IDS chưa được cấu hình, tất cả lệnh điều khiển Discord sẽ bị từ chối.")
        self._register_commands()

    def _is_allowed(self, user_id: int) -> bool:
        """Kiểm tra người dùng Discord có quyền điều khiển bot trading hay không."""
        return bool(self.allowed_user_ids) and str(user_id) in self.allowed_user_ids

    async def ensure_allowed_interaction(self, interaction: discord.Interaction) -> bool:
        """Kiểm tra quyền cho Discord interaction và phản hồi riêng nếu bị từ chối."""
        if self._is_allowed(interaction.user.id):
            return True
        print(f"🚫 Discord interaction bị từ chối cho user {interaction.user.id}")
        await interaction.response.send_message("Bạn không có quyền điều khiển bot.", ephemeral=True)
        return False

    async def respond_interaction_error(self, interaction: discord.Interaction, error: Exception):
        """Phản hồi lỗi interaction nếu còn hợp lệ, tránh lỗi dây chuyền khi token hết hạn."""
        print(f"❌ Discord interaction lỗi: {type(error).__name__}: {error}")
        if isinstance(error, discord.NotFound):
            print("⚠️  Interaction đã hết hạn hoặc Discord không còn tìm thấy interaction.")
            return
        message = "Có lỗi khi xử lý lệnh Discord. Kiểm tra log terminal để xem chi tiết."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.NotFound as e:
            print(f"⚠️  Không thể phản hồi interaction đã hết hạn: {e}")

    def has_token(self) -> bool:
        """Cho biết Discord app bot có token để kết nối gateway hay chưa."""
        return bool(self.token)

    def get_mode_options(self) -> List[str]:
        """Lấy danh sách mode hợp lệ để hiển thị trên Discord select menu."""
        if self.on_mode_options:
            return self.on_mode_options()
        return ["reversal", "conservative", "aggressive", "scalping", "swing"]

    def get_symbol_options(self) -> List[str]:
        """Lấy danh sách symbol hợp lệ để hiển thị trên Discord select menu."""
        if self.on_symbol_options:
            symbols = self.on_symbol_options()
        else:
            symbols = DISCORD_SYMBOL_OPTIONS or [tc.SYMBOL]
            symbols = [
                DISCORD_TOP_VOLUME_10_VALUE,
                DISCORD_TOP_MOVERS_10_VALUE,
                *symbols,
            ]
        return symbols[:25] or [tc.SYMBOL]

    def get_symbol_select_options(self) -> List[Dict[str, str]]:
        """Lấy danh sách option label/value để Discord hiển thị symbol kèm phần trăm dao động."""
        if self.on_symbol_select_options:
            options = self.on_symbol_select_options()
        else:
            options = [
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
                *[
                    {"label": symbol, "value": symbol, "description": ""}
                    for symbol in self.get_symbol_options()
                    if symbol not in DISCORD_SPECIAL_SYMBOL_VALUES
                ],
            ]
        return options[:25] or [{"label": tc.SYMBOL, "value": tc.SYMBOL, "description": ""}]

    async def refresh_symbol_options(self):
        """Làm mới cache symbol từ Binance trước khi gửi hoặc refresh control panel."""
        if self.on_symbol_options_refresh:
            await self.on_symbol_options_refresh()

    async def _resolve_handler(self, handler: Optional[AsyncOrSyncStringHandler], value: str) -> str:
        """Gọi callback đổi trạng thái, hỗ trợ cả hàm sync và async."""
        if not handler:
            return "Chưa cấu hình handler xử lý yêu cầu."
        result = handler(value)
        if hasattr(result, '__await__'):
            result = await result
        return str(result) if result else "Đã cập nhật yêu cầu."

    async def _resolve_signal_decision(
        self,
        handler: Optional[SignalDecisionHandler],
        verification_id: str,
        user_id: int | str,
    ) -> str:
        """Gọi callback xử lý phản hồi signal từ Discord button."""
        if not handler:
            return "Chưa cấu hình handler xử lý phản hồi signal."
        result = handler(verification_id, user_id)
        if hasattr(result, '__await__'):
            result = await result
        return str(result) if result else "Đã cập nhật phản hồi signal."

    async def change_symbol(self, symbol: str) -> str:
        """Đổi symbol qua callback đã được inject từ realtime service."""
        if symbol not in self.get_symbol_options():
            return f"Symbol `{symbol}` không nằm trong danh sách được phép."
        return await self._resolve_handler(self.on_symbol_change, symbol)

    async def change_mode(self, mode: str) -> str:
        """Đổi mode qua callback đã được inject từ realtime service."""
        if mode not in self.get_mode_options():
            return f"Mode `{mode}` không hợp lệ."
        return await self._resolve_handler(self.on_mode_change, mode)

    async def change_log(self, state: str) -> str:
        """Bật hoặc tắt analysis summary Discord bằng slash command `/log`."""
        normalized_state = state.lower()
        if normalized_state not in {"on", "off"}:
            return "Giá trị log không hợp lệ. Dùng `/log on` hoặc `/log off`."
        return await self._resolve_handler(self.on_log_change, normalized_state)

    async def confirm_signal(self, verification_id: str, user_id: int | str) -> str:
        """Xác nhận signal từ button Discord và trả message phản hồi cho user."""
        return await self._resolve_signal_decision(self.on_signal_confirm, verification_id, user_id)

    async def skip_signal(self, verification_id: str, user_id: int | str) -> str:
        """Bỏ qua signal từ button Discord và trả message phản hồi cho user."""
        return await self._resolve_signal_decision(self.on_signal_skip, verification_id, user_id)

    def get_status_data(self) -> Dict[str, object]:
        """Lấy dữ liệu trạng thái để render control panel Discord."""
        if self.on_status:
            return self.on_status()
        return {
            "mode": "unknown",
            "symbol": tc.SYMBOL,
            "analysis_log_enabled": False,
            "total_signals": 0,
            "verified_signals": 0,
            "win_rate": 0.0,
        }

    def format_control_panel(self, notice: str = "") -> str:
        """Format control panel bằng helper riêng để DiscordBotService giữ trách nhiệm gọn."""
        return format_control_panel(self.get_status_data(), notice)

    def _register_commands(self):
        """Đăng ký prefix command, slash command và handler lỗi cho Discord app bot."""
        guild = discord.Object(id=self.guild_id) if self.guild_id else None

        @self.bot.event
        async def on_ready():
            if self.synced_commands:
                return
            # `CommandTree.sync` đăng ký slash command; sync theo guild giúp `/trending` hiện nhanh.
            global_synced = await self.bot.tree.sync()
            print(f"✅ Đã sync {len(global_synced)} slash command global")
            if guild:
                self.bot.tree.clear_commands(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                print(f"✅ Đã sync {len(synced)} slash command vào guild {self.guild_id}")
            self.synced_commands = True
            print(f"✅ Discord app bot đã đăng nhập: {self.bot.user}")

        @self.bot.event
        async def on_command_error(ctx, error):
            print(f"❌ Discord prefix command lỗi: {type(error).__name__}: {error}")
            await ctx.reply("Có lỗi khi xử lý command. Kiểm tra log terminal để xem chi tiết.")

        @self.bot.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error):
            if getattr(interaction.command, "name", None) == "trending":
                print("⚠️  /trending bị lệch command tree, xử lý fallback trực tiếp.")
                await self.handle_trending(interaction)
                return
            await self.respond_interaction_error(interaction, error)

        @self.bot.command(name='symbol')
        async def change_symbol(ctx, symbol: str):
            if not self._is_allowed(ctx.author.id):
                await ctx.reply("Bạn không có quyền đổi symbol.")
                return
            message = await self.change_symbol(symbol)
            await ctx.reply(message)

        @self.bot.command(name='mode')
        async def change_mode(ctx, mode: str):
            if not self._is_allowed(ctx.author.id):
                await ctx.reply("Bạn không có quyền đổi mode.")
                return
            message = await self.change_mode(mode.lower())
            await ctx.reply(message)

        @self.bot.command(name='status')
        async def status(ctx):
            if not self._is_allowed(ctx.author.id):
                await ctx.reply("Bạn không có quyền xem trạng thái bot.")
                return
            await ctx.reply(self.format_control_panel())

        @self.bot.command(name='control')
        async def control(ctx):
            if not self._is_allowed(ctx.author.id):
                await ctx.reply("Bạn không có quyền mở control panel.")
                return
            self.control_channel_id = ctx.channel.id
            await self.refresh_symbol_options()
            # `discord.ui.View` tạo select/button native, phù hợp để thao tác trực tiếp trên Discord.
            await ctx.reply(self.format_control_panel(), view=TradingControlView(self))

        @self.bot.tree.command(name='trending', description='Mở trading control panel.')
        async def trending(interaction: discord.Interaction):
            await self.handle_trending(interaction)

        @self.bot.tree.command(name='log', description='Bật hoặc tắt analysis summary lên Discord.')
        async def log_command(interaction: discord.Interaction, state: str):
            await self.handle_log(interaction, state)

    async def handle_trending(self, interaction: discord.Interaction):
        """Xử lý slash command `/trending` và gửi control panel cho user hợp lệ."""
        try:
            print(f"🔎 Nhận slash command /trending từ user {interaction.user.id} trong guild {interaction.guild_id}")
            if not await self.ensure_allowed_interaction(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            if interaction.channel:
                self.control_channel_id = interaction.channel.id
            print("✅ /trending đã defer response, chuẩn bị gửi control panel")
            await self.refresh_symbol_options()
            await interaction.followup.send(
                self.format_control_panel(),
                view=TradingControlView(self),
                ephemeral=True
            )
            print("✅ /trending đã gửi control panel")
        except Exception as e:
            await self.respond_interaction_error(interaction, e)

    async def handle_log(self, interaction: discord.Interaction, state: str):
        """Xử lý slash command `/log on|off` cho user hợp lệ."""
        try:
            print(f"🔎 Nhận slash command /log {state} từ user {interaction.user.id}")
            if not await self.ensure_allowed_interaction(interaction):
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            message = await self.change_log(state)
            await interaction.followup.send(
                self.format_control_panel(message),
                view=TradingControlView(self),
                ephemeral=True,
            )
        except Exception as e:
            await self.respond_interaction_error(interaction, e)

    async def send_signal_action_panel(self, signal: TradingSignal, verification: SignalVerification) -> bool:
        """Gửi action panel cho signal tới kênh control gần nhất để user xác nhận hoặc bỏ qua."""
        if not self.control_channel_id:
            print("⚠️  Chưa có control channel để gửi signal action panel.")
            return False
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.control_channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(self.control_channel_id)
        await channel.send(
            format_signal_action_panel(signal, verification.verification_id),
            view=SignalActionView(self, verification.verification_id),
        )
        print(f"✅ Đã gửi signal action panel cho {signal.symbol} {signal.timeframe}")
        return True

    async def start(self):
        """Khởi động Discord app bot nếu token đã được cấu hình."""
        if not self.token:
            print("⚠️  DISCORD_BOT_TOKEN chưa được cấu hình, bỏ qua Discord app bot.")
            return
        await self.bot.start(self.token)

    async def stop(self):
        """Dừng Discord app bot và đóng kết nối gateway."""
        if not self.token or self.bot.is_closed():
            return
        await self.bot.close()
