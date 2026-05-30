import asyncio

from app.services.discord_message_queue import DiscordMessageQueueService


class FakeDiscordAdapter:
    """Adapter giả lập để ghi nhận các tin Discord đã được queue gửi."""

    def __init__(self):
        self.messages = []

    async def send_message(self, message):
        """Lưu tin nhắn thay vì gửi HTTP webhook thật."""
        self.messages.append(message)
        return True


class ManualClock:
    """Clock giả lập để test rate limit mà không cần chờ thời gian thật."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self) -> float:
        """Trả thời điểm hiện tại của clock giả lập."""
        return self.now

    async def sleep(self, seconds: float):
        """Ghi nhận thời gian sleep và đẩy clock giả lập tiến lên."""
        self.sleeps.append(seconds)
        self.now += seconds


def test_discord_message_queue_sends_at_most_five_messages_per_batch():
    """Kiểm tra mỗi lượt xử lý chỉ lấy tối đa 5 tin từ queue."""
    async def run_test():
        adapter = FakeDiscordAdapter()
        service = DiscordMessageQueueService(adapter)

        for index in range(7):
            await service.enqueue(f"message-{index}")

        sent_count = await service._send_batch()

        assert sent_count == 5
        assert adapter.messages == [f"message-{index}" for index in range(5)]
        assert service.queue.qsize() == 2

    asyncio.run(run_test())


def test_discord_message_queue_waits_after_five_requests_in_window():
    """Kiểm tra cùng một channel không vượt quá 5 request trong window 5 giây."""
    async def run_test():
        adapter = FakeDiscordAdapter()
        clock = ManualClock()
        service = DiscordMessageQueueService(
            adapter,
            batch_size=10,
            retry_buffer_seconds=0.0,
            sleep=clock.sleep,
            clock=clock,
        )

        for index in range(6):
            await service.enqueue(f"message-{index}")

        await service.flush()

        assert adapter.messages == [f"message-{index}" for index in range(6)]
        assert clock.sleeps == [5.0]
        assert clock.now == 5.0

    asyncio.run(run_test())


def test_discord_message_queue_uses_independent_bucket_per_channel():
    """Kiểm tra hai channel khác nhau không chặn rate limit của nhau."""
    async def run_test():
        adapter = FakeDiscordAdapter()
        clock = ManualClock()
        service = DiscordMessageQueueService(
            adapter,
            batch_size=6,
            retry_buffer_seconds=0.0,
            sleep=clock.sleep,
            clock=clock,
        )

        for index in range(5):
            await service.enqueue(f"default-{index}", channel_key="default")
        await service.enqueue("other-0", channel_key="other")

        await service.flush()

        assert adapter.messages == [
            "default-0",
            "default-1",
            "default-2",
            "default-3",
            "default-4",
            "other-0",
        ]
        assert clock.sleeps == []

    asyncio.run(run_test())


def test_discord_message_queue_stop_flushes_pending_messages_without_worker():
    """Kiểm tra stop vẫn flush tin còn lại khi worker nền chưa được start."""
    async def run_test():
        adapter = FakeDiscordAdapter()
        service = DiscordMessageQueueService(adapter)

        await service.enqueue("message-1")
        await service.enqueue("message-2")
        await service.stop()

        assert adapter.messages == ["message-1", "message-2"]
        assert service.queue.empty()

    asyncio.run(run_test())
