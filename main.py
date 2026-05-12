import sys
from rich.console import Console

from config        import TWS_HOST, TWS_PORT
from data_fetcher  import connect_tws, get_bars, get_current_price
from indicator    import (
    calc_ema_signal, calc_vwap, calc_volume_profile,
    calc_rsi, calc_atr,
)
from signal_engine import generate_signal
from display       import (
    render_output, print_startup_banner, print_error, console
)

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
                raw = input("  Ticker › ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue

            if raw.lower() in {'quit', 'exit', 'q'}:
                break

            symbol = raw.upper()

            try:
                # 1. Fetch data
                bars = get_bars(ib, symbol)
                price = get_current_price(ib, symbol, bars)

                # 2. Calculate indicators
                ema_res  = calc_ema_signal(bars)
                vwap_res = calc_vwap(bars, price)
                vp_res   = calc_volume_profile(bars, price)
                rsi_res  = calc_rsi(bars)
                atr_res  = calc_atr(bars)

                # 3. Generate signal
                sig_res  = generate_signal(
                    ema_res, vwap_res, vp_res, rsi_res, atr_res, price
                )

                # 4. Display
                render_output(
                    symbol, price,
                    ema_res, vwap_res, vp_res, rsi_res, atr_res,
                    sig_res,
                )

            except ValueError as e:
                print_error(str(e))
            except Exception as e:
                print_error(f"Unexpected error for {symbol}: {e}")

    finally:
        console.print("[dim]Disconnecting from TWS...[/dim]")
        ib.disconnect()
        console.print("[dim]Done.[/dim]")


if __name__ == '__main__':
    main()

    