"""
Market Data Feed and Technical Indicator Engine.
Uses free, zero-maintenance daily market data (Yahoo Finance / NSE) to compute
swing trading indicators: 20 EMA, 50 EMA, 200 EMA, RSI(14), ATR(14), and breakout channels.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yfinance as yf

from trading_agent.config import EXCHANGE


def get_ticker_symbol(symbol: str, exchange: str = EXCHANGE) -> str:
    """Format symbol for Yahoo Finance."""
    symbol = symbol.strip().upper()
    if exchange.upper() == "NSE" and not symbol.endswith(".NS"):
        return f"{symbol}.NS"
    elif exchange.upper() == "BSE" and not symbol.endswith(".BO"):
        return f"{symbol}.BO"
    return symbol


def fetch_historical_bars(
    symbol: str, exchange: str = EXCHANGE, period: str = "120d"
) -> Optional[pd.DataFrame]:
    """
    Fetch daily historical OHLCV candles for a given stock.
    Returns cleaned pandas DataFrame with Datetime index.
    """
    ticker_sym = get_ticker_symbol(symbol, exchange)
    try:
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period=period, interval="1d")
        if df is None or df.empty or len(df) < 30:
            return None

        # Clean columns
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(inplace=True)
        return df
    except Exception:
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate moving averages, Wilder RSI, ATR, and breakout levels.
    """
    df = df.copy()

    # Exponential Moving Averages (20, 50, 200)
    df["ema20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["Close"].ewm(span=50, adjust=False).mean()
    if len(df) >= 200:
        df["ema200"] = df["Close"].ewm(span=200, adjust=False).mean()
    else:
        df["ema200"] = df["ema50"]  # Proxy if historical bars < 200

    # Wilder RSI(14)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
    df["rsi14"] = df["rsi14"].fillna(50.0)

    # Average True Range ATR(14)
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr14"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    # 10-day Price Range (Breakout Resistance & Support)
    df["high10"] = df["High"].rolling(10).max().shift(1)
    df["low10"] = df["Low"].rolling(10).min().shift(1)

    # 20-day Volume Moving Average
    df["vol_ma20"] = df["Volume"].rolling(20).mean()

    return df


def get_latest_market_snapshot(
    symbol: str, exchange: str = EXCHANGE
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the latest technical snapshot for a symbol including indicators
    and candle patterns.
    """
    df = fetch_historical_bars(symbol, exchange, period="120d")
    if df is None or len(df) < 30:
        return None

    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    ltp = float(latest["Close"])
    open_price = float(latest["Open"])
    high = float(latest["High"])
    low = float(latest["Low"])
    volume = int(latest["Volume"])
    vol_ma20 = float(latest["vol_ma20"]) if not np.isnan(latest["vol_ma20"]) else volume

    ema20 = float(latest["ema20"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    rsi = float(latest["rsi14"])
    atr = float(latest["atr14"]) if not np.isnan(latest["atr14"]) else (high - low)
    high10 = float(latest["high10"]) if not np.isnan(latest["high10"]) else high
    low10 = float(latest["low10"]) if not np.isnan(latest["low10"]) else low

    volume_ratio = volume / vol_ma20 if vol_ma20 > 0 else 1.0

    return {
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "ltp": round(ltp, 2),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "volume": volume,
        "vol_ma20": round(vol_ma20, 0),
        "volume_ratio": round(volume_ratio, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "rsi14": round(rsi, 2),
        "atr14": round(atr, 2),
        "high10": round(high10, 2),
        "low10": round(low10, 2),
        "prev_close": round(float(prev["Close"]), 2),
        "prev_low": round(float(prev["Low"]), 2),
        "is_green": ltp >= open_price,
    }
