# ── IBKR Connection ────────────────────────────────────────────────────────────
TWS_HOST   = '127.0.0.1'
TWS_PORT   = 7497   # 7497 = paper trading TWS. 7496 = live TWS. 4002 = paper IB Gateway.
CLIENT_ID  = 1

# ── Account & Risk ─────────────────────────────────────────────────────────────
ACCOUNT_SIZE  = 10000   # USD — update this to your actual paper account size
RISK_PERCENT  = 0.01    # 1% of account risked per trade

# ── Indicator Parameters ───────────────────────────────────────────────────────
EMA_FAST             = 9
EMA_SLOW             = 20
RSI_PERIOD           = 14
ATR_PERIOD           = 14
ATR_STOP_MULTIPLIER  = 1.5   # Stop placed 1.5× ATR from entry
RRR                  = 2.0   # Risk-reward ratio used to calculate target

# ── Data ───────────────────────────────────────────────────────────────────────
BAR_SIZE       = '5 mins'
DATA_DURATION  = '1 D'
VP_BIN_COUNT   = 50          # Number of price buckets for Volume Profile

# ── Session & Streaming ────────────────────────────────────────────────────────
HTF_BAR_SIZE      = '15 mins'
SESSION_DURATION  = 3600        # seconds — auto-stop after 60 min

# ── Market Context ─────────────────────────────────────────────────────────────
MARKET_SYMBOL     = 'SPY'
AVG_VOL_LOOKBACK  = '1 M'       # daily bars lookback for average volume
GAP_THRESHOLD     = 0.005       # 0.5% — minimum gap size to score
