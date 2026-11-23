"""
OpenAlgo REST API Executor.
Communicates with OpenAlgo Analyzer Paper Trading API to manage orders,
positions, and funds.
"""

from typing import Any, Dict, List, Optional
import requests

from trading_agent.config import (
    EXCHANGE,
    OPENALGO_API_KEY,
    OPENALGO_HOST,
    PRODUCT_TYPE,
    STRATEGY_NAME,
)


class OpenAlgoExecutor:
    """REST API Client for OpenAlgo Analyzer Paper Trading Engine."""

    def __init__(
        self,
        host: str = OPENALGO_HOST,
        api_key: str = OPENALGO_API_KEY,
        strategy_name: str = STRATEGY_NAME,
    ):
        self.host = host.rstrip("/")
        self.api_key = api_key
        self.strategy_name = strategy_name
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send authenticated POST request to OpenAlgo REST API."""
        url = f"{self.host}/api/v1/{endpoint.strip('/')}/"
        body = {"apikey": self.api_key, **payload}
        try:
            res = self.session.post(url, json=body, timeout=10)
            return res.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection error: {str(e)}"}

    def get_funds(self) -> Dict[str, Any]:
        """Fetch virtual funds and available cash."""
        res = self._post("funds", {})
        if res.get("status") == "success" and "data" in res:
            data = res["data"]
            return {
                "available_cash": float(data.get("availablecash", 0.0)),
                "utilized_debits": float(data.get("utiliseddebits", 0.0)),
                "total_pnl": float(data.get("totalpnl", 0.0)),
                "mode": res.get("mode", "analyze"),
            }
        return {"available_cash": 0.0, "utilized_debits": 0.0, "total_pnl": 0.0, "mode": "unknown"}

    def get_positions(self, strategy_only: bool = True) -> List[Dict[str, Any]]:
        """Fetch all current positions from positionbook."""
        res = self._post("positionbook", {})
        if res.get("status") == "success" and "data" in res:
            positions = res["data"]
            active_positions = [
                p for p in positions if int(p.get("quantity", 0)) != 0
            ]
            return active_positions
        return []

    def get_orders(self) -> List[Dict[str, Any]]:
        """Fetch all orders from orderbook."""
        res = self._post("orderbook", {})
        if res.get("status") == "success" and "data" in res:
            return res["data"].get("orders", [])
        return []

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        pricetype: str = "MARKET",
        price: float = 0.0,
        product: str = PRODUCT_TYPE,
        exchange: str = EXCHANGE,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place an equity order in OpenAlgo Analyzer.
        """
        payload = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "action": action.upper(),
            "quantity": int(quantity),
            "pricetype": pricetype.upper(),
            "product": product.upper(),
            "price": float(price),
            "strategy": strategy or self.strategy_name,
        }
        return self._post("placeorder", payload)

    def close_position_for_symbol(
        self,
        symbol: str,
        current_quantity: int,
        exchange: str = EXCHANGE,
        product: str = PRODUCT_TYPE,
    ) -> Dict[str, Any]:
        """
        Close a position for a specific symbol by submitting an opposing market order.
        """
        action = "SELL" if current_quantity > 0 else "BUY"
        qty = abs(current_quantity)
        return self.place_order(
            symbol=symbol,
            action=action,
            quantity=qty,
            pricetype="MARKET",
            price=0.0,
            product=product,
            exchange=exchange,
        )

    def close_all_strategy_positions(self) -> Dict[str, Any]:
        """Close all positions belonging to this strategy."""
        return self._post("closeposition", {"strategy": self.strategy_name})
