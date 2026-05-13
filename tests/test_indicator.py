import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from tests.conftest import make_df


# ── calc_htf_trend ─────────────────────────────────────────────────────────────

def test_htf_trend_bullish():
    from indicator import calc_htf_trend
    df = make_df([100 + i for i in range(25)])
    result = calc_htf_trend(df)
    assert result['trend'] == 'BULLISH'
    assert 'ema_fast' in result
    assert 'ema_slow' in result


def test_htf_trend_bearish():
    from indicator import calc_htf_trend
    df = make_df([200 - i for i in range(25)])
    result = calc_htf_trend(df)
    assert result['trend'] == 'BEARISH'


def test_htf_trend_insufficient_bars():
    from indicator import calc_htf_trend
    df = make_df([100.0] * 5)
    result = calc_htf_trend(df)
    assert 'error' in result


# ── calc_market_context ────────────────────────────────────────────────────────

def test_market_context_bullish():
    from indicator import calc_market_context
    spy_df = make_df([520 + i for i in range(25)])
    result = calc_market_context(spy_df)
    assert result['trend'] == 'BULLISH'
    assert 'spy_price' in result
    assert 'ema_fast' in result
    assert 'ema_slow' in result


def test_market_context_bearish():
    from indicator import calc_market_context
    spy_df = make_df([540 - i for i in range(25)])
    result = calc_market_context(spy_df)
    assert result['trend'] == 'BEARISH'


def test_market_context_insufficient_bars():
    from indicator import calc_market_context
    result = calc_market_context(make_df([520.0] * 3))
    assert 'error' in result


# ── calc_volume_context ────────────────────────────────────────────────────────

def test_volume_context_high():
    from indicator import calc_volume_context
    df = make_df([100.0] * 78, volumes=[2_000_000] * 78)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'HIGH'
    assert result['session_vol'] == 78 * 2_000_000
    assert result['expected_vol'] == pytest.approx(1_000_000.0, rel=1e-3)


def test_volume_context_low():
    from indicator import calc_volume_context
    df = make_df([100.0] * 39, volumes=[100_000] * 39)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'LOW'


def test_volume_context_normal():
    from indicator import calc_volume_context
    df = make_df([100.0] * 39, volumes=[500_000] * 39)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'NORMAL'


def test_volume_context_invalid_avg():
    from indicator import calc_volume_context
    result = calc_volume_context(make_df([100.0] * 10), avg_daily_vol=0.0)
    assert 'error' in result


# ── calc_gap ───────────────────────────────────────────────────────────────────

def test_gap_up():
    from indicator import calc_gap
    df = make_df([101.0] * 10, opens=[101.0] * 10)
    result = calc_gap(df, prev_close=100.0)
    assert result['direction'] == 'UP'
    assert result['gap_pct'] == pytest.approx(0.01, rel=1e-3)


def test_gap_down():
    from indicator import calc_gap
    df = make_df([98.0] * 10, opens=[98.0] * 10)
    result = calc_gap(df, prev_close=100.0)
    assert result['direction'] == 'DOWN'
    assert result['gap_pct'] == pytest.approx(-0.02, rel=1e-3)


def test_gap_none():
    from indicator import calc_gap
    df = make_df([100.1] * 10, opens=[100.1] * 10)
    result = calc_gap(df, prev_close=100.0)
    assert result['direction'] == 'NONE'


def test_gap_invalid_prev_close():
    from indicator import calc_gap
    result = calc_gap(make_df([100.0] * 5), prev_close=0.0)
    assert 'error' in result
