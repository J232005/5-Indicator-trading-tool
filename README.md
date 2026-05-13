# IBKR Day Trading Signal Tool

A real-time terminal signal tool for intraday day trading. Connects to Interactive Brokers TWS, analyses **9 indicators across two timeframes**, and gives you a clear **BUY / SELL / HOLD** verdict with exact position sizing — updated automatically every 5-minute bar close for a 60-minute session.

---

## What it does

Type a ticker, and the tool:

1. Connects to your Interactive Brokers paper trading account
2. Pulls live 5-min and 15-min bar data for the ticker + SPY
3. Computes 9 indicators and scores them into a single composite signal
4. Displays the result in a clean terminal panel
5. **Auto-refreshes every 5-minute bar close** for 60 minutes, then returns to the prompt

---

## The 9 Indicators

| # | Indicator | Timeframe | Role |
|---|-----------|-----------|------|
| 1 | EMA 9 / 20 | 5-min | Trend direction + crossover detection |
| 2 | EMA 9 / 20 | **15-min** | Higher-timeframe trend confirmation |
| 3 | VWAP | 5-min | Institutional intraday price benchmark |
| 4 | Volume Profile | 5-min | Key price levels: POC, VAH, VAL |
| 5 | RSI (14) | 5-min | Momentum and entry timing |
| 6 | ATR (14) | 5-min | Stop placement and position sizing |
| 7 | SPY EMA | 5-min | Broad market direction |
| 8 | Volume Conviction | Session | Session volume vs 20-day average |
| 9 | Gap Detection | Daily | Overnight gap direction vs signal |

All indicators are scored and normalised into a single **-4.0 to +4.0** score.

---

## Signals

| Signal | Score | Meaning |
|--------|-------|---------|
| ▲▲ **BUY** | ≥ +3.0 | Strong long setup — most indicators aligned |
| ▲ **WEAK BUY** | ≥ +1.5 | Bullish lean — majority aligned |
| — **HOLD** | between | Mixed or conflicting signals |
| ▼ **WEAK SELL** | ≤ −1.5 | Bearish lean |
| ▼▼ **SELL** | ≤ −3.0 | Strong short setup |

---

## Terminal Output

```
─────────────── AAPL · $213.47 · 2026-05-13  10:32 ET · Session: 47:23 remaining ───────────────

 Indicator          Value                               Reading
 ─────────────────────────────────────────────────────────────────────────────────
 EMA 9/20 (5m)      213.12 / 211.84                    BULLISH
 EMA 9/20 (15m)     212.90 / 210.50                    BULLISH
 VWAP               $212.33  (+0.54%)                  ABOVE VWAP
 Vol Profile         POC $211.90  VAH $214.20  VAL...  IN VALUE AREA
 RSI (14)           RSI  58.4                          BULLISH RANGE
 ATR (14)           ATR $1.24   Stop dist $1.86        Risk tool
 SPY                $524.10  EMA 524.0 / 522.8         MARKET BULLISH
 Volume             2.1M vs 1.6M expected              HIGH VOLUME
 Gap                +0.82% gap up                      CONFIRMS LONG

╔══════════════════════════════════════════════════════════════╗
║  ▲▲  BUY  ▲▲    Score: +3.41 / 4.00  (9 indicators active) ║
╚══════════════════════════════════════════════════════════════╝

  Risk: $100.00  │  Shares: 53  │  Entry: $213.47  │  Stop: $211.61  │  Target: $217.19  │  RRR: 2:1
```

---

## Requirements

- Python 3.10+
- An **Interactive Brokers** account (paper trading recommended)
- **Trader Workstation (TWS)** installed and running on your machine
- A market data subscription through IBKR (required for live prices)

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/J232005/5-Indicator-trading-tool.git
cd 5-Indicator-trading-tool
```

### 2. Install dependencies

```bash
pip install ib_insync pandas numpy rich pytz
```

### 3. Configure your account

Open `config.py` and set your paper account size:

```python
ACCOUNT_SIZE = 10000   # Set this to your actual paper account balance
```

Leave `TWS_PORT = 7497` for paper trading. Change to `7496` for live trading.

### 4. Enable the TWS API

In TWS:
1. **Edit → Global Configuration → API → Settings**
2. Check **Enable ActiveX and Socket Clients**
3. Set **Socket Port** to `7497`
4. Uncheck **Read-Only API**
5. Restart TWS after saving

### 5. Run

```bash
python main.py
```

---

## How to use

1. Make sure TWS is open and you are logged in to your paper trading account
2. Run `python main.py` — it will connect and show a confirmation banner
3. Type any US stock ticker and press Enter (e.g. `AAPL`, `NVDA`, `TSLA`)
4. The tool fetches data and shows the full signal panel immediately
5. It **auto-refreshes every 5-min bar close** — you don't need to do anything
6. After **60 minutes** it stops and asks for a new ticker
7. Type `quit` to exit

---

## File Structure

```
├── main.py           # Entry point — session loop and live bar streaming
├── config.py         # All parameters (account size, ports, indicator periods)
├── data_fetcher.py   # TWS connection and data retrieval
├── indicator.py      # All 9 indicator calculations (pure functions)
├── signal_engine.py  # Scoring logic and position sizing
├── display.py        # Terminal rendering with Rich
└── tests/            # Unit tests for indicators and signal engine
```

---

## Adjustable Parameters

All key settings live in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ACCOUNT_SIZE` | 10000 | Paper account size in USD |
| `RISK_PERCENT` | 0.01 | Risk per trade (1%) |
| `RRR` | 2.0 | Risk-reward ratio for target price |
| `ATR_STOP_MULTIPLIER` | 1.5 | ATR multiplier for stop distance |
| `SESSION_DURATION` | 3600 | Auto-stop after this many seconds (60 min) |
| `EMA_FAST / EMA_SLOW` | 9 / 20 | EMA periods |
| `RSI_PERIOD` | 14 | RSI lookback |
| `ATR_PERIOD` | 14 | ATR lookback |

---

## Important Notes

- **This tool is for paper trading and educational use only.** Do not risk real money based solely on any automated signal.
- Markets must be open for live price data. Historical bars work after hours but prices reflect the last close.
- Always review your chart alongside the signal. The tool scores indicators — it does not replace your own market structure analysis.
- The first 30 minutes of the trading day (9:30–10:00 ET) are volatile. The tool shows a warning during this window.
