"""
Autonomous Swing Trader (Pillar 1 Mode A).
Monitors market data, executes qualifying setups automatically into OpenAlgo
Analyzer Paper Trading, tracks active positions against Target and Stop Loss,
and writes comprehensive trade logs to TRADES.md.
"""

from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from trading_agent.config import (
    DEFAULT_UNIVERSE,
    EXCHANGE,
    JOURNAL_PATH,
    MAX_OPEN_POSITIONS,
    ROOT_DIR,
)
from trading_agent.data_feed import get_latest_market_snapshot
from trading_agent.executor import OpenAlgoExecutor
from trading_agent.risk import RiskManager
from trading_agent.scanner import MarketScanner

# State persistence for active position targets & stop losses
STATE_FILE = ROOT_DIR / "trading_agent" / "active_trades_state.json"


class AutoTrader:
    """Fully Autonomous Paper Trading Engine."""

    def __init__(
        self,
        executor: Optional[OpenAlgoExecutor] = None,
        scanner: Optional[MarketScanner] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.executor = executor or OpenAlgoExecutor()
        self.risk_manager = risk_manager or RiskManager()
        self.scanner = scanner or MarketScanner(executor=self.executor, risk_manager=self.risk_manager)
        self.active_trades: Dict[str, Dict[str, Any]] = self._load_state()

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """Load active trade targets/stops from disk."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self):
        """Save active trade targets/stops to disk."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.active_trades, f, indent=2)
        except Exception:
            pass

    def manage_open_positions(self) -> List[Dict[str, Any]]:
        """
        Check existing open positions against target price and stop loss.
        Closes positions that reached exit criteria.
        """
        positions = self.executor.get_positions()
        exits: List[Dict[str, Any]] = []

        for pos in positions:
            symbol = pos["symbol"].upper()
            qty = int(pos.get("quantity", 0))
            if qty == 0:
                continue

            trade_meta = self.active_trades.get(symbol)
            if not trade_meta:
                continue

            entry_price = float(trade_meta.get("entry_price", pos.get("average_price", 0)))
            stop_loss = float(trade_meta.get("stop_loss", 0))
            target_price = float(trade_meta.get("target_price", 0))

            snap = get_latest_market_snapshot(symbol, pos.get("exchange", EXCHANGE))
            if not snap:
                continue

            current_ltp = snap["ltp"]
            exit_reason = None

            if stop_loss > 0 and current_ltp <= stop_loss:
                exit_reason = "STOP_LOSS_HIT"
            elif target_price > 0 and current_ltp >= target_price:
                exit_reason = "TARGET_HIT"

            if exit_reason:
                pnl = round((current_ltp - entry_price) * qty, 2)
                pnl_pct = round((current_ltp - entry_price) / entry_price * 100, 2)

                # Close position
                close_res = self.executor.close_position_for_symbol(
                    symbol=symbol,
                    current_quantity=qty,
                    exchange=pos.get("exchange", EXCHANGE),
                )

                exit_summary = {
                    "symbol": symbol,
                    "exit_reason": exit_reason,
                    "entry_price": entry_price,
                    "exit_price": current_ltp,
                    "quantity": qty,
                    "pnl": pnl,
                    "pnl_percent": pnl_pct,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                exits.append(exit_summary)

                # Update Journal
                self._log_exit_journal(exit_summary)

                # Remove from active trades
                self.active_trades.pop(symbol, None)

        if exits:
            self._save_state()

        return exits

    def scan_and_enter(self) -> List[Dict[str, Any]]:
        """
        Scan market and enter qualifying setups up to MAX_OPEN_POSITIONS.
        """
        positions = self.executor.get_positions()
        current_open = len(positions)

        available_slots = MAX_OPEN_POSITIONS - current_open
        if available_slots <= 0:
            return []

        setups = self.scanner.scan(max_candidates=available_slots)
        executed_entries: List[Dict[str, Any]] = []

        for setup in setups:
            symbol = setup["symbol"]
            res = self.executor.place_order(
                symbol=symbol,
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
                entry_info = {
                    "symbol": symbol,
                    "order_id": order_id,
                    "action": setup["action"],
                    "strategy": setup["strategy"],
                    "entry_price": setup["entry_price"],
                    "stop_loss": setup["stop_loss"],
                    "target_price": setup["target_price"],
                    "quantity": setup["quantity"],
                    "required_capital": setup["required_capital"],
                    "total_risk": setup["total_risk"],
                    "potential_profit": setup["potential_profit"],
                    "risk_reward_ratio": setup["risk_reward_ratio"],
                    "rationale": setup["rationale"],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.active_trades[symbol] = entry_info
                self._save_state()
                self._log_entry_journal(entry_info)
                executed_entries.append(entry_info)

        return executed_entries

    def run_cycle(self) -> Dict[str, Any]:
        """Execute one complete autonomous trading cycle."""
        funds = self.executor.get_funds()
        exits = self.manage_open_positions()
        entries = self.scan_and_enter()
        positions = self.executor.get_positions()

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "available_cash": funds["available_cash"],
            "total_open_positions": len(positions),
            "new_entries": entries,
            "closed_exits": exits,
        }

    def _log_entry_journal(self, entry: Dict[str, Any]):
        """Log new trade entry to TRADES.md."""
        log_text = f"""
## [{entry['timestamp']}] Trade #{entry['order_id']} - {entry['action']} {entry['symbol']}
- **Mode**: Autonomous Executor (Mode A)
- **Strategy**: {entry['strategy']}
- **Quantity**: {entry['quantity']} shares @ ₹{entry['entry_price']}
- **Stop Loss**: ₹{entry['stop_loss']} | **Target**: ₹{entry['target_price']}
- **Risk:Reward**: 1:{entry['risk_reward_ratio']}
- **Capital Used**: ₹{entry['required_capital']}
- **Max Risk**: ₹{entry['total_risk']} | **Target Profit**: ₹{entry['potential_profit']}
- **Rationale**: {entry['rationale']}
- **Status**: OPEN

---
"""
        self._append_to_journal(log_text)

    def _log_exit_journal(self, exit_info: Dict[str, Any]):
        """Log trade exit to TRADES.md."""
        outcome = "PROFIT 🎯" if exit_info["pnl"] > 0 else "LOSS 🛑"
        log_text = f"""
### 🏁 Position Closed: {exit_info['symbol']} ({outcome})
- **Exit Reason**: `{exit_info['exit_reason']}`
- **Entry**: ₹{exit_info['entry_price']} | **Exit**: ₹{exit_info['exit_price']}
- **Quantity**: {exit_info['quantity']} shares
- **Realized P&L**: ₹{exit_info['pnl']} ({exit_info['pnl_percent']}%)
- **Closed At**: {exit_info['timestamp']}

---
"""
        self._append_to_journal(log_text)

    def _append_to_journal(self, content: str):
        """Append entry to TRADES.md."""
        try:
            if not JOURNAL_PATH.exists():
                JOURNAL_PATH.write_text(
                    "# 📈 Agentic Swing Trading Journal\n\nLog of all executed paper trades, rationale, and performance.\n\n",
                    encoding="utf-8",
                )
            with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass


def run_auto():
    """CLI entrypoint for Autonomous mode single cycle."""
    print("=" * 65)
    print("🤖 ANTIGRAVITY AUTONOMOUS TRADER (MODE A - INDIAN EQUITIES)")
    print("=" * 65)
    trader = AutoTrader()
    cycle_res = trader.run_cycle()
    print(f"⏰ Execution Time: {cycle_res['timestamp']}")
    print(f"💰 Available Paper Capital: ₹{cycle_res['available_cash']:,.2f}")
    print(f"📊 Active Open Positions: {cycle_res['total_open_positions']}/{MAX_OPEN_POSITIONS}")

    if cycle_res["closed_exits"]:
        print(f"\n🚪 Closed {len(cycle_res['closed_exits'])} position(s):")
        for ex in cycle_res["closed_exits"]:
            print(f"  - {ex['symbol']}: {ex['exit_reason']} | PnL: ₹{ex['pnl']} ({ex['pnl_percent']}%)")

    if cycle_res["new_entries"]:
        print(f"\n🚀 Executed {len(cycle_res['new_entries'])} new swing entry(ies):")
        for en in cycle_res["new_entries"]:
            print(f"  - {en['symbol']} ({en['strategy']}): {en['quantity']} shares @ ₹{en['entry_price']} | SL: ₹{en['stop_loss']} | TP: ₹{en['target_price']}")
    else:
        print("\nℹ️ No new entries executed (no qualifying setups or portfolio at max capacity).")


if __name__ == "__main__":
    run_auto()
