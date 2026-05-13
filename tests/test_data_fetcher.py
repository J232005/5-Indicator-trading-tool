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

    closes  = [100.0] * 18 + [103.0, 105.0]
    volumes = [1_000_000] * 20

    with patch('data_fetcher.util') as mock_util:
        mock_util.df.return_value = _mock_daily_df(closes, volumes)
        avg_vol, prev_close = get_daily_context(ib, 'AAPL')

    assert avg_vol == 1_000_000.0
    assert prev_close == 103.0


def test_get_daily_context_raises_on_insufficient_bars():
    from data_fetcher import get_daily_context
    ib = MagicMock()
    ib.reqHistoricalData.return_value = ['placeholder']
    ib.sleep = MagicMock()

    with patch('data_fetcher.util') as mock_util:
        mock_util.df.return_value = _mock_daily_df([100.0], [500_000])
        try:
            get_daily_context(ib, 'AAPL')
            assert False, 'Expected ValueError'
        except ValueError:
            pass
