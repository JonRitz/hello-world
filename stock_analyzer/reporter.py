from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

_CATEGORY_COLORS = {
    "LONG": "bold green",
    "INCOME": "bold blue",
    "OPTIONS PLAY": "bold yellow",
    "AVOID": "bold red",
    "SHORT": "bold red",
}

_TREND_EMOJI = {
    "strong_uptrend": "↑↑",
    "uptrend": "↑",
    "sideways": "→",
    "downtrend": "↓",
    "strong_downtrend": "↓↓",
}

_SIGNAL_COLORS = {
    "bullish": "green",
    "strong_bullish": "bright_green",
    "bearish": "red",
    "strong_bearish": "bright_red",
    "neutral": "yellow",
    "undervalued": "green",
    "overvalued": "red",
    "fairly_valued": "yellow",
    "unknown": "dim",
}


def print_report(report_text: str | None, ranked: list, elapsed: float) -> None:
    today = date.today().strftime("%B %d, %Y")
    console.print()
    console.print(
        Panel(
            f"[bold white]MARKET SCANNER[/bold white]  •  [dim]{today}[/dim]",
            style="bold blue",
            box=box.DOUBLE,
        )
    )
    console.print()

    if report_text:
        console.print(report_text)
        console.print()

    # Summary table for top 10
    table = Table(
        title="[bold]Top 10 Candidates — Quantitative Summary[/bold]",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("Ticker", style="bold white", width=8)
    table.add_column("Name", width=22, no_wrap=True)
    table.add_column("Price", justify="right", width=8)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Valuation", width=12)
    table.add_column("P/E", justify="right", width=7)
    table.add_column("Div%", justify="right", width=6)
    table.add_column("RSI", justify="right", width=6)
    table.add_column("Trend", width=12)
    table.add_column("Options", width=14)
    table.add_column("Sector", width=16, no_wrap=True)

    for ticker, score, data in ranked[:10]:
        val = data["valuation"]
        tech = data["technical"]
        opts = data["options"]

        price_str = f"${tech['current_price']:.2f}" if tech.get("current_price") else "—"
        pe_str = f"{val['pe_ratio']:.1f}" if val.get("pe_ratio") else "—"
        div_str = f"{val['dividend_yield']:.1f}%" if val.get("dividend_yield") else "—"
        rsi_val = tech.get("rsi", 50)
        rsi_color = "green" if rsi_val < 40 else ("red" if rsi_val > 70 else "yellow")
        trend = tech.get("trend", "sideways")
        trend_sym = _TREND_EMOJI.get(trend, "→")
        trend_label = trend.replace("_", " ").title()
        opts_sig = opts.get("options_signal", "neutral")
        opts_color = _SIGNAL_COLORS.get(opts_sig, "yellow")
        val_sig = val.get("valuation_signal", "unknown")
        val_color = _SIGNAL_COLORS.get(val_sig, "dim")
        smart = " ★" if opts.get("smart_money_alert") else ""

        table.add_row(
            ticker,
            (val.get("name") or "")[:22],
            price_str,
            f"{score:.1f}",
            Text(val_sig.replace("_", " ").title(), style=val_color),
            pe_str,
            div_str,
            Text(f"{rsi_val:.0f}", style=rsi_color),
            f"{trend_sym} {trend_label}",
            Text(opts_sig.replace("_", " ").title() + smart, style=opts_color),
            (val.get("sector") or "")[:16],
        )

    console.print(table)
    console.print()
    console.print(
        f"[dim]Scanned {len(ranked)} candidates  •  Runtime: {elapsed:.0f}s  •  ★ = smart money alert[/dim]"
    )
    console.print()
