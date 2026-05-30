from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from app.services.discord_bot import DiscordBotService


class TradingControlView(discord.ui.View):
    """Hiển thị control panel Discord để chọn mode, symbol và refresh trạng thái bot."""

    def __init__(self, service: "DiscordBotService"):
        super().__init__(timeout=None)
        self.service = service
        self.add_item(TradingModeSelect(service))
        self.add_item(TradingSymbolSelect(service))
        self.add_item(TradingStatusButton(service))


class TradingModeSelect(discord.ui.Select):
    """Select menu dùng `discord.ui.Select` để người dùng đổi mode ngay trên Discord."""

    def __init__(self, service: "DiscordBotService"):
        self.service = service
        options = [
            discord.SelectOption(label=mode, value=mode)
            for mode in service.get_mode_options()
        ]
        super().__init__(
            placeholder="Chọn trading mode",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        """Xử lý lựa chọn mode, defer sớm và gửi panel mới bằng followup."""
        try:
            print(f"🔎 Discord mode select từ user {interaction.user.id}: {self.values[0]}")
            if not await self.service.ensure_allowed_interaction(interaction):
                return
            # `defer` xác nhận interaction sớm, phù hợp khi callback có thể xử lý lâu.
            await interaction.response.defer(ephemeral=True, thinking=True)
            message = await self.service.change_mode(self.values[0])
            await interaction.followup.send(
                self.service.format_control_panel(message),
                view=TradingControlView(self.service),
                ephemeral=True,
            )
        except Exception as e:
            await self.service.respond_interaction_error(interaction, e)


class TradingSymbolSelect(discord.ui.Select):
    """Select menu dùng `discord.ui.Select` để người dùng đổi symbol đang theo dõi."""

    def __init__(self, service: "DiscordBotService"):
        self.service = service
        options = [
            discord.SelectOption(
                label=option["label"],
                value=option["value"],
                description=option.get("description") or None,
            )
            for option in service.get_symbol_select_options()
        ]
        super().__init__(
            placeholder="Chọn symbol",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        """Xử lý lựa chọn symbol, defer trước khi restart watcher và fetch history."""
        try:
            print(f"🔎 Discord symbol select từ user {interaction.user.id}: {self.values[0]}")
            if not await self.service.ensure_allowed_interaction(interaction):
                return
            # Đổi symbol có thể dừng watcher và tải lại OHLCV nên phải defer trước.
            await interaction.response.defer(ephemeral=True, thinking=True)
            message = await self.service.change_symbol(self.values[0])
            await self.service.refresh_symbol_options()
            await interaction.followup.send(
                self.service.format_control_panel(message),
                view=TradingControlView(self.service),
                ephemeral=True,
            )
        except Exception as e:
            await self.service.respond_interaction_error(interaction, e)


class TradingStatusButton(discord.ui.Button):
    """Button refresh trạng thái control panel mà không cần gửi lại command text."""

    def __init__(self, service: "DiscordBotService"):
        self.service = service
        super().__init__(label="Status", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        """Cập nhật lại trạng thái bằng followup để tránh lỗi interaction hết hạn."""
        try:
            print(f"🔎 Discord status button từ user {interaction.user.id}")
            if not await self.service.ensure_allowed_interaction(interaction):
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            await self.service.refresh_symbol_options()
            await interaction.followup.send(
                self.service.format_control_panel("Đã refresh trạng thái."),
                view=TradingControlView(self.service),
                ephemeral=True,
            )
        except Exception as e:
            await self.service.respond_interaction_error(interaction, e)


class SignalActionView(discord.ui.View):
    """Hiển thị action buttons để user xác nhận hoặc bỏ qua một signal cụ thể."""

    def __init__(self, service: "DiscordBotService", verification_id: str):
        super().__init__(timeout=None)
        self.add_item(ConfirmEntryButton(service, verification_id))
        self.add_item(SkipSignalButton(service, verification_id))


class ConfirmEntryButton(discord.ui.Button):
    """Button xác nhận user muốn theo dõi hoặc vào lệnh giả định theo signal."""

    def __init__(self, service: "DiscordBotService", verification_id: str):
        self.service = service
        self.verification_id = verification_id
        super().__init__(
            label="Confirm Entry",
            style=discord.ButtonStyle.success,
            custom_id=f"signal_confirm:{verification_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        """Xử lý xác nhận signal và phản hồi lại user trên Discord."""
        try:
            if not await self.service.ensure_allowed_interaction(interaction):
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            message = await self.service.confirm_signal(self.verification_id, interaction.user.id)
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            await self.service.respond_interaction_error(interaction, e)


class SkipSignalButton(discord.ui.Button):
    """Button bỏ qua signal và hủy kiểm chứng nếu signal còn active."""

    def __init__(self, service: "DiscordBotService", verification_id: str):
        self.service = service
        self.verification_id = verification_id
        super().__init__(
            label="Skip",
            style=discord.ButtonStyle.secondary,
            custom_id=f"signal_skip:{verification_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        """Xử lý bỏ qua signal và phản hồi lại user trên Discord."""
        try:
            if not await self.service.ensure_allowed_interaction(interaction):
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            message = await self.service.skip_signal(self.verification_id, interaction.user.id)
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            await self.service.respond_interaction_error(interaction, e)
