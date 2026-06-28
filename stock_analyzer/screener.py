import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .data_fetcher import fetch_batch_info, fetch_bulk_price_data, fetch_options_chain, fetch_news
from .fundamental import classify_valuation, screen_by_criteria
from .technical import analyze_ticker_technical
from .options_flow import analyze_options_flow


def _score_ticker(criteria: dict, valuation: dict) -> float:
    score = 0.0
    score += 3 if criteria["is_undervalued"] else 0
    score += 2 if criteria["is_dividend_play"] else 0
    score += 2 if criteria["is_growth"] else 0
    score += 1 if criteria["is_overvalued"] else 0
    score += 1 if criteria["is_short_candidate"] else 0
    # Penalize unknown valuation
    if valuation["valuation_signal"] == "unknown":
        score -= 1
    return score


def stage1_screen(tickers: list[str], top_n: int = 50) -> tuple[list[str], dict]:
    """Fast bulk screen using fundamentals. Returns (top_n tickers, info_cache)."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(f"Fetching fundamentals for {len(tickers)} stocks...", total=len(tickers))
        info_cache = {}
        batches = [tickers[i:i + 50] for i in range(0, len(tickers), 50)]
        for batch in batches:
            batch_results = fetch_batch_info(batch)
            info_cache.update(batch_results)
            progress.advance(task, len(batch))

    scored = []
    for ticker, info in info_cache.items():
        if not info:
            continue
        val = classify_valuation(info)
        criteria = screen_by_criteria(info, val)
        score = _score_ticker(criteria, val)
        scored.append((ticker, score, val, criteria))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_tickers = [t for t, _, _, _ in scored[:top_n]]
    return top_tickers, info_cache


def stage2_deep_analysis(candidates: list[str], info_cache: dict) -> dict:
    """Deep analysis: technicals + options + news for each candidate."""
    result = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        price_task = progress.add_task("Fetching price history...", total=1)
        price_data = fetch_bulk_price_data(candidates, period="1y")
        progress.advance(price_task, 1)

        opts_task = progress.add_task("Analyzing options flow...", total=len(candidates))
        news_task = progress.add_task("Fetching news...", total=len(candidates))

        def _fetch_options_and_news(ticker: str):
            calls, puts = fetch_options_chain(ticker)
            options = analyze_options_flow(calls, puts)
            news = fetch_news(ticker)
            return ticker, options, news

        options_results = {}
        news_results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fetch_options_and_news, t): t for t in candidates}
            for future in as_completed(futures):
                ticker, options, news = future.result()
                options_results[ticker] = options
                news_results[ticker] = news
                progress.advance(opts_task, 1)
                progress.advance(news_task, 1)

    for ticker in candidates:
        info = info_cache.get(ticker, {})
        valuation = classify_valuation(info)
        criteria = screen_by_criteria(info, valuation)
        technical = analyze_ticker_technical(price_data.get(ticker))
        options = options_results.get(ticker, {})
        news = news_results.get(ticker, [])

        result[ticker] = {
            "ticker": ticker,
            "info": info,
            "valuation": valuation,
            "criteria": criteria,
            "technical": technical,
            "options": options,
            "news": news,
        }

    return result


def _options_signal_score(signal: str) -> float:
    return {
        "strong_bullish": 100,
        "bullish": 75,
        "neutral": 50,
        "bearish": 25,
        "strong_bearish": 0,
    }.get(signal, 50)


def _valuation_to_score(signal: str) -> float:
    return {"undervalued": 80, "fairly_valued": 50, "overvalued": 20, "unknown": 40}.get(signal, 40)


def rank_final_candidates(deep_analysis: dict) -> list[tuple[str, float, dict]]:
    ranked = []
    for ticker, data in deep_analysis.items():
        tech_score = data["technical"].get("technical_score", 50)
        quality_score = data["valuation"].get("quality_score", 50)
        options_score = _options_signal_score(data["options"].get("options_signal", "neutral"))
        val_score = _valuation_to_score(data["valuation"].get("valuation_signal", "unknown"))

        # Smart money boost
        if data["options"].get("smart_money_alert"):
            options_score = min(100, options_score + 15)

        composite = (
            tech_score * 0.30
            + quality_score * 0.30
            + options_score * 0.20
            + val_score * 0.20
        )
        ranked.append((ticker, composite, data))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
