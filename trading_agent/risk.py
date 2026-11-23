"""
Risk Management and Position Sizing Engine.
Implements Pillar 4 Option A: Fixed percentage risk per trade,
dynamic share sizing based on stop-loss distance, portfolio exposure caps,
and risk-to-reward validation.
"""

from typing import Any, Dict, Optional, Tuple

from trading_agent.config import (
    MAX_CAPITAL_PER_TRADE,
    MAX_OPEN_POSITIONS,
    MIN_RISK_REWARD,
    RISK_PERCENT_PER_TRADE,
)


class RiskManager:
    """Calculates position sizing and validates trade risk parameters."""

    def __init__(
        self,
        risk_percent: float = RISK_PERCENT_PER_TRADE,
        max_capital_per_trade: float = MAX_CAPITAL_PER_TRADE,
        max_open_positions: int = MAX_OPEN_POSITIONS,
        min_risk_reward: float = MIN_RISK_REWARD,
    ):
        self.risk_percent = risk_percent
        self.max_capital_per_trade = max_capital_per_trade
        self.max_open_positions = max_open_positions
        self.min_risk_reward = min_risk_reward

    def calculate_position_size(
        self,
        available_capital: float,
        entry_price: float,
        stop_loss: float,
        target_price: float,
    ) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Calculate share quantity based on risk budget and stop-loss distance.

        Returns:
            Tuple of (is_valid: bool, quantity: int, details: dict)
        """
        if entry_price <= 0 or stop_loss <= 0 or target_price <= 0:
            return False, 0, {"error": "Invalid price parameters"}

        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            return False, 0, {"error": "Stop loss must be strictly below entry price for long trades"}

        reward_per_share = target_price - entry_price
        if reward_per_share <= 0:
            return False, 0, {"error": "Target price must be strictly above entry price"}

        risk_reward_ratio = reward_per_share / risk_per_share
        if risk_reward_ratio < self.min_risk_reward:
            return False, 0, {
                "error": f"Risk:Reward {risk_reward_ratio:.2f} is below minimum {self.min_risk_reward:.2f}",
                "risk_reward_ratio": round(risk_reward_ratio, 2),
            }

        # Calculate cash risk budget (e.g. 0.5% of total capital)
        risk_budget = available_capital * self.risk_percent
        raw_quantity = int(risk_budget / risk_per_share)

        if raw_quantity <= 0:
            raw_quantity = 1

        # Enforce maximum capital exposure per trade cap (e.g. max ₹10 Lakhs)
        max_allowed_quantity = int(self.max_capital_per_trade / entry_price)
        quantity = min(raw_quantity, max_allowed_quantity)
        quantity = max(1, quantity)

        required_capital = quantity * entry_price
        total_risk = quantity * risk_per_share
        potential_profit = quantity * reward_per_share

        details = {
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_price": round(target_price, 2),
            "risk_per_share": round(risk_per_share, 2),
            "reward_per_share": round(reward_per_share, 2),
            "risk_reward_ratio": round(risk_reward_ratio, 2),
            "risk_budget": round(risk_budget, 2),
            "quantity": quantity,
            "required_capital": round(required_capital, 2),
            "total_risk": round(total_risk, 2),
            "potential_profit": round(potential_profit, 2),
        }

        return True, quantity, details

    def can_open_new_position(self, current_open_count: int) -> Tuple[bool, Optional[str]]:
        """Validate whether a new position is permitted within portfolio limits."""
        if current_open_count >= self.max_open_positions:
            return (
                False,
                f"Maximum open positions limit reached ({current_open_count}/{self.max_open_positions})",
            )
        return True, None
