# 5-Indicator-trading-tool
Institutional-style intraday trading engine using Market Structure, VWAP, Volume Profile, RSI, and ATR to generate directional bias, key liquidity levels, and risk-adjusted position sizing. Built in Python with Interactive Brokers integration via ib_insync.

# IBKR Day Trading Signal Tool

Real-time terminal signal tool for day trading. Connects to Interactive Brokers TWS
and analyses 5 technical indicators per ticker.

## Indicators
| # | Indicator       | Role                                      |
|---|-----------------|-------------------------------------------|
| 1 | EMA 9 / 20      | Trend direction and crossover detection   |
| 2 | VWAP            | Institutional intraday price benchmark    |
| 3 | Volume Profile  | Key price levels: POC, VAH, VAL           |
| 4 | RSI (14)        | Momentum — entry timing filter            |
| 5 | ATR (14)        | Stop placement and position sizing        |

## Signals
- **STRONG LONG / SHORT** — 4+ indicators aligned
- **LONG / SHORT BIAS** — majority aligned
- **NO TRADE** — mixed or insufficient signal

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure your account
Edit `config.py`:
- Set `ACCOUNT_SIZE` to your paper trading account balance
- Leave `TWS_PORT = 7497` for paper trading

### 3. Configure TWS API
In TWS:
1. Edit → Global Configuration → API → Settings
2. Check **Enable ActiveX and Socket Clients**
3. Set **Socket Port** to `7497`
4. Uncheck **Read-Only API**
5. Restart TWS after saving

### 4. Run
```bash
python main.py
```

Then type any US stock ticker (e.g. `AAPL`, `NVDA`, `TSLA`) and press Enter.
Type `quit` to exit.

## Notes
- Markets must be open for live price data. Historical bars are available after hours
  but prices will reflect the last close.
- Market structure analysis is intentionally left to the user — review your chart
  alongside every signal before acting.
- This tool is for paper trading and educational use.
