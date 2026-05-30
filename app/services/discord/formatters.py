from typing import Dict

from app.constants import trading as tc
from app.models.embed import Embed
from app.models.signal import TradingSignal


TREND_CONTEXT_LABELS = {
    "WITH_SAFE_TREND": "Thuận xu hướng lớn",
    "COUNTER_SAFE_TREND": "Ngược xu hướng lớn",
    "NEUTRAL_SAFE_TREND": "Xu hướng lớn chưa rõ",
    "NO_ACTION": "Chưa có hướng đảo chiều",
}

DECISION_LABELS = {
    "No signal": "Chưa gửi tín hiệu",
    "No signal: safe trend neutral": "Chưa gửi tín hiệu: xu hướng lớn chưa rõ",
    "No signal: volume not confirmed": "Chưa gửi tín hiệu: volume chưa xác nhận",
    "No signal: risk filters failed": "Chưa gửi tín hiệu: bộ lọc rủi ro chưa đạt",
    "No signal: mode threshold failed": "Chưa gửi tín hiệu: chưa đạt ngưỡng điểm của mode",
    "No signal: reversal confirmation missing": "Chưa gửi tín hiệu: chưa đủ xác nhận đảo chiều",
    "No signal: reversal volume not confirmed": "Chưa gửi tín hiệu: volume chưa xác nhận đảo chiều",
    "No signal: reversal mode threshold failed": "Chưa gửi tín hiệu: chưa đạt ngưỡng điểm reversal",
    "No signal: rate limit": "Chưa gửi tín hiệu: đã vượt giới hạn số tín hiệu",
}

FILTER_LABELS = [
    ("safe_trend", "Xu hướng lớn"),
    ("volume_confirmed", "Volume"),
    ("trend_filter", "Bộ lọc trend"),
    ("volatility_filter", "Bộ lọc biến động"),
    ("mode_threshold", "Ngưỡng mode"),
    ("rate_limit", "Giới hạn tín hiệu"),
    ("reversal_action", "Hướng đảo chiều"),
]


def format_control_panel(status: Dict[str, object], notice: str = "") -> str:
    """Tạo nội dung control panel Discord từ dữ liệu trạng thái bot.

    Tham số:
    - status: Dict chứa mode, symbol, tổng signal, signal đã kiểm chứng và win rate.
    - notice: Thông báo bổ sung sau khi người dùng thao tác.

    Trả về:
    - Chuỗi markdown ngắn gọn để gửi lên Discord.
    """
    watch_symbols = status.get("watch_symbols") or [status.get('symbol', tc.SYMBOL)]
    if not isinstance(watch_symbols, list):
        watch_symbols = [str(watch_symbols)]
    watch_preview = ", ".join(str(symbol) for symbol in watch_symbols[:5])
    if len(watch_symbols) > 5:
        watch_preview = f"{watch_preview}, ..."
    lines = [
        "**Trading Control Panel**",
        f"Mode: `{status.get('mode', 'unknown')}`",
        f"Symbol: `{status.get('symbol', tc.SYMBOL)}`",
        f"Watch mode: `{status.get('watch_mode', 'single_symbol')}`",
        f"Analysis log: `{'on' if status.get('analysis_log_enabled', False) else 'off'}`",
        f"Watching symbols: `{status.get('watch_symbol_count', len(watch_symbols))}`",
        f"Watchlist: `{watch_preview}`",
        f"Total signals: `{status.get('total_signals', 0)}`",
        f"Verified signals: `{status.get('verified_signals', 0)}`",
        f"Accuracy: `{float(status.get('win_rate', 0.0)):.1f}%`",
        f"TP/SL/Expired/Open: `{status.get('take_profit', 0)}/{status.get('stop_loss', 0)}/{status.get('expired', 0)}/{status.get('open_signals', 0)}`",
        f"Confirmed: `{status.get('confirmed_signals', 0)}`",
        f"Skipped: `{status.get('skipped_signals', 0)}`",
        f"Pending response: `{status.get('pending_responses', 0)}`",
    ]
    if notice:
        lines.append(f"Status: {notice}")
    return "\n".join(lines)


def format_signal_action_panel(signal: TradingSignal, verification_id: str) -> str:
    """Tạo nội dung panel xác nhận signal để user chọn Confirm Entry hoặc Skip.

    Tham số:
    - signal: TradingSignal vừa được strategy tạo và đã validate.
    - verification_id: Mã snapshot dùng để cập nhật phản hồi của user.

    Trả về:
    - Chuỗi markdown ngắn gọn gửi qua Discord app bot.
    """
    entry_basis = signal.indicators.get("entry_basis") if isinstance(signal.indicators, dict) else None
    entry_reference = signal.indicators.get("entry_reference_level") if isinstance(signal.indicators, dict) else None
    trend_context = signal.indicators.get("trend_context") if isinstance(signal.indicators, dict) else None
    lines = [
        "**Trading Signal Action**",
        f"ID: `{verification_id[:8]}`",
        f"Symbol: `{signal.symbol}`",
        f"Timeframe: `{signal.timeframe}`",
        f"Signal: `{signal.signal_type.value}`",
        f"Entry: `{signal.entry_price}`",
    ]
    if entry_basis:
        lines.append(f"Entry basis: `{entry_basis}`")
    if entry_reference:
        lines.append(f"Reference level: `{entry_reference}`")
    if trend_context:
        lines.append(f"Bối cảnh xu hướng: `{format_trend_context(trend_context)}`")
    lines.extend([
        f"Stop Loss: `{signal.stop_loss}`",
        f"Take Profit: `{signal.take_profit}`",
        f"Risk/Reward: `{signal.risk_reward_ratio:.2f}`",
        f"Confidence: `{signal.confidence_score:.1f}%`",
        f"Reason: {signal.reason or signal.notes or 'Không có ghi chú'}",
    ])
    return "\n".join(lines)


def format_analysis_summary_embed(analysis: Dict[str, object]) -> Embed:
    """Tạo embed Discord tóm tắt phân tích một nến, tách rõ raw score và weighted score."""
    embed = Embed()
    symbol = str(analysis.get("symbol", tc.SYMBOL))
    timeframe = str(analysis.get("timeframe", "unknown"))
    embed.title = f"{symbol} | {timeframe} Analysis Summary"
    embed.color = 0x3498DB
    raw_score = analysis.get("raw_score") or {}
    weighted_score = analysis.get("weighted_score") or {}
    filters = analysis.get("filters") or {}
    reasons = analysis.get("reasons") or []
    decision = str(analysis.get("decision", "No signal"))
    recommendation = format_recommendation(analysis)
    embed.fields = [
        {"name": "Mode", "value": str(analysis.get("mode", "unknown")), "inline": True},
        {"name": "Xu hướng lớn", "value": format_safe_trend(analysis.get("safe_trend", "NEUTRAL")), "inline": True},
        {"name": "Quyết định", "value": format_decision(decision), "inline": True},
        {"name": "Điểm tín hiệu", "value": f"{int(analysis.get('score', 0))}/100", "inline": True},
        {"name": "Confidence", "value": f"{float(analysis.get('confidence', 0.0)):.1f}%", "inline": True},
        {"name": "Alignment", "value": str(analysis.get("alignment_bonus", 0)), "inline": True},
        {"name": "Khuyến nghị", "value": recommendation, "inline": False},
    ]
    if "reversal_action" in analysis or "trend_context" in analysis:
        embed.fields.extend([
            {"name": "Hướng đảo chiều", "value": format_reversal_action(analysis.get("reversal_action", "n/a")), "inline": True},
            {"name": "Bối cảnh xu hướng", "value": format_trend_context(analysis.get("trend_context", "n/a")), "inline": True},
        ])
    embed.fields.extend([
        {"name": "Raw Score", "value": _format_score_map(raw_score), "inline": False},
        {"name": "Weighted Score", "value": _format_score_map(weighted_score, precision=2), "inline": False},
        {"name": "Bộ lọc", "value": _format_filters(filters), "inline": False},
        {"name": "Lý do", "value": _format_reasons(reasons), "inline": False},
    ])
    return embed


def format_trend_context(value: object) -> str:
    """Chuyển mã bối cảnh trend nội bộ sang tiếng Việt để hiển thị Discord."""
    return TREND_CONTEXT_LABELS.get(str(value), str(value))


def format_safe_trend(value: object) -> str:
    """Chuyển hướng safe trend sang tiếng Việt ngắn gọn."""
    labels = {
        "UP": "Tăng",
        "DOWN": "Giảm",
        "NEUTRAL": "Chưa rõ",
    }
    return labels.get(str(value), str(value))


def format_reversal_action(value: object) -> str:
    """Format hướng reversal sang tiếng Việt nhưng vẫn giữ LONG/SHORT để dễ nhận biết."""
    labels = {
        "LONG": "LONG - Quay đầu lên",
        "SHORT": "SHORT - Quay đầu xuống",
        "NONE": "Chưa có hướng đảo chiều",
        "n/a": "Không có dữ liệu",
    }
    return labels.get(str(value), str(value))


def format_decision(decision: str) -> str:
    """Chuyển decision kỹ thuật của strategy sang câu tiếng Việt dễ đọc."""
    if decision.startswith("Signal "):
        return decision.replace("Signal LONG", "Có tín hiệu LONG").replace("Signal SHORT", "Có tín hiệu SHORT")
    return DECISION_LABELS.get(decision, decision)


def format_recommendation(analysis: Dict[str, object]) -> str:
    """Tạo khuyến nghị hành động dựa trên decision, filter và bối cảnh trend.

    Tham số:
    - analysis: Dữ liệu summary do strategy tạo, gồm decision, filters và trend_context.

    Trả về:
    - Chuỗi tiếng Việt nêu nên cân nhắc vào lệnh, chờ thêm xác nhận hoặc không nên vào.
    """
    decision = str(analysis.get("decision", "No signal"))
    filters = analysis.get("filters") or {}
    trend_context = str(analysis.get("trend_context", ""))
    if decision.startswith("Signal "):
        if trend_context == "COUNTER_SAFE_TREND":
            return "Có tín hiệu nhưng ngược xu hướng lớn, chỉ cân nhắc với khối lượng nhỏ và quản trị rủi ro chặt."
        return "Có thể cân nhắc vào lệnh theo entry đề xuất nếu quản trị rủi ro phù hợp."
    if filters.get("volume_confirmed") is False:
        return "Không nên vào lệnh vì volume chưa xác nhận."
    if filters.get("reversal_action") is False:
        return "Không nên vào lệnh vì chưa có hướng đảo chiều rõ ràng."
    if filters.get("mode_threshold") is False:
        return "Chưa nên vào lệnh, chờ thêm xác nhận để điểm tín hiệu đạt ngưỡng."
    if filters.get("rate_limit") is False:
        return "Không nên vào thêm lệnh vì đã vượt giới hạn tín hiệu hiện tại."
    return "Chưa nên vào lệnh, tiếp tục chờ setup rõ hơn."


def _format_score_map(scores: Dict[str, object], precision: int = 0) -> str:
    """Format score dict thành một dòng ngắn để Discord embed dễ đọc."""
    if not scores:
        return "Không có dữ liệu"
    labels = [
        ("trend", "Trend"),
        ("momentum", "Momentum"),
        ("volatility", "Volatility"),
        ("volume", "Volume"),
        ("sr", "S/R"),
    ]
    parts = []
    for key, label in labels:
        value = float(scores.get(key, 0.0) or 0.0)
        parts.append(f"{label}: {value:.{precision}f}")
    return " | ".join(parts)


def _format_filters(filters: Dict[str, object]) -> str:
    """Format trạng thái pass/fail của các filter strategy."""
    if not filters:
        return "Không có dữ liệu"
    parts = []
    for key, label in FILTER_LABELS:
        if key not in filters:
            parts.append(f"{label}: không có dữ liệu")
            continue
        parts.append(f"{label}: {'đạt' if bool(filters.get(key, False)) else 'chưa đạt'}")
    return " | ".join(parts)


def _format_reasons(reasons: list, limit: int = 5) -> str:
    """Format lý do phân tích, giới hạn để embed không quá dài."""
    if not reasons:
        return "Không có lý do nổi bật"
    return " | ".join(str(reason) for reason in reasons[:limit])
