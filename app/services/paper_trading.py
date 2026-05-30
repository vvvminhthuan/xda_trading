import asyncio
from typing import Dict, List

from app.adapters.binance import BinanceAdapter
from app.models.order import OrderStatus, PaperOrder
from app.models.signal import TradingSignal


class PaperTradingService:
    """Dịch vụ phụ theo dõi lệnh giả định bằng ticker, không phải luồng kiểm chứng Phase 5 chính."""

    def __init__(self, binance_adapter: BinanceAdapter):
        self.binance_adapter = binance_adapter
        self.orders: List[PaperOrder] = []
        self.tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False

    def create_order(self, signal: TradingSignal) -> PaperOrder:
        """Tạo lệnh paper trading từ TradingSignal và lưu vào danh sách theo dõi."""
        order = PaperOrder.from_signal(signal)
        self.orders.append(order)
        return order

    async def start_symbol_watch(self, symbol: str):
        """Bắt đầu theo dõi ticker cho một symbol để cập nhật trạng thái lệnh."""
        if symbol in self.tasks and not self.tasks[symbol].done():
            return
        self.is_running = True
        self.tasks[symbol] = asyncio.create_task(
            self._watch_symbol(symbol),
            name=f"{symbol}_paper_ticker"
        )

    async def _watch_symbol(self, symbol: str):
        """Theo dõi giá realtime và cập nhật tất cả lệnh paper trading của symbol."""
        async for ticker in self.binance_adapter.watch_ticker(symbol):
            if not self.is_running:
                break
            price = ticker.get('last') or ticker.get('bid') or ticker.get('ask')
            if price is None:
                continue
            self.update_orders(symbol, float(price))

    def update_orders(self, symbol: str, price: float):
        """Cập nhật trạng thái các lệnh chưa đóng bằng giá mới nhất."""
        for order in self.orders:
            if order.symbol == symbol and order.status in {OrderStatus.PENDING, OrderStatus.OPEN}:
                order.update_by_price(price)

    def stats(self) -> Dict[str, float]:
        """Tổng hợp thống kê win/loss và PnL giả định hiện tại."""
        closed_orders = [
            order for order in self.orders
            if order.status in {OrderStatus.TAKE_PROFIT, OrderStatus.STOP_LOSS}
        ]
        wins = len([order for order in closed_orders if order.status == OrderStatus.TAKE_PROFIT])
        losses = len([order for order in closed_orders if order.status == OrderStatus.STOP_LOSS])
        total = len(closed_orders)
        return {
            'total_orders': len(self.orders),
            'closed_orders': total,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total * 100) if total else 0.0,
            'pnl': sum(order.pnl for order in closed_orders),
        }

    async def stop(self):
        """Dừng toàn bộ task theo dõi ticker paper trading."""
        self.is_running = False
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()
