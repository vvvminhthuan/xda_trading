from app.constants.discord_constants import *
from app.models.embed import Embed
import aiohttp
import asyncio
import json
from typing import Any

class DiscordAdapter:
    """Dịch vụ kết nối và gửi thông báo đến Discord thông qua Webhook.
    Cung cấp phương thức để gửi tin nhắn đơn giản đến kênh Discord.
    Kiểm tra kết nối và xử lý lỗi khi sau khi tạo một đối tượng DiscordAdapter."""
    
    def __init__(self, max_retries: int = 3, retry_buffer_seconds: float = 0.1):
        self.webhook_url = DISCORD_WEBHOOK_URL
        self.session = None
        self.max_retries = max_retries
        self.retry_buffer_seconds = retry_buffer_seconds
    
    def _is_configured(self) -> bool:
        """Kiểm tra xem Webhook URL đã được cấu hình hay chưa."""
        if not self.webhook_url or not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
            print("⚠️  Discord Webhook chưa được cấu hình!")
            print("   Cập nhật DISCORD_WEBHOOK_URL trong trading_constants.py")
            return False
        return True
    def _create_session(self) -> aiohttp.ClientSession:
        """Tạo aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def is_connected(self) -> bool:
        """Kiểm tra kết nối Discord bằng cách đọc metadata webhook, không gửi tin nhắn."""
        if not self._is_configured():
            return False
        try:
            # Dùng GET webhook metadata để kiểm tra URL hợp lệ mà không tạo message ngoài queue.
            self._create_session()
            async with self.session.get(self.webhook_url) as response:
                if response.status == 200:
                    print("✅ Kết nối Discord thành công!")
                    return True
                else:
                    response_text = await response.text()
                    print(f"❌ Lỗi kết nối Discord: {response.status} - {response_text}")
                    return False
        except aiohttp.ClientError as e:
            print(f"❌ Lỗi khi kết nối tới Discord: {e}")
            return False
        except asyncio.TimeoutError:
            print("❌ Lỗi kết nối Discord: Request timed out")
            return False
        except Exception as e:
            print(f"❌ Lỗi khi kết nối tới Discord: {e}")
            return False
    
    async def send_message(self, embed: Embed | str) -> bool:
        """Gửi một tin nhắn lên Discord và retry khi webhook bị rate limit.

        Tham số:
        - embed: Nội dung text hoặc Embed cần gửi qua webhook.

        Trả về:
        - True nếu Discord nhận tin thành công, False nếu gửi thất bại sau số lần retry cho phép.
        """
        if not self._is_configured():
            return False

        payload = self._build_payload(embed)
        try:
            self._create_session()
            for attempt in range(self.max_retries + 1):
                async with self.session.post(self.webhook_url, json=payload) as response:
                    if response.status in (200, 204):
                        print("✅ Tin nhắn đã được gửi thành công!")
                        return True
                    response_text = await response.text()
                    if response.status == 429 and attempt < self.max_retries:
                        retry_after = self._retry_after_from_response_text(response_text)
                        wait_seconds = retry_after + self.retry_buffer_seconds
                        print(f"⏳ Discord rate limit, thử lại sau {wait_seconds:.3f}s...")
                        await asyncio.sleep(wait_seconds)
                        continue
                    print(f"❌ Lỗi khi gửi tin nhắn: {response.status} - {response_text}")
                    return False
            return False
        except aiohttp.ClientError as e:
            print(f"❌ Lỗi khi kết nối tới Discord: {e}")
            return False
        except asyncio.TimeoutError:
            print("❌ Lỗi kết nối Discord: Request timed out")
            return False
        except Exception as e:
            print(f"❌ Lỗi khi gửi tin nhắn: {e}")
            return False

    def _build_payload(self, embed: Embed | str) -> dict:
        """Tạo payload webhook Discord từ text hoặc Embed.

        Tham số:
        - embed: Chuỗi text hoặc object Embed nội bộ.

        Trả về:
        - Dict JSON phù hợp với Discord webhook API.
        """
        if isinstance(embed, str):
            return {"content": embed}
        return {"embeds": [embed()]}

    def _retry_after_from_response_text(self, response_text: str) -> float:
        """Lấy số giây cần chờ từ response `429` của Discord.

        Tham số:
        - response_text: Body JSON hoặc text Discord trả về.

        Trả về:
        - Số giây cần chờ trước khi retry; mặc định 1 giây nếu không parse được.
        """
        try:
            data: dict[str, Any] = json.loads(response_text)
            return float(data.get("retry_after", 1.0))
        except (TypeError, ValueError):
            return 1.0

    async def close(self):
        """Đóng aiohttp session khi không còn cần thiết."""
        if self.session and not self.session.closed:
            await self.session.close()
            print("✅ Session Discord đã được đóng.")
