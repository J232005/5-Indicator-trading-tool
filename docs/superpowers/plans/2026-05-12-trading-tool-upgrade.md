# Trading Tool Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the 5-indicator IBKR tool from manual snapshots to a live auto-refreshing BUY/SELL/HOLD signal tool with 4 new indicators (15m EMA, SPY context, volume conviction, gap detection) and a 60-minute streaming session.

**Architecture:** Use `ib_insync`'s `reqHistoricalData(keepUpToDate=True)` to subscribe to live bar streams; an `updateEvent` callback on the 5-min bar list fires on each bar close to recompute all indicators and redraw the terminal. SPY and 15-min bars stream silently in parallel and are read from their `BarDataList` inside the callback.

**Tech Stack:** Python 3.10+, ib_insync, pandas, numpy, rich, pytz, pytest

---

## File Map

| File | Change |
|------|--------|
| `config.py` | Add 5 new constants |
| `data_fetcher.py` | Add `bar_size` param to `get_bars`; add `get_daily_context` |
| `indicator.py` | Add `calc_htf_trend`, `calc_market_context`, `calc_volume_context`, `calc_gap` |
| `signal_engine.py` | Add 4 new indicator scores; rename signal labels |
| `display.py` | Add 4 new table rows; session timer in header; opening range note; updated color map |
| `main.py` | Replace manual loop with `watch_symbol` using live bar streaming |
| `tests/conftest.py` | Create — shared `make_df` test helper |
| `tests/test_indicator.py` | Create — unit tests for all 4 new indicator functions |
| `tests/test_signal_engine.py` | Create — unit tests for new scoring + signal rename |

---

## Task 1: Config Constants

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add the 5 new constants**

Open `config.py` and append after the existing `VP_BIN_COUNT` line:

```python
# ── Session & Streaming ────────────────────────────────────────────────────────
HTF_BAR_SIZE      = '15 mins'
SESSION_DURATION  = 3600        # seconds — auto-stop after 60 min

# ── Market Context ─────────────────────────────────────────────────────────────
MARKET_SYMBOL     = 'SPY'
AVG_VOL_LOOKBACK  = '1 M'       # daily bars lookback for average volume
GAP_THRESHOLD     = 0.005       # 0.5% — minimum gap size to score
```

- [ ] **Step 2: Verify Python can import the module cleanly**

```bash
cd /Users/jean-michelgeorr/Desktop/5-Indicator-Trading-Tool/5-Indicator-trading-tool
python -c "from config import HTF_BAR_SIZE, SESSION_DURATION, MARKET_SYMBOL, AVG_VOL_LOOKBACK, GAP_THRESHOLD; print('OK')"
```
Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat: add config constants for streaming session and new indicators"
```

---

## Task 2: Test Infrastructure + data_fetcher Updates

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `data_fetcher.py`

- [ ] **Step 1: Create empty `tests/__init__.py`**

Create `/Users/jean-michelgeorr/Desktop/5-Indicator-Trading-Tool/5-Indicator-trading-tool/tests/__init__.py` with no content.

- [ ] **Step 2: Create `tests/conftest.py` with shared test helper**

```python
import pandas as pd


def make_df(closes, opens=None, highs=None, lows=None, volumes=None):
    """Build a minimal OHLCV DataFrame for unit tests."""
    n = len(closes)
    closes_list = list(closes)
    return pd.DataFrame({
        'date':   pd.date_range('2026-01-02 09:30', periods=n, freq='5min'),
        'open':   opens   if opens   is not None else closes_list,
        'high':   highs   if highs   is not None else [c + 0.5 for c in closes_list],
        'low':    lows    if lows    is not None else [c - 0.5 for c in closes_list],
        'close':  closes_list,
        'volume': volumes if volumes is not None else [1_000_000] * n,
    })
```

- [ ] **Step 3: Write failing tests for `get_daily_context`**

Create `tests/test_data_fetcher.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from unittest.mock import MagicMock, patch


def _mock_daily_df(closes, volumes):
    return pd.DataFrame({
        'date':   [f'2026-01-{i+1:02d}' for i in range(len(closes))],
        'close':  closes,
        'volume': volumes,
    })


def test_get_daily_context_returns_avg_vol_and_prev_close():
    from data_fetcher import get_daily_context
    ib = MagicMock()
    ib.reqHistoricalData.return_value = ['placeholder'] * 20
    ib.sleep = MagicMock()

    closes  = [100.0] * 18 + [103.0, 105.0]   # prev_close = 103.0 (index -2)
    volumes = [1_000_000] * 20

    with patch('data_fetcher.util') as mock_util:
        mock_util.df.return_value = _mock_daily_df(closes, volumes)
        avg_vol, prev_close = get_daily_context(ib, 'AAPL')

    assert avg_vol == 1_000_000.0
    assert prev_close == 103.0


def test_get_daily_context_raises_on_insufficient_bars():
    from data_fetcher import get_daily_context
    ib = MagicMock()
    ib.reqHistoricalData.return_value = ['placeholder']   # only 1 bar
    ib.sleep = MagicMock()

    with patch('data_fetcher.util') as mock_util:
        mock_util.df.return_value = _mock_daily_df([100.0], [500_000])
        try:
            get_daily_context(ib, 'AAPL')
            assert False, 'Expected ValueError'
        except ValueError:
            pass
```

- [ ] **Step 4: Run tests — expect failure**

```bash
cd /Users/jean-michelgeorr/Desktop/5-Indicator-Trading-Tool/5-Indicator-trading-tool
python -m pytest tests/test_data_fetcher.py -v
```
Expected: `FAILED` — `ImportError` or `AttributeError` because `get_daily_context` does not exist yet.

- [ ] **Step 5: Update `data_fetcher.py` — add `bar_size` param to `get_bars` and add `get_daily_context`**

Change the import line at the top of `data_fetcher.py`:
```python
from config import TWS_HOST, TWS_PORT, CLIENT_ID, BAR_SIZE, DATA_DURATION, AVG_VOL_LOOKBACK
```

Change the `get_bars` signature (default unchanged so existing callers still work):
```python
def get_bars(ib: IB, symbol: str, bar_size: str = BAR_SIZE) -> pd.DataFrame:
    """
    Fetch intraday bars for the given symbol from TWS.
    Returns a DataFrame with columns: date, open, high, low, close, volume.
    Raises ValueError if no data is returned.
    """
    contract = Stock(symbol.upper(), 'SMART', 'USD')
    ib.qualifyContracts(contract)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=DATA_DURATION,
        barSizeSetting=bar_size,
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
    )
    ib.sleep(1)

    if not bars:
        raise ValueError(
            f"No data returned for '{symbol.upper()}'.\n"
            f"Possible reasons: invalid ticker, market is closed, or TWS data subscription issue."
        )

    df = util.df(bars)[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
    df = df.reset_index(drop=True)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close'])
    return df
```

Append `get_daily_context` after `get_current_price`:
```python
def get_daily_context(ib: IB, symbol: str) -> tuple:
    """
    Fetch daily bars going back AVG_VOL_LOOKBACK.
    Returns (avg_daily_vol, prev_close) where prev_close is yesterday's closing price.
    Raises ValueError if fewer than 2 daily bars are returned.
    """
    contract = Stock(symbol.upper(), 'SMART', 'USD')
    ib.qualifyContracts(contract)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=AVG_VOL_LOOKBACK,
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
    )
    ib.sleep(1)

    df = util.df(bars)[['date', 'close', 'volume']].copy()
    df['close']  = pd.to_numeric(df['close'],  errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    df = df.dropna()

    if len(df) < 2:
        raise ValueError(
            f"Insufficient daily data for '{symbol.upper()}'. Need at least 2 trading days."
        )

    avg_daily_vol = float(df['volume'].mean())
    prev_close    = float(df['close'].iloc[-2])
    return avg_daily_vol, prev_close
```

- [ ] **Step 6: Run tests — expect pass**

```bash
python -m pytest tests/test_data_fetcher.py -v
```
Expected:
```
PASSED tests/test_data_fetcher.py::test_get_daily_context_returns_avg_vol_and_prev_close
PASSED tests/test_data_fetcher.py::test_get_daily_context_raises_on_insufficient_bars
```

- [ ] **Step 7: Commit**

```bash
git add data_fetcher.py tests/__init__.py tests/conftest.py tests/test_data_fetcher.py
git commit -m "feat: add get_daily_context and bar_size param to get_bars"
```

---

## Task 3: calc_htf_trend

**Files:**
- Modify: `indicator.py`
- Create: `tests/test_indicator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_indicator.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from conftest import make_df


# ── calc_htf_trend ─────────────────────────────────────────────────────────────

def test_htf_trend_bullish():
    from indicator import calc_htf_trend
    df = make_df([100 + i for i in range(25)])   # ascending → fast EMA > slow EMA
    result = calc_htf_trend(df)
    assert result['trend'] == 'BULLISH'
    assert 'ema_fast' in result
    assert 'ema_slow' in result


def test_htf_trend_bearish():
    from indicator import calc_htf_trend
    df = make_df([200 - i for i in range(25)])   # descending → fast EMA < slow EMA
    result = calc_htf_trend(df)
    assert result['trend'] == 'BEARISH'


def test_htf_trend_insufficient_bars():
    from indicator import calc_htf_trend
    df = make_df([100.0] * 5)
    result = calc_htf_trend(df)
    assert 'error' in result
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_indicator.py::test_htf_trend_bullish tests/test_indicator.py::test_htf_trend_bearish tests/test_indicator.py::test_htf_trend_insufficient_bars -v
```
Expected: `FAILED` — `ImportError: cannot import name 'calc_htf_trend'`

- [ ] **Step 3: Add `calc_htf_trend` to `indicator.py`**

Add after the existing `calc_ema_signal` function (around line 62):

```python
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
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_indicator.py::test_htf_trend_bullish tests/test_indicator.py::test_htf_trend_bearish tests/test_indicator.py::test_htf_trend_insufficient_bars -v
```
Expected: 3 × `PASSED`

- [ ] **Step 5: Commit**

```bash
git add indicator.py tests/test_indicator.py
git commit -m "feat: add calc_htf_trend for 15-min EMA confirmation"
```

---

## Task 4: calc_market_context

**Files:**
- Modify: `indicator.py`, `tests/test_indicator.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_indicator.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_indicator.py -k "market_context" -v
```
Expected: `FAILED` — `ImportError: cannot import name 'calc_market_context'`

- [ ] **Step 3: Add `calc_market_context` to `indicator.py`**

Add after `calc_htf_trend`:

```python
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
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_indicator.py -k "market_context" -v
```
Expected: 3 × `PASSED`

- [ ] **Step 5: Commit**

```bash
git add indicator.py tests/test_indicator.py
git commit -m "feat: add calc_market_context for SPY EMA trend"
```

---

## Task 5: calc_volume_context

**Files:**
- Modify: `indicator.py`, `tests/test_indicator.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_indicator.py`:

```python
# ── calc_volume_context ────────────────────────────────────────────────────────

def test_volume_context_high():
    from indicator import calc_volume_context
    # 78 bars elapsed (78 × 5 = 390 min = full day) with 2× avg volume → HIGH
    df = make_df([100.0] * 78, volumes=[2_000_000] * 78)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'HIGH'
    assert result['session_vol'] == 78 * 2_000_000
    assert result['expected_vol'] == pytest.approx(1_000_000.0, rel=1e-3)


def test_volume_context_low():
    from indicator import calc_volume_context
    # 39 bars elapsed (half day), session volume = 20% of expected → LOW
    df = make_df([100.0] * 39, volumes=[100_000] * 39)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'LOW'


def test_volume_context_normal():
    from indicator import calc_volume_context
    # 39 bars elapsed (half day), session volume = 100% of expected → NORMAL
    df = make_df([100.0] * 39, volumes=[500_000] * 39)
    result = calc_volume_context(df, avg_daily_vol=1_000_000.0)
    assert result['status'] == 'NORMAL'


def test_volume_context_invalid_avg():
    from indicator import calc_volume_context
    result = calc_volume_context(make_df([100.0] * 10), avg_daily_vol=0.0)
    assert 'error' in result
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_indicator.py -k "volume_context" -v
```
Expected: `FAILED` — `ImportError: cannot import name 'calc_volume_context'`

- [ ] **Step 3: Add `calc_volume_context` to `indicator.py`**

Add after `calc_market_context`:

```python
# ── Indicator: Volume Conviction ───────────────────────────────────────────────

def calc_volume_context(df: pd.DataFrame, avg_daily_vol: float) -> dict:
    """
    Compares cumulative session volume against the expected volume given how much of
    the trading day has elapsed (len(df) bars × 5 min / 390 min).
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

    if session_vol > expected_vol * 1.3:
        status = 'HIGH'
    elif session_vol < expected_vol * 0.7:
        status = 'LOW'
    else:
        status = 'NORMAL'

    return {
        'status':       status,
        'session_vol':  round(session_vol),
        'expected_vol': round(expected_vol),
    }
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_indicator.py -k "volume_context" -v
```
Expected: 4 × `PASSED`

- [ ] **Step 5: Commit**

```bash
git add indicator.py tests/test_indicator.py
git commit -m "feat: add calc_volume_context for volume conviction scoring"
```

---

## Task 6: calc_gap

**Files:**
- Modify: `indicator.py`, `tests/test_indicator.py`

- [ ] **Step 1: Update the `indicator.py` config import to include `GAP_THRESHOLD`**

Change the existing import at the top of `indicator.py`:

```python
from config import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    ATR_STOP_MULTIPLIER, VP_BIN_COUNT, GAP_THRESHOLD
)
```

- [ ] **Step 2: Add tests**

Append to `tests/test_indicator.py`:

```python
# ── calc_gap ───────────────────────────────────────────────────────────────────

def test_gap_up():
    from indicator import calc_gap
    # today opened 1% above prev_close → UP
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
    # 0.1% gap — below GAP_THRESHOLD of 0.5%
    df = make_df([100.1] * 10, opens=[100.1] * 10)
    result = calc_gap(df, prev_close=100.0)
    assert result['direction'] == 'NONE'


def test_gap_invalid_prev_close():
    from indicator import calc_gap
    result = calc_gap(make_df([100.0] * 5), prev_close=0.0)
    assert 'error' in result
```

- [ ] **Step 3: Run — expect failure**

```bash
python -m pytest tests/test_indicator.py -k "gap" -v
```
Expected: `FAILED` — `ImportError: cannot import name 'calc_gap'`

- [ ] **Step 4: Add `calc_gap` to `indicator.py`**

Add after `calc_volume_context`:

```python
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
```

- [ ] **Step 5: Run all indicator tests — expect all pass**

```bash
python -m pytest tests/test_indicator.py -v
```
Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add indicator.py tests/test_indicator.py
git commit -m "feat: add calc_gap for overnight gap detection"
```

---

## Task 7: Update signal_engine — New Scoring + Signal Rename

**Files:**
- Modify: `signal_engine.py`
- Create: `tests/test_signal_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_signal_engine.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from signal_engine import generate_signal

# ── Helpers ────────────────────────────────────────────────────────────────────

def _bullish_base():
    """Minimal passing dicts that produce a bullish base score (EMA+VWAP bullish)."""
    return dict(
        ema_result    = {'trend': 'BULLISH', 'crossover': None, 'ema_fast': 101.0, 'ema_slow': 100.0},
        vwap_result   = {'price_vs_vwap': 'ABOVE', 'vwap': 100.0, 'distance_pct': 0.5},
        vp_result     = {'error': 'skipped'},
        rsi_result    = {'condition': 'NEUTRAL', 'rsi': 50.0},
        atr_result    = {'atr': 1.0, 'stop_distance': 1.5},
        current_price = 101.0,
    )


# ── Signal label rename ────────────────────────────────────────────────────────

def test_signal_labels_are_renamed():
    result = generate_signal(**_bullish_base())
    assert result['signal'] in {'BUY', 'WEAK BUY', 'HOLD', 'WEAK SELL', 'SELL'}


def test_no_trade_label_is_gone():
    result = generate_signal(**_bullish_base())
    assert result['signal'] != 'NO TRADE'
    assert result['signal'] != 'STRONG LONG'


# ── HTF scoring ────────────────────────────────────────────────────────────────

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


# ── SPY scoring ────────────────────────────────────────────────────────────────

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


# ── Volume conviction scoring ──────────────────────────────────────────────────

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


# ── Gap scoring ────────────────────────────────────────────────────────────────

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
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_signal_engine.py -v
```
Expected: most tests `FAILED` — signal labels are still `STRONG LONG` / `NO TRADE`, and new keyword args don't exist yet.

- [ ] **Step 3: Rewrite `signal_engine.py`**

Replace the entire file with:

```python
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
        max_score    += 0.5
        active_count += 1
        direction = gap_result['direction']
        if direction != 'NONE':
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
```

- [ ] **Step 4: Run all signal engine tests — expect pass**

```bash
python -m pytest tests/test_signal_engine.py -v
```
Expected: all tests `PASSED`

- [ ] **Step 5: Run full test suite — no regressions**

```bash
python -m pytest tests/ -v
```
Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add signal_engine.py tests/test_signal_engine.py
git commit -m "feat: add 4 new indicator scores and rename signals to BUY/SELL/HOLD"
```

---

## Task 8: Update display.py

**Files:**
- Modify: `display.py`

- [ ] **Step 1: Replace the entire `display.py` with the updated version**

```python
from datetime import datetime
import pytz
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich         import box

from config import RRR

console = Console()

ET = pytz.timezone('America/New_York')


def _trend_color(value: str) -> str:
    bullish = {
        'BULLISH', 'ABOVE', 'GOLDEN CROSS', 'BULLISH_RANGE',
        'BELOW_VALUE_AREA', 'BUY', 'WEAK BUY',
        'HIGH', 'MARKET BULLISH', 'CONFIRMS LONG', 'AGAINST SHORT', 'GAP UP',
    }
    bearish = {
        'BEARISH', 'BELOW', 'DEATH CROSS', 'BEARISH_RANGE',
        'ABOVE_VALUE_AREA', 'SELL', 'WEAK SELL',
        'LOW', 'MARKET BEARISH', 'CONFIRMS SHORT', 'AGAINST LONG', 'GAP DOWN',
    }
    if value in bullish:
        return 'green'
    if value in bearish:
        return 'red'
    return 'yellow'


def _signal_style(signal: str):
    styles = {
        'BUY':       ('bright_green', '▲▲  BUY        ▲▲'),
        'WEAK BUY':  ('green',        '▲   WEAK BUY    ▲'),
        'HOLD':      ('dim white',    '—   HOLD         —'),
        'WEAK SELL': ('red',          '▼   WEAK SELL   ▼'),
        'SELL':      ('bright_red',   '▼▼  SELL       ▼▼'),
    }
    return styles.get(signal, ('yellow', signal))


def _gap_reading(direction: str, signal: str) -> str:
    if direction == 'NONE':
        return 'NO SIGNIFICANT GAP'
    long_signals  = {'BUY', 'WEAK BUY'}
    short_signals = {'SELL', 'WEAK SELL'}
    if signal in long_signals:
        return 'CONFIRMS LONG'  if direction == 'UP'   else 'AGAINST LONG'
    if signal in short_signals:
        return 'CONFIRMS SHORT' if direction == 'DOWN' else 'AGAINST SHORT'
    return 'GAP UP' if direction == 'UP' else 'GAP DOWN'


def render_output(
    symbol:             str,
    current_price:      float,
    seconds_remaining:  int,
    ema_result:         dict,
    vwap_result:        dict,
    vp_result:          dict,
    rsi_result:         dict,
    atr_result:         dict,
    htf_result:         dict,
    market_result:      dict,
    vol_context_result: dict,
    gap_result:         dict,
    signal_result:      dict,
) -> None:
    """Render the full analysis panel to the terminal."""

    now_et = datetime.now(ET)
    time_str  = now_et.strftime('%Y-%m-%d  %H:%M ET')
    mins, secs = divmod(seconds_remaining, 60)
    timer_str = f'{mins:02d}:{secs:02d}'

    # ── Opening range warning ──────────────────────────────────────────────────
    if now_et.hour < 10:
        console.print('[dim yellow]⚠  Opening range — first 30 min[/dim yellow]')

    # ── Header ─────────────────────────────────────────────────────────────────
    console.print()
    console.rule(
        f"[bold cyan]{symbol.upper()}[/bold cyan]  ·  "
        f"[white]${current_price:.2f}[/white]  ·  [dim]{time_str}[/dim]  ·  "
        f"[dim]Session: {timer_str} remaining[/dim]"
    )

    # ── Indicator Table ────────────────────────────────────────────────────────
    tbl = Table(box=box.SIMPLE_HEAD, show_header=True, header_style='bold dim')
    tbl.add_column('Indicator',  style='bold',    width=18)
    tbl.add_column('Value',      justify='right', width=32)
    tbl.add_column('Reading',    justify='left',  width=22)

    # EMA 5m
    if 'error' not in ema_result:
        val_str = f"EMA{ema_result['ema_fast']} / EMA{ema_result['ema_slow']}"
        cross   = f"  [{_trend_color(ema_result.get('crossover',''))}]{ema_result.get('crossover','') or ''}[/]"
        reading = Text(ema_result['trend'], style=_trend_color(ema_result['trend']))
        tbl.add_row('EMA 9/20 (5m)', val_str + cross, reading)
    else:
        tbl.add_row('EMA 9/20 (5m)', '[dim]—[/dim]', f"[dim]{ema_result['error']}[/dim]")

    # EMA 15m
    if 'error' not in htf_result:
        val_str = f"EMA{htf_result['ema_fast']} / EMA{htf_result['ema_slow']}"
        reading = Text(htf_result['trend'], style=_trend_color(htf_result['trend']))
        tbl.add_row('EMA 9/20 (15m)', val_str, reading)
    else:
        tbl.add_row('EMA 9/20 (15m)', '[dim]—[/dim]', f"[dim]{htf_result['error']}[/dim]")

    # VWAP
    if 'error' not in vwap_result:
        dist_sign = '+' if vwap_result['distance_pct'] >= 0 else ''
        val_str   = f"${vwap_result['vwap']:.2f}  ({dist_sign}{vwap_result['distance_pct']}%)"
        reading   = Text(vwap_result['price_vs_vwap'] + ' VWAP',
                         style=_trend_color(vwap_result['price_vs_vwap']))
        tbl.add_row('VWAP', val_str, reading)
    else:
        tbl.add_row('VWAP', '[dim]—[/dim]', f"[dim]{vwap_result['error']}[/dim]")

    # Volume Profile
    if 'error' not in vp_result:
        val_str      = (f"POC ${vp_result['poc']:.2f}  "
                        f"VAH ${vp_result['vah']:.2f}  "
                        f"VAL ${vp_result['val']:.2f}")
        zone_display = vp_result['zone'].replace('_', ' ')
        reading      = Text(zone_display, style=_trend_color(vp_result['zone']))
        tbl.add_row('Vol Profile', val_str, reading)
    else:
        tbl.add_row('Vol Profile', '[dim]—[/dim]', f"[dim]{vp_result['error']}[/dim]")

    # RSI
    if 'error' not in rsi_result:
        val_str = f"RSI  {rsi_result['rsi']}"
        cond    = rsi_result['condition'].replace('_', ' ')
        reading = Text(cond, style=_trend_color(rsi_result['condition']))
        tbl.add_row('RSI (14)', val_str, reading)
    else:
        tbl.add_row('RSI (14)', '[dim]—[/dim]', f"[dim]{rsi_result['error']}[/dim]")

    # ATR
    if 'error' not in atr_result:
        val_str = f"ATR ${atr_result['atr']:.2f}   Stop dist ${atr_result['stop_distance']:.2f}"
        tbl.add_row('ATR (14)', val_str, '[dim]Risk tool[/dim]')
    else:
        tbl.add_row('ATR (14)', '[dim]—[/dim]', f"[dim]{atr_result['error']}[/dim]")

    # SPY
    if 'error' not in market_result:
        spy_reading = f"MARKET {market_result['trend']}"
        val_str     = (f"${market_result['spy_price']:.2f}  "
                       f"EMA {market_result['ema_fast']} / {market_result['ema_slow']}")
        reading     = Text(spy_reading, style=_trend_color(spy_reading))
        tbl.add_row('SPY', val_str, reading)
    else:
        tbl.add_row('SPY', '[dim]—[/dim]', f"[dim]{market_result['error']}[/dim]")

    # Volume conviction
    if 'error' not in vol_context_result:
        s_m        = vol_context_result['session_vol']  / 1_000_000
        e_m        = vol_context_result['expected_vol'] / 1_000_000
        vol_label  = f"{vol_context_result['status']} VOLUME"
        val_str    = f"{s_m:.1f}M vs {e_m:.1f}M expected"
        reading    = Text(vol_label, style=_trend_color(vol_context_result['status']))
        tbl.add_row('Volume', val_str, reading)
    else:
        tbl.add_row('Volume', '[dim]—[/dim]', f"[dim]{vol_context_result['error']}[/dim]")

    # Gap
    if 'error' not in gap_result:
        direction  = gap_result['direction']
        sign       = '+' if gap_result['gap_pct'] >= 0 else ''
        dir_word   = {'UP': 'up', 'DOWN': 'down', 'NONE': '—'}[direction]
        val_str    = f"{sign}{gap_result['gap_pct'] * 100:.2f}% gap {dir_word}"
        gap_read   = _gap_reading(direction, signal_result['signal'])
        reading    = Text(gap_read, style=_trend_color(gap_read))
        tbl.add_row('Gap', val_str, reading)
    else:
        tbl.add_row('Gap', '[dim]—[/dim]', f"[dim]{gap_result['error']}[/dim]")

    console.print(tbl)

    # ── Signal Banner ──────────────────────────────────────────────────────────
    sig   = signal_result['signal']
    score = signal_result['score']
    color, label = _signal_style(sig)

    console.print(
        Panel(
            f"[bold {color}]{label}[/bold {color}]"
            f"    [dim]Score: {score:+.2f} / 4.00  "
            f"({signal_result['active_count']} indicators active)[/dim]",
            border_style=color,
            padding=(0, 2),
        )
    )

    # ── Position Sizing ────────────────────────────────────────────────────────
    sz = signal_result['sizing']
    if sig != 'HOLD':
        sizing_text = (
            f"  Risk: [yellow]${sz['risk_amount']:.2f}[/yellow]"
            f"  │  Shares: [cyan]{sz['shares']}[/cyan]"
            f"  │  Entry: [white]${current_price:.2f}[/white]"
            f"  │  Stop: [red]${sz['stop_price']:.2f}[/red]"
            f"  │  Target: [green]${sz['target_price']:.2f}[/green]"
            f"  │  RRR: [dim]{RRR:.0f}:1[/dim]"
        )
    else:
        sizing_text = (
            f"  [dim]No position sizing — signal does not meet threshold.[/dim]"
            f"  Max risk if trading: [yellow]${sz['risk_amount']:.2f}[/yellow]"
        )

    console.print(Panel(sizing_text, border_style='dim', padding=(0, 1)))

    # ── Warnings ───────────────────────────────────────────────────────────────
    if signal_result['warnings']:
        for w in signal_result['warnings']:
            console.print(f"  [dim yellow]⚠  {w}[/dim yellow]")

    console.print()


def print_startup_banner(connected: bool, host: str, port: int) -> None:
    if connected:
        console.print(Panel(
            f"[green bold]✓ Connected to TWS[/green bold]  [dim]{host}:{port}[/dim]\n"
            f"[dim]Paper trading mode  ·  Type a ticker to start a 60-min session  ·  'quit' to exit[/dim]",
            border_style='green',
        ))
    else:
        console.print(Panel(
            "[red bold]✗ Not connected[/red bold]",
            border_style='red',
        ))


def print_error(message: str) -> None:
    console.print(f"[red]  Error: {message}[/red]\n")
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
python -c "from display import render_output, print_startup_banner, print_error; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full test suite — no regressions**

```bash
python -m pytest tests/ -v
```
Expected: all tests `PASSED`

- [ ] **Step 4: Commit**

```bash
git add display.py
git commit -m "feat: update display with new indicator rows, session timer, and BUY/SELL/HOLD labels"
```

---

## Task 9: Rewrite main.py with watch_symbol

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace the entire `main.py` with the streaming version**

```python
import sys
import time
import pandas as pd
from rich.console import Console
from ib_insync import IB, Stock, util

from config import (
    TWS_HOST, TWS_PORT, BAR_SIZE, DATA_DURATION,
    HTF_BAR_SIZE, SESSION_DURATION, MARKET_SYMBOL,
)
from data_fetcher import connect_tws, get_daily_context
from indicator import (
    calc_ema_signal, calc_vwap, calc_volume_profile,
    calc_rsi, calc_atr,
    calc_htf_trend, calc_market_context, calc_volume_context, calc_gap,
)
from signal_engine import generate_signal
from display import render_output, print_startup_banner, print_error, console


def _to_df(bar_list) -> pd.DataFrame:
    """Convert a ib_insync BarDataList to a clean OHLCV DataFrame."""
    if not bar_list:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    df = util.df(bar_list)[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close']).reset_index(drop=True)
    return df


def watch_symbol(ib: IB, symbol: str, duration: int = SESSION_DURATION) -> None:
    """
    Subscribe to live 5-min bars for symbol + SPY and a 15-min bar stream.
    Recomputes all indicators and redraws the terminal on every 5-min bar close.
    Runs for `duration` seconds then cancels all subscriptions.
    """
    contract     = Stock(symbol.upper(), 'SMART', 'USD')
    spy_contract = Stock(MARKET_SYMBOL,  'SMART', 'USD')
    ib.qualifyContracts(contract, spy_contract)

    # ── Fetch daily context (avg volume + yesterday's close) ───────────────────
    try:
        avg_daily_vol, prev_close = get_daily_context(ib, symbol)
    except ValueError as e:
        print_error(str(e))
        avg_daily_vol, prev_close = 0.0, 0.0

    # ── Subscribe to live bar streams ──────────────────────────────────────────
    common = dict(endDateTime='', durationStr=DATA_DURATION,
                  whatToShow='TRADES', useRTH=True, formatDate=1, keepUpToDate=True)

    bars_5m  = ib.reqHistoricalData(contract,     barSizeSetting=BAR_SIZE,     **common)
    bars_15m = ib.reqHistoricalData(contract,     barSizeSetting=HTF_BAR_SIZE, **common)
    spy_bars = ib.reqHistoricalData(spy_contract, barSizeSetting=BAR_SIZE,     **common)
    ib.sleep(2)   # Allow initial bars to load before first render

    start_time = time.monotonic()

    def _render():
        elapsed           = int(time.monotonic() - start_time)
        seconds_remaining = max(0, duration - elapsed)

        df_5m  = _to_df(bars_5m)
        df_15m = _to_df(bars_15m)
        df_spy = _to_df(spy_bars)

        if df_5m.empty:
            return

        price = float(df_5m['close'].iloc[-1])

        ema_res     = calc_ema_signal(df_5m)
        vwap_res    = calc_vwap(df_5m, price)
        vp_res      = calc_volume_profile(df_5m, price)
        rsi_res     = calc_rsi(df_5m)
        atr_res     = calc_atr(df_5m)
        htf_res     = calc_htf_trend(df_15m)
        market_res  = calc_market_context(df_spy)
        vol_ctx_res = calc_volume_context(df_5m, avg_daily_vol)
        gap_res     = calc_gap(df_5m, prev_close)

        sig_res = generate_signal(
            ema_res, vwap_res, vp_res, rsi_res, atr_res,
            current_price      = price,
            htf_result         = htf_res,
            market_result      = market_res,
            vol_context_result = vol_ctx_res,
            gap_result         = gap_res,
        )

        console.clear()
        render_output(
            symbol, price, seconds_remaining,
            ema_res, vwap_res, vp_res, rsi_res, atr_res,
            htf_res, market_res, vol_ctx_res, gap_res,
            sig_res,
        )

    # ── Initial render ─────────────────────────────────────────────────────────
    _render()

    # ── Bar-close callback ─────────────────────────────────────────────────────
    def on_bar_update(bars, has_new_bar):
        if not has_new_bar:
            return
        if time.monotonic() - start_time >= duration:
            return
        _render()

    bars_5m.updateEvent += on_bar_update

    # ── Heartbeat loop — runs until session expires ────────────────────────────
    while time.monotonic() - start_time < duration:
        ib.sleep(1)

    # ── Cleanup ────────────────────────────────────────────────────────────────
    bars_5m.updateEvent -= on_bar_update
    ib.cancelHistoricalData(bars_5m)
    ib.cancelHistoricalData(bars_15m)
    ib.cancelHistoricalData(spy_bars)
    console.print('[dim]Session complete — returning to ticker prompt.[/dim]\n')


def main():
    # ── Connect ────────────────────────────────────────────────────────────────
    try:
        ib = connect_tws()
        print_startup_banner(connected=True, host=TWS_HOST, port=TWS_PORT)
    except ConnectionError as e:
        print(str(e))
        sys.exit(1)

    # ── Main Loop ──────────────────────────────────────────────────────────────
    try:
        while True:
            try:
                raw = input('  Ticker › ').strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue
            if raw.lower() in {'quit', 'exit', 'q'}:
                break

            symbol = raw.upper()

            try:
                watch_symbol(ib, symbol)
            except ValueError as e:
                print_error(str(e))
            except Exception as e:
                print_error(f"Unexpected error for {symbol}: {e}")

    finally:
        console.print('[dim]Disconnecting from TWS...[/dim]')
        ib.disconnect()
        console.print('[dim]Done.[/dim]')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
python -c "import main; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run full test suite — no regressions**

```bash
python -m pytest tests/ -v
```
Expected: all tests `PASSED`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: rewrite main with watch_symbol live bar streaming and 60-min session"
```

---

## Self-Review Checklist

- [x] **Config** — 5 constants added, all used downstream
- [x] **data_fetcher** — `get_bars` bar_size param; `get_daily_context` returns `(avg_vol, prev_close)`
- [x] **indicator** — 4 new pure functions; `GAP_THRESHOLD` imported from config
- [x] **signal_engine** — all 4 new indicators scored; `HOLD` replaces `NO TRADE`; `BUY`/`SELL` replace `STRONG LONG`/`STRONG SHORT`; `if signal != 'HOLD'` check is correct
- [x] **display** — `seconds_remaining` param; 4 new rows; timer in header; opening range note; `_gap_reading` helper; `if sig != 'HOLD'` updated; `RRR` imported
- [x] **main** — `watch_symbol` uses `keepUpToDate=True`; cleanup cancels all 3 streams; `_to_df` helper used consistently; `get_current_price` no longer called (price from bar stream)
- [x] **Types consistent** — `htf_result`, `market_result`, `vol_context_result`, `gap_result` named identically across signal_engine, display, and main
- [x] **No placeholders** — all code blocks are complete
