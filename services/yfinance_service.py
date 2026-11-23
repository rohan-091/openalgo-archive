"""services/yfinance_service.py

Yahoo Finance Public Market Data Service for OpenAlgo.
Provides free, zero-KYC OHLCV candlestick historical data for NSE/BSE indices and equities.
"""

from datetime import date, datetime, timedelta
from typing import Any
import pandas as pd
import yfinance as yf

from utils.logging import get_logger

logger = get_logger(__name__)

# Common Index Mapping to Yahoo Finance tickers
INDEX_TICKER_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY 50": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY FIN SERVICE": "NIFTY_FIN_SERVICE.NS",
    "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    "NIFTY MID SELECT": "NIFTY_MID_SELECT.NS",
    "SENSEX": "^BSESN",
    "BSE SENSEX": "^BSESN",
    "BANKEX": "BSE-BANK.BO",
}

# OpenAlgo interval to Yahoo Finance interval
YFINANCE_INTERVAL_MAP = {
    "1m": "1m",
    "2m": "2m",
    "3m": "5m",  # yfinance doesn't support 3m, map to closest standard 5m
    "5m": "5m",
    "10m": "15m",  # yfinance doesn't support 10m, map to closest standard 15m
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
    "1h": "60m",
    "D": "1d",
    "1d": "1d",
    "W": "1wk",
    "1w": "1wk",
    "M": "1mo",
    "1mo": "1mo",
}


def to_yfinance_ticker(symbol: str, exchange: str) -> str:
    """Resolve OpenAlgo symbol and exchange to Yahoo Finance ticker string."""
    clean_sym = symbol.strip().upper()
    clean_ex = exchange.strip().upper()

    # Check index dictionary first
    if clean_sym in INDEX_TICKER_MAP:
        return INDEX_TICKER_MAP[clean_sym]

    # If symbol already has standard exchange suffix
    if clean_sym.endswith(".NS") or clean_sym.endswith(".BO") or clean_sym.startswith("^"):
        return clean_sym

    # Handle equities based on exchange
    if clean_ex in ("NSE", "NSE_INDEX"):
        return f"{clean_sym}.NS"
    elif clean_ex in ("BSE", "BSE_INDEX"):
        return f"{clean_sym}.BO"

    return clean_sym


def get_history_from_yfinance(
    symbol: str,
    exchange: str,
    interval: str,
    start_date: str | date,
    end_date: str | date,
) -> tuple[bool, dict[str, Any], int]:
    """Fetch historical OHLCV candles from Yahoo Finance.

    Returns:
        tuple (success, response_dict, status_code)
    """
    try:
        ticker_str = to_yfinance_ticker(symbol, exchange)
        yf_interval = YFINANCE_INTERVAL_MAP.get(interval, "1d")

        ticker = yf.Ticker(ticker_str)

        # Parse start and end dates
        if isinstance(start_date, date):
            start_dt = datetime.combine(start_date, datetime.min.time())
        else:
            start_dt = datetime.strptime(str(start_date).strip(), "%Y-%m-%d")

        if isinstance(end_date, date):
            end_dt = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
        else:
            end_dt = datetime.strptime(str(end_date).strip(), "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )

        # Yahoo Finance imposes lookback limits on intraday data:
        # 1m/2m: max 7-8 days
        # 5m/15m/30m: max 60 days
        # 60m: max 730 days
        if yf_interval in ("1m", "2m"):
            df = ticker.history(period="7d", interval=yf_interval)
        elif yf_interval in ("5m", "15m", "30m"):
            df = ticker.history(period="60d", interval=yf_interval)
        elif yf_interval == "60m":
            df = ticker.history(period="730d", interval=yf_interval)
        else:
            # Daily and above can use full requested range
            df = ticker.history(
                start=start_dt.strftime("%Y-%m-%d"),
                end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval=yf_interval,
            )

        if df is None or df.empty:
            return (
                False,
                {
                    "status": "error",
                    "message": f"No data returned from Yahoo Finance for ticker '{ticker_str}' interval '{interval}'.",
                },
                404,
            )

        df = df.reset_index()

        # Determine time column name
        time_col = "Datetime" if "Datetime" in df.columns else "Date"
        # Convert timestamp to epoch seconds
        df["timestamp"] = pd.to_datetime(df[time_col]).astype("int64") // 10**9

        # Filter strictly within requested start and end timestamps if valid overlap
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        filtered = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
        if not filtered.empty:
            df = filtered

        # Standardize columns and round decimals
        df["open"] = df["Open"].round(2)
        df["high"] = df["High"].round(2)
        df["low"] = df["Low"].round(2)
        df["close"] = df["Close"].round(2)
        df["volume"] = df["Volume"].fillna(0).astype("int64")
        df["oi"] = 0

        # Sort and deduplicate
        df = (
            df.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp"])
            .reset_index(drop=True)
        )

        columns = ["timestamp", "open", "high", "low", "close", "volume", "oi"]
        df = df[columns]

        return True, {"status": "success", "data": df.to_dict(orient="records")}, 200

    except Exception as e:
        logger.exception(
            f"Error fetching historical data from Yahoo Finance for {exchange}:{symbol}: {e}"
        )
        return False, {"status": "error", "message": f"Yahoo Finance error: {str(e)}"}, 500
