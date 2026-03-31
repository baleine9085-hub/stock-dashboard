import pandas as pd
import numpy as np

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})

def calc_bollinger_bands(close, period=20, std_dev=2.0):
    middle = close.rolling(window=period).mean()
    std    = close.rolling(window=period).std()
    upper  = middle + (std * std_dev)
    lower  = middle - (std * std_dev)
    pct_b  = (close - lower) / (upper - lower)
    return pd.DataFrame({"upper": upper, "middle": middle, "lower": lower, "pct_b": pct_b})

def calc_moving_averages(close):
    return pd.DataFrame({
        "MA5":   close.rolling(5).mean(),
        "MA20":  close.rolling(20).mean(),
        "MA50":  close.rolling(50).mean(),
        "MA200": close.rolling(200).mean(),
    })

def get_all_indicators(df: pd.DataFrame) -> dict:
    close  = df["Close"]
    volume = df["Volume"]

    rsi_series = calc_rsi(close)
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    macd_df   = calc_macd(close)
    macd_hist = float(macd_df["histogram"].iloc[-1])
    macd_prev = float(macd_df["histogram"].iloc[-2]) if len(macd_df) > 1 else 0
    if macd_hist > 0 and macd_hist > macd_prev:
        macd_cross = "golden"
    elif macd_hist < 0 and macd_hist < macd_prev:
        macd_cross = "dead"
    else:
        macd_cross = "neutral"

    bb_df = calc_bollinger_bands(close)
    pct_b = float(bb_df["pct_b"].iloc[-1])
    if pct_b > 0.8:
        bb_position = "upper"
    elif pct_b < 0.2:
        bb_position = "lower"
    else:
        bb_position = "middle"

    ma_df  = calc_moving_averages(close)
    price  = float(close.iloc[-1])
    ma20   = float(ma_df["MA20"].iloc[-1])
    ma50   = float(ma_df["MA50"].iloc[-1])
    if price > ma20 > ma50:
        ma_trend = "bullish"
    elif price < ma20 < ma50:
        ma_trend = "bearish"
    else:
        ma_trend = "neutral"

    vol_ma20   = volume.rolling(20).mean()
    vol_ratio  = float(volume.iloc[-1] / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 1.0
    volume_surge = bool(vol_ratio > 1.5)

    score = 50
    if 40 <= rsi <= 65:
        score += 15
    elif rsi > 70:
        score -= 10
    elif rsi < 30:
        score += 5
    if macd_cross == "golden":
        score += 15
    elif macd_cross == "dead":
        score -= 15
    if ma_trend == "bullish":
        score += 15
    elif ma_trend == "bearish":
        score -= 15
    if volume_surge and ma_trend == "bullish":
        score += 10
    if bb_position == "lower":
        score += 5
    score = max(0, min(100, score))

    return {
        "rsi":          round(rsi, 1),
        "macd_cross":   macd_cross,
        "bb_position":  bb_position,
        "pct_b":        round(pct_b, 2) if not np.isnan(pct_b) else 0.5,
        "ma_trend":     ma_trend,
        "volume_surge": volume_surge,
        "vol_ratio":    round(vol_ratio, 2),
        "score":        int(score),
    }