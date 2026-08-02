"""Rate limiting — the pure sliding-window decision."""
from app.domain.ratelimit import evaluate


def test_first_hit_allowed():
    d = evaluate([], now=100.0, limit=3, window=10.0)
    assert d.allowed and d.remaining == 2 and d.retry_after == 0.0
    assert d.kept == [100.0]


def test_under_limit_allowed_and_appended():
    d = evaluate([100.0, 101.0], now=102.0, limit=3, window=10.0)
    assert d.allowed and d.kept == [100.0, 101.0, 102.0]


def test_at_limit_blocked_with_retry_after():
    d = evaluate([100.0, 101.0, 102.0], now=103.0, limit=3, window=10.0)
    assert not d.allowed and d.remaining == 0
    assert abs(d.retry_after - 7.0) < 1e-9   # oldest (100) frees at 110
    assert d.kept == [100.0, 101.0, 102.0]   # nothing appended when blocked


def test_old_hits_prune_and_reallow():
    d = evaluate([100.0, 101.0, 102.0], now=115.0, limit=3, window=10.0)
    assert d.allowed and d.kept == [115.0]


def test_window_boundary_is_strict():
    # a hit exactly `window` old is outside the window (cutoff uses strict >)
    d = evaluate([100.0], now=110.0, limit=1, window=10.0)
    assert d.allowed and d.kept == [110.0]


def test_zero_limit_blocks_everything():
    assert evaluate([], now=1.0, limit=0, window=10.0).allowed is False


def test_unordered_input():
    d = evaluate([102.0, 100.0, 101.0], now=103.0, limit=3, window=10.0)
    assert not d.allowed and abs(d.retry_after - 7.0) < 1e-9
