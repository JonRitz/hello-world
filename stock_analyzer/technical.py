import numpy as np
import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
    }


def calculate_bollinger_bands(close: pd.Series, period: int = 20, std: float = 2.0) -> dict:
    middle = close.rolling(period).mean()
    deviation = close.rolling(period).std()
    upper = middle + std * deviation
    lower = middle - std * deviation
    current = float(close.iloc[-1])
    mid_val = float(middle.iloc[-1])
    upper_val = float(upper.iloc[-1])
    lower_val = float(lower.iloc[-1])
    band_width = upper_val - lower_val
    percent_b = (current - lower_val) / band_width if band_width > 0 else 0.5
    return {
        "upper": upper_val,
        "middle": mid_val,
        "lower": lower_val,
        "percent_b": percent_b,
    }


def calculate_moving_averages(close: pd.Series) -> dict:
    def _ma(n):
        if len(close) >= n:
            return float(close.rolling(n).mean().iloc[-1])
        return None

    return {"ma20": _ma(20), "ma50": _ma(50), "ma200": _ma(200)}


def calculate_volume_analysis(close: pd.Series, volume: pd.Series) -> dict:
    avg_vol = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
    current_vol = float(volume.iloc[-1])
    ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
    return {
        "avg_volume_20d": avg_vol,
        "volume_ratio": ratio,
        "volume_surge": ratio > 1.5,
    }


def analyze_ticker_technical(price_df: pd.DataFrame) -> dict:
    if price_df is None or price_df.empty or "Close" not in price_df.columns:
        return _neutral_technical()

    close = price_df["Close"].dropna()
    volume = price_df.get("Volume", pd.Series(dtype=float)).dropna()

    if len(close) < 30:
        return _neutral_technical()

    rsi = calculate_rsi(close)
    macd_data = calculate_macd(close)
    bb = calculate_bollinger_bands(close)
    mas = calculate_moving_averages(close)
    vol_data = calculate_volume_analysis(close, volume) if not volume.empty else {"avg_volume_20d": 0, "volume_ratio": 1, "volume_surge": False}

    current = float(close.iloc[-1])
    high_52w = float(close.tail(252).max())
    low_52w = float(close.tail(252).min())
    week52_range = high_52w - low_52w
    week52_position = (current - low_52w) / week52_range if week52_range > 0 else 0.5

    # MACD signal
    if macd_data["histogram"] > 0 and macd_data["macd"] > macd_data["signal"]:
        macd_signal = "bullish"
    elif macd_data["histogram"] < 0 and macd_data["macd"] < macd_data["signal"]:
        macd_signal = "bearish"
    else:
        macd_signal = "neutral"

    # Bollinger position
    pb = bb["percent_b"]
    if pb > 1.0:
        bb_position = "above_upper"
    elif pb > 0.5:
        bb_position = "above_middle"
    elif pb > 0.0:
        bb_position = "below_middle"
    else:
        bb_position = "below_lower"

    # Trend based on MAs
    ma20, ma50, ma200 = mas.get("ma20"), mas.get("ma50"), mas.get("ma200")
    if ma20 and ma50 and ma200:
        if current > ma20 > ma50 > ma200:
            trend = "strong_uptrend"
        elif current > ma50 > ma200:
            trend = "uptrend"
        elif current < ma20 < ma50 < ma200:
            trend = "strong_downtrend"
        elif current < ma50 < ma200:
            trend = "downtrend"
        else:
            trend = "sideways"
    else:
        trend = "sideways"

    # Composite technical score (0-100)
    score = 50.0
    # RSI contribution
    if 30 <= rsi <= 50:
        score += 15  # oversold recovery
    elif rsi < 30:
        score += 10  # deeply oversold
    elif 50 <= rsi <= 70:
        score += 10  # healthy momentum
    elif rsi > 80:
        score -= 15  # overbought
    # MACD
    if macd_signal == "bullish":
        score += 10
    elif macd_signal == "bearish":
        score -= 10
    # Trend
    trend_scores = {"strong_uptrend": 15, "uptrend": 8, "sideways": 0, "downtrend": -8, "strong_downtrend": -15}
    score += trend_scores.get(trend, 0)
    # BB position — below lower band = potential bounce
    if bb_position == "below_lower":
        score += 8
    elif bb_position == "above_upper":
        score -= 8
    # Volume surge on uptrend is positive
    if vol_data["volume_surge"] and trend in ("uptrend", "strong_uptrend"):
        score += 5

    score = max(0.0, min(100.0, score))

    return {
        "rsi": rsi,
        "macd_signal": macd_signal,
        "bb_position": bb_position,
        "trend": trend,
        "volume_surge": vol_data["volume_surge"],
        "volume_ratio": vol_data["volume_ratio"],
        "week_52_position": week52_position,
        "technical_score": score,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "current_price": current,
    }


def _neutral_technical() -> dict:
    return {
        "rsi": 50.0,
        "macd_signal": "neutral",
        "bb_position": "above_middle",
        "trend": "sideways",
        "volume_surge": False,
        "volume_ratio": 1.0,
        "week_52_position": 0.5,
        "technical_score": 50.0,
        "ma20": None,
        "ma50": None,
        "ma200": None,
        "current_price": None,
    }
