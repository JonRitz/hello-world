import os

CLAUDE_MODEL = "claude-sonnet-4-6"

SCREENING_CANDIDATES = 50
FINAL_PICKS = 10
TECHNICAL_LOOKBACK_DAYS = 365

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

CATEGORIES = [
    "undervalued",
    "overvalued_short",
    "dividend",
    "momentum_breakout",
    "options_smart_money",
]
