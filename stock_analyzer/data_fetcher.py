import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

_INFO_FIELDS = [
    "trailingPE", "forwardPE", "priceToBook", "enterpriseToEbitda",
    "dividendYield", "payoutRatio", "trailingEps", "forwardEps",
    "revenueGrowth", "earningsGrowth", "debtToEquity", "currentRatio",
    "freeCashflow", "marketCap", "sector", "industry",
    "shortPercentOfFloat", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "fiftyDayAverage", "twoHundredDayAverage", "regularMarketPrice",
    "previousClose", "volume", "averageVolume", "longName", "shortName",
]


def fetch_ticker_info(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {k: info.get(k) for k in _INFO_FIELDS}
    except Exception:
        return {}


def fetch_bulk_price_data(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    try:
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
        result = {}
        if isinstance(raw.columns, pd.MultiIndex):
            for ticker in tickers:
                try:
                    df = raw.xs(ticker, level=1, axis=1).dropna(how="all")
                    if not df.empty:
                        result[ticker] = df
                except Exception:
                    pass
        else:
            # Single ticker download returns flat columns
            if len(tickers) == 1:
                df = raw.dropna(how="all")
                if not df.empty:
                    result[tickers[0]] = df
        return result
    except Exception:
        return {}


def fetch_options_chain(ticker: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return None, None
        expiry = expirations[1] if len(expirations) > 1 else expirations[0]
        chain = t.option_chain(expiry)
        calls = chain.calls.fillna(0)
        puts = chain.puts.fillna(0)
        return calls, puts
    except Exception:
        return None, None


def fetch_news(ticker: str) -> list[dict]:
    try:
        news = yf.Ticker(ticker).news or []
        return [
            {
                "title": item.get("content", {}).get("title", item.get("title", "")),
                "publisher": item.get("content", {}).get("provider", {}).get("displayName",
                             item.get("publisher", "")),
                "link": item.get("content", {}).get("canonicalUrl", {}).get("url",
                        item.get("link", "")),
            }
            for item in news[:5]
        ]
    except Exception:
        return []


def fetch_batch_info(tickers: list[str], max_workers: int = 10) -> dict[str, dict]:
    results = {}
    batches = [tickers[i:i + 50] for i in range(0, len(tickers), 50)]
    for batch in batches:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(fetch_ticker_info, t): t for t in batch}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    results[ticker] = future.result()
                except Exception:
                    results[ticker] = {}
        time.sleep(0.5)
    return results
