"""
Trading Agent Configuration.
Contains global parameters, stock universe, OpenAlgo API settings, and risk limits.
"""

import os
from pathlib import Path

# Workspace Root
ROOT_DIR = Path(__file__).resolve().parent.parent

# Attempt loading .env if available
env_file = ROOT_DIR / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_file)
    except ImportError:
        pass

# OpenAlgo Connection
OPENALGO_HOST = os.getenv("OPENALGO_HOST", "http://127.0.0.1:5000")
OPENALGO_API_KEY = os.getenv("OPENALGO_API_KEY", "")

# Trading Strategy Meta
EXCHANGE = "NSE"
STRATEGY_NAME = "AgenticSwing"
PRODUCT_TYPE = "CNC"  # Cash & Carry delivery for swing trading (holding 2-30 days)

# Risk & Sizing Parameters (Pillar 4 Option A)
RISK_PERCENT_PER_TRADE = 0.005  # 0.5% risk calculation parameter
MAX_CAPITAL_PER_TRADE = 50_000.0  # ₹50,000 max investment per trade (0.5% test phase allocation)
MAX_OPEN_POSITIONS = 5  # Maximum concurrent active swing positions
MIN_RISK_REWARD = 1.5  # Minimum acceptable Risk-to-Reward ratio

# Universe: High liquidity Large/Mid-cap Indian Equities
DEFAULT_UNIVERSE = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "BHARTIARTL",
    "ITC",
    "LT",
    "SBIN",
    "KOTAKBANK",
    "HINDUNILVR",
    "AXISBANK",
    "MARUTI",
    "SUNPHARMA",
    "TITAN",
    "BAJFINANCE",
    "ASIANPAINT",
    "HCLTECH",
    "NTPC",
    "POWERGRID",
    "M&M",
    "ULTRACEMCO",
    "TATASTEEL",
    "BAJAJFINSV",
    "NESTLEIND",
    "TECHM",
    "ONGC",
    "JSWSTEEL",
    "ADANIENT",
    "COALINDIA",
]

# Trade Journal File
JOURNAL_PATH = ROOT_DIR / "TRADES.md"
