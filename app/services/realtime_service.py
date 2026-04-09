from app.services import BinanceAdapter
from app.models.candle_frame import CandleFrames

class RealtimeService:
    """Dịch vụ theo dõi dữ liệu thời gian thực từ sàn giao dịch. Hiện tại chỉ hỗ trợ Binance thông qua BinanceAdapter."""
    
    def __init__(self, binance_adapter: BinanceAdapter):
        self.binance_adapter = binance_adapter
        self.candle_frames = CandleFrames()  # Lưu trữ dữ liệu nến theo thời gian thực

    async def initialize(self):
        """Khởi tạo kết nối và kiểm tra kết nối với Binance."""
        if not self.binance_adapter.is_connected():
            raise ConnectionError("Không thể kết nối tới Binance. Vui lòng kiểm tra API key và kết nối mạng.")
        print("✅ RealtimeService đã được khởi tạo thành công!")
        # Gởi test signal lên Discord để xác nhận kết nối thành công nếu cần thiết
        