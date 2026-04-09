import aiohttp
import asyncio
from typing import Optional
from datetime import datetime
from app.models.signal import TradingSignal
from app.constants.discord_constants import *
from app.models.embed import Embed

class DiscordService:
    """
    Dịch vụ gửi thông báo lên Discord qua Webhook.
    Hỗ trợ Embeds, error handling và rate limiting.
    """
    
    def __init__(self):
        self.webhook_url = DISCORD_WEBHOOK_URL
        self.last_message_time = 0
        self.message_count = 0
        self.session = None
        
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Tạo hoặc trả về aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
        
    async def close(self):
        """Đóng session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def test_connection(self) -> bool:
        """Test connection tới Discord webhook"""
        if not self._is_webhook_configured():
            print("⚠️  Discord Webhook chưa được cấu hình!")
            print("   Cập nhật DISCORD_WEBHOOK_URL trong trading_constants.py")
            return False
            
        try:
            embed = Embed()
            embed.title = "🤖 Trading Bot Connected"
            embed.description = "Bot đã kết nối thành công với Discord!"
            embed.color = 0x00FF00
            embed.timestamp = datetime.utcnow().isoformat()
            embed.footer = "Trading Bot System By XDA" 
            
            success = await self._send_embed(embed())
            if success:
                print("✅ Discord connection test thành công!")
            else:
                print("❌ Discord connection test thất bại!")
                
            return success
            
        except Exception as e:
            print(f"❌ Lỗi test Discord: {e}")
            return False
            
    async def send_signal(self, signal: TradingSignal) -> bool:
        """
        Gửi trading signal lên Discord dạng rich embed.
        """
        if not self._is_webhook_configured():
            print("⚠️  Không thể gửi Discord - chưa cấu hình webhook!")
            return False
            
        try:
            # Rate limiting (không spam quá 5 message/phút)
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_message_time < DISCORD_BLOCK_TIME:  # 12 giây/message
                print("⏳ Rate limit - bỏ qua gửi Discord")
                return False
                
            embed = self._create_signal_embed(signal)
            success = await self._send_embed(embed)
            
            if success:
                self.last_message_time = current_time
                self.message_count += 1
                
            return success
            
        except Exception as e:
            print(f"❌ Lỗi gửi signal Discord: {e}")
            return False
            
    async def send_error_notification(self, error_msg: str) -> bool:
        """Gửi thông báo lỗi hệ thống"""
        if not self._is_webhook_configured():
            return False
            
        try:
            embed = Embed()
            embed.title = "⚠️ System Error Alert"
            embed.description = f"```\n{error_msg}\n```"
            embed.color = 0xFF0000
            embed.timestamp = datetime.utcnow().isoformat()
            embed.footer = "Trading Bot Error System" 
            
            return await self._send_embed(embed())
            
        except Exception as e:
            print(f"❌ Lỗi gửi error Discord: {e}")
            return False
            
    async def send_stats_update(self, stats: dict) -> bool:
        """Gửi thống kê định kỳ"""
        if not self._is_webhook_configured():
            return False
            
        try:
            embed = Embed()
            embed.title = "📊 Trading Bot Statistics"
            embed.color = 0x3498DB
            embed.fields = [
                    {
                        "name": "Total Signals",
                        "value": f"{stats.get('total_signals', 0)}",
                        "inline": True
                    },
                    {
                        "name": "Uptime",
                        "value": f"{stats.get('uptime', '0h 0m')}",
                        "inline": True
                    },
                    {
                        "name": "Signals by Timeframe",
                        "value": f"```\n{self._format_timeframe_stats(stats.get('signals_per_timeframe', {}))}\n```",
                        "inline": False
                    }
                ]
            embed.timestamp = datetime.utcnow().isoformat()
            embed.footer = "Hourly Statistics Report"
            
            return await self._send_embed(embed())
            
        except Exception as e:
            print(f"❌ Lỗi gửi stats Discord: {e}")
            return False
    
    def _create_signal_embed(self, signal: TradingSignal) -> dict:
        """Tạo rich embed cho trading signal"""
        
        # Màu sắc theo action
        color = 0x00FF00 if signal.action == 'LONG' else 0xFF0000
        
        # Icon và emoji
        action_emoji = "📈" if signal.action == 'LONG' else "📉"
        profit_emoji = "💰" if signal.action == 'LONG' else "💸"
        
        # Tính Risk:Reward ratio
        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        rr_ratio = f"1:{reward/risk:.1f}" if risk > 0 else "N/A"
        
        # Tính $ risk amount
        risk_usd = abs(signal.entry_price - signal.stop_loss) * signal.quantity
        
        # Tạo embed
        embed = Embed()
        embed.title = f"{action_emoji} **{signal.action} SIGNAL** - {signal.symbol}"
        embed.description = f"**🎯 Win Probability: {signal.win_probability}%** (Score: {signal.score}/100)\n📊 Timeframe: **{signal.timeframe.upper()}** | RR: **{rr_ratio}**"
        embed.color = color
        embed.fields = [
                {
                    "name": "💰 Entry Price",
                    "value": f"**${signal.entry_price:,}**",
                    "inline": True
                },
                {
                    "name": "⚖️ Quantity",
                    "value": f"**{signal.quantity:,} coin**",
                    "inline": True
                },
                {
                    
                },
                {
                    "name": f"{profit_emoji} Take Profit",
                    "value": f"**${signal.take_profit:,}**",
                    "inline": True
                },
                {
                    "name": "🛑 Stop Loss", 
                    "value": f"**${signal.stop_loss:,}**",
                    "inline": True
                },
                {
                    "name": "📈 Potential Profit",
                    "value": f"**${reward * signal.quantity:.2f}**",
                    "inline": True
                },
                {
                    "name": "💡 Signal Reason",
                    "value": f"```{signal.reason}```",
                    "inline": False
                }
            ]
        embed.timestamp = datetime.utcnow().isoformat()
        embed.footer = "⚠️ Khuyến cáo: Tự quản lý rủi ro và không đầu tư quá khả năng tài chính!"
        embed.thumbnail = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
      
        return embed()
        
    async def _send_embed(self, embed: dict) -> bool:
        """Gửi embed lên Discord webhook"""
        payload = {"embeds": [embed]}
        
        try:
            session = await self.get_session()
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status in (200, 204):
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Discord API Error {response.status}: {error_text}")
                    return False
                    
        except asyncio.TimeoutError:
            print("❌ Discord request timeout")
            await self.session.close()
            return False
        except Exception as e:
            print(f"❌ Lỗi kết nối discord: {e}")
            await self.session.close()
            return False
        finally:
            await self.session.close()
            
    def _is_webhook_configured(self) -> bool:
        """Kiểm tra webhook đã được cấu hình chưa"""
        return (self.webhook_url and 
                self.webhook_url.startswith("https://discord.com/api/webhooks/"))
                
    def _format_timeframe_stats(self, stats: dict) -> str:
        """Format thống kê timeframe cho Discord"""
        if not stats:
            return "Không có data"
            
        lines = []
        for tf, count in stats.items():
            lines.append(f"{tf}: {count} signals")
            
        return "\n".join(lines)