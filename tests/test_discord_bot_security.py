from app.services.discord_bot import DiscordBotService
from app.constants.discord_constants import DISCORD_TOP_MOVERS_10_VALUE, DISCORD_TOP_VOLUME_10_VALUE
import asyncio


def test_discord_bot_denies_control_when_allowed_users_empty():
    """Kiểm tra DiscordBotService mặc định từ chối điều khiển khi chưa cấu hình whitelist."""
    service = DiscordBotService()
    service.allowed_user_ids = set()

    assert not service._is_allowed(123456789)


def test_discord_bot_allows_only_configured_user():
    """Kiểm tra DiscordBotService chỉ cho phép user nằm trong whitelist điều khiển bot."""
    service = DiscordBotService()
    service.allowed_user_ids = {"123456789"}

    assert service._is_allowed(123456789)
    assert not service._is_allowed(987654321)


def test_discord_bot_symbol_options_include_top_watchlists():
    """Kiểm tra Discord symbol option có lựa chọn watchlist top volume và top movers."""
    service = DiscordBotService()

    values = [option["value"] for option in service.get_symbol_select_options()]

    assert DISCORD_TOP_VOLUME_10_VALUE in values
    assert DISCORD_TOP_MOVERS_10_VALUE in values


def test_discord_bot_log_command_toggles_runtime_handler():
    """Kiểm tra handler `/log on|off` gọi callback runtime tương ứng."""
    states = []
    service = DiscordBotService(on_log_change=lambda state: states.append(state) or f"log {state}")

    message = asyncio.run(service.change_log("on"))

    assert states == ["on"]
    assert message == "log on"
