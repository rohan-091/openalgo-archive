"""
Swing Trading Strategies for Indian Equities (Daily Timeframe, 2 to 30 Days Hold).
Implements Pillar 2:
1. 20-EMA Pullback in established uptrend (Trend Continuation).
2. 10-Day Resistance Breakout with volume expansion.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TradeSignal:
    """Standardized Trade Setup Signal."""
    symbol: str
    strategy_type: str  # "EMA_PULLBACK" or "RANGE_BREAKOUT"
    action: str  # "BUY"
    ltp: float
    entry_price: float
    stop_loss: float
    target_price: float
    risk_reward_ratio: float
    quality_score: float  # 0 to 100 confidence score
    rationale: str
    snapshot: Dict[str, Any]


class SwingStrategyEngine:
    """Evaluates market snapshots against swing trading rules."""

    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Evaluate a single stock snapshot. Returns highest quality TradeSignal if triggered,
        or None if no setup is currently valid.
        """
        symbol = snapshot["symbol"]
        ltp = snapshot["ltp"]
        ema20 = snapshot["ema20"]
        ema50 = snapshot["ema50"]
        rsi = snapshot["rsi14"]
        atr = snapshot["atr14"]
        high10 = snapshot["high10"]
        low = snapshot["low"]
        volume_ratio = snapshot["volume_ratio"]
        is_green = snapshot["is_green"]

        signals: List[TradeSignal] = []

        # =========================================================================
        # Strategy 1: 20-EMA Pullback in Uptrend
        # =========================================================================
        # 1. Broad Uptrend: Price > 50 EMA and 20 EMA >= 50 EMA
        # 2. Pullback zone: Low came within 1.5% of 20 EMA (or low <= ema20 * 1.015)
        # 3. Confirmation: Current Close > 20 EMA, candle is green
        # 4. Momentum: 42 <= RSI <= 68 (not oversold breakdown, not excessively overbought)
        if (
            ltp > ema50
            and ema20 >= (ema50 * 0.995)
            and low <= (ema20 * 1.02)
            and ltp >= ema20
            and 42.0 <= rsi <= 68.0
            and is_green
        ):
            # Stop loss: 1.5 * ATR below 20 EMA or recent low
            sl_candidate = min(low, ema20) - (0.5 * atr)
            stop_loss = round(min(sl_candidate, ltp - (1.0 * atr)), 2)

            risk = ltp - stop_loss
            if risk > 0:
                target_price = round(ltp + (2.0 * risk), 2)
                rr = round((target_price - ltp) / risk, 2)

                # Quality Score (higher score for stronger trend and volume)
                score = 70.0
                if ltp > ema50 * 1.02:
                    score += 10.0
                if volume_ratio >= 1.0:
                    score += 10.0
                if 50.0 <= rsi <= 60.0:
                    score += 10.0

                rationale = (
                    f"20-EMA Pullback Bounce: Stock found support near 20 EMA ({ema20}), "
                    f"closed green above EMA with RSI at {rsi} in an established uptrend (50 EMA {ema50})."
                )

                signals.append(
                    TradeSignal(
                        symbol=symbol,
                        strategy_type="EMA_PULLBACK",
                        action="BUY",
                        ltp=ltp,
                        entry_price=ltp,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        risk_reward_ratio=rr,
                        quality_score=score,
                        rationale=rationale,
                        snapshot=snapshot,
                    )
                )

        # =========================================================================
        # Strategy 2: 10-Day Range Breakout with Volume Expansion
        # =========================================================================
        # 1. Base Trend: Price > 20 EMA and 20 EMA > 50 EMA
        # 2. Breakout: LTP >= 10-day High
        # 3. Volume Expansion: Volume ratio >= 1.15
        # 4. Momentum: RSI >= 52.0
        if (
            ltp > ema20 > ema50
            and ltp >= (high10 * 0.998)
            and volume_ratio >= 1.15
            and rsi >= 52.0
        ):
            # Stop loss: below 20 EMA or 1.5 * ATR
            sl_candidate = max(ema20, ltp - (1.5 * atr))
            stop_loss = round(min(sl_candidate, ltp - (1.0 * atr)), 2)

            risk = ltp - stop_loss
            if risk > 0:
                target_price = round(ltp + (2.0 * risk), 2)
                rr = round((target_price - ltp) / risk, 2)

                score = 75.0
                if volume_ratio >= 1.5:
                    score += 15.0
                if rsi >= 60.0:
                    score += 10.0

                rationale = (
                    f"10-Day High Breakout: Stock broke above 10-day resistance ({high10}) "
                    f"with {volume_ratio}x 20-day average volume and strong RSI ({rsi})."
                )

                signals.append(
                    TradeSignal(
                        symbol=symbol,
                        strategy_type="RANGE_BREAKOUT",
                        action="BUY",
                        ltp=ltp,
                        entry_price=ltp,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        risk_reward_ratio=rr,
                        quality_score=score,
                        rationale=rationale,
                        snapshot=snapshot,
                    )
                )

        if not signals:
            return None

        # Return the signal with highest quality score
        signals.sort(key=lambda s: s.quality_score, reverse=True)
        return signals[0]
