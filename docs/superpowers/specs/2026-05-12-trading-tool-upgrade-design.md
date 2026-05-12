# Trading Tool Upgrade — Design Spec
**Date:** 2026-05-12
**Status:** Approved

---

## Goal

Upgrade the 5-indicator IBKR day trading tool from a manual snapshot model to a live auto-refreshing signal tool that gives the user a clear BUY / SELL / HOLD verdict on a single ticker, updated every 5-min bar close, for a 60-minute session.

---

## New Features

1. **Auto-refresh via `keepUpToDate=True`** — live bar streaming from IBKR, recomputes on every 5-min bar close
2. **15-min higher timeframe EMA** — confirms or opposes the 5-min signal
3. **SPY market context** — broad market direction affects the score
4. **Volume conviction** — compares session volume to 20-day average, normalized by elapsed day fraction
5. **Gap detection** — overnight gap direction relative to the signal
6. **60-minute session timer** — auto-stops streaming after 1 hour, returns to `Ticker ›` prompt
7. **Renamed signals** — BUY / WEAK BUY / HOLD / WEAK SELL / SELL (same thresholds, clearer language)

---

## Indicators & Scoring

### Existing (unchanged logic)

| Indicator | Max contribution | Notes |
|-----------|-----------------|-------|
| EMA 9/20 (5m) | ±2.0 | Trend ±1.0 + crossover bonus ±1.0 |
| VWAP | ±1.0 | Price above/below |
| Volume Profile | ±0.5 | Zone relative to value area |
| RSI (14) | ±1.0 | Condition bucket |
| ATR (14) | n/a | Position sizing only, not scored |

### New

| Indicator | Max contribution | Scoring rule |
|-----------|-----------------|--------------|
| EMA 9/20 (15m) | ±1.5 | BULLISH +1.5, BEARISH -1.5 |
| SPY EMA (5m) | ±1.0 | BULLISH +1.0, BEARISH -1.0 |
| Volume conviction | ±0.5 | >1.3× expected +0.5, <0.7× expected -0.5, else 0 |
| Gap detection | ±0.5 | Gap >0.5% in signal direction +0.5, against -0.5, else 0 |

Volume expected = `avg_daily_vol × (len(df_5m) * 5 / 390)` — number of 5-min bars elapsed × 5 minutes, divided by 390 (full trading day in minutes).

Gap = `(today_open - prev_close) / prev_close` where `today_open = df_5m.iloc[0]['open']` and `prev_close` comes from the daily bars (second-to-last bar's close). Significant if `abs(gap) > GAP_THRESHOLD (0.005)`.
Gap "in direction" means gap up when score ≥ 0, gap down when score < 0 (evaluated after all other indicators).

Normalization: `normalised = (score / max_score) * 4.0` — existing formula, handles expanded range automatically.

### Signal thresholds (unchanged)

| Normalised score | Signal |
|-----------------|--------|
| ≥ 3.0 | BUY |
| ≥ 1.5 | WEAK BUY |
| > -1.5 and < 1.5 | HOLD |
| ≤ -1.5 | WEAK SELL |
| ≤ -3.0 | SELL |

---

## File Changes

### `config.py`
Add:
```python
HTF_BAR_SIZE      = '15 mins'
SESSION_DURATION  = 3600        # seconds
MARKET_SYMBOL     = 'SPY'
AVG_VOL_LOOKBACK  = '1 M'       # 1 month of daily bars for avg volume
GAP_THRESHOLD     = 0.005       # 0.5% minimum gap to be considered significant
```

### `data_fetcher.py`
- `get_bars(ib, symbol, bar_size=BAR_SIZE)` — add `bar_size` parameter, default unchanged
- `get_daily_context(ib, symbol) -> tuple[float, float]` — fetches `AVG_VOL_LOOKBACK` of daily bars, returns `(avg_daily_vol, prev_close)` where `prev_close` is the second-to-last bar's close (yesterday's close)

### `indicator.py`
Four new functions:

- `calc_htf_trend(df_15m) -> dict` — EMA 9/20 on 15-min bars, returns `{'trend', 'ema_fast', 'ema_slow'}` or `{'error'}`
- `calc_market_context(spy_df) -> dict` — EMA 9/20 on SPY 5-min bars, returns `{'trend', 'spy_price', 'ema_fast', 'ema_slow'}` or `{'error'}`
- `calc_volume_context(df, avg_daily_vol) -> dict` — `elapsed = len(df) * 5`, `expected = avg_daily_vol * (elapsed / 390)`, returns `{'status', 'session_vol', 'expected_vol'}` where status is `HIGH`, `LOW`, or `NORMAL`
- `calc_gap(df, prev_close) -> dict` — `gap_pct = (df.iloc[0]['open'] - prev_close) / prev_close`, returns `{'gap_pct', 'direction'}` where direction is `UP`, `DOWN`, or `NONE`

### `signal_engine.py`
- `generate_signal()` accepts four new keyword args: `htf_result`, `market_result`, `vol_context_result`, `gap_result`
- Scoring added for each per table above
- Signal label map updated: `STRONG LONG→BUY`, `LONG BIAS→WEAK BUY`, `NO TRADE→HOLD`, `SHORT BIAS→WEAK SELL`, `STRONG SHORT→SELL`

### `display.py`
- `render_output()` accepts four new result dicts
- Four new rows added to indicator table below ATR: SPY, Volume, Gap, 15-min Trend (placed second row, below 5-min EMA)
- Header gains session countdown: `·  Session: MM:SS remaining`
- Subtle opening range note: if current ET time is before 10:00, print `[dim yellow]⚠  Opening range — first 30 min[/dim yellow]` above the table
- `_trend_color()` updated for new value strings: `HIGH` → green, `LOW` → red, `MARKET BULLISH` → green, `MARKET BEARISH` → red

### `main.py`
Full restructure of the main loop:

```
main()
  └─ connect_tws()
  └─ prompt loop
       └─ user types ticker
       └─ watch_symbol(ib, symbol, duration=SESSION_DURATION)
            ├─ get_daily_context(ib, symbol)  → (avg_daily_vol, prev_close)
            ├─ reqHistoricalData(ticker 5m,  keepUpToDate=True)  → bars_5m
            ├─ reqHistoricalData(ticker 15m, keepUpToDate=True)  → bars_15m
            ├─ reqHistoricalData(SPY 5m,     keepUpToDate=True)  → spy_bars
            ├─ initial render (don't wait for first bar update)
            ├─ bars_5m.updateEvent += on_bar_update
            └─ ib.sleep(1) heartbeat until SESSION_DURATION elapsed
                 └─ on_bar_update(bars, has_new_bar):
                      if not has_new_bar: return
                      if session expired: return
                      compute all 9 indicators from bars_5m, bars_15m, spy_bars
                      console.clear()
                      render_output(...)
            └─ cancelHistoricalData for all three streams
            └─ print "Session complete"
       └─ return to prompt
```

`on_bar_update` reads the current state of `bars_15m` and `spy_bars` directly (they update silently in the background via their own `keepUpToDate` subscriptions) — no separate callbacks needed for them.

---

## Display Layout

```
─── AAPL · $213.47 · 2026-05-12  10:32 ET · Session: 47:23 remaining ───

 Indicator        Value                               Reading
 ────────────────────────────────────────────────────────────────────
 EMA 9/20 (5m)    213.12 / 211.84                    BULLISH
 EMA 9/20 (15m)   212.90 / 210.50                    BULLISH
 VWAP             $212.33  (+0.54%)                   ABOVE VWAP
 Vol Profile      POC $211.90  VAH $214.20  VAL...    IN VALUE AREA
 RSI (14)         RSI  58.4                           BULLISH RANGE
 ATR (14)         ATR $1.24   Stop dist $1.86         Risk tool
 SPY              $524.10  EMA 523.80 / 521.40        MARKET BULLISH
 Volume           2.1M vs 1.6M expected               HIGH VOLUME
 Gap              +0.82% gap up                       CONFIRMS LONG

╔═══════════════════════════════════════════════════════════╗
║  ▲▲  BUY  ▲▲    Score: +3.41 / 4.00  (9 indicators)    ║
╚═══════════════════════════════════════════════════════════╝

  Risk: $100.00 │ Shares: 53 │ Entry: $213.47 │ Stop: $211.61 │ Target: $217.19 │ RRR: 2:1
```

---

## Out of Scope

- Order execution (manual entry in TWS)
- Multiple simultaneous tickers
- QQQ context (can be added later)
- Backtesting
- Pre-market / after-hours data
