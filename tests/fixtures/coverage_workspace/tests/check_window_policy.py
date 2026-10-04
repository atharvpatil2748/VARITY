def test_refund_window_days():
    from src.window_policy import refund_window_days

    assert refund_window_days() == 30
