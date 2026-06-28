def classify_valuation(info: dict) -> dict:
    pe = info.get("trailingPE") or info.get("forwardPE")
    pb = info.get("priceToBook")
    ev_ebitda = info.get("enterpriseToEbitda")
    div_yield_raw = info.get("dividendYield") or 0.0
    div_yield = div_yield_raw * 100 if div_yield_raw < 1 else div_yield_raw
    payout = info.get("payoutRatio")
    rev_growth = info.get("revenueGrowth")
    earn_growth = info.get("earningsGrowth")
    debt_equity = info.get("debtToEquity")
    short_pct = info.get("shortPercentOfFloat")
    beta = info.get("beta")
    market_cap = info.get("marketCap") or 0

    # Valuation signal
    if pe and pb:
        if pe < 15 and pb < 2:
            valuation_signal = "undervalued"
        elif pe < 12:
            valuation_signal = "undervalued"
        elif pe > 40 or (pb and pb > 10):
            valuation_signal = "overvalued"
        else:
            valuation_signal = "fairly_valued"
    elif pe:
        if pe < 12:
            valuation_signal = "undervalued"
        elif pe > 40:
            valuation_signal = "overvalued"
        else:
            valuation_signal = "fairly_valued"
    else:
        valuation_signal = "unknown"

    # Dividend signal
    if div_yield >= 3.5:
        dividend_signal = "high"
    elif div_yield >= 1.5:
        dividend_signal = "moderate"
    elif div_yield > 0:
        dividend_signal = "low"
    else:
        dividend_signal = "none"

    # Dividend sustainability
    dividend_sustainable = False
    if payout and 0 < payout < 0.75:
        if earn_growth is None or earn_growth > -0.1:
            dividend_sustainable = True

    # Debt signal
    if debt_equity is None:
        debt_signal = "unknown"
    elif debt_equity > 200:
        debt_signal = "high"
    elif debt_equity > 80:
        debt_signal = "moderate"
    else:
        debt_signal = "low"

    # Quality score (0-100)
    quality = 50.0
    if rev_growth:
        if rev_growth > 0.2:
            quality += 15
        elif rev_growth > 0.05:
            quality += 8
        elif rev_growth < 0:
            quality -= 10
    if earn_growth:
        if earn_growth > 0.2:
            quality += 10
        elif earn_growth < -0.1:
            quality -= 10
    if debt_signal == "low":
        quality += 10
    elif debt_signal == "high":
        quality -= 15
    if valuation_signal == "undervalued":
        quality += 10
    elif valuation_signal == "overvalued":
        quality -= 5
    if market_cap > 50_000_000_000:
        quality += 5  # large-cap stability
    quality = max(0.0, min(100.0, quality))

    return {
        "pe_ratio": pe,
        "pb_ratio": pb,
        "ev_ebitda": ev_ebitda,
        "valuation_signal": valuation_signal,
        "dividend_yield": round(div_yield, 2),
        "dividend_signal": dividend_signal,
        "payout_ratio": payout,
        "dividend_sustainable": dividend_sustainable,
        "revenue_growth": rev_growth,
        "earnings_growth": earn_growth,
        "debt_signal": debt_signal,
        "debt_equity": debt_equity,
        "quality_score": quality,
        "short_interest": short_pct,
        "beta": beta,
        "market_cap": market_cap,
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "name": info.get("longName") or info.get("shortName", ""),
    }


def screen_by_criteria(info: dict, valuation: dict) -> dict:
    is_undervalued = valuation["valuation_signal"] == "undervalued"
    is_overvalued = valuation["valuation_signal"] == "overvalued"
    is_dividend = valuation["dividend_signal"] in ("high", "moderate") and valuation["dividend_sustainable"]
    is_growth = (
        (valuation.get("revenue_growth") or 0) > 0.15
        and (valuation.get("earnings_growth") or 0) > 0.1
    )
    is_short_candidate = (
        is_overvalued
        and (valuation.get("short_interest") or 0) > 0.05
        and (valuation.get("earnings_growth") or 0) < 0
    )
    return {
        "is_undervalued": is_undervalued,
        "is_overvalued": is_overvalued,
        "is_dividend_play": is_dividend,
        "is_growth": is_growth,
        "is_short_candidate": is_short_candidate,
    }
