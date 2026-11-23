"""
Market Scanner.
Iterates across the stock universe, computes technical indicators, identifies
active swing setups, applies risk sizing, and filters out already-held positions.
"""

from typing import Any, Dict, List
import concurrent.futures

from trading_agent.config import DEFAULT_UNIVERSE, EXCHANGE
from trading_agent.data_feed import get_latest_market_snapshot
from trading_agent.executor import OpenAlgoExecutor
from trading_agent.risk import RiskManager
from trading_agent.strategy import SwingStrategyEngine, TradeSignal


class MarketScanner:
    """Scans equity universe for swing trading setups with risk sizing."""

    def __init__(
        self,
        universe: List[str] = DEFAULT_UNIVERSE,
        exchange: str = EXCHANGE,
        executor: OpenAlgoExecutor = None,
        risk_manager: RiskManager = None,
    ):
        self.universe = universe
        self.exchange = exchange
        self.executor = executor or OpenAlgoExecutor()
        self.risk_manager = risk_manager or RiskManager()
        self.strategy_engine = SwingStrategyEngine()

    def scan(self, max_candidates: int = 5) -> List[Dict[str, Any]]:
        """
        Scan all stocks in the universe.
        Returns ranked list of executable setups with position sizing.
        """
        funds = self.executor.get_funds()
        available_cash = funds.get("available_cash", 10_000_000.0)

        # Get existing open positions to avoid duplicate entries
        positions = self.executor.get_positions()
        held_symbols = {p["symbol"].upper() for p in positions}

        candidates: List[Dict[str, Any]] = []

        # Scan universe using parallel workers for high speed
        def _scan_symbol(sym: str):
            if sym.upper() in held_symbols:
                return None
            try:
                snapshot = get_latest_market_snapshot(sym, self.exchange)
                if not snapshot:
                    return None
                signal = self.strategy_engine.evaluate(snapshot)
                if not signal:
                    return None

                # Calculate position size and risk parameters
                ok, qty, risk_det = self.risk_manager.calculate_position_size(
                    available_capital=available_cash,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    target_price=signal.target_price,
                )
                if not ok or qty <= 0:
                    return None

                return {
                    "symbol": signal.symbol,
                    "exchange": self.exchange,
                    "strategy": signal.strategy_type,
                    "action": signal.action,
                    "quality_score": signal.quality_score,
                    "ltp": signal.ltp,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "target_price": signal.target_price,
                    "quantity": qty,
                    "risk_reward_ratio": risk_det["risk_reward_ratio"],
                    "required_capital": risk_det["required_capital"],
                    "total_risk": risk_det["total_risk"],
                    "potential_profit": risk_det["potential_profit"],
                    "rationale": signal.rationale,
                    "snapshot": snapshot,
                }
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = executor.map(_scan_symbol, self.universe)
            for res in results:
                if res:
                    candidates.append(res)

        # Rank candidates by quality score and risk-reward
        candidates.sort(
            key=lambda c: (c["quality_score"], c["risk_reward_ratio"]),
            reverse=True,
        )

        return candidates[:max_candidates]
