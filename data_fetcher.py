import sys
import numpy as np
import pandas as pd
from ib_insync import IB, Stock, util
from config import TWS_HOST, TWS_PORT, CLIENT_ID, BAR_SIZE, DATA_DURATION, AVG_VOL_LOOKBACK

# Fix Windows asyncio event loop policy (required for Python 3.10+ on Windows)
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def connect_tws() -> IB:
    """
    Connect to TWS. Returns a connected IB instance.
    Prints a clear error and raises ConnectionError if connection fails.
    """
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID)
        return ib
    except Exception:
        raise ConnectionError(
            f"\n[CONNECTION FAILED]\n"
            f"Could not connect to TWS on {TWS_HOST}:{TWS_PORT}.\n\n"
            f"Checklist:\n"
            f"  1. TWS is open and you are logged into your PAPER TRADING account.\n"
            f"  2. In TWS: Edit > Global Configuration > API > Settings\n"
            f"       - 'Enable ActiveX and Socket Clients' is CHECKED\n"
            f"       - Socket Port is set to {TWS_PORT}\n"
            f"       - 'Read-Only API' is UNCHECKED\n"
            f"  3. Restart TWS after changing API settings.\n"
        )


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


def get_current_price(ib: IB, symbol: str, bars_df: pd.DataFrame) -> float:
    """
    Fetch the latest traded price for the symbol.
    Falls back to the last bar's close if live price is unavailable.
    """
    contract = Stock(symbol.upper(), 'SMART', 'USD')
    ib.qualifyContracts(contract)

    ticker = ib.reqMktData(contract, '', False, False)
    ib.sleep(2)  # Wait for market data snapshot

    price = ticker.last
    if price is None or (isinstance(price, float) and np.isnan(price)):
        price = ticker.close
    if price is None or (isinstance(price, float) and np.isnan(price)):
        price = float(bars_df['close'].iloc[-1])

    ib.cancelMktData(contract)
    return float(price)


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
