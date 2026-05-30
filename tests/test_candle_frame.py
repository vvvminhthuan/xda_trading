from app.models.candle_frame import CandleFrames


def test_candle_frame_detects_new_candle():
    """Kiểm tra CandleFrames nhận biết nến mới theo timestamp."""
    frames = CandleFrames()
    frames.set("1m", [[1000, 1, 2, 0.5, 1.5, 10]])

    assert not frames.is_new_closed_candle("1m", [1000, 1, 2, 0.5, 1.6, 11])
    assert frames.is_new_closed_candle("1m", [2000, 1.5, 2, 1, 1.8, 12])
