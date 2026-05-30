import asyncio

from app.adapters.discord import DiscordAdapter


class FakeResponse:
    """Response giả lập từ Discord webhook."""

    def __init__(self, status: int, text: str = ""):
        self.status = status
        self._text = text

    async def text(self) -> str:
        """Trả body response giả lập."""
        return self._text


class FakePostContext:
    """Async context manager giả lập kết quả session.post()."""

    def __init__(self, response: FakeResponse):
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        """Trả response khi vào async context."""
        return self.response

    async def __aexit__(self, exc_type, exc, traceback):
        """Không xử lý lỗi đặc biệt khi thoát async context."""
        return False


class FakeSession:
    """Session giả lập để kiểm tra DiscordAdapter không gọi network thật."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.closed = False
        self.payloads = []

    def post(self, webhook_url: str, json: dict):
        """Ghi nhận payload và trả response tiếp theo trong danh sách giả lập."""
        self.payloads.append((webhook_url, json))
        return FakePostContext(self.responses.pop(0))


def test_discord_adapter_retries_when_rate_limited():
    """Kiểm tra adapter chờ `retry_after` và retry khi Discord trả 429."""
    async def run_test():
        adapter = DiscordAdapter(max_retries=1, retry_buffer_seconds=0.0)
        adapter.webhook_url = "https://discord.com/api/webhooks/test/token"
        adapter.session = FakeSession([
            FakeResponse(429, '{"message":"rate limited","retry_after":0,"global":false}'),
            FakeResponse(204),
        ])

        result = await adapter.send_message("hello")

        assert result is True
        assert len(adapter.session.payloads) == 2

    asyncio.run(run_test())


def test_discord_adapter_stops_retrying_after_limit():
    """Kiểm tra adapter không retry vô hạn khi Discord liên tục trả lỗi 429."""
    async def run_test():
        adapter = DiscordAdapter(max_retries=1, retry_buffer_seconds=0.0)
        adapter.webhook_url = "https://discord.com/api/webhooks/test/token"
        adapter.session = FakeSession([
            FakeResponse(429, '{"message":"rate limited","retry_after":0,"global":false}'),
            FakeResponse(429, '{"message":"rate limited","retry_after":0,"global":false}'),
        ])

        result = await adapter.send_message("hello")

        assert result is False
        assert len(adapter.session.payloads) == 2

    asyncio.run(run_test())
