from datetime import datetime
import pytz
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich         import box

from config import RRR

console = Console()

ET = pytz.timezone('America/New_York')


def _trend_color(value: str) -> str:
    bullish = {
        'BULLISH', 'ABOVE', 'GOLDEN CROSS', 'BULLISH_RANGE',
        'BELOW_VALUE_AREA', 'BUY', 'WEAK BUY',
        'HIGH', 'MARKET BULLISH', 'CONFIRMS LONG', 'AGAINST SHORT', 'GAP UP',
    }
    bearish = {
        'BEARISH', 'BELOW', 'DEATH CROSS', 'BEARISH_RANGE',
        'ABOVE_VALUE_AREA', 'SELL', 'WEAK SELL',
        'LOW', 'MARKET BEARISH', 'CONFIRMS SHORT', 'AGAINST LONG', 'GAP DOWN',
    }
    if value in bullish:
        return 'green'
    if value in bearish:
        return 'red'
    return 'yellow'


def _signal_style(signal: str):
    styles = {
        'BUY':       ('bright_green', '▲▲  BUY        ▲▲'),
        'WEAK BUY':  ('green',        '▲   WEAK BUY    ▲'),
        'HOLD':      ('dim white',    '—   HOLD         —'),
        'WEAK SELL': ('red',          '▼   WEAK SELL   ▼'),
        'SELL':      ('bright_red',   '▼▼  SELL       ▼▼'),
    }
    return styles.get(signal, ('yellow', signal))


def _gap_reading(direction: str, signal: str) -> str:
    if direction == 'NONE':
        return 'NO SIGNIFICANT GAP'
    long_signals  = {'BUY', 'WEAK BUY'}
    short_signals = {'SELL', 'WEAK SELL'}
    if signal in long_signals:
        return 'CONFIRMS LONG'  if direction == 'UP'   else 'AGAINST LONG'
    if signal in short_signals:
        return 'CONFIRMS SHORT' if direction == 'DOWN' else 'AGAINST SHORT'
    return 'GAP UP' if direction == 'UP' else 'GAP DOWN'


def render_output(
    symbol:             str,
    current_price:      float,
    seconds_remaining:  int,
    ema_result:         dict,
    vwap_result:        dict,
    vp_result:          dict,
    rsi_result:         dict,
    atr_result:         dict,
    htf_result:         dict,
    market_result:      dict,
    vol_context_result: dict,
    gap_result:         dict,
    signal_result:      dict,
) -> None:
    """Render the full analysis panel to the terminal."""

    now_et = datetime.now(ET)
    time_str  = now_et.strftime('%Y-%m-%d  %H:%M ET')
    mins, secs = divmod(seconds_remaining, 60)
    timer_str = f'{mins:02d}:{secs:02d}'

    # ── Opening range warning ──────────────────────────────────────────────────
    if now_et.hour < 10:
        console.print('[dim yellow]⚠  Opening range — first 30 min[/dim yellow]')

    # ── Header ─────────────────────────────────────────────────────────────────
    console.print()
    console.rule(
        f"[bold cyan]{symbol.upper()}[/bold cyan]  ·  "
        f"[white]${current_price:.2f}[/white]  ·  [dim]{time_str}[/dim]  ·  "
        f"[dim]Session: {timer_str} remaining[/dim]"
    )

    # ── Indicator Table ────────────────────────────────────────────────────────
    tbl = Table(box=box.SIMPLE_HEAD, show_header=True, header_style='bold dim')
    tbl.add_column('Indicator',  style='bold',    width=18)
    tbl.add_column('Value',      justify='right', width=32)
    tbl.add_column('Reading',    justify='left',  width=22)

    # EMA 5m
    if 'error' not in ema_result:
        val_str = f"EMA{ema_result['ema_fast']} / EMA{ema_result['ema_slow']}"
        cross   = f"  [{_trend_color(ema_result.get('crossover',''))}]{ema_result.get('crossover','') or ''}[/]"
        reading = Text(ema_result['trend'], style=_trend_color(ema_result['trend']))
        tbl.add_row('EMA 9/20 (5m)', val_str + cross, reading)
    else:
        tbl.add_row('EMA 9/20 (5m)', '[dim]—[/dim]', f"[dim]{ema_result['error']}[/dim]")

    # EMA 15m
    if 'error' not in htf_result:
        val_str = f"EMA{htf_result['ema_fast']} / EMA{htf_result['ema_slow']}"
        reading = Text(htf_result['trend'], style=_trend_color(htf_result['trend']))
        tbl.add_row('EMA 9/20 (15m)', val_str, reading)
    else:
        tbl.add_row('EMA 9/20 (15m)', '[dim]—[/dim]', f"[dim]{htf_result['error']}[/dim]")

    # VWAP
    if 'error' not in vwap_result:
        dist_sign = '+' if vwap_result['distance_pct'] >= 0 else ''
        val_str   = f"${vwap_result['vwap']:.2f}  ({dist_sign}{vwap_result['distance_pct']}%)"
        reading   = Text(vwap_result['price_vs_vwap'] + ' VWAP',
                         style=_trend_color(vwap_result['price_vs_vwap']))
        tbl.add_row('VWAP', val_str, reading)
    else:
        tbl.add_row('VWAP', '[dim]—[/dim]', f"[dim]{vwap_result['error']}[/dim]")

    # Volume Profile
    if 'error' not in vp_result:
        val_str      = (f"POC ${vp_result['poc']:.2f}  "
                        f"VAH ${vp_result['vah']:.2f}  "
                        f"VAL ${vp_result['val']:.2f}")
        zone_display = vp_result['zone'].replace('_', ' ')
        reading      = Text(zone_display, style=_trend_color(vp_result['zone']))
        tbl.add_row('Vol Profile', val_str, reading)
    else:
        tbl.add_row('Vol Profile', '[dim]—[/dim]', f"[dim]{vp_result['error']}[/dim]")

    # RSI
    if 'error' not in rsi_result:
        val_str = f"RSI  {rsi_result['rsi']}"
        cond    = rsi_result['condition'].replace('_', ' ')
        reading = Text(cond, style=_trend_color(rsi_result['condition']))
        tbl.add_row('RSI (14)', val_str, reading)
    else:
        tbl.add_row('RSI (14)', '[dim]—[/dim]', f"[dim]{rsi_result['error']}[/dim]")

    # ATR
    if 'error' not in atr_result:
        val_str = f"ATR ${atr_result['atr']:.2f}   Stop dist ${atr_result['stop_distance']:.2f}"
        tbl.add_row('ATR (14)', val_str, '[dim]Risk tool[/dim]')
    else:
        tbl.add_row('ATR (14)', '[dim]—[/dim]', f"[dim]{atr_result['error']}[/dim]")

    # SPY
    if 'error' not in market_result:
        spy_reading = f"MARKET {market_result['trend']}"
        val_str     = (f"${market_result['spy_price']:.2f}  "
                       f"EMA {market_result['ema_fast']} / {market_result['ema_slow']}")
        reading     = Text(spy_reading, style=_trend_color(spy_reading))
        tbl.add_row('SPY', val_str, reading)
    else:
        tbl.add_row('SPY', '[dim]—[/dim]', f"[dim]{market_result['error']}[/dim]")

    # Volume conviction
    if 'error' not in vol_context_result:
        s_m        = vol_context_result['session_vol']  / 1_000_000
        e_m        = vol_context_result['expected_vol'] / 1_000_000
        vol_label  = f"{vol_context_result['status']} VOLUME"
        val_str    = f"{s_m:.1f}M vs {e_m:.1f}M expected"
        reading    = Text(vol_label, style=_trend_color(vol_context_result['status']))
        tbl.add_row('Volume', val_str, reading)
    else:
        tbl.add_row('Volume', '[dim]—[/dim]', f"[dim]{vol_context_result['error']}[/dim]")

    # Gap
    if 'error' not in gap_result:
        direction  = gap_result['direction']
        sign       = '+' if gap_result['gap_pct'] >= 0 else ''
        dir_word   = {'UP': 'up', 'DOWN': 'down', 'NONE': '—'}[direction]
        val_str    = f"{sign}{gap_result['gap_pct'] * 100:.2f}% gap {dir_word}"
        gap_read   = _gap_reading(direction, signal_result['signal'])
        reading    = Text(gap_read, style=_trend_color(gap_read))
        tbl.add_row('Gap', val_str, reading)
    else:
        tbl.add_row('Gap', '[dim]—[/dim]', f"[dim]{gap_result['error']}[/dim]")

    console.print(tbl)

    # ── Signal Banner ──────────────────────────────────────────────────────────
    sig   = signal_result['signal']
    score = signal_result['score']
    color, label = _signal_style(sig)

    console.print(
        Panel(
            f"[bold {color}]{label}[/bold {color}]"
            f"    [dim]Score: {score:+.2f} / 4.00  "
            f"({signal_result['active_count']} indicators active)[/dim]",
            border_style=color,
            padding=(0, 2),
        )
    )

    # ── Position Sizing ────────────────────────────────────────────────────────
    sz = signal_result['sizing']
    if sig != 'HOLD':
        sizing_text = (
            f"  Risk: [yellow]${sz['risk_amount']:.2f}[/yellow]"
            f"  │  Shares: [cyan]{sz['shares']}[/cyan]"
            f"  │  Entry: [white]${current_price:.2f}[/white]"
            f"  │  Stop: [red]${sz['stop_price']:.2f}[/red]"
            f"  │  Target: [green]${sz['target_price']:.2f}[/green]"
            f"  │  RRR: [dim]{RRR:.0f}:1[/dim]"
        )
    else:
        sizing_text = (
            f"  [dim]No position sizing — signal does not meet threshold.[/dim]"
            f"  Max risk if trading: [yellow]${sz['risk_amount']:.2f}[/yellow]"
        )

    console.print(Panel(sizing_text, border_style='dim', padding=(0, 1)))

    # ── Warnings ───────────────────────────────────────────────────────────────
    if signal_result['warnings']:
        for w in signal_result['warnings']:
            console.print(f"  [dim yellow]⚠  {w}[/dim yellow]")

    console.print()


def print_startup_banner(connected: bool, host: str, port: int) -> None:
    if connected:
        console.print(Panel(
            f"[green bold]✓ Connected to TWS[/green bold]  [dim]{host}:{port}[/dim]\n"
            f"[dim]Paper trading mode  ·  Type a ticker to start a 60-min session  ·  'quit' to exit[/dim]",
            border_style='green',
        ))
    else:
        console.print(Panel(
            "[red bold]✗ Not connected[/red bold]",
            border_style='red',
        ))


def print_error(message: str) -> None:
    console.print(f"[red]  Error: {message}[/red]\n")
