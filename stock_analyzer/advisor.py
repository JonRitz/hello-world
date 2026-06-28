import os
import json
from datetime import date

import anthropic

from .config import CLAUDE_MODEL, FINAL_PICKS


def _format_candidate(ticker: str, score: float, data: dict) -> dict:
    val = data["valuation"]
    tech = data["technical"]
    opts = data["options"]
    news = data["news"]

    return {
        "ticker": ticker,
        "composite_score": round(score, 1),
        "name": val.get("name", ""),
        "sector": val.get("sector", "Unknown"),
        "industry": val.get("industry", "Unknown"),
        "price": tech.get("current_price"),
        "market_cap_b": round(val.get("market_cap", 0) / 1e9, 1) if val.get("market_cap") else None,
        "valuation": {
            "signal": val.get("valuation_signal"),
            "pe": val.get("pe_ratio"),
            "pb": val.get("pb_ratio"),
            "ev_ebitda": val.get("ev_ebitda"),
            "dividend_yield_pct": val.get("dividend_yield"),
            "dividend_signal": val.get("dividend_signal"),
            "dividend_sustainable": val.get("dividend_sustainable"),
        },
        "growth": {
            "revenue_growth_pct": round(val.get("revenue_growth", 0) * 100, 1) if val.get("revenue_growth") else None,
            "earnings_growth_pct": round(val.get("earnings_growth", 0) * 100, 1) if val.get("earnings_growth") else None,
        },
        "risk": {
            "debt_signal": val.get("debt_signal"),
            "beta": val.get("beta"),
            "short_interest_pct": round(val.get("short_interest", 0) * 100, 1) if val.get("short_interest") else None,
        },
        "technical": {
            "trend": tech.get("trend"),
            "rsi": round(tech.get("rsi", 50), 1),
            "macd_signal": tech.get("macd_signal"),
            "bb_position": tech.get("bb_position"),
            "week_52_position_pct": round(tech.get("week_52_position", 0.5) * 100, 1),
            "volume_surge": tech.get("volume_surge"),
            "technical_score": round(tech.get("technical_score", 50), 1),
        },
        "options_flow": {
            "signal": opts.get("options_signal"),
            "put_call_ratio": opts.get("put_call_ratio"),
            "unusual_calls": opts.get("unusual_call_activity"),
            "smart_money_alert": opts.get("smart_money_alert"),
            "iv_skew": opts.get("iv_skew"),
        },
        "recent_headlines": [n.get("title", "") for n in news[:3]],
        "criteria": data.get("criteria", {}),
    }


def generate_hedge_fund_report(ranked: list[tuple[str, float, dict]], top_n: int = FINAL_PICKS) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[No ANTHROPIC_API_KEY set — run with --no-ai or set the environment variable]"

    client = anthropic.Anthropic(api_key=api_key)

    top20 = ranked[:20]
    candidates_data = [_format_candidate(t, s, d) for t, s, d in top20]
    today = date.today().strftime("%B %d, %Y")

    system_prompt = """You are a world-class hedge fund portfolio manager — think Bill Ackman's activist
conviction, Jamie Dimon's macro perspective, and Stan Druckenmiller's trend-reading ability.

You receive quantitative market analysis data and synthesize it into actionable, institutional-grade
investment recommendations. Your voice is direct, confident, and data-driven. You back every call
with specific numbers. You acknowledge risks clearly. You think in terms of risk/reward, catalysts,
and time horizons. You are not a generalist — you have strong opinions.

Your output is a daily morning note structured as hedge fund managers actually write them."""

    user_prompt = f"""Today is {today}. I have run quantitative analysis across 600+ stocks (S&P 500,
NASDAQ 100, Russell 2000). Here are the top 20 candidates ranked by a composite score combining
technical momentum, fundamental quality, options flow intelligence, and valuation:

{json.dumps(candidates_data, indent=2)}

Your task:
1. Select exactly {top_n} stocks from these candidates as today's recommendations.
2. Assign each a category: LONG (undervalued or momentum), INCOME (dividend play),
   OPTIONS PLAY (unusual smart money flow), or AVOID/SHORT (overvalued with deteriorating fundamentals).
3. For each pick write:
   - One-line headline thesis (bold, punchy)
   - 2-3 sentence investment rationale grounded in the data
   - Key metrics (P/E, RSI, relevant valuation metric, etc.)
   - Entry rationale and approximate price target or range
   - Primary risk / bear case (1 sentence)
4. Open with a 2-paragraph "Today's Macro View" — your read on the current market environment
   and what themes are driving today's picks.
5. Close with a "Portfolio Construction Note" — 2-3 sentences on how to size these together
   (e.g., which are high-conviction, which are speculative, how to balance long vs income vs options).

Format cleanly for terminal output. Use section headers. Be specific about numbers.
Do NOT pad with generic disclaimers. Write like you're talking to a sophisticated LP."""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    return message.content[0].text
