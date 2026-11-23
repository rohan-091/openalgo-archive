# 🤖 Antigravity Agentic Paper Trading System for Indian Equities

An autonomous and copilot swing trading system built natively for **Indian Equities (NSE)** using **Antigravity session quota** (zero external paid LLM token costs) connected directly to **OpenAlgo's Analyzer Paper Trading engine** (₹1.00 Cr virtual capital).

---

## 🏛️ Strategic Pillars

1. **Dual Autonomy Modes (Pillar 1)**:
   - **Mode B (Copilot / Human-in-the-Loop)**: Scans the market, calculates exact position size, risk-to-reward, and stop loss, presenting an interactive approval card before placing the order.
   - **Mode A (Fully Autonomous)**: Scans the universe, executes qualifying setups, manages active positions against Target and Stop Loss, and automatically updates the trade journal [TRADES.md](../TRADES.md).
2. **Strategy & Universe (Pillar 2)**:
   - **Equity Cash Only** (`product="CNC"`), Swing timeframe holding **2 to 30 days**.
   - **Strategy 1 (20-EMA Trend Pullback)**: Identifies strong uptrends (Price > 50 EMA, 20 EMA > 50 EMA), detects pullbacks to the 20 EMA, and triggers on bullish bounce confirmation with RSI momentum (42–68).
   - **Strategy 2 (10-Day Resistance Breakout)**: Enters on clean breakouts above 10-day price highs supported by volume expansion (Volume > 1.2x 20-day average) and bullish RSI.
3. **Hybrid Data Feed (Pillar 3)**:
   - Uses zero-maintenance, free daily market data (`yfinance` for NSE) to compute daily indicators without requiring daily Zerodha Kite 2FA logins or paid historical API subscriptions.
   - Seamlessly falls back to Yahoo Finance quotes in OpenAlgo analyzer mode.
4. **Risk & Position Sizing Engine (Pillar 4)**:
   - **Fixed % Risk Sizing**: 0.5% risk per trade (`₹50,000` max risk on `₹1.00 Cr` capital).
   - **Dynamic Sizing**: `Quantity = int(Risk_Budget / (Entry - Stop_Loss))`.
   - **Safety Caps**: Maximum `₹10,00,000` capital allocated per trade (10% max single-stock exposure), maximum 5 concurrent open positions, and minimum `1:1.5` Risk-to-Reward ratio.

---

## 📁 Package Architecture

```
trading_agent/
├── __init__.py               # Package metadata
├── config.py                 # Universe, API keys, risk limits, paths
├── data_feed.py              # Daily candles & indicators (20/50 EMA, RSI, ATR, High10, Volume)
├── executor.py               # REST API client for OpenAlgo Analyzer (/placeorder, /positionbook, /funds)
├── risk.py                   # Dynamic position sizing & risk validation engine
├── strategy.py               # Swing strategy rule evaluator (EMA Pullback & Range Breakout)
├── scanner.py                # Parallel multi-stock universe scanner
├── copilot.py                # Mode B interactive CLI runner
├── auto_trader.py            # Mode A autonomous cycle executor
├── active_trades_state.json  # Target & Stop Loss state tracker
└── README.md                 # System documentation
```

---

## 🚀 How to Run

### 1. Interactive Copilot (Mode B)
Scan the market and review proposed setups with entry, target, and stop loss before approving:
```powershell
.venv\Scripts\python -m trading_agent.copilot
```

### 2. Autonomous Cycle (Mode A)
Run an automated execution cycle (scans, places qualifying orders, monitors open positions against SL/TP, and updates `TRADES.md`):
```powershell
.venv\Scripts\python -m trading_agent.auto_trader
```

### 3. Automated Scheduling with Antigravity
You can schedule recurring execution (e.g. daily at market open 09:45 IST and near market close 15:15 IST) using Antigravity's `/schedule` command or cron runner:
```powershell
# Schedule via Antigravity session
/schedule "Run .venv\\Scripts\\python -m trading_agent.auto_trader every weekday at 15:15 IST"
```
