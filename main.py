import sys
import time
import pandas as pd
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

    try:
        avg_daily_vol, prev_close = get_daily_context(ib, symbol)
    except ValueError as e:
        print_error(str(e))
        avg_daily_vol, prev_close = 0.0, 0.0

    common = dict(endDateTime='', durationStr=DATA_DURATION,
                  whatToShow='TRADES', useRTH=True, formatDate=1, keepUpToDate=True)

    bars_5m  = ib.reqHistoricalData(contract,     barSizeSetting=BAR_SIZE,     **common)
    bars_15m = ib.reqHistoricalData(contract,     barSizeSetting=HTF_BAR_SIZE, **common)
    spy_bars = ib.reqHistoricalData(spy_contract, barSizeSetting=BAR_SIZE,     **common)
    ib.sleep(2)

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

    _render()

    def on_bar_update(_bars, has_new_bar):
        if not has_new_bar:
            return
        if time.monotonic() - start_time >= duration:
            return
        _render()

    bars_5m.updateEvent += on_bar_update

    while time.monotonic() - start_time < duration:
        ib.sleep(1)

    bars_5m.updateEvent -= on_bar_update
    ib.cancelHistoricalData(bars_5m)
    ib.cancelHistoricalData(bars_15m)
    ib.cancelHistoricalData(spy_bars)
    console.print('[dim]Session complete — returning to ticker prompt.[/dim]\n')


def main():
    try:
        ib = connect_tws()
        print_startup_banner(connected=True, host=TWS_HOST, port=TWS_PORT)
    except ConnectionError as e:
        print(str(e))
        sys.exit(1)

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
