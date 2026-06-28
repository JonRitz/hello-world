import pandas as pd


def analyze_options_flow(calls: pd.DataFrame | None, puts: pd.DataFrame | None) -> dict:
    default = {
        "put_call_ratio": 1.0,
        "put_call_signal": "neutral",
        "unusual_call_activity": False,
        "unusual_put_activity": False,
        "max_call_oi_strike": None,
        "max_put_oi_strike": None,
        "iv_skew": "neutral",
        "options_signal": "neutral",
        "smart_money_alert": False,
    }

    if calls is None or puts is None or calls.empty or puts.empty:
        return default

    try:
        call_vol = calls["volume"].fillna(0).sum()
        put_vol = puts["volume"].fillna(0).sum()

        pc_ratio = put_vol / call_vol if call_vol > 0 else 1.0

        if pc_ratio < 0.7:
            pc_signal = "bullish"
        elif pc_ratio > 1.3:
            pc_signal = "bearish"
        else:
            pc_signal = "neutral"

        # Unusual activity: any single strike with volume > 2x open interest
        def _has_unusual(df: pd.DataFrame) -> bool:
            oi = df["openInterest"].fillna(0)
            vol = df["volume"].fillna(0)
            mask = (oi > 0) & (vol > 2 * oi)
            return bool(mask.any())

        unusual_calls = _has_unusual(calls)
        unusual_puts = _has_unusual(puts)

        # Max open interest strikes
        max_call_oi_row = calls.loc[calls["openInterest"].fillna(0).idxmax()] if not calls.empty else None
        max_put_oi_row = puts.loc[puts["openInterest"].fillna(0).idxmax()] if not puts.empty else None
        max_call_strike = float(max_call_oi_row["strike"]) if max_call_oi_row is not None else None
        max_put_strike = float(max_put_oi_row["strike"]) if max_put_oi_row is not None else None

        # IV skew: compare near-ATM implied vol for calls vs puts
        try:
            mid_idx = len(calls) // 2
            call_iv = float(calls["impliedVolatility"].fillna(0).iloc[mid_idx])
            put_iv = float(puts["impliedVolatility"].fillna(0).iloc[mid_idx])
            if call_iv > put_iv * 1.1:
                iv_skew = "call_skew"
            elif put_iv > call_iv * 1.1:
                iv_skew = "put_skew"
            else:
                iv_skew = "neutral"
        except Exception:
            iv_skew = "neutral"

        # Composite options signal
        bull_points = (
            (1 if pc_signal == "bullish" else 0)
            + (1 if unusual_calls else 0)
            + (1 if iv_skew == "call_skew" else 0)
        )
        bear_points = (
            (1 if pc_signal == "bearish" else 0)
            + (1 if unusual_puts else 0)
            + (1 if iv_skew == "put_skew" else 0)
        )

        if bull_points >= 3:
            options_signal = "strong_bullish"
        elif bull_points >= 2:
            options_signal = "bullish"
        elif bear_points >= 3:
            options_signal = "strong_bearish"
        elif bear_points >= 2:
            options_signal = "bearish"
        else:
            options_signal = "neutral"

        smart_money_alert = unusual_calls and pc_ratio < 0.8

        return {
            "put_call_ratio": round(pc_ratio, 2),
            "put_call_signal": pc_signal,
            "unusual_call_activity": unusual_calls,
            "unusual_put_activity": unusual_puts,
            "max_call_oi_strike": max_call_strike,
            "max_put_oi_strike": max_put_strike,
            "iv_skew": iv_skew,
            "options_signal": options_signal,
            "smart_money_alert": smart_money_alert,
        }
    except Exception:
        return default
