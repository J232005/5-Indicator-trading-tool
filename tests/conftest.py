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
