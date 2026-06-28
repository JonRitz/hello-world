import pandas as pd
import warnings

warnings.filterwarnings("ignore")

NASDAQ100_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL", "GOOG", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "ASML", "QCOM", "INTC", "INTU", "AMAT", "BKNG", "ISRG",
    "CSCO", "TXN", "HON", "AMGN", "LRCX", "VRTX", "REGN", "MU", "ADI", "PANW",
    "KLAC", "CDNS", "SNPS", "MRVL", "CRWD", "FTNT", "AZN", "MDLZ", "GILD", "SBUX",
    "PYPL", "ABNB", "MRNA", "TEAM", "DDOG", "ZS", "WDAY", "BIIB", "IDXX", "ALGN",
]

RUSSELL2000_SAMPLE = [
    "SMCI", "CELH", "BOOT", "CRVL", "AGIO", "IIPR", "CASS", "PRGS", "MGEE", "STRL",
    "HALO", "STEP", "MGNI", "ARLO", "NTST", "WRLD", "HIMS", "ACMR", "TTGT", "BAND",
    "COOP", "PDFS", "MTRN", "TITN", "BLKB", "ALRM", "CWEN", "INVA", "SWIM", "LPSN",
    "ASAN", "APPN", "PRVA", "EVTC", "KRUS", "SFBS", "RGNX", "OSCR", "RXRX", "HRMY",
    "GSHD", "POWL", "IDCC", "YELP", "CNMD", "AEIS", "KRYS", "FORM", "RELY", "NARI",
]


def get_sp500_tickers() -> list[str]:
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            attrs={"id": "constituents"},
        )
        tickers = tables[0]["Symbol"].tolist()
        return [t.replace(".", "-") for t in tickers]
    except Exception:
        try:
            tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
            tickers = tables[0]["Symbol"].tolist()
            return [t.replace(".", "-") for t in tickers]
        except Exception:
            return []


def get_nasdaq100_tickers() -> list[str]:
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for table in tables:
            cols = [str(c).lower() for c in table.columns]
            if any("ticker" in c or "symbol" in c for c in cols):
                col = table.columns[[i for i, c in enumerate(cols) if "ticker" in c or "symbol" in c][0]]
                return [t.replace(".", "-") for t in table[col].dropna().tolist() if isinstance(t, str) and len(t) <= 5]
        return NASDAQ100_FALLBACK
    except Exception:
        return NASDAQ100_FALLBACK


def get_russell2000_sample() -> list[str]:
    return RUSSELL2000_SAMPLE


def get_full_universe() -> list[str]:
    sp500 = get_sp500_tickers()
    nasdaq = get_nasdaq100_tickers()
    russell = get_russell2000_sample()
    seen = set()
    combined = []
    for t in sp500 + nasdaq + russell:
        if t not in seen:
            seen.add(t)
            combined.append(t)
    return combined
