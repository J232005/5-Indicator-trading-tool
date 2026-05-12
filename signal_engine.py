import math
from config import ACCOUNT_SIZE, RISK_PERCENT, RRR


def generate_signal(
    ema_result:  dict,
    vwap_result: dict,
    vp_result:   dict,
    rsi_result:  dict,
    atr_result:  dict,
    current_price: float,
) -> dict:
    """
    Scores all available indicators and returns a composite signal
    with full position sizing details.
    """

    score         = 0.0
    max_score     = 0.0   # Tracks maximum achievable score given available indicators
    active_count  = 0
    warnings      = []

    # ── EMA Score ──────────────────────────────────────────────────────────────
    if 'error' not in ema_result:
        max_score += 2.0   # Base 1 + possible crossover bonus 1
        active_count += 1
        if ema_result['trend'] == 'BULLISH':
            score += 1.0
        else:
            score -= 1.0
        if ema_result['crossover'] == 'GOLDEN CROSS':
            score += 1.0
        elif ema_result['crossover'] == 'DEATH CROSS':
            score -= 1.0
    else:
        warnings.append(f"EMA: {ema_result['error']}")

    # ── VWAP Score ─────────────────────────────────────────────────────────────
    if 'error' not in vwap_result:
        max_score += 1.0
        active_count += 1
        if vwap_result['price_vs_vwap'] == 'ABOVE':
            score += 1.0
        else:
            score -= 1.0
    else:
        warnings.append(f"VWAP: {vwap_result['error']}")

    # ── Volume Profile Score ───────────────────────────────────────────────────
    if 'error' not in vp_result:
        max_score += 0.5
        active_count += 1
        zone = vp_result['zone']
        # Determine overall directional bias from other indicators first
        bias_score = score  # Use score so far as directional proxy
        if zone == 'BELOW_VALUE_AREA':
            score += 0.5 if bias_score >= 0 else -0.5
        elif zone == 'ABOVE_VALUE_AREA':
            score -= 0.5 if bias_score >= 0 else -0.5
        # AT_POC and IN_VALUE_AREA: neutral, 0 added
    else:
        warnings.append(f"Volume Profile: {vp_result['error']}")

    # ── RSI Score ──────────────────────────────────────────────────────────────
    if 'error' not in rsi_result:
        max_score += 1.0
        active_count += 1
        condition = rsi_result['condition']
        if condition == 'BULLISH_RANGE':
            score += 1.0
        elif condition == 'BEARISH_RANGE':
            score -= 1.0
        elif condition == 'OVERBOUGHT':
            score -= 1.0   # Penalise: overextended, likely not a good long entry
        elif condition == 'OVERSOLD':
            score += 1.0   # Penalise short bias: likely not a good short entry
        # NEUTRAL: 0
    else:
        warnings.append(f"RSI: {rsi_result['error']}")

    # ── ATR is always required for sizing — not scored but validated ───────────
    if 'error' in atr_result:
        warnings.append(f"ATR: {atr_result['error']}")

    # ── Composite Signal ───────────────────────────────────────────────────────
    # Normalise score relative to maximum achievable, then scale back to ±4 range
    if max_score > 0:
        normalised = (score / max_score) * 4.0
    else:
        normalised = 0.0

    if normalised >= 3.0:
        signal = 'STRONG LONG'
    elif normalised >= 1.5:
        signal = 'LONG BIAS'
    elif normalised <= -3.0:
        signal = 'STRONG SHORT'
    elif normalised <= -1.5:
        signal = 'SHORT BIAS'
    else:
        signal = 'NO TRADE'

    # ── Position Sizing ────────────────────────────────────────────────────────
    sizing = {}
    if signal != 'NO TRADE' and 'error' not in atr_result:
        risk_amount   = round(ACCOUNT_SIZE * RISK_PERCENT, 2)
        stop_dist     = atr_result['stop_distance']
        shares        = max(1, math.floor(risk_amount / stop_dist)) if stop_dist > 0 else 0

        if 'LONG' in signal:
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
            'risk_amount':  round(ACCOUNT_SIZE * RISK_PERCENT, 2),
            'shares':       'N/A',
            'stop_price':   'N/A',
            'target_price': 'N/A',
        }

    return {
        'signal':        signal,
        'score':         round(normalised, 2),
        'active_count':  active_count,
        'sizing':        sizing,
        'warnings':      warnings,
    }