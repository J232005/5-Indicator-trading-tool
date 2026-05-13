import math
from config import ACCOUNT_SIZE, RISK_PERCENT, RRR


def generate_signal(
    ema_result:          dict,
    vwap_result:         dict,
    vp_result:           dict,
    rsi_result:          dict,
    atr_result:          dict,
    current_price:       float,
    htf_result:          dict = None,
    market_result:       dict = None,
    vol_context_result:  dict = None,
    gap_result:          dict = None,
) -> dict:
    """
    Scores all available indicators and returns a composite signal
    with full position sizing details.
    """

    score        = 0.0
    max_score    = 0.0
    active_count = 0
    warnings     = []

    # ── EMA Score ──────────────────────────────────────────────────────────────
    if 'error' not in ema_result:
        max_score    += 2.0
        active_count += 1
        score += 1.0 if ema_result['trend'] == 'BULLISH' else -1.0
        if ema_result['crossover'] == 'GOLDEN CROSS':
            score += 1.0
        elif ema_result['crossover'] == 'DEATH CROSS':
            score -= 1.0
    else:
        warnings.append(f"EMA: {ema_result['error']}")

    # ── VWAP Score ─────────────────────────────────────────────────────────────
    if 'error' not in vwap_result:
        max_score    += 1.0
        active_count += 1
        score += 1.0 if vwap_result['price_vs_vwap'] == 'ABOVE' else -1.0
    else:
        warnings.append(f"VWAP: {vwap_result['error']}")

    # ── Volume Profile Score ───────────────────────────────────────────────────
    if 'error' not in vp_result:
        max_score    += 0.5
        active_count += 1
        zone       = vp_result['zone']
        bias_score = score
        if zone == 'BELOW_VALUE_AREA':
            score += 0.5 if bias_score >= 0 else -0.5
        elif zone == 'ABOVE_VALUE_AREA':
            score -= 0.5 if bias_score >= 0 else -0.5
    else:
        warnings.append(f"Volume Profile: {vp_result['error']}")

    # ── RSI Score ──────────────────────────────────────────────────────────────
    if 'error' not in rsi_result:
        max_score    += 1.0
        active_count += 1
        condition = rsi_result['condition']
        if condition == 'BULLISH_RANGE':
            score += 1.0
        elif condition == 'BEARISH_RANGE':
            score -= 1.0
        elif condition == 'OVERBOUGHT':
            score -= 1.0
        elif condition == 'OVERSOLD':
            score += 1.0
    else:
        warnings.append(f"RSI: {rsi_result['error']}")

    # ── ATR — sizing only, not scored ─────────────────────────────────────────
    if 'error' in atr_result:
        warnings.append(f"ATR: {atr_result['error']}")

    # ── HTF EMA Score ──────────────────────────────────────────────────────────
    if htf_result and 'error' not in htf_result:
        max_score    += 1.5
        active_count += 1
        score += 1.5 if htf_result['trend'] == 'BULLISH' else -1.5
    elif htf_result:
        warnings.append(f"HTF EMA: {htf_result['error']}")

    # ── SPY Market Context Score ───────────────────────────────────────────────
    if market_result and 'error' not in market_result:
        max_score    += 1.0
        active_count += 1
        score += 1.0 if market_result['trend'] == 'BULLISH' else -1.0
    elif market_result:
        warnings.append(f"SPY: {market_result['error']}")

    # ── Volume Conviction Score ────────────────────────────────────────────────
    if vol_context_result and 'error' not in vol_context_result:
        max_score    += 0.5
        active_count += 1
        status = vol_context_result['status']
        if status == 'HIGH':
            score += 0.5
        elif status == 'LOW':
            score -= 0.5
    elif vol_context_result:
        warnings.append(f"Volume: {vol_context_result['error']}")

    # ── Gap Score ──────────────────────────────────────────────────────────────
    if gap_result and 'error' not in gap_result:
        direction = gap_result['direction']
        if direction != 'NONE':
            max_score    += 0.5
            active_count += 1
            confirms = (direction == 'UP' and score >= 0) or (direction == 'DOWN' and score < 0)
            score += 0.5 if confirms else -0.5
    elif gap_result:
        warnings.append(f"Gap: {gap_result['error']}")

    # ── Composite Signal ───────────────────────────────────────────────────────
    normalised = (score / max_score) * 4.0 if max_score > 0 else 0.0

    if normalised >= 3.0:
        signal = 'BUY'
    elif normalised >= 1.5:
        signal = 'WEAK BUY'
    elif normalised <= -3.0:
        signal = 'SELL'
    elif normalised <= -1.5:
        signal = 'WEAK SELL'
    else:
        signal = 'HOLD'

    # ── Position Sizing ────────────────────────────────────────────────────────
    risk_amount = round(ACCOUNT_SIZE * RISK_PERCENT, 2)

    if signal != 'HOLD' and 'error' not in atr_result:
        stop_dist    = atr_result['stop_distance']
        shares       = max(1, math.floor(risk_amount / stop_dist)) if stop_dist > 0 else 0
        if 'BUY' in signal:
            stop_price   = round(current_price - stop_dist, 2)
            target_price = round(current_price + stop_dist * RRR, 2)
        else:
            stop_price   = round(current_price + stop_dist, 2)
            target_price = round(current_price - stop_dist * RRR, 2)
        sizing = {
            'risk_amount':   risk_amount,
            'shares':        shares,
            'stop_price':    stop_price,
            'target_price':  target_price,
        }
    else:
        sizing = {
            'risk_amount':  risk_amount,
            'shares':       'N/A',
            'stop_price':   'N/A',
            'target_price': 'N/A',
        }

    return {
        'signal':       signal,
        'score':        round(normalised, 2),
        'active_count': active_count,
        'sizing':       sizing,
        'warnings':     warnings,
    }