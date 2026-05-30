import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Awaitable, Callable, Deque

from app.adapters.discord import DiscordAdapter
from app.models.embed import Embed


@dataclass
class DiscordQueuedMessage:
    """Đại diện cho một tin nhắn đang chờ gửi lên Discord.

    Tham số:
    - message: Nội dung text hoặc Embed cần gửi qua DiscordAdapter.
    - channel_key: Khóa định danh channel/webhook để áp dụng rate limit riêng.
    """

    message: Embed | str
    channel_key: str = "default"


class DiscordMessageQueueService:
    """Service hàng đợi chịu trách nhiệm gửi toàn bộ webhook Discord theo rate limit."""

    def __init__(
        self,
        discord_adapter: DiscordAdapter,
        max_requests: int = 5,
        window_seconds: float = 5.0,
        batch_size: int = 5,
        retry_buffer_seconds: float = 0.1,
        queue_warning_size: int = 100,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Khởi tạo queue gửi Discord với sliding window rate limit.

        Tham số:
        - discord_adapter: Adapter thực hiện HTTP request tới Discord webhook.
        - max_requests: Số request tối đa trong một window cho mỗi channel.
        - window_seconds: Độ dài window rate limit tính bằng giây.
        - batch_size: Số tin tối đa xử lý trong một lượt worker.
        - retry_buffer_seconds: Khoảng đệm khi chờ slot rate limit để tránh chạm ngưỡng sát.
        - queue_warning_size: Ngưỡng log cảnh báo khi queue bị dồn quá dài.
        - sleep: Hàm sleep async, cho phép inject trong test.
        - clock: Hàm lấy thời gian đơn điệu, cho phép inject trong test.
        """
        self.discord_adapter = discord_adapter
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.batch_size = batch_size
        self.retry_buffer_seconds = retry_buffer_seconds
        self.queue_warning_size = queue_warning_size
        self.sleep = sleep
        self.clock = clock
        self.queue: asyncio.Queue[DiscordQueuedMessage] = asyncio.Queue()
        self.sent_timestamps: dict[str, Deque[float]] = defaultdict(deque)
        self.worker_task: asyncio.Task | None = None
        self.is_running = False

    def start(self):
        """Khởi động worker nền để xử lý queue gửi Discord."""
        if self.worker_task and not self.worker_task.done():
            return
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, message: Embed | str, channel_key: str = "default"):
        """Đưa một tin nhắn vào hàng đợi gửi Discord.

        Tham số:
        - message: Nội dung text hoặc Embed cần gửi.
        - channel_key: Khóa channel/webhook dùng để tách rate limit.
        """
        await self.queue.put(DiscordQueuedMessage(message=message, channel_key=channel_key))
        if self.queue.qsize() > self.queue_warning_size:
            print(f"⚠️  Discord message queue đang có {self.queue.qsize()} tin chờ gửi.")

    async def stop(self):
        """Dừng worker và flush các tin còn lại trong queue trước khi shutdown."""
        self.is_running = False
        if self.worker_task and not self.worker_task.done():
            await self.queue.join()
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        else:
            await self.flush()
        self.worker_task = None

    async def flush(self):
        """Gửi hết các tin còn lại trong queue mà không cần worker nền."""
        while not self.queue.empty():
            await self._send_batch()

    async def _worker(self):
        """Vòng lặp nền lấy tin từ queue và gửi theo batch có kiểm soát tốc độ."""
        while self.is_running:
            await self._send_batch(wait_for_item=True)
        while not self.queue.empty():
            await self._send_batch()

    async def _send_batch(self, wait_for_item: bool = False) -> int:
        """Gửi tối đa `batch_size` tin trong một lượt xử lý.

        Tham số:
        - wait_for_item: Nếu True, worker sẽ chờ đến khi queue có ít nhất một tin.

        Trả về:
        - Số tin đã được lấy ra và gửi qua adapter.
        """
        messages = []
        if wait_for_item:
            messages.append(await self.queue.get())

        while len(messages) < self.batch_size and not self.queue.empty():
            messages.append(self.queue.get_nowait())

        for queued_message in messages:
            try:
                await self._wait_for_rate_limit(queued_message.channel_key)
                self._record_request(queued_message.channel_key)
                await self.discord_adapter.send_message(queued_message.message)
            finally:
                self.queue.task_done()
        return len(messages)

    async def _wait_for_rate_limit(self, channel_key: str):
        """Chờ đến khi channel còn slot gửi theo giới hạn 5 request / 5 giây.

        Tham số:
        - channel_key: Khóa channel/webhook cần kiểm tra rate bucket.
        """
        timestamps = self.sent_timestamps[channel_key]
        while True:
            now = self.clock()
            self._drop_expired_timestamps(timestamps, now)
            if len(timestamps) < self.max_requests:
                return
            wait_seconds = self.window_seconds - (now - timestamps[0]) + self.retry_buffer_seconds
            await self.sleep(max(wait_seconds, self.retry_buffer_seconds))

    def _record_request(self, channel_key: str):
        """Ghi nhận thời điểm một request Discord sắp được gửi cho channel."""
        self.sent_timestamps[channel_key].append(self.clock())

    def _drop_expired_timestamps(self, timestamps: Deque[float], now: float):
        """Xóa các timestamp đã nằm ngoài window rate limit.

        Tham số:
        - timestamps: Danh sách thời điểm request của một channel.
        - now: Thời điểm hiện tại từ clock đơn điệu.
        """
        while timestamps and now - timestamps[0] >= self.window_seconds:
            timestamps.popleft()
