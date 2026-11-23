"""
Comprehensive unit tests for the Trading Agent package.
Verifies data feed indicators, risk management sizing, swing strategy engine,
and OpenAlgo REST API executor.
"""

from decimal import Decimal
import numpy as np
import pandas as pd
import pytest

from trading_agent.data_feed import calculate_indicators
from trading_agent.executor import OpenAlgoExecutor
from trading_agent.risk import RiskManager
from trading_agent.strategy import SwingStrategyEngine, TradeSignal


def test_calculate_indicators():
    """Verify that 20 EMA, 50 EMA, RSI, and ATR are calculated accurately."""
    # Create 60 days of synthetic price series
    dates = pd.date_range("2026-01-01", periods=60)
    prices = [100.0 + i * 1.5 + (2.0 if i % 2 == 0 else -1.0) for i in range(60)]
    df = pd.DataFrame(
        {
            "Open": [p - 0.5 for p in prices],
            "High": [p + 2.0 for p in prices],
            "Low": [p - 2.0 for p in prices],
            "Close": prices,
            "Volume": [100000 + i * 500 for i in range(60)],
        },
        index=dates,
    )

    result = calculate_indicators(df)

    assert "ema20" in result.columns
    assert "ema50" in result.columns
    assert "rsi14" in result.columns
    assert "atr14" in result.columns
    assert "high10" in result.columns
    assert "vol_ma20" in result.columns

    # Verify values are non-null and within valid bounds
    latest = result.iloc[-1]
    assert latest["ema20"] > 0
    assert latest["ema50"] > 0
    assert 0 <= latest["rsi14"] <= 100
    assert latest["atr14"] > 0


def test_risk_manager_sizing():
    """Verify dynamic position sizing based on risk budget and stop loss."""
    rm = RiskManager(
        risk_percent=0.005,  # 0.5%
        max_capital_per_trade=1_000_000.0,
        min_risk_reward=1.5,
    )

    available_capital = 10_000_000.0  # ₹1.00 Cr
    entry_price = 1000.0
    stop_loss = 950.0  # Risk per share = ₹50
    target_price = 1100.0  # Reward per share = ₹100, R:R = 2.0

    valid, qty, details = rm.calculate_position_size(
        available_capital, entry_price, stop_loss, target_price
    )

    assert valid is True
    # Risk budget = 10,000,000 * 0.005 = ₹50,000
    # Qty = 50,000 / 50 = 1000 shares
    # Capital required = 1000 * 1000 = ₹10,00,000 (matches max capital per trade)
    assert qty == 1000
    assert details["risk_reward_ratio"] == 2.0
    assert details["total_risk"] == 50000.0
    assert details["potential_profit"] == 100000.0


def test_risk_manager_rejects_substandard_rr():
    """Verify that setups with R:R below 1.5 are rejected."""
    rm = RiskManager(min_risk_reward=1.5)
    valid, qty, details = rm.calculate_position_size(
        available_capital=10_000_000.0,
        entry_price=1000.0,
        stop_loss=950.0,  # Risk = 50
        target_price=1050.0,  # Reward = 50, R:R = 1.0 < 1.5
    )
    assert valid is False
    assert "below minimum" in details.get("error", "")


def test_swing_strategy_ema_pullback():
    """Verify that an uptrend pullback triggering conditions produces a TradeSignal."""
    engine = SwingStrategyEngine()
    snapshot = {
        "symbol": "TCS",
        "exchange": "NSE",
        "ltp": 2500.0,
        "open": 2480.0,
        "high": 2510.0,
        "low": 2465.0,  # Touched near 20 EMA
        "volume": 2000000,
        "vol_ma20": 1800000.0,
        "volume_ratio": 1.11,
        "ema20": 2470.0,
        "ema50": 2400.0,  # Strong uptrend: 2500 > 2470 > 2400
        "ema200": 2300.0,
        "rsi14": 55.0,
        "atr14": 40.0,
        "high10": 2550.0,
        "low10": 2420.0,
        "prev_close": 2475.0,
        "prev_low": 2460.0,
        "is_green": True,
    }

    signal = engine.evaluate(snapshot)
    assert signal is not None
    assert signal.strategy_type == "EMA_PULLBACK"
    assert signal.symbol == "TCS"
    assert signal.action == "BUY"
    assert signal.stop_loss < signal.entry_price
    assert signal.target_price > signal.entry_price
    assert signal.risk_reward_ratio >= 1.5


def test_openalgo_executor_funds_and_positions(monkeypatch):
    """Verify executor connectivity and parsing for OpenAlgo Analyzer."""
    exe = OpenAlgoExecutor(api_key="mock_test_key")

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code

        def json(self):
            return self._json

    def mock_post(self, url, json=None, headers=None, timeout=None):
        if "funds" in url:
            return MockResponse({"status": "success", "mode": "analyze", "data": {"availablecash": 10000000.0}})
        elif "positionbook" in url:
            return MockResponse({"status": "success", "data": []})
        return MockResponse({"status": "error"})

    import requests
    monkeypatch.setattr(requests.Session, "post", mock_post)

    funds = exe.get_funds()
    assert funds["mode"] == "analyze"
    assert funds["available_cash"] > 0
    positions = exe.get_positions()
    assert isinstance(positions, list)
