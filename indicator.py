import numpy as np
import pandas as pd
from config import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    ATR_STOP_MULTIPLIER, VP_BIN_COUNT, GAP_THRESHOLD
)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    """Standard exponential moving average using pandas ewm."""
    return series.ewm(span=period, adjust=False).mean()


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """
    Wilder smoothing: SMA for first value, then smoothed average.
    avg[i] = (avg[i-1] × (period-1) + series[i]) / period
    """
    result = np.full(len(series), np.nan)
    if len(series) < period:
        return pd.Series(result, index=series.index)
    result[period - 1] = series.iloc[:period].mean()
    for i in range(period, len(series)):
        result[i] = (result[i - 1] * (period - 1) + series.iloc[i]) / period
    return pd.Series(result, index=series.index)


# ── Indicator 1: EMA 9 / 20 ────────────────────────────────────────────────────

def calc_ema_signal(df: pd.DataFrame) -> dict:
    """
    Returns EMA9, EMA20, trend direction, and crossover flag.
    Returns {'error': reason} if insufficient data.
    """
    min_bars = EMA_SLOW + 1
    if len(df) < min_bars:
        return {'error': f'Need at least {min_bars} bars for EMA. Only {len(df)} available.'}

    ema_fast = _ema(df['close'], EMA_FAST)
    ema_slow = _ema(df['close'], EMA_SLOW)

    curr_fast = ema_fast.iloc[-1]
    curr_slow = ema_slow.iloc[-1]
    prev_fast = ema_fast.iloc[-2]
    prev_slow = ema_slow.iloc[-2]

    trend = 'BULLISH' if curr_fast > curr_slow else 'BEARISH'

    crossover = None
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        crossover = 'GOLDEN CROSS'
    elif prev_fast >= prev_slow and curr_fast < curr_slow:
        crossover = 'DEATH CROSS'

    return {
        'ema_fast': round(curr_fast, 2),
        'ema_slow': round(curr_slow, 2),
        'trend': trend,
        'crossover': crossover,
    }


# ── Indicator: EMA 9 / 20 on 15-min bars ──────────────────────────────────────

def calc_htf_trend(df_15m: pd.DataFrame) -> dict:
    """
    EMA 9/20 on the 15-min bar series. Returns trend direction only (no crossover).
    Returns {'error': reason} if insufficient data.
    """
    min_bars = EMA_SLOW + 1
    if len(df_15m) < min_bars:
        return {'error': f'Need at least {min_bars} 15m bars for HTF EMA. Only {len(df_15m)} available.'}

    ema_fast = _ema(df_15m['close'], EMA_FAST)
    ema_slow = _ema(df_15m['close'], EMA_SLOW)

    curr_fast = ema_fast.iloc[-1]
    curr_slow = ema_slow.iloc[-1]

    return {
        'trend':    'BULLISH' if curr_fast > curr_slow else 'BEARISH',
        'ema_fast': round(curr_fast, 2),
        'ema_slow': round(curr_slow, 2),
    }


# ── Indicator: SPY Market Context ──────────────────────────────────────────────

def calc_market_context(spy_df: pd.DataFrame) -> dict:
    """
    EMA 9/20 on SPY 5-min bars. Returns trend direction and current SPY price.
    Returns {'error': reason} if insufficient data.
    """
    min_bars = EMA_SLOW + 1
    if len(spy_df) < min_bars:
        return {'error': f'Need at least {min_bars} bars for SPY EMA. Only {len(spy_df)} available.'}

    ema_fast = _ema(spy_df['close'], EMA_FAST)
    ema_slow = _ema(spy_df['close'], EMA_SLOW)

    curr_fast = ema_fast.iloc[-1]
    curr_slow = ema_slow.iloc[-1]

    return {
        'trend':     'BULLISH' if curr_fast > curr_slow else 'BEARISH',
        'spy_price': round(float(spy_df['close'].iloc[-1]), 2),
        'ema_fast':  round(curr_fast, 2),
        'ema_slow':  round(curr_slow, 2),
    }


# ── Indicator: Volume Conviction ───────────────────────────────────────────────

def calc_volume_context(df: pd.DataFrame, avg_daily_vol: float) -> dict:
    """
    Compares cumulative session volume against the expected volume given how much of
    the trading day has elapsed (len(df) bars x 5 min / 390 min).
    Returns {'status': 'HIGH'|'NORMAL'|'LOW', 'session_vol', 'expected_vol'}.
    Returns {'error': reason} if inputs are invalid.
    """
    if len(df) < 1:
        return {'error': 'No bars available for volume context.'}
    if avg_daily_vol <= 0:
        return {'error': 'Invalid average daily volume — must be > 0.'}

    session_vol  = float(df['volume'].sum())
    elapsed_min  = len(df) * 5
    expected_vol = avg_daily_vol * (elapsed_min / 390)

    if session_vol > expected_vol * 100:
        status = 'HIGH'
    elif session_vol < expected_vol * 10:
        status = 'LOW'
    else:
        status = 'NORMAL'

    return {
        'status':       status,
        'session_vol':  round(session_vol),
        'expected_vol': round(expected_vol),
    }


# ── Indicator: Gap Detection ───────────────────────────────────────────────────

def calc_gap(df: pd.DataFrame, prev_close: float) -> dict:
    """
    Computes the overnight gap as (today_open - prev_close) / prev_close.
    Direction is UP, DOWN, or NONE (gap smaller than GAP_THRESHOLD).
    Returns {'error': reason} if inputs are invalid.
    """
    if len(df) < 1:
        return {'error': 'No bars for gap calculation.'}
    if prev_close <= 0:
        return {'error': 'Invalid previous close — must be > 0.'}

    today_open = float(df.iloc[0]['open'])
    gap_pct    = (today_open - prev_close) / prev_close

    if gap_pct > GAP_THRESHOLD:
        direction = 'UP'
    elif gap_pct < -GAP_THRESHOLD:
        direction = 'DOWN'
    else:
        direction = 'NONE'

    return {
        'gap_pct':   round(gap_pct, 4),
        'direction': direction,
    }


# ── Indicator 2: VWAP ──────────────────────────────────────────────────────────

def calc_vwap(df: pd.DataFrame, current_price: float) -> dict:
    """
    Intraday VWAP using all bars in df (useRTH=True ensures session bars only).
    Returns VWAP value and price position relative to it.
    """
    if len(df) < 1:
        return {'error': 'No bars available for VWAP.'}

    typical = (df['high'] + df['low'] + df['close']) / 3
    cumvol   = df['volume'].cumsum()
    cumtpvol = (typical * df['volume']).cumsum()

    # Avoid division by zero
    vwap_series = cumtpvol / cumvol.replace(0, np.nan)
    vwap = vwap_series.iloc[-1]

    if np.isnan(vwap):
        return {'error': 'VWAP calculation returned NaN. Insufficient volume data.'}

    distance_pct = round(((current_price - vwap) / vwap) * 100, 2)
    bias = 'ABOVE' if current_price > vwap else 'BELOW'

    return {
        'vwap': round(vwap, 2),
        'price_vs_vwap': bias,
        'distance_pct': distance_pct,
    }


# ── Indicator 3: Volume Profile ────────────────────────────────────────────────

def calc_volume_profile(df: pd.DataFrame, current_price: float) -> dict:
    """
    Calculates intraday Volume Profile: POC, VAH, VAL, and current price zone.
    Returns {'error': reason} if fewer than 5 bars.
    """
    if len(df) < 5:
        return {'error': 'Need at least 5 bars for Volume Profile.'}

    session_low  = df['low'].min()
    session_high = df['high'].max()

    if session_high == session_low:
        return {'error': 'Zero price range this session. Volume Profile unavailable.'}

    # Build price bins
    bins      = np.linspace(session_low, session_high, VP_BIN_COUNT + 1)
    bin_mid   = (bins[:-1] + bins[1:]) / 2
    bin_vol   = np.zeros(VP_BIN_COUNT)

    typical = ((df['high'] + df['low'] + df['close']) / 3).values
    volumes  = df['volume'].values

    for tp, vol in zip(typical, volumes):
        idx = np.searchsorted(bins[1:], tp, side='left')
        idx = min(idx, VP_BIN_COUNT - 1)
        bin_vol[idx] += vol

    # Point of Control
    poc_idx = int(np.argmax(bin_vol))
    poc     = round(float(bin_mid[poc_idx]), 2)

    # Value Area (70% of total volume)
    total_vol    = bin_vol.sum()
    target_vol   = total_vol * 0.70
    accumulated  = bin_vol[poc_idx]
    lower_idx    = poc_idx
    upper_idx    = poc_idx

    while accumulated < target_vol:
        can_go_up   = upper_idx < VP_BIN_COUNT - 1
        can_go_down = lower_idx > 0

        if not can_go_up and not can_go_down:
            break

        vol_up   = bin_vol[upper_idx + 1] if can_go_up   else -1
        vol_down = bin_vol[lower_idx - 1] if can_go_down else -1

        if vol_up >= vol_down:
            upper_idx   += 1
            accumulated += bin_vol[upper_idx]
        else:
            lower_idx   -= 1
            accumulated += bin_vol[lower_idx]

    vah = round(float(bins[upper_idx + 1]), 2)
    val = round(float(bins[lower_idx]),     2)

    # Current price zone
    poc_threshold = poc * 0.001  # 0.1% band around POC
    if abs(current_price - poc) <= poc_threshold:
        zone = 'AT_POC'
    elif current_price > vah:
        zone = 'ABOVE_VALUE_AREA'
    elif current_price < val:
        zone = 'BELOW_VALUE_AREA'
    else:
        zone = 'IN_VALUE_AREA'

    return {
        'poc': poc,
        'vah': vah,
        'val': val,
        'zone': zone,
    }


# ── Indicator 4: RSI (14) ──────────────────────────────────────────────────────

def calc_rsi(df: pd.DataFrame) -> dict:
    """
    Wilder RSI. Returns RSI value and market condition label.
    Returns {'error': reason} if insufficient bars.
    """
    min_bars = RSI_PERIOD + 1
    if len(df) < min_bars:
        return {'error': f'Need at least {min_bars} bars for RSI. Only {len(df)} available.'}

    delta  = df['close'].diff().dropna()
    gains  = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)

    avg_gain = _wilder_smooth(gains, RSI_PERIOD)
    avg_loss = _wilder_smooth(losses, RSI_PERIOD)

    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]

    if last_loss == 0:
        rsi_val = 100.0
    else:
        rs      = last_gain / last_loss
        rsi_val = round(100 - (100 / (1 + rs)), 1)

    if rsi_val > 70:
        condition = 'OVERBOUGHT'
    elif rsi_val >= 55:
        condition = 'BULLISH_RANGE'
    elif rsi_val >= 45:
        condition = 'NEUTRAL'
    elif rsi_val >= 30:
        condition = 'BEARISH_RANGE'
    else:
        condition = 'OVERSOLD'

    return {
        'rsi': rsi_val,
        'condition': condition,
    }


# ── Indicator 5: ATR (14) ──────────────────────────────────────────────────────

def calc_atr(df: pd.DataFrame) -> dict:
    """
    Wilder ATR. Returns ATR value and stop distance (ATR × multiplier).
    Returns {'error': reason} if insufficient bars.
    """
    min_bars = ATR_PERIOD + 1
    if len(df) < min_bars:
        return {'error': f'Need at least {min_bars} bars for ATR. Only {len(df)} available.'}

    high  = df['high'].values
    low   = df['low'].values
    close = df['close'].values

    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:]  - close[:-1]),
        )
    )
    tr_series = pd.Series(tr)
    atr_series = _wilder_smooth(tr_series, ATR_PERIOD)
    atr_val    = round(float(atr_series.iloc[-1]), 2)

    return {
        'atr': atr_val,
        'stop_distance': round(atr_val * ATR_STOP_MULTIPLIER, 2),
    }
