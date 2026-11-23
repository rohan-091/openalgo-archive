"""
Copilot Mode (Pillar 1 Mode B - Human-in-the-Loop).
Scans the market, formats actionable swing trading proposals with full risk-reward
and technical rationale, and dispatches approved orders to OpenAlgo Paper Trading.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from trading_agent.config import JOURNAL_PATH
from trading_agent.executor import OpenAlgoExecutor
from trading_agent.scanner import MarketScanner


class CopilotAgent:
    """Interactive Copilot for Swing Trading."""

    def __init__(self, scanner: Optional[MarketScanner] = None, executor: Optional[OpenAlgoExecutor] = None):
        self.executor = executor or OpenAlgoExecutor()
        self.scanner = scanner or MarketScanner(executor=self.executor)

    def scan_opportunities(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Scan the universe and return top qualifying trade setups."""
        return self.scanner.scan(max_candidates=limit)

    def format_setup_card(self, setup: Dict[str, Any]) -> str:
        """Format a trade proposal into a structured Markdown card."""
        s = setup
        card = f"""
### 📊 Trade Setup Proposal: **{s['symbol']}** ({s['strategy']})
- **Action**: `{s['action']}` (CNC Delivery / Swing 2-30 Days)
- **Quality Score**: `{s['quality_score']}/100` | **Risk:Reward**: `1:{s['risk_reward_ratio']}`
- **Current Price (LTP)**: ₹{s['ltp']:,.2f}
- **Entry Price**: ₹{s['entry_price']:,.2f}
- **Stop Loss (SL)**: ₹{s['stop_loss']:,.2f} (-{round((s['entry_price'] - s['stop_loss']) / s['entry_price'] * 100, 2)}%)
- **Target (TP)**: ₹{s['target_price']:,.2f} (+{round((s['target_price'] - s['entry_price']) / s['entry_price'] * 100, 2)}%)
- **Calculated Quantity**: `{s['quantity']} shares`
- **Capital Required**: ₹{s['required_capital']:,.2f}
- **Max Capital at Risk**: ₹{s['total_risk']:,.2f}
- **Potential Profit**: ₹{s['potential_profit']:,.2f}

**Technical Rationale**:
> {s['rationale']}

*Indicators*: 20 EMA: ₹{s['snapshot']['ema20']} | 50 EMA: ₹{s['snapshot']['ema50']} | RSI(14): {s['snapshot']['rsi14']} | Vol Ratio: {s['snapshot']['volume_ratio']}x
"""
        return card.strip()

    def execute_setup(self, setup: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved setup directly into OpenAlgo Analyzer Paper Trading.
        Logs the trade to TRADES.md.
        """
        res = self.executor.place_order(
            symbol=setup["symbol"],
            action=setup["action"],
            quantity=setup["quantity"],
            pricetype="LIMIT",
            price=setup["entry_price"],
            product="CNC",
            exchange=setup["exchange"],
        )

        order_id = res.get("orderid", "N/A")
        status = res.get("status", "error")

        if status == "success":
            self._log_trade_journal(setup, order_id)

        return {
            "symbol": setup["symbol"],
            "status": status,
            "order_id": order_id,
            "response": res,
        }

    def _log_trade_journal(self, setup: Dict[str, Any], order_id: str):
        """Append executed trade details to TRADES.md."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"""
## [{now}] Trade #{order_id} - {setup['action']} {setup['symbol']}
- **Mode**: Copilot (Approved by User)
- **Strategy**: {setup['strategy']}
- **Quantity**: {setup['quantity']} shares @ ₹{setup['entry_price']}
- **Stop Loss**: ₹{setup['stop_loss']} | **Target**: ₹{setup['target_price']}
- **Risk:Reward**: 1:{setup['risk_reward_ratio']}
- **Max Risk**: ₹{setup['total_risk']} | **Target Profit**: ₹{setup['potential_profit']}
- **Capital Used**: ₹{setup['required_capital']}
- **Rationale**: {setup['rationale']}
- **Status**: OPEN

---
"""
        try:
            if not JOURNAL_PATH.exists():
                JOURNAL_PATH.write_text(
                    "# 📈 Agentic Swing Trading Journal\n\nLog of all executed paper trades, rationale, and performance.\n\n",
                    encoding="utf-8",
                )
            with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


def run_copilot():
    """CLI entrypoint for interactive Copilot."""
    print("=" * 65)
    print("🤖 ANTIGRAVITY SWING COPILOT (INDIAN EQUITIES - PAPER TRADING)")
    print("=" * 65)
    copilot = CopilotAgent()
    funds = copilot.executor.get_funds()
    print(f"💰 Available Paper Capital: ₹{funds['available_cash']:,.2f}")
    print("🔍 Scanning market universe for swing trading opportunities...")

    setups = copilot.scan_opportunities(limit=3)
    if not setups:
        print("ℹ️ No high-conviction swing setups found matching criteria today.")
        return

    print(f"\n✨ Found {len(setups)} qualifying swing setup(s):\n")
    for idx, setup in enumerate(setups, 1):
        print(f"[{idx}] {copilot.format_setup_card(setup)}\n")

    for idx, setup in enumerate(setups, 1):
        choice = input(f"Approve and execute trade for {setup['symbol']}? [y/N]: ").strip().lower()
        if choice in ("y", "yes"):
            print(f"🚀 Dispatching order to OpenAlgo Analyzer...")
            result = copilot.execute_setup(setup)
            if result["status"] == "success":
                print(f"✅ Order placed successfully! Order ID: {result['order_id']}")
            else:
                print(f"❌ Order failed: {result.get('response', {}).get('message', 'Unknown error')}")
        else:
            print(f"⏭️ Skipped {setup['symbol']}.")


if __name__ == "__main__":
    run_copilot()
