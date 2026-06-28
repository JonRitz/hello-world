---
name: market-scan
description: Run the daily stock market scanner and generate 10 hedge fund-style recommendations across S&P 500, NASDAQ 100, and Russell 2000.
---

Run the stock market scanner to analyze 600+ stocks and produce today's top 10 investment recommendations, styled as a hedge fund morning note (Bill Ackman / Jamie Dimon voice).

## Steps

1. Ensure dependencies are installed:
   ```
   pip install -r requirements.txt
   ```

2. Set your API key (required for AI synthesis):
   ```
   export ANTHROPIC_API_KEY=your_key_here
   ```

3. Run the scanner:
   ```
   python main.py
   ```

## Options

| Flag | Description |
|------|-------------|
| `--quick` | S&P 500 only — faster (~3 min vs ~8 min full) |
| `--universe sp500\|nasdaq\|all` | Choose stock universe (default: all) |
| `--sector Technology` | Filter candidates to a specific sector |
| `--top 10` | Number of final picks (default: 10) |
| `--no-ai` | Skip Claude synthesis, show raw quantitative rankings |

## What it analyzes

- **Fundamentals**: P/E, P/B, EV/EBITDA, dividend yield & sustainability, revenue/earnings growth, debt levels
- **Technicals**: RSI, MACD, Bollinger Bands, 20/50/200-day MAs, volume surge detection, 52-week positioning
- **Options flow**: Put/call ratios, unusual activity detection, IV skew, smart money alerts
- **News**: Recent headlines per stock fed into the AI synthesis

## Pick categories

| Label | Criteria |
|-------|----------|
| **LONG** | Undervalued fundamentals + bullish technical setup |
| **INCOME** | High sustainable dividend yield |
| **OPTIONS PLAY** | Unusual smart money options flow (large call sweeps, low P/C ratio) |
| **AVOID/SHORT** | Overvalued + deteriorating fundamentals + high short interest |

## Runtime estimates

- Full universe (600+ stocks): ~8–12 minutes
- S&P 500 only (`--quick`): ~3–5 minutes
- Most time is spent rate-limit-friendly data fetching from yfinance
