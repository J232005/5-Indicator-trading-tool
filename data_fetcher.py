import sys
import numpy as np
import pandas as pd
from ib_insync import IB, Stock, util
from config import TWS_HOST, TWS_PORT, CLIENT_ID, BAR_SIZE, DATA_DURATION

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


def get_bars(ib: IB, symbol: str) -> pd.DataFrame:
    """
    Fetch today's intraday 5-min bars for the given symbol from TWS.
    Returns a DataFrame with columns: date, open, high, low, close, volume.
    Raises ValueError if no data is returned.
    """
    contract = Stock(symbol.upper(), 'SMART', 'USD')
    ib.qualifyContracts(contract)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=DATA_DURATION,
        barSizeSetting=BAR_SIZE,
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
    )
    ib.sleep(1)  # Allow event loop to process the response

    if not bars:
        raise ValueError(
            f"No data returned for '{symbol.upper()}'.\n"
            f"Possible reasons: invalid ticker, market is closed, or TWS data subscription issue."
        )

    df = util.df(bars)[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
    df = df.reset_index(drop=True)

    # Ensure numeric types
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
