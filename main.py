#!/usr/bin/env python3
"""
Market Scanner — Daily Stock Recommendations
Usage:
  python main.py                        # Full scan, all universes
  python main.py --quick                # S&P 500 only, faster
  python main.py --universe sp500       # Specific universe
  python main.py --sector Technology    # Filter by sector
  python main.py --no-ai                # Skip Claude synthesis
"""

import argparse
import time

from rich.console import Console

from stock_analyzer.universe import get_full_universe, get_sp500_tickers, get_nasdaq100_tickers
from stock_analyzer.screener import stage1_screen, stage2_deep_analysis, rank_final_candidates
from stock_analyzer.advisor import generate_hedge_fund_report
from stock_analyzer.reporter import print_report
from stock_analyzer.emailer import build_html_email, send_email

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily stock market scanner and recommendation engine")
    parser.add_argument("--quick", action="store_true", help="S&P 500 only, faster run")
    parser.add_argument("--universe", choices=["sp500", "nasdaq", "all"], default="all")
    parser.add_argument("--sector", type=str, default=None, help="Filter by sector (e.g. Technology)")
    parser.add_argument("--no-ai", action="store_true", help="Skip Claude AI synthesis")
    parser.add_argument("--top", type=int, default=10, help="Number of final picks (default: 10)")
    parser.add_argument("--email", action="store_true", help="Send report via email (requires GMAIL_USER + GMAIL_APP_PASSWORD)")
    args = parser.parse_args()

    start = time.time()

    console.print()
    console.print("[bold blue]Market Scanner[/bold blue]  initializing...")

    # Get universe
    if args.quick or args.universe == "sp500":
        console.print("[dim]Universe: S&P 500[/dim]")
        tickers = get_sp500_tickers()
    elif args.universe == "nasdaq":
        console.print("[dim]Universe: NASDAQ 100[/dim]")
        tickers = get_nasdaq100_tickers()
    else:
        console.print("[dim]Universe: S&P 500 + NASDAQ 100 + Russell 2000 sample[/dim]")
        tickers = get_full_universe()

    if not tickers:
        console.print("[red]Failed to fetch stock universe. Check your internet connection.[/red]")
        return

    console.print(f"[dim]Total universe: {len(tickers)} stocks[/dim]")

    # Stage 1: Fast fundamental screen
    console.print("\n[bold]Stage 1[/bold]  Fast fundamental screen...")
    candidates, info_cache = stage1_screen(tickers, top_n=50)
    console.print(f"[green]→ Narrowed to {len(candidates)} candidates[/green]")

    # Optional sector filter
    if args.sector:
        filtered = [
            t for t in candidates
            if (info_cache.get(t, {}).get("sector") or "").lower() == args.sector.lower()
        ]
        if filtered:
            candidates = filtered
            console.print(f"[dim]Sector filter '{args.sector}': {len(candidates)} candidates[/dim]")
        else:
            console.print(f"[yellow]No candidates found in sector '{args.sector}', ignoring filter[/yellow]")

    # Stage 2: Deep analysis
    console.print("\n[bold]Stage 2[/bold]  Deep analysis (technicals, options, news)...")
    deep_analysis = stage2_deep_analysis(candidates, info_cache)

    # Rank
    ranked = rank_final_candidates(deep_analysis)

    # AI synthesis
    report_text = None
    if not args.no_ai:
        console.print("\n[bold]Stage 3[/bold]  Generating hedge fund analysis...")
        report_text = generate_hedge_fund_report(ranked, top_n=args.top)

    elapsed = time.time() - start
    print_report(report_text, ranked, elapsed)

    if args.email:
        html = build_html_email(report_text, ranked)
        send_email(html)


if __name__ == "__main__":
    main()
