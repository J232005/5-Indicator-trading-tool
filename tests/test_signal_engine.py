import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from signal_engine import generate_signal

def _bullish_base():
    return dict(
        ema_result    = {'trend': 'BULLISH', 'crossover': None, 'ema_fast': 101.0, 'ema_slow': 100.0},
        vwap_result   = {'price_vs_vwap': 'ABOVE', 'vwap': 100.0, 'distance_pct': 0.5},
        vp_result     = {'error': 'skipped'},
        rsi_result    = {'condition': 'NEUTRAL', 'rsi': 50.0},
        atr_result    = {'atr': 1.0, 'stop_distance': 1.5},
        current_price = 101.0,
    )

def test_signal_labels_are_renamed():
    result = generate_signal(**_bullish_base())
    assert result['signal'] in {'BUY', 'WEAK BUY', 'HOLD', 'WEAK SELL', 'SELL'}

def test_no_trade_label_is_gone():
    result = generate_signal(**_bullish_base())
    assert result['signal'] != 'NO TRADE'
    assert result['signal'] != 'STRONG LONG'

def test_htf_bullish_raises_score():
    base = _bullish_base()
    without = generate_signal(**base)
    base['htf_result'] = {'trend': 'BULLISH', 'ema_fast': 101.0, 'ema_slow': 100.0}
    with_htf = generate_signal(**base)
    assert with_htf['score'] > without['score']

def test_htf_bearish_lowers_score():
    base = _bullish_base()
    base['htf_result'] = {'trend': 'BEARISH', 'ema_fast': 99.0, 'ema_slow': 100.0}
    result = generate_signal(**base)
    without = generate_signal(**_bullish_base())
    assert result['score'] < without['score']

def test_spy_bullish_raises_score():
    base = _bullish_base()
    without = generate_signal(**base)
    base['market_result'] = {'trend': 'BULLISH', 'spy_price': 524.0, 'ema_fast': 524.0, 'ema_slow': 523.0}
    with_spy = generate_signal(**base)
    assert with_spy['score'] > without['score']

def test_spy_bearish_lowers_score():
    base = _bullish_base()
    base['market_result'] = {'trend': 'BEARISH', 'spy_price': 524.0, 'ema_fast': 523.0, 'ema_slow': 524.0}
    result = generate_signal(**base)
    assert result['score'] < generate_signal(**_bullish_base())['score']

def test_high_volume_raises_score():
    base = _bullish_base()
    without = generate_signal(**base)
    base['vol_context_result'] = {'status': 'HIGH', 'session_vol': 2_000_000, 'expected_vol': 1_000_000}
    result = generate_signal(**base)
    assert result['score'] > without['score']

def test_low_volume_lowers_score():
    base = _bullish_base()
    without = generate_signal(**base)
    base['vol_context_result'] = {'status': 'LOW', 'session_vol': 200_000, 'expected_vol': 1_000_000}
    result = generate_signal(**base)
    assert result['score'] < without['score']

def test_gap_up_confirms_bullish_bias():
    base = _bullish_base()
    without = generate_signal(**base)
    base['gap_result'] = {'gap_pct': 0.01, 'direction': 'UP'}
    result = generate_signal(**base)
    assert result['score'] > without['score']

def test_gap_down_opposes_bullish_bias():
    base = _bullish_base()
    without = generate_signal(**base)
    base['gap_result'] = {'gap_pct': -0.01, 'direction': 'DOWN'}
    result = generate_signal(**base)
    assert result['score'] < without['score']

def test_gap_none_is_neutral():
    base = _bullish_base()
    without = generate_signal(**base)
    base['gap_result'] = {'gap_pct': 0.001, 'direction': 'NONE'}
    result = generate_signal(**base)
    assert result['score'] == without['score']
